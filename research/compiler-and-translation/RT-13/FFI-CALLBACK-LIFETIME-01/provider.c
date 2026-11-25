#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>

#include "fixture.h"

struct session {
    pthread_mutex_t mutex;
    pthread_cond_t signal;
    pthread_t registrar;
    pthread_t worker;
    uint64_t generation;
    callback call;
    void *context;
    bool active;
    bool asynchronous;
    bool started;
    bool released;
    bool joining;
    int payload;
    int result;
};

session *fixture_create(void)
{
    session *self = calloc(1, sizeof(*self));
    if (!self)
        return NULL;
    if (pthread_mutex_init(&self->mutex, NULL)) {
        free(self);
        return NULL;
    }
    if (pthread_cond_init(&self->signal, NULL)) {
        pthread_mutex_destroy(&self->mutex);
        free(self);
        return NULL;
    }
    return self;
}

static bool valid(const session *self, uint64_t ticket)
{
    return self->call && self->generation == ticket;
}

int fixture_register(session *self, callback call, void *context, uint64_t *ticket)
{
    if (!call || !ticket)
        return INVALID;
    pthread_mutex_lock(&self->mutex);
    int status = OK;
    if (self->call || self->active)
        status = BUSY;
    else if (self->generation == UINT64_MAX)
        status = INVALID;
    else {
        self->call = call;
        self->context = context;
        self->registrar = pthread_self();
        *ticket = ++self->generation;
    }
    pthread_mutex_unlock(&self->mutex);
    return status;
}

int fixture_retire(session *self, uint64_t ticket)
{
    pthread_mutex_lock(&self->mutex);
    int status = OK;
    if (!valid(self, ticket))
        status = STALE;
    else if (self->active)
        status = BUSY;
    else {
        self->call = NULL;
        self->context = NULL;
    }
    pthread_mutex_unlock(&self->mutex);
    return status;
}

int fixture_destroy(session *self)
{
    pthread_mutex_lock(&self->mutex);
    bool busy = self->active || self->call;
    pthread_mutex_unlock(&self->mutex);
    if (busy)
        return BUSY;
    pthread_cond_destroy(&self->signal);
    pthread_mutex_destroy(&self->mutex);
    free(self);
    return OK;
}

int fixture_thread(session *self, uint64_t ticket, int *kind)
{
    pthread_mutex_lock(&self->mutex);
    int status = STALE;
    if (valid(self, ticket) && self->active) {
        *kind = pthread_equal(self->registrar, pthread_self()) ? 1 : 2;
        status = OK;
    }
    pthread_mutex_unlock(&self->mutex);
    return status;
}

static int reserve(session *self, uint64_t ticket)
{
    if (!valid(self, ticket))
        return STALE;
    if (self->active)
        return BUSY;
    self->active = true;
    return OK;
}

int fixture_inline(session *self, uint64_t ticket, int payload, int *result)
{
    pthread_mutex_lock(&self->mutex);
    int status = reserve(self, ticket);
    pthread_mutex_unlock(&self->mutex);
    if (status)
        return status;
    *result = self->call(self, ticket, payload, self->context);
    pthread_mutex_lock(&self->mutex);
    self->active = false;
    pthread_mutex_unlock(&self->mutex);
    return OK;
}

static void *run_worker(void *data)
{
    session *self = data;
    pthread_mutex_lock(&self->mutex);
    self->started = true;
    pthread_cond_broadcast(&self->signal);
    while (!self->released)
        pthread_cond_wait(&self->signal, &self->mutex);
    pthread_mutex_unlock(&self->mutex);
    self->result = self->call(self, self->generation, self->payload, self->context);
    return NULL;
}

int fixture_start(session *self, uint64_t ticket, int payload)
{
    pthread_mutex_lock(&self->mutex);
    int status = reserve(self, ticket);
    if (!status) {
        self->asynchronous = true;
        self->started = self->released = self->joining = false;
        self->payload = payload;
        if (pthread_create(&self->worker, NULL, run_worker, self)) {
            self->active = self->asynchronous = false;
            status = SYSTEM_ERROR;
        } else {
            while (!self->started)
                pthread_cond_wait(&self->signal, &self->mutex);
        }
    }
    pthread_mutex_unlock(&self->mutex);
    return status;
}

int fixture_finish(session *self, uint64_t ticket, int *result)
{
    pthread_mutex_lock(&self->mutex);
    if (!valid(self, ticket)) {
        pthread_mutex_unlock(&self->mutex);
        return STALE;
    }
    if (!self->asynchronous || self->joining || pthread_equal(self->worker, pthread_self())) {
        pthread_mutex_unlock(&self->mutex);
        return BUSY;
    }
    self->released = self->joining = true;
    pthread_cond_broadcast(&self->signal);
    pthread_mutex_unlock(&self->mutex);

    int failure = pthread_join(self->worker, NULL);
    pthread_mutex_lock(&self->mutex);
    self->joining = false;
    if (!failure) {
        *result = self->result;
        self->active = self->asynchronous = false;
    }
    pthread_mutex_unlock(&self->mutex);
    return failure ? SYSTEM_ERROR : OK;
}
