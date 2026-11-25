#ifndef ALLOCATOR_LEASE_PROVIDER_H
#define ALLOCATOR_LEASE_PROVIDER_H

#include <stdbool.h>
#include <stddef.h>

typedef enum { OK, INVALID_RANGE, OWNER_MISMATCH, STALE, BUSY, OS_ERROR } Status;
typedef enum { HEAP, MAPPING } Allocator;
typedef struct { unsigned owner; unsigned generation; } Lease;
typedef struct { Lease allocation; unsigned ordinal; } Borrow;
typedef struct {
    unsigned owner;
    unsigned generation;
    Allocator allocator;
    unsigned char *bytes;
    size_t length;
    unsigned borrow_ordinal;
    bool borrowed;
    bool cancellation_requested;
} Provider;

Status reserve(Provider *provider, size_t size, Lease *lease, int *external_error);
Status borrow_bytes(Provider *provider, Lease lease, size_t offset, size_t count, unsigned char **borrowed, Borrow *token);
Status cancel_borrow(Provider *provider, Borrow token);
Status finish_borrow(Provider *provider, Borrow token);
Status release(Provider *provider, Lease lease, int *external_error);
int probe_allocator_failure(Allocator allocator);

#endif
