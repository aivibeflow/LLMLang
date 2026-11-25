#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum policy { reload, guarded, forward, premature };

struct trace {
    uint32_t slot;
    uint32_t events[2];
    unsigned count;
};

static void effect(struct trace *trace, bool modifies, uint32_t replacement) {
    trace->events[trace->count++] = trace->slot;
    if (modifies)
        trace->slot = replacement;
}

static bool invoke(enum policy policy, uint32_t produced, uint32_t amount,
                   bool modifies, uint32_t replacement, struct trace *trace) {
    if (policy == premature && amount > produced)
        return false;
    trace->slot = produced;
    effect(trace, modifies, replacement);
    bool use_forwarding = policy == forward || (policy == guarded && !modifies);
    uint32_t available = use_forwarding ? produced : trace->slot;
    if (amount > available)
        return false;
    trace->slot = available - amount;
    trace->events[trace->count++] = trace->slot;
    return true;
}

int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    enum policy policy;
    if (!strcmp(argv[1], "reload"))
        policy = reload;
    else if (!strcmp(argv[1], "guarded"))
        policy = guarded;
    else if (!strcmp(argv[1], "forward"))
        policy = forward;
    else if (!strcmp(argv[1], "premature"))
        policy = premature;
    else
        return 2;
    uint32_t produced, amount, replacement;
    unsigned modifies;
    int fields;
    while ((fields = scanf("%" SCNu32 " %" SCNu32 " %u %" SCNu32,
                           &produced, &amount, &modifies, &replacement)) == 4) {
        assert(modifies <= 1);
        struct trace trace = {.slot = 0xabad1234};
        bool success = invoke(policy, produced, amount, modifies, replacement, &trace);
        printf("%u %" PRIu32, (unsigned)success, trace.slot);
        for (unsigned index = 0; index < trace.count; ++index)
            printf(" %" PRIu32, trace.events[index]);
        putchar('\n');
    }
    return fields != EOF || ferror(stdin) || ferror(stdout);
}
