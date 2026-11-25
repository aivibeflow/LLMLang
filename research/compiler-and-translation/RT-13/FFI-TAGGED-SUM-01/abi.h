#ifndef FFI_TAGGED_SUM_ABI_H
#define FFI_TAGGED_SUM_ABI_H

#include <stddef.h>
#include <stdint.h>

typedef union { int64_t integer; double floating; const void *pointer; } Payload;
typedef struct { uint32_t tag; uint32_t reserved; Payload payload; } Sum;
typedef struct { uint32_t disposition; uint32_t reserved; int64_t value; } Result;

_Static_assert(sizeof(Sum) == 16 && _Alignof(Sum) == 8 && offsetof(Sum, payload) == 8, "sum layout");
_Static_assert(sizeof(Result) == 16 && _Alignof(Result) == 8 && offsetof(Result, value) == 8, "result layout");

Result __attribute__((sysv_abi)) call_sysv(Sum value, const void *authorized);
Result __attribute__((ms_abi)) call_ms(Sum value, const void *authorized);

#endif
