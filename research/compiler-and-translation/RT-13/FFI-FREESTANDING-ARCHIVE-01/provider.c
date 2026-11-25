#include "ffi.h"

struct outcome dispatch(u32 state, u32 request, event_sink sink, void *context) {
    sink(context, 1);
    if (request > 5) {
        return (struct outcome){state, 1};
    }
    state += checked_support(request);
#ifndef OMIT_EVENT
    sink(context, 2);
#endif
    return (struct outcome){state, 0};
}
