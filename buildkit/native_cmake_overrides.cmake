# Conda initializes compiler flags with -isystem <prefix>/include. The original
# VINS CMakeLists then overwrites CMAKE_CXX_FLAGS, removing that flag. Ensure
# CMake does not suppress explicitly requested package include directories as
# "implicit" after the overwrite. No VINS source or algorithm is changed.
if(DEFINED ENV{CONDA_PREFIX})
  list(REMOVE_ITEM CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "$ENV{CONDA_PREFIX}/include")
  list(REMOVE_ITEM CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES "$ENV{CONDA_PREFIX}/include")
endif()
if(PROJECT_NAME MATCHES "^(camera_models|vins|loop_fusion)$")
  add_compile_options(-include "${CMAKE_CURRENT_LIST_DIR}/opencv4_legacy_compat.h")
endif()
