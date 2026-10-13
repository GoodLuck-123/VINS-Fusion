#include <vins/image_frame.hpp>
#include <cassert>
#include <iostream>

int main() {
    for (const auto &encoding : {"mono8", "8UC1"}) {
        auto message = std::make_shared<sensor_msgs::msg::Image>();
        message->width = 7;
        message->height = 5;
        message->step = 12;
        message->encoding = encoding;
        message->data.resize(message->height * message->step, 0xEE);
        for (unsigned row = 0; row < message->height; ++row)
            for (unsigned col = 0; col < message->width; ++col)
                message->data[row * message->step + col] = row * 7 + col;
        auto shared = vins_ros::imageFrame(message, true);
        auto copied = vins_ros::imageFrame(message, false);
        assert(shared.shared && shared.materializations == 0);
        assert(shared.image.data == message->data.data());
        assert(shared.image.step == 12 && !shared.image.isContinuous());
        assert(!copied.shared && copied.image.data != message->data.data());
        assert(cv::norm(shared.image, copied.image, cv::NORM_INF) == 0);
        std::weak_ptr<sensor_msgs::msg::Image> owner = message;
        message.reset();
        assert(!owner.expired());
        assert(shared.image.at<unsigned char>(4, 6) == 34);
        shared = {};
        assert(owner.expired());
        assert(copied.image.at<unsigned char>(4, 6) == 34);
    }
    auto rgb = std::make_shared<sensor_msgs::msg::Image>();
    rgb->width = 7; rgb->height = 5; rgb->step = 21;
    rgb->encoding = "rgb8";
    rgb->data.resize(105, 64);
    auto converted = vins_ros::imageFrame(rgb, true);
    assert(!converted.shared && converted.materializations == 1);
    assert(converted.image.type() == CV_8UC1);
    assert(converted.image.at<unsigned char>(4, 6) == 64);
    auto invalid = std::make_shared<sensor_msgs::msg::Image>(*rgb);
    invalid->step = 1;
    bool rejected = false;
    try { vins_ros::imageFrame(invalid, true); }
    catch (const cv_bridge::Exception &) { rejected = true; }
    assert(rejected);
    std::cout << "PASS mono8/8UC1 copy/share, padded stride, retained owner, RGB fallback, invalid stride rejection\n";
}
