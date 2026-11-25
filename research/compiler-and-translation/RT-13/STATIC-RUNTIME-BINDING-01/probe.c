#define _GNU_SOURCE
#include "provider.h"

#include <assert.h>
#include <dlfcn.h>
#include <inttypes.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>

struct provider {
    unsigned id;
    void *handle;
    entry call;
    unsigned leases;
    bool retired;
};

struct binding {
    unsigned catalog;
    struct provider *selected;
};

struct invocation {
    entry call;
    unsigned provider;
    uint32_t input;
    uint32_t output;
    uint32_t effect_value;
    unsigned effects;
    pthread_barrier_t *entered;
    pthread_barrier_t *resume;
};

static struct provider load(const char *path, unsigned expected) {
    void *handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    assert(handle);
    unsigned (*identity)(void) = (unsigned (*)(void))dlsym(handle, "provider_identity");
    entry call = (entry)dlsym(handle, "step");
    assert(identity && call && identity() == expected);
    return (struct provider){.id = expected, .handle = handle, .call = call};
}

static void close_if_drained(struct provider *provider) {
    if (provider->retired && provider->leases == 0) {
        assert(provider->handle && dlclose(provider->handle) == 0);
        provider->handle = NULL;
        provider->call = NULL;
    }
}

static struct provider *acquire(struct binding binding, unsigned current_catalog) {
    if (!binding.selected || binding.catalog != current_catalog || binding.selected->retired)
        return NULL;
    ++binding.selected->leases;
    return binding.selected;
}

static void release(struct provider *provider) {
    assert(provider->leases);
    --provider->leases;
    close_if_drained(provider);
}

static void wait_at(pthread_barrier_t *barrier) {
    int status = pthread_barrier_wait(barrier);
    assert(status == 0 || status == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void observe(uint32_t value, void *context) {
    struct invocation *run = context;
    ++run->effects;
    run->effect_value = value;
    if (run->entered) {
        wait_at(run->entered);
        wait_at(run->resume);
    }
}

static void *invoke(void *context) {
    struct invocation *run = context;
    run->output = run->call(run->input, observe, run);
    return NULL;
}

static void record(const char *label, struct invocation run) {
    printf("%s %u %" PRIu32 " %" PRIu32 " %u\n",
           label, run.provider, run.output, run.effect_value, run.effects);
}

static void call_now(const char *label, entry call, unsigned provider, uint32_t input) {
    struct invocation run = {.call = call, .provider = provider, .input = input};
    invoke(&run);
    record(label, run);
}

int main(int argc, char **argv) {
    if (argc != 3)
        return 2;
    struct provider old = load(argv[1], 1);
    struct provider replacement = load(argv[2], 2);
    unsigned catalog = 1;
    const struct binding before = {catalog, &old};

    call_now("static-before", step, provider_identity(), 9);
    struct provider *lease = acquire(before, catalog);
    assert(lease == &old);
    pthread_barrier_t entered, resume;
    assert(pthread_barrier_init(&entered, NULL, 2) == 0);
    assert(pthread_barrier_init(&resume, NULL, 2) == 0);
    struct invocation earlier = {
        .call = lease->call, .provider = lease->id, .input = UINT32_MAX,
        .entered = &entered, .resume = &resume,
    };
    pthread_t thread;
    assert(pthread_create(&thread, NULL, invoke, &earlier) == 0);
    wait_at(&entered);

    catalog = 2;
    old.retired = true;
    close_if_drained(&old);
    assert(old.handle != NULL);
    printf("retained-during-replacement %u\n", old.leases);
    assert(acquire(before, catalog) == NULL);
    printf("stale-new-call-rejected 1\n");
    assert(acquire((struct binding){before.catalog, &replacement}, catalog) == NULL);
    assert(acquire((struct binding){catalog, &old}, catalog) == NULL);
    printf("independent-rejection-controls 2\n");
    const struct binding after = {catalog, &replacement};
    struct provider *current = acquire(after, catalog);
    assert(current == &replacement);
    call_now("runtime-after", current->call, current->id, 9);
    release(current);
    call_now("static-after", step, provider_identity(), 9);

    wait_at(&resume);
    assert(pthread_join(thread, NULL) == 0);
    record("runtime-already-started", earlier);
    release(lease);
    assert(old.handle == NULL);
    assert(dlopen(argv[1], RTLD_NOW | RTLD_NOLOAD) == NULL);
    printf("retired-handle-released 1\n");
    catalog = 3;
    replacement.retired = true;
    close_if_drained(&replacement);
    assert(acquire((struct binding){catalog, NULL}, catalog) == NULL);
    printf("runtime-no-binding 1\n");
    call_now("static-without-runtime-binding", step, provider_identity(), 9);
    assert(pthread_barrier_destroy(&resume) == 0);
    assert(pthread_barrier_destroy(&entered) == 0);
    return ferror(stdout);
}
