#define _GNU_SOURCE
#include "provider.h"

#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

static Status current(const Provider *provider, Lease lease) {
    if (lease.owner != provider->owner)
        return OWNER_MISMATCH;
    if (!provider->bytes || lease.generation != provider->generation)
        return STALE;
    return OK;
}

Status reserve(Provider *provider, size_t size, Lease *lease, int *external_error) {
    *external_error = 0;
    if (size == 0 || size > 64)
        return INVALID_RANGE;
    if (provider->bytes)
        return BUSY;
    if (provider->generation == UINT32_MAX)
        return STALE;
    unsigned char *memory;
    if (provider->allocator == HEAP) {
        memory = malloc(size);
        if (!memory) {
            *external_error = errno;
            return OS_ERROR;
        }
    } else {
        memory = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (memory == MAP_FAILED) {
            *external_error = errno;
            return OS_ERROR;
        }
    }
    memset(memory, 0, size);
    provider->bytes = memory;
    provider->length = size;
    provider->generation++;
    *lease = (Lease){provider->owner, provider->generation};
    return OK;
}

Status borrow_bytes(Provider *provider, Lease lease, size_t offset, size_t count, unsigned char **borrowed, Borrow *token) {
    Status status = current(provider, lease);
    if (status != OK)
        return status;
    if (offset > provider->length || count == 0 || count > provider->length - offset)
        return INVALID_RANGE;
    if (provider->borrowed)
        return BUSY;
    if (provider->borrow_ordinal == UINT32_MAX)
        return STALE;
    provider->borrowed = true;
    *token = (Borrow){lease, ++provider->borrow_ordinal};
    *borrowed = provider->bytes + offset;
    return OK;
}

Status cancel_borrow(Provider *provider, Borrow token) {
    Status status = current(provider, token.allocation);
    if (status != OK)
        return status;
    if (!provider->borrowed || token.ordinal != provider->borrow_ordinal)
        return STALE;
    provider->cancellation_requested = true;
    return OK;
}

Status finish_borrow(Provider *provider, Borrow token) {
    Status status = current(provider, token.allocation);
    if (status != OK)
        return status;
    if (!provider->borrowed || token.ordinal != provider->borrow_ordinal)
        return STALE;
    provider->borrowed = false;
    provider->cancellation_requested = false;
    return OK;
}

Status release(Provider *provider, Lease lease, int *external_error) {
    *external_error = 0;
    Status status = current(provider, lease);
    if (status != OK)
        return status;
    if (provider->borrowed)
        return BUSY;
    if (provider->allocator == HEAP) {
        free(provider->bytes);
    } else if (munmap(provider->bytes, provider->length) != 0) {
        *external_error = errno;
        return OS_ERROR;
    }
    provider->bytes = NULL;
    provider->length = 0;
    return OK;
}

int probe_allocator_failure(Allocator allocator) {
    if (allocator == HEAP) {
        volatile size_t unavailable = SIZE_MAX;
        void *blocked = malloc(unavailable);
        if (!blocked)
            return errno;
        free(blocked);
        return 0;
    }
    void *blocked = mmap(NULL, 0, PROT_READ, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    return blocked == MAP_FAILED ? errno : 0;
}
