#include <iostream>
int main() {
#ifndef __aarch64__
#error "Expected an aarch64 target"
#endif
    std::cout << "AARCH64_CROSS_OK pointer_bytes=" << sizeof(void*)
              << " compiler=" << __VERSION__ << '\n';
}
