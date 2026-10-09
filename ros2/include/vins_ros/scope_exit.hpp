#pragma once
#include <functional>
#include <utility>

namespace vins_ros {
// Destroy global ROS handles before middleware static state is torn down.
class ScopeExit {
public:
    explicit ScopeExit(std::function<void()> action) : action_(std::move(action)) {}
    ScopeExit(const ScopeExit &) = delete;
    ScopeExit &operator=(const ScopeExit &) = delete;
    ~ScopeExit() { action_(); }
private:
    std::function<void()> action_;
};
}
