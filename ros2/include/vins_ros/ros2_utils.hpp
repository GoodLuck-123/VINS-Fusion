#pragma once

#include <rclcpp/rclcpp.hpp>
#include <builtin_interfaces/msg/time.hpp>
#include <cmath>
#include <cstdlib>
#include <string>

namespace vins_ros {
inline double seconds(const builtin_interfaces::msg::Time &stamp) {
    return static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1e-9;
}
inline builtin_interfaces::msg::Time stamp(double seconds) {
    builtin_interfaces::msg::Time result;
    const double whole = std::floor(seconds);
    result.sec = static_cast<int32_t>(whole);
    const auto nanoseconds = static_cast<uint64_t>(std::llround((seconds - whole) * 1e9));
    result.sec += static_cast<int32_t>(nanoseconds / 1000000000ULL);
    result.nanosec = static_cast<uint32_t>(nanoseconds % 1000000000ULL);
    return result;
}
inline std::string private_topic(const std::string &topic) {
    return !topic.empty() && topic.front() == '/' ? topic : "~/" + topic;
}
}  // namespace vins_ros

// Preserve ROS_ASSERT's failure behavior in Release builds.
#define VINS_ASSERT(condition) do { if (!(condition)) { \
    RCLCPP_FATAL(rclcpp::get_logger("vins"), "Assertion failed: %s", #condition); \
    std::abort(); \
} } while (false)
