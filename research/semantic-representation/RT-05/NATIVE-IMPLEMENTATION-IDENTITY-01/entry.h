#include <stddef.h>
#include <stdint.h>

#if TARGET_ABI == 0
#define CALL_ABI __attribute__((sysv_abi))
#elif TARGET_ABI == 1
#define CALL_ABI __attribute__((ms_abi))
#else
#error Unsupported target ABI
#endif

struct record {
    uint64_t first;
    uint64_t second;
};

_Static_assert(sizeof(struct record) == 16, "record size");
_Static_assert(_Alignof(struct record) == 8, "record alignment");
_Static_assert(offsetof(struct record, first) == 0, "first field offset");
_Static_assert(offsetof(struct record, second) == 8, "second field offset");

typedef struct record (CALL_ABI *step_fn)(struct record, uint64_t);
