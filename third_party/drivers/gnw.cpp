#include "gnw_protocol.h"
#include <ros/ros.h>
#include <sensor_msgs/Imu.h>
#include <std_msgs/UInt8MultiArray.h>
#include <cerrno>
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>
#include <stdexcept>

int main(int argc,char** argv) {
    ros::init(argc,argv,"vins_imu");ros::NodeHandle n,p("~");int fd=-1;
    try {
        std::string device,topic,raw;int baud,nominal;
        p.param<std::string>("device",device,"/dev/ttyS7");p.param<std::string>("topic",topic,"/gnw_imu/data");
        p.param<std::string>("raw_topic",raw,"/gnw_imu/serial_raw");p.param("baud",baud,115200);p.param("nominal_hz",nominal,200);
        if(baud!=115200)throw std::runtime_error("GNW adapter supports the verified 115200 baud only");
        fd=open(device.c_str(),O_RDONLY|O_NOCTTY|O_NONBLOCK);
        if(fd<0)throw std::runtime_error("open "+device+": "+strerror(errno));
        termios options{};
        if(tcgetattr(fd,&options))throw std::runtime_error("tcgetattr: "+std::string(strerror(errno)));
        cfmakeraw(&options);cfsetispeed(&options,B115200);cfsetospeed(&options,B115200);
        options.c_cflag|=CLOCAL|CREAD;options.c_cflag&=~CRTSCTS;
        if(tcsetattr(fd,TCSANOW,&options))throw std::runtime_error("tcsetattr: "+std::string(strerror(errno)));
        auto pub=n.advertise<sensor_msgs::Imu>(topic,200);
        auto serial=n.advertise<std_msgs::UInt8MultiArray>(raw,200);
        ROS_INFO("GNW ready %s baud=%d nominal=%d (not a device rate command); header=host parse time, no device clock",device.c_str(),baud,nominal);
        gnw::Parser parser;uint32_t seq=0;uint8_t bytes[1024];
        while(ros::ok()) {
            pollfd item{fd,POLLIN,0};int ready=poll(&item,1,200);
            if(ready<0) {if(errno==EINTR)continue;throw std::runtime_error("serial poll failed");}
            if(item.revents&(POLLERR|POLLHUP|POLLNVAL))throw std::runtime_error("serial disconnected");
            if(!(item.revents&POLLIN))continue;
            ssize_t count=read(fd,bytes,sizeof(bytes));
            if(count<0) {if(errno==EAGAIN||errno==EINTR)continue;throw std::runtime_error("serial read failed");}
            std_msgs::UInt8MultiArray rawmsg;rawmsg.data.assign(bytes,bytes+count);serial.publish(rawmsg);
            const auto old=parser.bad_checksum;
            for(const auto& frame:parser.feed(bytes,count)) {
                if(!std::all_of(frame.values.begin(),frame.values.end(),[](float v){return std::isfinite(v);}))
                    throw std::runtime_error("GNW packet contains NaN/Inf; raw bytes retained");
                sensor_msgs::Imu m;m.header.seq=seq++;m.header.stamp=ros::Time::now();m.header.frame_id="imu";
                m.orientation_covariance[0]=-1; // RPY convention is unverified; VINS consumes accel/gyro only.
                m.linear_acceleration.x=frame.values[3];m.linear_acceleration.y=frame.values[4];m.linear_acceleration.z=frame.values[5];
                constexpr double rad=3.14159265358979323846/180.;
                m.angular_velocity.x=frame.values[6]*rad;m.angular_velocity.y=frame.values[7]*rad;m.angular_velocity.z=frame.values[8]*rad;
                pub.publish(m);
            }
            if(parser.bad_checksum!=old)ROS_WARN_THROTTLE(5,"GNW checksum failures total=%lu",parser.bad_checksum);
            ros::spinOnce();
        }
        close(fd);return 0;
    }catch(const std::exception& e){ROS_FATAL("%s",e.what());if(fd>=0)close(fd);return 1;}
}
