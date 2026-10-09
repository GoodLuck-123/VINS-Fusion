"""Launch the original stereo IMU pipeline; configure outputs in the supplied YAML."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = LaunchConfiguration("config")
    return LaunchDescription([
        DeclareLaunchArgument("config", description="Absolute path to the OpenCV YAML configuration"),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("loop_fusion", default_value="false"),
        Node(package="vins", executable="vins_node", name="vins_estimator", arguments=[config],
             parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}], output="screen"),
        Node(package="loop_fusion", executable="loop_fusion_node", name="loop_fusion", arguments=[config],
             parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}], output="screen",
             condition=IfCondition(LaunchConfiguration("loop_fusion"))),
    ])
