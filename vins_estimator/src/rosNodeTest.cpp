#include <vins/vins_node.hpp>
#include <cstdio>

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    const auto positional = rclcpp::remove_ros_arguments(argc, argv);
    if (positional.size() != 2) {
        fprintf(stderr, "Usage: ros2 run vins vins_node /absolute/config.yaml [--ros-args ...]\n");
        rclcpp::shutdown();
        return 1;
    }
    int result = 0;
    try {
        auto options = rclcpp::NodeOptions();
        options.append_parameter_override("config_file", positional[1]);
        auto node = std::make_shared<vins_ros::VinsNode>(options);
        rclcpp::spin(node);
        node.reset();
    } catch (const std::exception &error) {
        fprintf(stderr, "VINS startup failed: %s\n", error.what());
        result = 1;
    }
    rclcpp::shutdown();
    return result;
}
