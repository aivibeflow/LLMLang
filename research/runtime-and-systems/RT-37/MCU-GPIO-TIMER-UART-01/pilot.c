#include "pilot.h"

pilot_result pilot_step(pilot_state *state, unsigned tick) {
    if (!state || !state->gpio || !state->uart)
        return PILOT_CALLBACK;
    if (tick == 0 || tick > 6 || tick != state->tick + 1)
        return PILOT_RANGE;
    unsigned level = (tick / 2) % 2;
    state->gpio(level);
    pilot_emit_result(state->uart, tick, level);
    state->tick = tick;
    return PILOT_OK;
}
