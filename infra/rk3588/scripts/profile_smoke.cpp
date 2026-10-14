#include <chrono>
#include <cstdint>
#include <iostream>

__attribute__((noinline)) std::uint64_t profile_work(std::uint64_t seed) {
  for (unsigned i = 0; i < 10000; ++i) seed = seed * 6364136223846793005ULL + 1;
  return seed;
}

int main() {
  auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  std::uint64_t seed = 1;
  while (std::chrono::steady_clock::now() < deadline) seed = profile_work(seed);
  std::cout << "PROFILE_SMOKE " << seed << '\n';
}
