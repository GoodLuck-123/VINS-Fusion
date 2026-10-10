#pragma once
#include <cv_bridge/cv_bridge.h>
#include <sensor_msgs/image_encodings.hpp>

namespace vins_ros {
// Keep this owner alive for every retained cv::Mat view, including prev_img.
// Shared pixels are read-only; image processing outputs own separate storage.
struct ImageFrame {
    cv_bridge::CvImageConstPtr owner;
    std::shared_ptr<void> memory_owner; // External mapping/lease, including prev_img.
    cv::Mat image;
    bool shared = false;
    uint64_t materializations = 0;
    uint64_t materialized_bytes = 0;
};

inline ImageFrame imageFrame(const sensor_msgs::msg::Image::ConstSharedPtr &message, bool share)
{
    ImageFrame frame;
    const bool gray = message->encoding == "mono8" || message->encoding == "8UC1";
    if (share) {
        // An empty destination encoding preserves the 8UC1 alias without making
        // a temporary Image (and copying its vector). cv_bridge validates stride.
        frame.owner = cv_bridge::toCvShare(message, gray ? "" : "mono8");
        frame.image = frame.owner->image;
        frame.shared = gray && frame.image.data == message->data.data();
        frame.materializations = frame.shared ? 0 : 1;
    } else {
        cv_bridge::CvImageConstPtr converted;
        if (message->encoding == "8UC1") {
            sensor_msgs::msg::Image alias = *message;
            alias.encoding = "mono8";
            converted = cv_bridge::toCvCopy(alias, "mono8");
            ++frame.materializations;
            frame.materialized_bytes += message->data.size();
        } else {
            converted = cv_bridge::toCvCopy(message, "mono8");
        }
        frame.image = converted->image.clone();
        frame.materializations += 2; // historical conversion/copy plus clone
    }
    frame.materialized_bytes += frame.materializations == 0 ? 0 :
        (share ? 1 : 2) * frame.image.total() * frame.image.elemSize();
    return frame;
}
} // namespace vins_ros
