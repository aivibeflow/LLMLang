#include "api.h"

struct record record_step(struct record current, u32 delta) {
    current.sequence += 1;
    current.state += delta;
    current.status = current.state >= delta ? 0 : 1;
    return current;
}
