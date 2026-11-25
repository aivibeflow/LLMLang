#include "public.h"

#include <iostream>

int main() {
    for (uint64_t word; std::cin >> word; ) {
        uint32_t mode = 0;
        std::cin >> mode;
        uint64_t result = 0xabad1234abcdef01ULL;
        const auto status = checked_add(word, mode, &result);
        std::cout << status << ' ' << result << '\n';
    }
}
