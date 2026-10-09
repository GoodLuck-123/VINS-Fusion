cmake_minimum_required(VERSION 3.16)
project(camera_models)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
# Match the ROS 1 Release flags; ROS 2 requires the C++17 language level.
set(CMAKE_CXX_FLAGS "-std=c++17")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -fPIC")
list(REMOVE_ITEM CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "$ENV{CONDA_PREFIX}/include")
find_package(ament_cmake REQUIRED)
find_package(OpenCV 4.2.0 EXACT REQUIRED)
find_package(Ceres 1.14.0 EXACT REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS filesystem program_options system)
include_directories(include ../ros2/include ${CERES_INCLUDE_DIRS} ${OpenCV_INCLUDE_DIRS})
include_directories(${Boost_INCLUDE_DIRS})
add_compile_options(-include "${CMAKE_CURRENT_SOURCE_DIR}/../infra/desktop/scripts/opencv4_legacy_compat.h")

add_executable(Calibrations 
    src/intrinsic_calib.cc
    src/chessboard/Chessboard.cc
    src/calib/CameraCalibration.cc
    src/camera_models/Camera.cc
    src/camera_models/CameraFactory.cc
    src/camera_models/CostFunctionFactory.cc
    src/camera_models/PinholeCamera.cc
    src/camera_models/PinholeFullCamera.cc
    src/camera_models/CataCamera.cc
    src/camera_models/EquidistantCamera.cc
    src/camera_models/ScaramuzzaCamera.cc
    src/sparse_graph/Transform.cc
    src/gpl/gpl.cc
    src/gpl/EigenQuaternionParameterization.cc)

add_library(camera_models
    src/chessboard/Chessboard.cc
    src/calib/CameraCalibration.cc
    src/camera_models/Camera.cc
    src/camera_models/CameraFactory.cc
    src/camera_models/CostFunctionFactory.cc
    src/camera_models/PinholeCamera.cc
    src/camera_models/PinholeFullCamera.cc
    src/camera_models/CataCamera.cc
    src/camera_models/EquidistantCamera.cc
    src/camera_models/ScaramuzzaCamera.cc
    src/sparse_graph/Transform.cc
    src/gpl/gpl.cc
    src/gpl/EigenQuaternionParameterization.cc)

target_link_libraries(Calibrations ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen ${Boost_LIBRARIES})
target_link_libraries(camera_models ${OpenCV_LIBS} ${CERES_LIBRARIES} Eigen3::Eigen ${Boost_LIBRARIES})
install(TARGETS Calibrations camera_models ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
ament_export_include_directories(include)
ament_export_libraries(camera_models)
ament_export_dependencies(OpenCV Ceres Eigen3 Boost)
ament_package()
