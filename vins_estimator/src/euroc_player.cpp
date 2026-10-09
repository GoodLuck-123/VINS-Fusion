// Desktop EuRoC fixture: typed bag replay with movable messages for ROS 2 IPC.
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp_components/register_node_macro.hpp>
#include <rosbag2_cpp/reader.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <std_msgs/msg/bool.hpp>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <thread>

namespace vins_ros {
class EurocPlayer : public rclcpp::Node {
public:
    explicit EurocPlayer(const rclcpp::NodeOptions &options) : Node("euroc_player", options)
    {
        bag_ = declare_parameter<std::string>("bag_path", "");
        rate_ = declare_parameter<double>("rate", 1.0);
        stereo_ = declare_parameter<bool>("stereo", true);
        trace_ = declare_parameter<bool>("trace_image_pointers", false);
        if (bag_.empty() || rate_ <= 0 || rate_ > 1)
            throw std::invalid_argument("bag_path is required; rate must be in (0, 1]");
        image0_ = create_publisher<sensor_msgs::msg::Image>("/cam0/image_raw", rclcpp::QoS(100).reliable());
        if (stereo_)
            image1_ = create_publisher<sensor_msgs::msg::Image>("/cam1/image_raw", rclcpp::QoS(100).reliable());
        imu_ = create_publisher<sensor_msgs::msg::Imu>("/imu0", rclcpp::QoS(2000).reliable());
        clock_ = create_publisher<rosgraph_msgs::msg::Clock>("/clock", rclcpp::ClockQoS());
        done_ = create_publisher<std_msgs::msg::Bool>("~/finished", rclcpp::QoS(1).reliable());
        // The observer must subscribe to completion before replay is started.
        timer_ = create_wall_timer(std::chrono::milliseconds(100), [this] {
            if (image0_->get_subscription_count() && imu_->get_subscription_count() &&
                (!stereo_ || image1_->get_subscription_count()) && done_->get_subscription_count()) {
                timer_->cancel();
                worker_ = std::thread([this] { replay(); });
            }
        });
    }
    ~EurocPlayer() override {
        stop_.store(true);
        wake_.notify_all();
        if (worker_.joinable()) worker_.join();
    }
private:
    bool waitUntil(std::chrono::steady_clock::time_point deadline) {
        std::unique_lock<std::mutex> lock(wait_mutex_);
        wake_.wait_until(lock, deadline, [this] { return stop_.load(); });
        return !stop_.load();
    }
    template<class Message, class Publisher>
    void publish(const std::shared_ptr<rosbag2_storage::SerializedBagMessage> &record,
                 const Publisher &publisher, uint64_t &count, const char *camera = "") {
        rclcpp::SerializedMessage serialized(*record->serialized_data);
        auto message = std::make_unique<Message>();
        rclcpp::Serialization<Message>().deserialize_message(&serialized, message.get());
        ++count;
        if constexpr (std::is_same_v<Message, sensor_msgs::msg::Image>) {
            if (trace_ && count <= 3)
                RCLCPP_INFO(get_logger(), "image_source %s stamp_ns=%ld message=%p data=%p",
                    camera, static_cast<int64_t>(message->header.stamp.sec)*1000000000+message->header.stamp.nanosec,
                    static_cast<void *>(message.get()), static_cast<void *>(message->data.data()));
        }
        publisher->publish(std::move(message));
    }
    void replay() {
        uint64_t images0 = 0, images1 = 0, imus = 0;
        bool success = false;
        try {
            rosbag2_cpp::Reader reader;
            reader.open(bag_);
            rosbag2_storage::StorageFilter filter;
            filter.topics = {"/cam0/image_raw", "/imu0"};
            if (stereo_) filter.topics.push_back("/cam1/image_raw");
            reader.set_filter(filter);
            if (!reader.has_next()) throw std::runtime_error("Empty sensor bag");
            auto record = reader.read_next();
            const auto first = record->time_stamp;
            const auto start = std::chrono::steady_clock::now() + std::chrono::seconds(3);
            while (!stop_.load()) {
                const auto offset = std::chrono::nanoseconds(static_cast<int64_t>((record->time_stamp-first)/rate_));
                if (!waitUntil(start+offset)) break;
                rosgraph_msgs::msg::Clock clock;
                clock.clock = rclcpp::Time(record->time_stamp);
                clock_->publish(clock);
                if (record->topic_name == "/cam0/image_raw")
                    publish<sensor_msgs::msg::Image>(record, image0_, images0, "img0");
                else if (record->topic_name == "/cam1/image_raw")
                    publish<sensor_msgs::msg::Image>(record, image1_, images1, "img1");
                else if (record->topic_name == "/imu0")
                    publish<sensor_msgs::msg::Imu>(record, imu_, imus);
                if (!reader.has_next()) { success = true; break; }
                record = reader.read_next();
            }
        } catch (const std::exception &error) {
            RCLCPP_ERROR(get_logger(), "EuRoC replay failed: %s", error.what());
        }
        RCLCPP_INFO(get_logger(), "replay_counts img0=%lu img1=%lu imu=%lu status=%s",
                    images0, images1, imus, success ? "ok" : "failed");
        if (!stop_.load()) { std_msgs::msg::Bool done; done.data = success; done_->publish(done); }
    }
    std::string bag_;
    double rate_;
    bool stereo_, trace_;
    std::atomic<bool> stop_{false};
    std::mutex wait_mutex_;
    std::condition_variable wake_;
    std::thread worker_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image0_, image1_;
    rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_;
    rclcpp::Publisher<rosgraph_msgs::msg::Clock>::SharedPtr clock_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr done_;
};
} // namespace vins_ros
RCLCPP_COMPONENTS_REGISTER_NODE(vins_ros::EurocPlayer)
