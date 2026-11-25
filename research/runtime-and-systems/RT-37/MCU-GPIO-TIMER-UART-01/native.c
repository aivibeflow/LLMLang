#include "pilot.h"
#include <assert.h>
#include <stdio.h>

static unsigned gpio_calls;
static unsigned actual_level;

static void gpio(unsigned level) {
    actual_level = level;
    gpio_calls++;
}

static void uart(char value) {
    putchar(value);
}

int main(void) {
    const unsigned levels[] = {0, 1, 1, 0, 0, 1};
    pilot_state state = {0, gpio, uart};
    pilot_state no_uart = {0, gpio, 0};
    assert(pilot_step(&no_uart, 1) == PILOT_CALLBACK);
    assert(pilot_step(&state, 0) == PILOT_RANGE);
    assert(pilot_step(&state, 2) == PILOT_RANGE);
    assert(gpio_calls == 0 && state.tick == 0);
    for (unsigned tick = 1; tick <= 6; ++tick) {
        assert(pilot_step(&state, tick) == PILOT_OK);
        assert(actual_level == levels[tick - 1]);
        assert(pilot_step(&state, tick) == PILOT_RANGE);
    }
    assert(pilot_step(&state, 7) == PILOT_RANGE);
    assert(gpio_calls == 6 && state.tick == 6);
}
