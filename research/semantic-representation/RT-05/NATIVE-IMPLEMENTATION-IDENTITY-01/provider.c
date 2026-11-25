#include "entry.h"

struct record CALL_ABI step(struct record input, uint64_t salt)
{
    return (struct record){input.first + salt + PROVIDER_DELTA, input.second ^ salt};
}
