#pragma once

#include <stdint.h>

struct Record {
    uint32_t first;
    uint32_t second;
#if NONTRIVIAL
    ~Record() noexcept;
#endif
};

Record make_record(uint32_t value);
extern "C" void emit_record(uint32_t value, uint32_t *first, uint32_t *second) noexcept;
extern "C" uint32_t retirement_count() noexcept;
