#include <stdio.h>

struct observation {
    unsigned result;
    unsigned effect;
};

static void emit(struct observation *observation) {
    observation->effect = 1;
}

static struct observation observe(unsigned provider, unsigned input) {
    unsigned code = (provider >> (2 * input)) & 3;
    struct observation observation = {.result = code & 1};
    if (code & 2) {
        emit(&observation);
    }
    return observation;
}

int main(void) {
    for (unsigned provider = 0; provider < 16; provider++) {
        for (unsigned input = 0; input < 2; input++) {
            struct observation outcome = observe(provider, input);
            printf("%u %u %u %u\n", provider, input, outcome.result, outcome.effect);
        }
    }
    return ferror(stdout) != 0;
}
