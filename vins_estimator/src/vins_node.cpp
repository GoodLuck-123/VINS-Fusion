/*******************************************************
 * Copyright (C) 2019, Aerial Robotics Group, Hong Kong University of Science and Technology
 * 
 * This file is part of VINS.
 * 
 * Licensed under the GNU General Public License v3.0;
 * you may not use this file except in compliance with the License.
 *
 * Author: Qin Tong (qintonguav@gmail.com)
 *******************************************************/

#include <stdio.h>
#include <queue>
#include <map>
#include <thread>
#include <mutex>
#include <vins_ros/ros2_utils.hpp>
#include <vins/vins_node.hpp>
#include <rclcpp_components/register_node_macro.hpp>
#include <fstream>
#include <stdexcept>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include "estimator/estimator.h"
#include "estimator/parameters.h"
#include "utility/visualization.h"

namespace vins_ros {
namespace {
struct ProcessLease {
    static std::atomic<bool> &claimed() { static std::atomic<bool> value{false}; return value; }
    ProcessLease() {
        bool expected = false;
        if (!claimed().compare_exchange_strong(expected, true))
            throw std::runtime_error("Only one VINS estimator is supported in a process (upstream global settings)");
    }
    ~ProcessLease() { claimed().store(false); }
};
}
struct VinsNode::Impl {
    ProcessLease process_lease;
    rclcpp::Node &n;
Estimator estimator;

queue<sensor_msgs::msg::Imu::ConstSharedPtr> imu_buf;
queue<sensor_msgs::msg::PointCloud::ConstSharedPtr> feature_buf;
queue<sensor_msgs::msg::Image::ConstSharedPtr> img0_buf;
queue<sensor_msgs::msg::Image::ConstSharedPtr> img1_buf;
std::mutex m_buf;
std::atomic<uint64_t> received_img0{0}, received_img1{0}, received_imu{0};
uint64_t processed_images = 0;


    std::atomic<bool> stop_requested{false};
    std::thread sync_thread;
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr sub_imu;
    rclcpp::Subscription<sensor_msgs::msg::PointCloud>::SharedPtr sub_feature;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_img0, sub_img1;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr sub_restart, sub_imu_switch, sub_cam_switch;
    explicit Impl(rclcpp::Node &node) : n(node)
    {
        const auto config = n.declare_parameter<std::string>("config_file", "");
        if (config.empty() || !std::ifstream(config).good())
            throw std::invalid_argument("config_file must name a readable OpenCV YAML file");
        // Upstream settings/publishers are process globals: one VINS per process.
        RIC.clear(); TIC.clear(); CAM_NAMES.clear(); STEREO = 0;
        try
        {
            readParameters(config);
            estimator.setParameter();
            registerPub(n);
            if (USE_IMU)
                sub_imu = n.create_subscription<sensor_msgs::msg::Imu>(IMU_TOPIC, rclcpp::QoS(2000).reliable(),
                    [this](sensor_msgs::msg::Imu::ConstSharedPtr msg) { imu_callback(msg); });
            sub_feature = n.create_subscription<sensor_msgs::msg::PointCloud>("/feature_tracker/feature", rclcpp::QoS(2000).reliable(),
                [this](sensor_msgs::msg::PointCloud::ConstSharedPtr msg) { feature_callback(msg); });
            sub_img0 = n.create_subscription<sensor_msgs::msg::Image>(IMAGE0_TOPIC, rclcpp::QoS(100).reliable(),
                [this](sensor_msgs::msg::Image::ConstSharedPtr msg) { img0_callback(msg); });
            if (STEREO)
                sub_img1 = n.create_subscription<sensor_msgs::msg::Image>(IMAGE1_TOPIC, rclcpp::QoS(100).reliable(),
                    [this](sensor_msgs::msg::Image::ConstSharedPtr msg) { img1_callback(msg); });
            sub_restart = n.create_subscription<std_msgs::msg::Bool>("/vins_restart", rclcpp::QoS(100).reliable(),
                [this](std_msgs::msg::Bool::ConstSharedPtr msg) { restart_callback(msg); });
            sub_imu_switch = n.create_subscription<std_msgs::msg::Bool>("/vins_imu_switch", rclcpp::QoS(100).reliable(),
                [this](std_msgs::msg::Bool::ConstSharedPtr msg) { imu_switch_callback(msg); });
            sub_cam_switch = n.create_subscription<std_msgs::msg::Bool>("/vins_cam_switch", rclcpp::QoS(100).reliable(),
                [this](std_msgs::msg::Bool::ConstSharedPtr msg) { cam_switch_callback(msg); });
            sync_thread = std::thread([this] { sync_process(); });
        }
        catch (...)
        {
            estimator.stop();
            shutdownPub();
            throw;
        }
        RCLCPP_INFO(n.get_logger(), "VINS component ready (%s)", STEREO ? "stereo" : "mono");
    }

