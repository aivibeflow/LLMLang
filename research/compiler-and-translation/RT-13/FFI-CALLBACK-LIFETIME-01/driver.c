#include <stdio.h>
#include <stdlib.h>

#include "fixture.h"

static void expect(const char *action, int actual, int expected)
{
    if (actual == expected)
        return;
    fprintf(stderr, "%s: got %d, expected %d\n", action, actual, expected);
    exit(1);
}

int fixture_drive(callback call, void *context, void *peer, int payload, int profile)
{
    session *first = fixture_create();
    session *second = fixture_create();
    if (!first || !second)
        return 1;
    uint64_t ticket_one, ticket_two, ignored, renewed;
    int inline_result, worker_one, worker_two, renewed_result, ignored_result;

    expect("register first", fixture_register(first, call, context, &ticket_one), OK);
    expect("register second", fixture_register(second, call, peer, &ticket_two), OK);
    expect("call inline", fixture_inline(first, ticket_one, payload, &inline_result), OK);
    expect("start first", fixture_start(first, ticket_one, payload), OK);
    expect("start second", fixture_start(second, ticket_two, payload + 1), OK);
    expect("first still active", fixture_retire(first, ticket_one), BUSY);
    expect("second still active", fixture_retire(second, ticket_two), BUSY);
    expect("early destroy", fixture_destroy(first), BUSY);
    expect("early replace", fixture_register(first, call, context, &ignored), BUSY);
    expect("second call on first instance", fixture_start(first, ticket_one, payload), BUSY);

    if (profile == 0) {
        expect("join first", fixture_finish(first, ticket_one, &worker_one), OK);
        expect("peer still active", fixture_retire(second, ticket_two), BUSY);
        expect("join second", fixture_finish(second, ticket_two, &worker_two), OK);
    } else {
        expect("join second", fixture_finish(second, ticket_two, &worker_two), OK);
        expect("peer still active", fixture_retire(first, ticket_one), BUSY);
        expect("join first", fixture_finish(first, ticket_one, &worker_one), OK);
    }

    expect("retire first", fixture_retire(first, ticket_one), OK);
    expect("retire second", fixture_retire(second, ticket_two), OK);
    expect("retired ticket", fixture_inline(first, ticket_one, payload, &ignored_result), STALE);
    expect("register again", fixture_register(first, call, context, &renewed), OK);
    expect("old ticket against new provider", fixture_start(first, ticket_one, payload), STALE);
    expect("new ticket inline", fixture_inline(first, renewed, payload, &renewed_result), OK);
    expect("retire new ticket", fixture_retire(first, renewed), OK);
    expect("destroy first", fixture_destroy(first), OK);
    expect("destroy second", fixture_destroy(second), OK);
    printf("%d\t%d\t%d\t%d\t%llu\t%llu\t%llu\n", inline_result, worker_one, worker_two,
           renewed_result, (unsigned long long)ticket_one, (unsigned long long)ticket_two,
           (unsigned long long)renewed);
    return 0;
}
