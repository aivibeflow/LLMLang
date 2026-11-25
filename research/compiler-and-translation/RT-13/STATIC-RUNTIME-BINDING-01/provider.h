#pragma once
#include <stdint.h>

typedef void (*effect)(uint32_t value, void *context);
typedef uint32_t (*entry)(uint32_t value, effect callback, void *context);
unsigned provider_identity(void);
uint32_t step(uint32_t value, effect callback, void *context);
