#include "provider.h"

unsigned provider_identity(void) {
    return PROVIDER_ID;
}

uint32_t step(uint32_t value, effect callback, void *context) {
    callback(value, context);
#if PROVIDER_ID == 1
    return value * 3u + 1u;
#else
    return value + value + value + 1u;
#endif
}
