#include "selected.h"

int provider_base(int value);
int provider_equivalent(int value);
int provider_wrong(int value);
int provider_restricted(int value);
int provider_other(int value);

int site(int value) {
#if FEATURE
    return SELECTED(value);
#else
    return provider_base(value);
#endif
}
