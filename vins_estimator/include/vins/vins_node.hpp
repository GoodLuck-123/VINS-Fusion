#pragma once
#include <memory>
#include <rclcpp/rclcpp.hpp>

namespace vins_ros {
// One estimator per process; can share a container with sensor/processing nodes.
class VinsNode : public rclcpp::Node {
public:
    explicit VinsNode(const rclcpp::NodeOptions &options = rclcpp::NodeOptions());
    ~VinsNode() override;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
