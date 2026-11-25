#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

#ifdef PROVIDER
EXPORT unsigned fixture_step(unsigned *slot, unsigned delta, unsigned *trace) {
    unsigned before = *slot;
    unsigned value = before + delta;
    if (value < before)
        return 1;
    trace[0] = before;
    trace[1] = value;
    *slot = value;
    return 0;
}
#else
#ifdef WRONG_SYMBOL
#define fixture_step missing_fixture_step
#endif
unsigned fixture_step(unsigned *slot, unsigned delta, unsigned *trace);
EXPORT unsigned ffi_observe(unsigned *slot, unsigned delta, unsigned *trace) {
    return fixture_step(slot, delta, trace);
}
#endif
