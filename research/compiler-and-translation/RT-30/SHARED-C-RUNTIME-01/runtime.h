#ifndef LLMLANG_PROBE_RUNTIME_H
#define LLMLANG_PROBE_RUNTIME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

uint64_t rt_dispatch(uint32_t receiver, uint32_t state, int32_t change, uint32_t grants);

#ifdef __cplusplus
}
#endif

#endif
