cmake_minimum_required(VERSION 3.16)
project(loop_fusion)

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
find_package(Ceres 1.14.0 EXACT REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(rclcpp REQUIRED)
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

add_executable(loop_fusion_node
    src/pose_graph_node.cpp
    src/pose_graph.cpp
    src/keyframe.cpp
    src/utility/CameraPoseVisualization.cpp
    src/ThirdParty/DBoW/BowVector.cpp
    src/ThirdParty/DBoW/FBrief.cpp
    src/ThirdParty/DBoW/FeatureVector.cpp
    src/ThirdParty/DBoW/QueryResults.cpp
    src/ThirdParty/DBoW/ScoringObject.cpp
    src/ThirdParty/DUtils/Random.cpp
    src/ThirdParty/DUtils/Timestamp.cpp
    src/ThirdParty/DVision/BRIEF.cpp
    src/ThirdParty/VocabularyBinary.cpp
    )

target_link_libraries(loop_fusion_node ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen)
ament_target_dependencies(loop_fusion_node rclcpp std_msgs sensor_msgs geometry_msgs nav_msgs visualization_msgs tf2_ros ament_index_cpp cv_bridge camera_models)
install(TARGETS loop_fusion_node ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY ../support_files/ DESTINATION share/${PROJECT_NAME}/support_files)
ament_package()
