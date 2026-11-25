#include "runtime.h"

extern "C" uint32_t step(uint32_t operation, uint32_t actor, uint32_t peer,
                         uint32_t handle, uint32_t payload) {
#ifdef ALTER_TRANSFER
    if (operation == 1 && peer < 4) {
        peer = actor;
    }
#endif
    return rt_apply(operation, actor, peer, handle, payload);
}
