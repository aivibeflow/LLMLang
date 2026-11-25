#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*jit_entry)(uint32_t, uint32_t (*)(uint32_t));
int host_call(jit_entry entry, size_t code_size);
int callback_fde_registered(void);

#ifdef __cplusplus
}
#endif
