#include <ros/ros.h>
#include <csignal>
static volatile std::sig_atomic_t running=1;
static void request_stop(int){running=0;}
#include <sensor_msgs/Image.h>
#include <std_msgs/UInt64MultiArray.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include "Spinnaker.h"
#include "SpinGenApi/SpinnakerGenApi.h"
#include <cstring>
#include <stdexcept>
using namespace Spinnaker;
using namespace Spinnaker::GenApi;

static void integer(INodeMap& m,const char* key,int64_t value) {
    CIntegerPtr node=m.GetNode(key);
    if(!IsWritable(node)||value<node->GetMin()||value>node->GetMax()||(value-node->GetMin())%node->GetInc())
        throw std::runtime_error(std::string("Unsupported camera ")+key+"="+std::to_string(value));
    node->SetValue(value);
}
static void enumeration(INodeMap& m,const char* key,const std::string& value) {
    CEnumerationPtr node=m.GetNode(key);
    if(!IsWritable(node))throw std::runtime_error(std::string("Camera node not writable: ")+key);
    CEnumEntryPtr entry=node->GetEntryByName(value.c_str());
    if(!IsReadable(entry))throw std::runtime_error(std::string("Unsupported camera ")+key+"="+value);
    node->SetIntValue(entry->GetValue());
}
int main(int argc,char** argv) {
    ros::init(argc,argv,"vins_camera",ros::init_options::NoSigintHandler);std::signal(SIGINT,request_stop);std::signal(SIGTERM,request_stop);ros::NodeHandle n,p("~");
    SystemPtr system;CameraList cameras;CameraPtr camera;bool initialized=false,acquiring=false;int result=0;
    try {
        std::string serial,topic,raw,metadata,trigger,exposure_auto;int width,height,binning,ow,oh,x,y,cw,ch;double fps,exposure,auto_max;
        p.param<std::string>("serial",serial,"25162247");p.param<std::string>("topic",topic,"/usb_camera/gray/image_raw");
        p.param<std::string>("raw_topic",raw,"/usb_camera/raw/image_raw");p.param<std::string>("metadata_topic",metadata,"/usb_camera/frame_metadata");
        p.param("width",width,1024);p.param("height",height,768);p.param("binning",binning,2);
        p.param("output_width",ow,512);p.param("output_height",oh,512);p.param("crop_x",x,256);p.param("crop_y",y,128);p.param("crop_width",cw,512);p.param("crop_height",ch,512);
        p.param<std::string>("trigger",trigger,"hardware");p.param("fps",fps,20.);p.param<std::string>("exposure_auto",exposure_auto,"Continuous");p.param("exposure_us",exposure,10000.);p.param("auto_max_us",auto_max,20000.);
        if(x<0||y<0||cw<1||ch<1||x+cw>width||y+ch>height||ow<1||oh<1)throw std::runtime_error("Camera crop outside raw frame");
        auto pub=n.advertise<sensor_msgs::Image>(topic,4);auto rawpub=n.advertise<sensor_msgs::Image>(raw,4);
        auto info=n.advertise<std_msgs::UInt64MultiArray>(metadata,100);
        system=System::GetInstance();cameras=system->GetCameras();camera=cameras.GetBySerial(serial.c_str());
        if(!camera.IsValid())throw std::runtime_error("Camera serial not found: "+serial);
        camera->Init();initialized=true;auto& map=camera->GetNodeMap();
        enumeration(map,"TriggerMode","Off");
        integer(map,"OffsetX",0);integer(map,"OffsetY",0);
        // Width/height must fit while changing binning; reduce before setting it.
        integer(map,"Width",8);integer(map,"Height",6);
        integer(map,"BinningHorizontal",binning);integer(map,"BinningVertical",binning);
        integer(map,"Width",width);integer(map,"Height",height);
        integer(map,"DecimationHorizontal",1);integer(map,"DecimationVertical",1);
        enumeration(map,"GainAuto","Off");CFloatPtr gain=map.GetNode("Gain");gain->SetValue(0.);
        CBooleanPtr gamma=map.GetNode("GammaEnable");if(IsWritable(gamma))gamma->SetValue(false);
        CFloatPtr black=map.GetNode("BlackLevel");if(IsWritable(black))black->SetValue(0.);
        enumeration(map,"PixelFormat","Mono8");enumeration(map,"AcquisitionMode","Continuous");
        enumeration(map,"ExposureAuto",exposure_auto);
        if(exposure_auto=="Continuous") {CFloatPtr node=map.GetNode("AutoExposureExposureTimeUpperLimit");if(!IsWritable(node)||auto_max<node->GetMin()||auto_max>node->GetMax())throw std::runtime_error("Invalid automatic exposure upper limit");node->SetValue(auto_max);}
        if(exposure_auto=="Off") {CFloatPtr node=map.GetNode("ExposureTime");if(!IsWritable(node)||exposure<node->GetMin()||exposure>node->GetMax())throw std::runtime_error("Invalid camera exposure_us");node->SetValue(exposure);}
        CBooleanPtr rate=map.GetNode("AcquisitionFrameRateEnable");
        if(!IsWritable(rate))throw std::runtime_error("Camera frame rate control unavailable");
        rate->SetValue(trigger=="continuous");
        if(trigger=="continuous") {CFloatPtr node=map.GetNode("AcquisitionFrameRate");if(!IsWritable(node)||fps<node->GetMin()||fps>node->GetMax())throw std::runtime_error("Invalid camera fps");node->SetValue(fps);}
        else {enumeration(map,"TriggerSelector","FrameStart");enumeration(map,"TriggerSource",trigger=="hardware"?"Line0":"Software");enumeration(map,"TriggerMode","On");}
        ROS_INFO("Camera serial=%s binning=%d raw=%dx%d crop=(%d,%d,%d,%d) output=%dx%d trigger=%s; timestamps=host receive, metadata retains device ns/frame ID",serial.c_str(),binning,width,height,x,y,cw,ch,ow,oh,trigger.c_str());
        int minimum_subscribers;p.param("minimum_subscribers",minimum_subscribers,2);
        const auto deadline=ros::WallTime::now()+ros::WallDuration(10.);
        while(ros::ok() && running && (pub.getNumSubscribers()<unsigned(minimum_subscribers)||rawpub.getNumSubscribers()<1||info.getNumSubscribers()<1)) {
            if(ros::WallTime::now()>deadline)throw std::runtime_error("Camera recorder/observer connections not ready");
            ros::spinOnce();ros::WallDuration(.01).sleep();
        }
        if(!running)throw std::runtime_error("Camera cancelled before acquisition");
        camera->BeginAcquisition();acquiring=true;uint32_t seq=0;ros::WallRate software_rate(fps);
        ROS_INFO("Camera acquisition armed");
        while(ros::ok() && running) {
            if(trigger=="software") {software_rate.sleep();CCommandPtr command=map.GetNode("TriggerSoftware");command->Execute();}
            ImagePtr image;
            try {image=camera->GetNextImage(500);}
            catch(const Spinnaker::Exception& e){if(e.GetError()==SPINNAKER_ERR_TIMEOUT){ROS_WARN_THROTTLE(5,"Camera waiting for frame/trigger");continue;}throw;}
            try {
                if(image->IsIncomplete()) {ROS_WARN_THROTTLE(5,"Incomplete camera frame status=%d",image->GetImageStatus());image->Release();continue;}
                const size_t w=image->GetWidth(),h=image->GetHeight(),stride=image->GetStride();
                if(w!=size_t(width)||h!=size_t(height)||stride<w||image->GetPixelFormat()!=PixelFormat_Mono8||image->GetBufferSize()<stride*h)
                    throw std::runtime_error("Camera delivered unexpected dimensions/pixel format/stride");
                sensor_msgs::Image rawmsg;rawmsg.header.seq=seq++;rawmsg.header.stamp=ros::Time::now();rawmsg.header.frame_id="camera";
                rawmsg.width=w;rawmsg.height=h;rawmsg.encoding="mono8";rawmsg.step=w;rawmsg.data.resize(w*h);
                for(size_t row=0;row<h;++row)std::memcpy(rawmsg.data.data()+row*w,static_cast<const uint8_t*>(image->GetData())+row*stride,w);
                std_msgs::UInt64MultiArray md;md.data={image->GetFrameID(),image->GetTimeStamp(),rawmsg.header.stamp.toNSec()};
                image->Release();image=nullptr; // ROS owns copied pixels before returning the SDK buffer.
                rawpub.publish(rawmsg);info.publish(md);
                cv::Mat view(h,w,CV_8UC1,rawmsg.data.data()),processed;
                cv::resize(view(cv::Rect(x,y,cw,ch)),processed,cv::Size(ow,oh),0,0,cv::INTER_LINEAR);
                sensor_msgs::Image output;output.header=rawmsg.header;output.width=ow;output.height=oh;output.encoding="mono8";output.step=ow;
                output.data.assign(processed.datastart,processed.dataend);pub.publish(output);ros::spinOnce();
            }catch(...){if(image.IsValid())image->Release();throw;}
        }
        camera->EndAcquisition();acquiring=false;
        // Publishers are scoped to this try block: flush BEFORE their destruction.
        // Waiting after the block is too late (unadvertise drops queued output).
        ros::WallDuration(.2).sleep();
    }catch(const std::exception& e){ROS_FATAL("%s",e.what());result=1;}
    try {if(acquiring)camera->EndAcquisition();if(initialized)camera->DeInit();camera=nullptr;cameras.Clear();if(system.IsValid())system->ReleaseInstance();}
    catch(const std::exception& e){ROS_ERROR("Camera cleanup: %s",e.what());result=1;}
    ros::shutdown();
    return result;
}
