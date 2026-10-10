cmake_minimum_required(VERSION 3.16)
project(vins)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
# Match the ROS 1 Release flags; ROS 2 requires the C++17 language level.
set(CMAKE_CXX_FLAGS "-std=c++17")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -Wall -g")
list(REMOVE_ITEM CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "$ENV{CONDA_PREFIX}/include")
find_package(ament_cmake REQUIRED)
find_package(OpenCV 4.2.0 EXACT REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(Ceres 1.14.0 EXACT REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(rosbag2_cpp REQUIRED)
find_package(rosgraph_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(camera_models REQUIRED)
include_directories(include ../ros2/include ${CERES_INCLUDE_DIRS} ${OpenCV_INCLUDE_DIRS})
add_compile_options(-include "${CMAKE_CURRENT_SOURCE_DIR}/../infra/desktop/scripts/opencv4_legacy_compat.h")

add_library(vins_lib
    src/estimator/parameters.cpp
    src/estimator/estimator.cpp
    src/estimator/feature_manager.cpp
    src/factor/pose_local_parameterization.cpp
    src/factor/projectionTwoFrameOneCamFactor.cpp
    src/factor/projectionTwoFrameTwoCamFactor.cpp
    src/factor/projectionOneFrameTwoCamFactor.cpp
    src/factor/marginalization_factor.cpp
    src/utility/utility.cpp
    src/utility/visualization.cpp
    src/utility/CameraPoseVisualization.cpp
    src/initial/solve_5pts.cpp
    src/initial/initial_aligment.cpp
    src/initial/initial_sfm.cpp
    src/initial/initial_ex_rotation.cpp
    src/featureTracker/feature_tracker.cpp)
set_target_properties(vins_lib PROPERTIES POSITION_INDEPENDENT_CODE ON)

add_library(vins_shared_frames STATIC src/shared_frames.cpp)
set_target_properties(vins_shared_frames PROPERTIES POSITION_INDEPENDENT_CODE ON)
ament_target_dependencies(vins_shared_frames cv_bridge sensor_msgs)
target_link_libraries(vins_shared_frames ${OpenCV_LIBS} OpenSSL::Crypto)

add_library(vins_component SHARED src/vins_node.cpp)
target_link_libraries(vins_component vins_lib vins_shared_frames)
ament_target_dependencies(vins_component rclcpp rclcpp_components std_msgs sensor_msgs cv_bridge)
rclcpp_components_register_nodes(vins_component "vins_ros::VinsNode")

add_library(vins_euroc_component SHARED src/euroc_player.cpp)
ament_target_dependencies(vins_euroc_component rclcpp rclcpp_components rosbag2_cpp rosgraph_msgs sensor_msgs std_msgs)
target_link_libraries(vins_euroc_component vins_shared_frames)
add_executable(euroc_player_node src/euroc_player_main.cpp)
target_link_libraries(euroc_player_node vins_euroc_component)
ament_target_dependencies(euroc_player_node rclcpp)
rclcpp_components_register_nodes(vins_euroc_component "vins_ros::EurocPlayer")

add_executable(vins_node src/rosNodeTest.cpp)

add_executable(kitti_odom_test src/KITTIOdomTest.cpp)

add_executable(kitti_gps_test src/KITTIGPSTest.cpp)

target_link_libraries(vins_lib ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen)
ament_target_dependencies(vins_lib rclcpp std_msgs sensor_msgs geometry_msgs nav_msgs visualization_msgs tf2_ros ament_index_cpp cv_bridge camera_models)
target_link_libraries(vins_node vins_component)
ament_target_dependencies(vins_node rclcpp std_msgs sensor_msgs geometry_msgs nav_msgs visualization_msgs tf2_ros ament_index_cpp cv_bridge camera_models)
target_link_libraries(kitti_odom_test ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen vins_lib)
ament_target_dependencies(kitti_odom_test rclcpp std_msgs sensor_msgs geometry_msgs nav_msgs visualization_msgs tf2_ros ament_index_cpp cv_bridge camera_models)
target_link_libraries(kitti_gps_test ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen vins_lib)
ament_target_dependencies(kitti_gps_test rclcpp std_msgs sensor_msgs geometry_msgs nav_msgs visualization_msgs tf2_ros ament_index_cpp cv_bridge camera_models)
install(TARGETS euroc_player_node vins_node kitti_odom_test kitti_gps_test vins_lib vins_component vins_euroc_component ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
ament_export_include_directories(include)
ament_export_libraries(vins_component)
ament_export_dependencies(rclcpp cv_bridge sensor_msgs)
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})
ament_package()
