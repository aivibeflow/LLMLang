#include "provider.h"

#include <assert.h>
#include <pthread.h>

enum { OK = 0, CANCELED = 1, STALE = -3, BUSY = -4, NOT_WORKER = -6 };

static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static pthread_t worker;
static uint32_t generation, active, completions;
static int32_t pending, released, canceled, value, last_result;
static callback_fn callback;
static void *context;

static void *invoke(void *unused) {
    (void)unused;
    assert(pthread_mutex_lock(&mutex) == 0);
    while (!released) {
        assert(pthread_cond_wait(&changed, &mutex) == 0);
    }
    const int32_t skip = canceled;
    callback_fn target = callback;
    void *argument = context;
    const uint32_t token = active;
    const int32_t supplied = value;
    assert(pthread_mutex_unlock(&mutex) == 0);
    if (!skip) {
        const int32_t outcome = target(argument, token, supplied);
        assert(pthread_mutex_lock(&mutex) == 0);
        last_result = outcome;
        ++completions;
        assert(pthread_mutex_unlock(&mutex) == 0);
    }
    return NULL;
}

uint32_t open_session(void) {
    assert(pthread_mutex_lock(&mutex) == 0);
    if (active == 0 && generation < 1000000) {
        active = ++generation;
    }
    const uint32_t token = active;
    assert(pthread_mutex_unlock(&mutex) == 0);
    return token;
}

int32_t close_session(uint32_t token) {
    assert(pthread_mutex_lock(&mutex) == 0);
    const int32_t outcome = token == 0 || token != active ? STALE : pending ? BUSY : OK;
    if (outcome == OK) {
        active = 0;
    }
    assert(pthread_mutex_unlock(&mutex) == 0);
    return outcome;
}

int32_t start_callback(uint32_t token, callback_fn target, void *argument, int32_t supplied) {
    assert(pthread_mutex_lock(&mutex) == 0);
    const int32_t outcome = token == 0 || token != active ? STALE : pending ? BUSY : OK;
    if (outcome == OK) {
        pending = 1;
        released = 0;
        canceled = 0;
        callback = target;
        context = argument;
        value = supplied;
        assert(pthread_create(&worker, NULL, invoke, NULL) == 0);
    }
    assert(pthread_mutex_unlock(&mutex) == 0);
    return outcome;
}

int32_t finish_callback(uint32_t token, int32_t cancel, int32_t *result) {
    assert(pthread_mutex_lock(&mutex) == 0);
    if (token == 0 || token != active || !pending || released) {
        assert(pthread_mutex_unlock(&mutex) == 0);
        return STALE;
    }
    canceled = cancel;
    released = 1;
    assert(pthread_cond_signal(&changed) == 0);
    assert(pthread_mutex_unlock(&mutex) == 0);
    assert(pthread_join(worker, NULL) == 0);
    assert(pthread_mutex_lock(&mutex) == 0);
    if (!cancel) {
        *result = last_result;
    }
    callback = NULL;
    context = NULL;
    pending = 0;
    assert(pthread_mutex_unlock(&mutex) == 0);
    return cancel ? CANCELED : OK;
}

int32_t peek_worker(uint32_t token) {
    assert(pthread_mutex_lock(&mutex) == 0);
    int32_t outcome = NOT_WORKER;
    if (token == 0 || token != active) {
        outcome = STALE;
    } else if (pending && pthread_equal(worker, pthread_self())) {
        outcome = (int32_t)token + 1000;
    }
    assert(pthread_mutex_unlock(&mutex) == 0);
    return outcome;
}

uint32_t completed_count(void) {
    assert(pthread_mutex_lock(&mutex) == 0);
    const uint32_t count = completions;
    assert(pthread_mutex_unlock(&mutex) == 0);
    return count;
}
