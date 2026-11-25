#ifndef LLMLANG_ABI_FIXTURE_H
#define LLMLANG_ABI_FIXTURE_H

#include <stddef.h>
#include <stdint.h>

#if CALL_STYLE == 0
#define CALL_ABI __attribute__((sysv_abi))
#elif CALL_STYLE == 1
#define CALL_ABI __attribute__((ms_abi))
#else
#error Explicit calling convention required
#endif

struct Pair {
    uint64_t x;
    uint64_t y;
};

_Static_assert(sizeof(struct Pair) == 16, "Pair size");
_Static_assert(_Alignof(struct Pair) == 8, "Pair alignment");
_Static_assert(offsetof(struct Pair, x) == 0 && offsetof(struct Pair, y) == 8, "Pair offsets");

struct Pair CALL_ABI transform_record(struct Pair input, uint64_t salt);
void bridge_record(const struct Pair *input, uint64_t salt, struct Pair *output);
unsigned provider_call_style(void);

#endif
