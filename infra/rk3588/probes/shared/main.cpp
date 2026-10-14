#include <vins/shared_frames.hpp>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <thread>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3);
    const unsigned frames = 1000, width = 32, height = 16;
    const std::string path = "/tmp/vins-rk-probe-" + std::to_string(getpid()) + ".sock";
    int finished[2];
    assert(pipe(finished) == 0);
    // Fork before constructing either endpoint or starting its worker threads.
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        close(finished[1]);
        std::atomic<unsigned> count{0};
        std::mutex mutex;
        vins_ros::ImageFrame previous;
        unsigned previous_index = 0;
        {
            vins_ros::SharedReader reader(path, [&](vins_ros::SharedImage image) {
                std::lock_guard<std::mutex> lock(mutex);
                unsigned index = count.load();
                assert(image.stamp_ns == int64_t(index) * 1000000);
                assert(image.camera == index % 2 && image.frame.shared);
                assert(image.frame.memory_owner && image.frame.image.type() == CV_8UC1);
                assert(image.frame.image.cols == width && image.frame.image.rows == height);
                assert(image.frame.image.step >= width);
                if (index == 0)
                    printf("mapping_layout width=%u height=%u stride=%zu format=mono8 source_stride=64\n",
                           width, height, image.frame.image.step[0]);
                for (unsigned row = 0; row < height; ++row)
                    for (unsigned col = 0; col < width; ++col)
                        assert(image.frame.image.at<unsigned char>(row, col) ==
                               (index + row * width + col) % 251);
                if (!previous.image.empty())
                    assert(previous.image.at<unsigned char>(15, 31) == (previous_index + 511) % 251);
                previous = std::move(image.frame);
                previous_index = index;
                std::this_thread::sleep_for(std::chrono::microseconds(300));
                count.store(index + 1);
            });
            auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
            while (count.load() < frames) {
                assert(std::chrono::steady_clock::now() < deadline);
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            // Do not close the consumer before the producer has marked Done.
            char marker;
            assert(read(finished[0], &marker, 1) == 1);
            {
                std::lock_guard<std::mutex> lock(mutex);
                previous = {};
            }
            reader.stop();
        }
        close(finished[0]);
        fflush(stdout);
        _exit(0); // Dependency libraries are not fully ASan/LSan instrumented.
    }
    close(finished[0]);
    {
        vins_ros::SharedOptions options;
        options.socket_path = path;
        options.backend = argv[1];
        options.device = argc == 3 ? argv[2] : "";
        options.width = width; options.height = height; options.slots = 4;
        vins_ros::SharedWriter writer(options);
        auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        while (!writer.ready()) {
            assert(std::chrono::steady_clock::now() < deadline);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        unsigned char storage[height * 64];
        cv::Mat padded(height, width, CV_8UC1, storage, 64);
        for (unsigned i = 0; i < frames; ++i) {
            for (unsigned row = 0; row < height; ++row)
                for (unsigned col = 0; col < width; ++col)
                    padded.at<unsigned char>(row, col) = (i + row * width + col) % 251;
            writer.write(i % 2, int64_t(i) * 1000000, padded);
        }
        writer.finish();
        char marker = 'D';
        assert(write(finished[1], &marker, 1) == 1);
        close(finished[1]);
        int status;
        assert(waitpid(child, &status, 0) == child);
        assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    }
    assert(access(path.c_str(), F_OK) != 0);
    printf("PASS %s: independent processes, 1000 frames, padded input, retained previous frame, 4-slot backpressure\n", argv[1]);
}
