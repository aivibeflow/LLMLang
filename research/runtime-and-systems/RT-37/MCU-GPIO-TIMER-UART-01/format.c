#include "pilot.h"

void pilot_emit_result(void (*uart)(char), unsigned tick, unsigned level) {
    const char message[] = {'P', ':', '0' + tick, ':', '0' + level, '\n'};
    for (unsigned i = 0; i < sizeof(message); ++i)
        uart(message[i]);
}
