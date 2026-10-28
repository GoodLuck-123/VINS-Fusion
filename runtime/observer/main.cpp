// Read-only ROS observation. These counts do not assert VINS consumption.
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/Imu.h>
#include <nav_msgs/Odometry.h>
#include <chrono>
#include <deque>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <cstdio>
struct Stream {
    uint64_t count=0,invalid=0,stamp=0,backward=0;
    double arrival=0;std::deque<double> recent;
    void seen(uint64_t t,double now,bool valid){
        if(count && t<=stamp)++backward;
        if(!valid || !t)++invalid;
        ++count;stamp=t;arrival=now;recent.push_back(now);
        while(recent.size()>1 && now-recent.front()>2)recent.pop_front();
    }
    void json(std::ostream& o,double now){
        double hz=recent.size()>1?(recent.size()-1)/(recent.back()-recent.front()):0;
        o<<"{\"count\":"<<count<<",\"stamp_ns\":"<<stamp<<",\"age_s\":"<<(count?now-arrival:-1)
         <<",\"hz\":"<<hz<<",\"invalid\":"<<invalid<<",\"nonincreasing\":"<<backward<<"}";
    }
};
int main(int argc,char**argv){
    ros::init(argc,argv,"vins_observer");ros::NodeHandle n("~");
    std::string image,imu,output,encoding;int width,height;
    n.param<std::string>("image",image,"/cam0/image_raw");n.param<std::string>("imu",imu,"/imu0");
    n.param<std::string>("output",output,"observation.json");n.param<std::string>("encoding",encoding,"mono8");
    n.param("width",width,752);n.param("height",height,480);
    auto start=std::chrono::steady_clock::now();
    auto clock=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
    Stream cam,inertial,pose;double xyz[3]={0,0,0};
    auto a=n.subscribe<sensor_msgs::Image>(image,50,[&](const sensor_msgs::ImageConstPtr&m){
        bool valid=m->width==unsigned(width)&&m->height==unsigned(height)&&(m->encoding==encoding || (encoding=="mono8"&&m->encoding=="8UC1"))&&m->step>=m->width&&m->data.size()>=size_t(m->step)*m->height;
        cam.seen(m->header.stamp.toNSec(),clock(),valid);
    });
    auto b=n.subscribe<sensor_msgs::Imu>(imu,1000,[&](const sensor_msgs::ImuConstPtr&m){
        auto v=m->linear_acceleration,w=m->angular_velocity;
        inertial.seen(m->header.stamp.toNSec(),clock(),std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z)&&std::isfinite(w.x)&&std::isfinite(w.y)&&std::isfinite(w.z));
    });
    auto c=n.subscribe<nav_msgs::Odometry>("/vins_estimator/odometry",100,[&](const nav_msgs::OdometryConstPtr&m){
        auto p=m->pose.pose.position; auto q=m->pose.pose.orientation;
        bool valid=std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z)&&std::isfinite(q.x)&&std::isfinite(q.y)&&std::isfinite(q.z)&&std::isfinite(q.w);
        pose.seen(m->header.stamp.toNSec(),clock(),valid);
        if(valid){xyz[0]=p.x;xyz[1]=p.y;xyz[2]=p.z;}
    });
    uint64_t seq=0;ros::WallRate rate(20);double last=-1;
    while(ros::ok()){
        ros::spinOnce();double now=clock();
        if(now-last>=.5){
            std::ostringstream o;o<<std::setprecision(16)<<"{\"seq\":"<<++seq<<",\"monotonic_elapsed_s\":"<<now<<",\"image\":";
            cam.json(o,now);o<<",\"imu\":";inertial.json(o,now);o<<",\"pose\":";pose.json(o,now);
            o<<",\"position_m\":["<<xyz[0]<<","<<xyz[1]<<","<<xyz[2]<<"]}\n";
            auto tmp=output+".tmp";{std::ofstream f(tmp);f<<o.str();}std::rename(tmp.c_str(),output.c_str());last=now;
        }
        rate.sleep();
    }
    return 0;
}
