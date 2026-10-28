#pragma once
// Original VINS uses the legacy CV_* constants but includes only C++ headers.
// OpenCV 4.2 still supplies these definitions in its compatibility headers.
// Force-include the declarations during the reference build; preserve values
// and algorithms without editing the upstream source tree.
#include <opencv2/imgproc/imgproc_c.h>
#include <opencv2/calib3d/calib3d_c.h>
#include <opencv2/imgcodecs/legacy/constants_c.h>
#include <opencv2/highgui/highgui_c.h>
