#include "routes.h"

int site_primary(void) {
#if MODE
    return PRIMARY();
#else
    return provider_base();
#endif
}

int site_secondary(void) {
#if AUDIT
    return provider_audit();
#else
    return SECONDARY();
#endif
}

int site_optional(void) {
#if EXTRA
    return OPTIONAL();
#else
    return 0;
#endif
}
