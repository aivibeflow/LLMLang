#include "runtime.h"

uint32_t step(uint32_t operation, uint32_t actor, uint32_t peer,
              uint32_t handle, uint32_t payload) {
    return rt_apply(operation, actor, peer, handle, payload);
}
