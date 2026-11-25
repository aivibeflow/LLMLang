#include "abi.h"

struct span update_span(struct span from, u32 requested) {
    if (requested <= from.length) {
        from.origin += requested;
        from.length -= requested;
        from.status = 0;
    } else {
        from.status = 1;
    }
    return from;
}
