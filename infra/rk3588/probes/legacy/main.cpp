#include <ceres/ceres.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>
#include <cmath>
#include <iostream>
#include <stdexcept>

struct Residual {
  template <typename T> bool operator()(const T* x, T* residual) const {
    residual[0] = T(10) - x[0];
    return true;
  }
};

int main() {
  cv::Mat storage = cv::Mat::zeros(64, 80, CV_8UC1);
  cv::Mat image = storage(cv::Rect(0, 0, 64, 64));
  cv::rectangle(image, cv::Rect(16, 16, 12, 12), cv::Scalar(255), -1);
  cv::rectangle(image, cv::Rect(40, 40, 10, 10), cv::Scalar(255), -1);
  const cv::Mat original = image.clone();
  if (image.isContinuous()) throw std::runtime_error("Expected padded input");
  std::vector<cv::Point2f> points, tracked;
  cv::goodFeaturesToTrack(image, points, 20, 0.01, 5);
  if (points.size() < 8) throw std::runtime_error("Missing image corners");
  cv::Mat moved;
  cv::Mat translation = (cv::Mat_<double>(2, 3) << 1, 0, 2, 0, 1, 1);
  cv::warpAffine(image, moved, translation, image.size());
  std::vector<unsigned char> status;
  std::vector<float> error;
  cv::calcOpticalFlowPyrLK(image, moved, points, tracked, status, error);
  for (std::size_t i = 0; i < points.size(); ++i) {
    if (!status[i] || cv::norm(tracked[i] - points[i] - cv::Point2f(2, 1)) > 0.1)
      throw std::runtime_error("Incorrect optical flow");
  }
  if (cv::norm(original, image, cv::NORM_INF) != 0)
    throw std::runtime_error("Input image was modified");
  for (auto library : {ceres::SUITE_SPARSE, ceres::CX_SPARSE}) {
    if (!ceres::IsSparseLinearAlgebraLibraryTypeAvailable(library))
      throw std::runtime_error("Missing reference sparse backend");
    double x = 0;
    ceres::Problem problem;
    problem.AddResidualBlock(new ceres::AutoDiffCostFunction<Residual, 1, 1>(new Residual), nullptr, &x);
    ceres::Solver::Options options;
    options.linear_solver_type = ceres::SPARSE_NORMAL_CHOLESKY;
    options.sparse_linear_algebra_library_type = library;
    options.minimizer_progress_to_stdout = false;
    ceres::Solver::Summary summary;
    ceres::Solve(options, &problem, &summary);
    if (!summary.IsSolutionUsable() || std::abs(x - 10) > 1e-6)
      throw std::runtime_error("Sparse solve failed");
    std::cout << "sparse_backend=" << ceres::SparseLinearAlgebraLibraryTypeToString(library)
              << " x=" << x << '\n';
  }
  std::cout << "ARM_LEGACY_OK opencv=" << CV_VERSION << " ceres=" << CERES_VERSION_STRING
            << " corners=" << points.size() << " input_step=" << image.step << '\n';
}
