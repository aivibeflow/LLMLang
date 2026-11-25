#include "provider.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static void require(int condition) {
    if (!condition)
        abort();
}

static void sequence(Allocator allocator) {
    Provider provider = {.owner = 11, .allocator = allocator};
    Provider other = {.owner = 12, .allocator = allocator == HEAP ? MAPPING : HEAP};
    Lease old, active;
    Borrow initial, current;
    int error = -1;
    unsigned char *borrowed = NULL;
    require(reserve(&provider, 8, &old, &error) == OK && error == 0);
    require(reserve(&other, 8, &active, &error) == OK);
    require(active.generation == old.generation && active.owner != old.owner);
    printf("wrong-provider:%d\n", release(&other, old, &error));
    printf("oversize:%d\n", borrow_bytes(&provider, old, 7, SIZE_MAX, &borrowed, &current));
    require(!borrowed);
    require(borrow_bytes(&provider, old, 6, 2, &borrowed, &initial) == OK);
    require(borrowed[0] == 0 && borrowed[1] == 0);
    borrowed[0] = 5;
    printf("aliased-borrow:%d\n", borrow_bytes(&provider, old, 0, 1, &borrowed, &current));
    printf("cancel:%d\n", cancel_borrow(&provider, initial));
    require(provider.cancellation_requested);
    printf("release-pending:%d\n", release(&provider, old, &error));
    printf("settle:%d\n", finish_borrow(&provider, initial));
    require(borrow_bytes(&provider, old, 6, 2, &borrowed, &current) == OK);
    require(!provider.cancellation_requested);
    printf("stale-borrow:%d\n", finish_borrow(&provider, initial));
    printf("settled-byte:%d\n", borrowed[0]);
    require(finish_borrow(&provider, current) == OK);
    printf("release:%d\n", release(&provider, old, &error));
    require(reserve(&provider, 8, &active, &error) == OK);
    printf("retired-generation:%d\n", release(&provider, old, &error));
    require(borrow_bytes(&provider, active, 6, 2, &borrowed, &current) == OK);
    printf("new-byte:%d\n", borrowed[0]);
    require(finish_borrow(&provider, current) == OK);
    require(release(&provider, active, &error) == OK);
    require(release(&other, (Lease){12, 1}, &error) == OK);
    printf("backend-error:%d\n", probe_allocator_failure(allocator));
}

int main(void) {
    sequence(HEAP);
    sequence(MAPPING);
}
