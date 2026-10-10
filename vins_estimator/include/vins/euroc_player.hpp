#pragma once
#include <rclcpp/rclcpp.hpp>
namespace vins_ros { std::shared_ptr<rclcpp::Node> makeEurocPlayer(const rclcpp::NodeOptions &options); }