    ~Impl()
    {
        stop_requested.store(true);
        if (sync_thread.joinable()) sync_thread.join();
        estimator.stop();
        shutdownPub();
        printf("sensor_counts img0=%lu img1=%lu imu=%lu processed=%lu\n",
               received_img0.load(), received_img1.load(), received_imu.load(), processed_images);
    }
void img0_callback(const sensor_msgs::msg::Image::ConstSharedPtr &img_msg)
{
    ++received_img0;
    m_buf.lock();
    img0_buf.push(img_msg);
    m_buf.unlock();
}

void img1_callback(const sensor_msgs::msg::Image::ConstSharedPtr &img_msg)
{
    ++received_img1;
    m_buf.lock();
    img1_buf.push(img_msg);
    m_buf.unlock();
}


cv::Mat getImageFromMsg(const sensor_msgs::msg::Image::ConstSharedPtr &img_msg)
{
    cv_bridge::CvImageConstPtr ptr;
    if (img_msg->encoding == "8UC1")
    {
        sensor_msgs::msg::Image img;
        img.header = img_msg->header;
        img.height = img_msg->height;
        img.width = img_msg->width;
        img.is_bigendian = img_msg->is_bigendian;
        img.step = img_msg->step;
        img.data = img_msg->data;
        img.encoding = "mono8";
        ptr = cv_bridge::toCvCopy(img, sensor_msgs::image_encodings::MONO8);
    }
    else
        ptr = cv_bridge::toCvCopy(img_msg, sensor_msgs::image_encodings::MONO8);

    cv::Mat img = ptr->image.clone();
    return img;
}

// extract images with same timestamp from two topics
void sync_process()
{
    while(!stop_requested.load() && rclcpp::ok(n.get_node_base_interface()->get_context()))
    {
        if(STEREO)
        {
            cv::Mat image0, image1;
            std_msgs::msg::Header header;
            double time = 0;
            m_buf.lock();
            if (!img0_buf.empty() && !img1_buf.empty())
            {
                double time0 = vins_ros::seconds(img0_buf.front()->header.stamp);
                double time1 = vins_ros::seconds(img1_buf.front()->header.stamp);
                // 0.003s sync tolerance
                if(time0 < time1 - 0.003)
                {
                    img0_buf.pop();
                    printf("throw img0\n");
                }
                else if(time0 > time1 + 0.003)
                {
                    img1_buf.pop();
                    printf("throw img1\n");
                }
                else
                {
                    time = vins_ros::seconds(img0_buf.front()->header.stamp);
                    header = img0_buf.front()->header;
                    image0 = getImageFromMsg(img0_buf.front());
                    img0_buf.pop();
                    image1 = getImageFromMsg(img1_buf.front());
                    img1_buf.pop();
                    //printf("find img0 and img1\n");
                }
            }
            m_buf.unlock();
            if(!image0.empty())
            {
                estimator.inputImage(time, image0, image1);
                ++processed_images;
            }
        }
        else
        {
            cv::Mat image;
            std_msgs::msg::Header header;
            double time = 0;
            m_buf.lock();
            if(!img0_buf.empty())
            {
                time = vins_ros::seconds(img0_buf.front()->header.stamp);
                header = img0_buf.front()->header;
                image = getImageFromMsg(img0_buf.front());
                img0_buf.pop();
            }
            m_buf.unlock();
            if(!image.empty())
            {
                estimator.inputImage(time, image);
                ++processed_images;
            }
        }

        std::chrono::milliseconds dura(2);
        std::this_thread::sleep_for(dura);
    }
}


void imu_callback(const sensor_msgs::msg::Imu::ConstSharedPtr &imu_msg)
{
    ++received_imu;
    double t = vins_ros::seconds(imu_msg->header.stamp);
    double dx = imu_msg->linear_acceleration.x;
    double dy = imu_msg->linear_acceleration.y;
    double dz = imu_msg->linear_acceleration.z;
    double rx = imu_msg->angular_velocity.x;
    double ry = imu_msg->angular_velocity.y;
    double rz = imu_msg->angular_velocity.z;
    Vector3d acc(dx, dy, dz);
    Vector3d gyr(rx, ry, rz);
    estimator.inputIMU(t, acc, gyr);
    return;
}


void feature_callback(const sensor_msgs::msg::PointCloud::ConstSharedPtr &feature_msg)
{
    map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> featureFrame;
    for (unsigned int i = 0; i < feature_msg->points.size(); i++)
    {
        int feature_id = feature_msg->channels[0].values[i];
        int camera_id = feature_msg->channels[1].values[i];
        double x = feature_msg->points[i].x;
        double y = feature_msg->points[i].y;
        double z = feature_msg->points[i].z;
        double p_u = feature_msg->channels[2].values[i];
        double p_v = feature_msg->channels[3].values[i];
        double velocity_x = feature_msg->channels[4].values[i];
        double velocity_y = feature_msg->channels[5].values[i];
        if(feature_msg->channels.size() > 5)
        {
            double gx = feature_msg->channels[6].values[i];
            double gy = feature_msg->channels[7].values[i];
            double gz = feature_msg->channels[8].values[i];
            pts_gt[feature_id] = Eigen::Vector3d(gx, gy, gz);
            //printf("receive pts gt %d %f %f %f\n", feature_id, gx, gy, gz);
        }
        VINS_ASSERT(z == 1);
        Eigen::Matrix<double, 7, 1> xyz_uv_velocity;
        xyz_uv_velocity << x, y, z, p_u, p_v, velocity_x, velocity_y;
        featureFrame[feature_id].emplace_back(camera_id,  xyz_uv_velocity);
    }
    double t = vins_ros::seconds(feature_msg->header.stamp);
    estimator.inputFeature(t, featureFrame);
    return;
}

void restart_callback(const std_msgs::msg::Bool::ConstSharedPtr &restart_msg)
{
    if (restart_msg->data == true)
    {
        RCLCPP_WARN(rclcpp::get_logger("vins_estimator"), "restart the estimator!");
        estimator.clearState();
        estimator.setParameter();
    }
    return;
}

void imu_switch_callback(const std_msgs::msg::Bool::ConstSharedPtr &switch_msg)
{
    if (switch_msg->data == true)
    {
        //RCLCPP_WARN(rclcpp::get_logger("vins_estimator"), "use IMU!");
        estimator.changeSensorType(1, STEREO);
    }
    else
    {
        //RCLCPP_WARN(rclcpp::get_logger("vins_estimator"), "disable IMU!");
        estimator.changeSensorType(0, STEREO);
    }
    return;
}

void cam_switch_callback(const std_msgs::msg::Bool::ConstSharedPtr &switch_msg)
{
    if (switch_msg->data == true)
    {
        //RCLCPP_WARN(rclcpp::get_logger("vins_estimator"), "use stereo!");
        estimator.changeSensorType(USE_IMU, 1);
    }
    else
    {
        //RCLCPP_WARN(rclcpp::get_logger("vins_estimator"), "use mono camera (left)!");
        estimator.changeSensorType(USE_IMU, 0);
    }
    return;
}


};
VinsNode::VinsNode(const rclcpp::NodeOptions &options)
    : Node("vins_estimator", options), impl_(std::make_unique<Impl>(*this)) {}
VinsNode::~VinsNode() = default;
} // namespace vins_ros
RCLCPP_COMPONENTS_REGISTER_NODE(vins_ros::VinsNode)
