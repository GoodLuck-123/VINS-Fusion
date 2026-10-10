#include <vins/euroc_player.hpp>
int main(int argc,char **argv) { rclcpp::init(argc,argv); { auto node=vins_ros::makeEurocPlayer(rclcpp::NodeOptions()); rclcpp::spin(node); } rclcpp::shutdown(); return 0; }
