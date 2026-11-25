#include "record.h"

static uint32_t retired = 0;

#if NONTRIVIAL
Record::~Record() noexcept
{
    ++retired;
}
#endif

Record make_record(uint32_t value)
{
    return {value, 2u * value + 1u};
}

extern "C" void emit_record(uint32_t value, uint32_t *first, uint32_t *second) noexcept
{
    const Record object = make_record(value);
    *first = object.first;
    *second = object.second;
}

extern "C" uint32_t retirement_count() noexcept
{
    return retired;
}
