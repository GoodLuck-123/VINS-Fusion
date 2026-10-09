"""Load VINS into a ROS 2 container; supports mono/stereo OpenCV YAML configs."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode, ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("config", description="Absolute OpenCV YAML path"),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("image_mode", default_value="share"),
        ComposableNodeContainer(
            name="vins_container", namespace="", package="rclcpp_components",
            executable="component_container", output="screen",
            composable_node_descriptions=[ComposableNode(
                package="vins", plugin="vins_ros::VinsNode", name="vins_estimator",
                parameters=[{"config_file": LaunchConfiguration("config"),
                             "use_sim_time": ParameterValue(LaunchConfiguration("use_sim_time"), value_type=bool),
                             "image_mode": LaunchConfiguration("image_mode")}],
                extra_arguments=[{"use_intra_process_comms": True}],
            )],
        ),
    ])
