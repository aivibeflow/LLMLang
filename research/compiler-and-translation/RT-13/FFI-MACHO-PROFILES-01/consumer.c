#include "abi.h"

u32 observe_span(void) {
    struct span initial = {64, 17, 0};
    struct span result = update_span(initial, 5);
    return result.origin == 69 && result.length == 12 && result.status == 0;
}
