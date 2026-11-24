/* Scripted C outcome provider with real Linux event descriptors and a role guard. */
#include <assert.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/eventfd.h>
#include <unistd.h>

enum { HANDLE, LOCAL, SECOND, SLOTS };
enum { EMPTY, USABLE, RECONCILE };
enum { OK, RETAINED, CONSUMED, INDETERMINATE };

struct outcome {
    uint32_t disposition;
    uint32_t usable_token;
};

_Static_assert(sizeof(struct outcome) == 8, "two-field outcome ABI");
_Static_assert(offsetof(struct outcome, usable_token) == 4, "usable token layout");

struct resource {
    int fd;
    uint32_t state;
    uint32_t source;
    uint32_t destination;
};

static struct resource table[SLOTS];
static uint32_t close_unknown;
static uint32_t acquire_count;
static uint32_t release_count;
static uint32_t physical_closes;

void rt_begin(uint32_t consume_unknown) {
    for (uint32_t slot = 0; slot < SLOTS; ++slot) {
        assert(table[slot].state == EMPTY);
        table[slot].fd = -1;
    }
    close_unknown = consume_unknown;
    acquire_count = 0;
    release_count = 0;
    physical_closes = 0;
}

uint32_t rt_acquire(uint32_t slot, uint32_t source, uint32_t destination) {
    assert(slot < SLOTS && table[slot].state == EMPTY);
    const struct resource *held = &table[HANDLE];
    if (slot != LOCAL && source == destination)
        return 0;
    if (slot == SECOND && held->state != EMPTY &&
        (held->destination == source || held->destination == destination || held->source == destination))
        return 0;
    int fd = eventfd(0, EFD_CLOEXEC);
    assert(fd >= 0);
    table[slot] = (struct resource){fd, USABLE, source, destination};
    ++acquire_count;
    return slot + 1;
}

static void close_native(struct resource *resource) {
    assert(resource->fd >= 0);
    assert(fcntl(resource->fd, F_GETFD) >= 0);
    assert(close(resource->fd) == 0);
    resource->fd = -1;
    ++physical_closes;
}

struct outcome rt_release(uint32_t token, uint32_t disposition) {
    assert(token > 0 && token <= SLOTS && disposition <= INDETERMINATE);
    struct resource *resource = &table[token - 1];
    assert(resource->state == USABLE && fcntl(resource->fd, F_GETFD) >= 0);
    ++release_count;
    if (disposition == RETAINED)
        return (struct outcome){disposition, token};
    if (disposition != INDETERMINATE || close_unknown)
        close_native(resource);
    resource->state = disposition == INDETERMINATE ? RECONCILE : EMPTY;
    return (struct outcome){disposition, 0};
}

uint64_t rt_finish(void) {
    uint32_t live = 0;
    uint32_t pending = 0;
    for (uint32_t slot = 0; slot < SLOTS; ++slot) {
        struct resource *resource = &table[slot];
        if (resource->state == RECONCILE)
            pending |= 1u << slot;
        if (resource->fd >= 0) {
            assert(fcntl(resource->fd, F_GETFD) >= 0);
            live |= 1u << slot;
        }
    }
    const uint64_t audit = (uint64_t)live | ((uint64_t)pending << 8) |
        ((uint64_t)acquire_count << 16) | ((uint64_t)release_count << 24) |
        ((uint64_t)physical_closes << 32);
    for (uint32_t slot = 0; slot < SLOTS; ++slot) {
        if (table[slot].fd >= 0)
            close_native(&table[slot]);
        table[slot].state = EMPTY;
    }
    return audit;
}
