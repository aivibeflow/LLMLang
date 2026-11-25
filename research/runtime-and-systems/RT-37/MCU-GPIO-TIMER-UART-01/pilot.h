#ifndef LLMLANG_PILOT_H
#define LLMLANG_PILOT_H

#include <stdint.h>

typedef enum { PILOT_OK, PILOT_RANGE, PILOT_CALLBACK } pilot_result;
typedef struct {
    unsigned tick;
    void (*gpio)(unsigned level);
    void (*uart)(char value);
} pilot_state;

pilot_result pilot_step(pilot_state *state, unsigned tick);
void pilot_emit_result(void (*uart)(char), unsigned tick, unsigned level);

#endif
