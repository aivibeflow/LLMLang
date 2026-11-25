#include <stdlib.h>

#include "fixture.h"

static int c_callback(session *self, uint64_t ticket, int payload, void *context)
{
    int kind, ignored;
    if (fixture_thread(self, ticket, &kind) != OK ||
        fixture_retire(self, ticket) != BUSY ||
        fixture_finish(self, ticket, &ignored) != BUSY)
        return CALLBACK_PROTOCOL_ERROR;
    if (payload == -7)
        return CALLBACK_ERROR;
    return kind * 1000 + payload * 3 + *(const int *)context;
}

int main(int argc, char **argv)
{
    if (argc != 4)
        return 1;
    int offset = atoi(argv[3]);
    int peer = offset + 7;
    return fixture_drive(c_callback, &offset, &peer, atoi(argv[1]), atoi(argv[2]));
}
