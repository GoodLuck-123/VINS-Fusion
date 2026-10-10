#pragma once
#include <vins/image_frame.hpp>
#include <array>
#include <atomic>
#include <functional>
#include <memory>
#include <string>

namespace vins_ros {
using PixelHash = std::array<unsigned char, 32>;
PixelHash pixelHash(const cv::Mat &image);
std::string hashText(const PixelHash &hash);
class ImageDigest {
public:
    ImageDigest();
    ~ImageDigest();
    void add(unsigned camera, int64_t stamp_ns, const PixelHash &hash);
    std::string value(unsigned camera) const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
struct SharedImage {
    unsigned camera;
    int64_t stamp_ns;
    ImageFrame frame;
};
struct SharedOptions {
    std::string socket_path;
    std::string backend = "memfd"; // memfd, dma_heap, or vgem; never silently fallback.
    std::string device;
    unsigned width = 752, height = 480, slots = 32;
    bool verify_pixels = true;
};
class SharedWriter {
public:
    explicit SharedWriter(const SharedOptions &options);
    ~SharedWriter();
    bool ready() const;
    void write(unsigned camera, int64_t stamp_ns, const cv::Mat &image);
    void finish();
    void stop();
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
class SharedReader {
public:
    SharedReader(const std::string &socket_path, std::function<void(SharedImage)> deliver);
    ~SharedReader();
    void stop();
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
} // namespace vins_ros
