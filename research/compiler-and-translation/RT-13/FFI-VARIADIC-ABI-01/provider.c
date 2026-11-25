#include "fixture.h"

VARIADIC_ABI void fixture_var(output_record *output, unsigned int marker, ...)
{
#if defined(MS_ABI)
    __builtin_ms_va_list args;
    __builtin_ms_va_start(args, marker);
#else
    __builtin_va_list args;
    __builtin_va_start(args, marker);
#endif
    int integer = __builtin_va_arg(args, int);
    double promoted = __builtin_va_arg(args, double);
    word tag = __builtin_va_arg(args, word);
#if defined(MS_ABI)
    __builtin_ms_va_end(args);
#else
    __builtin_va_end(args);
#endif
    union { double value; word bits; } encoded = { .value = promoted };
    *output = (output_record){marker, (word)(long)integer, encoded.bits, tag};
}
