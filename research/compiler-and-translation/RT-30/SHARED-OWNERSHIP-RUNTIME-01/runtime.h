#ifndef OWNERSHIP_RUNTIME_H
#define OWNERSHIP_RUNTIME_H

#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

uint32_t rt_apply(uint32_t operation, uint32_t actor, uint32_t peer,
                  uint32_t handle, uint32_t payload);
uint32_t rt_snapshot(void);
void rt_reset(void);

#ifdef __cplusplus
}
#endif
#endif
