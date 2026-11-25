#include "api.h"

unsigned int mainCRTStartup(void) {
    const struct record source = {17, 0xfffffffeu, 3};
    const struct record result = record_step(source, 3);
    return !(result.sequence == 18 && result.state == 1 && result.status == 1);
}
