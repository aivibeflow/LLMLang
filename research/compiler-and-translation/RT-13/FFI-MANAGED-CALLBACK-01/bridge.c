#include <stdio.h>

#include "_cgo_export.h"

static int cgo_callback(session *self, uint64_t ticket, int payload, void *context)
{
    uintptr_t token = *(const uintptr_t *)context;
    return goCallback(self, ticket, payload, token);
}

int drive_go(uintptr_t primary, uintptr_t peer, int payload, int profile, int flush)
{
    int status = fixture_drive(cgo_callback, &primary, &peer, payload, profile);
    if (flush && fflush(stdout))
        return SYSTEM_ERROR;
    return status;
}
