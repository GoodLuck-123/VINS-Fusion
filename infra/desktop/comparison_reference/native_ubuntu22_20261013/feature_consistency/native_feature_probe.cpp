#include <vins/image_frame.hpp>
#include "../vins_estimator/src/featureTracker/feature_tracker.h"
#include <cassert>
#include <fstream>

int main(int argc, char **argv) {
    assert(argc == 3);
    rclcpp::init(argc, argv);
    readParameters(argv[1]);
    FeatureTracker copied_tracker, shared_tracker;
    copied_tracker.readIntrinsicParameter(CAM_NAMES);
    shared_tracker.readIntrinsicParameter(CAM_NAMES);
    vins_ros::ImageFrame previous_left;
    std::ifstream input(argv[2]);
    int64_t stamp;
    std::string left_path, right_path;
    unsigned frames = 0;
    while (input >> stamp >> left_path >> right_path) {
        auto message = [](const std::string &path) {
            cv::Mat image = cv::imread(path, cv::IMREAD_GRAYSCALE);
            assert(!image.empty() && image.isContinuous());
            auto m = std::make_shared<sensor_msgs::msg::Image>();
            m->height = image.rows; m->width = image.cols; m->step = image.cols;
            m->encoding = "mono8";
            m->data.assign(image.data, image.data + image.total());
            return m;
        };
        auto left = message(left_path), right = message(right_path);
        auto copied_left = vins_ros::imageFrame(left, false);
        auto shared_left = vins_ros::imageFrame(left, true);
        auto copied_right = vins_ros::imageFrame(right, false);
        auto shared_right = vins_ros::imageFrame(right, true);
        left.reset(); right.reset();
        const double time = double(stamp) * 1e-9;
        auto a = copied_tracker.trackImage(time, copied_left.image, STEREO ? copied_right.image : cv::Mat());
        auto b = shared_tracker.trackImage(time, shared_left.image, STEREO ? shared_right.image : cv::Mat());
        assert(!a.empty() && a.size() == b.size());
        for (const auto &feature : a) {
            const auto &other = b.at(feature.first);
            assert(feature.second.size() == other.size());
            for (size_t i = 0; i < other.size(); ++i) {
                assert(feature.second[i].first == other[i].first);
                assert((feature.second[i].second - other[i].second).cwiseAbs().maxCoeff() <= 1e-12);
            }
        }
        previous_left = std::move(shared_left);
        ++frames;
    }
    assert(frames == 10);
    rclcpp::shutdown();
    printf("PASS %s: ten real EuRoC frames, identical copy/share feature IDs and observations\n", STEREO ? "stereo" : "mono");
}
