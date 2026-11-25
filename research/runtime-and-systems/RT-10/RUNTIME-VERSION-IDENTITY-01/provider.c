#include <stdint.h>

const char *probe_label(void) {
    return PROBE_LABEL;
}

const char *probe_build_stamp(void) {
    return PROBE_STAMP;
}

uint32_t probe_interface(void) {
    return PROBE_INTERFACE;
}

/* Status 1 leaves the caller's slot unchanged. */
int32_t probe_quantize(int32_t input, int32_t *slot) {
    if (input < 0 || input > 31) {
        return 1;
    }
    *slot = (input + PROBE_OFFSET) / 4;
    return 0;
}
