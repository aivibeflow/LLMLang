#include <stdint.h>

enum permission {
    READ = 1,
    AUDIT = 2,
    REPAIR = 4,
};

enum outcome {
    FOUND,
    MISSING,
    IO_ERROR,
    DENIED,
    RECOVERED,
};

static uint32_t finish(enum outcome result, uint32_t trace)
{
    return ((uint32_t)result << 8) | trace;
}

uint32_t evaluate(uint32_t fetch, uint32_t enabled, uint32_t grants)
{
    if (!(grants & READ))
        return finish(DENIED, 0);

    uint32_t trace = 1;  /* Read. */
    if (fetch == FOUND)
        return finish(FOUND, trace);
    if (fetch == IO_ERROR)
        return finish(IO_ERROR, trace);
    if (!enabled)
        return finish(MISSING, trace);

    if (!(grants & AUDIT))
        return finish(DENIED, trace);
    trace = trace * 4u + 2u;  /* Audit. */
    if (!(grants & REPAIR))
        return finish(DENIED, trace);
    trace = trace * 4u + 3u;  /* Repair. */
    return finish(RECOVERED, trace);
}
