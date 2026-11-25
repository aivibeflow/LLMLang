#ifndef CALLBACK_PROVIDER_H
#define CALLBACK_PROVIDER_H

#include <stdint.h>

typedef int32_t (*callback_fn)(void *, uint32_t, int32_t);
typedef int32_t (*peek_fn)(uint32_t);

struct context {
    peek_fn peek;
    int32_t fail;
};

uint32_t open_session(void);
int32_t close_session(uint32_t token);
int32_t start_callback(uint32_t token, callback_fn callback, void *context, int32_t value);
int32_t finish_callback(uint32_t token, int32_t cancel, int32_t *result);
int32_t peek_worker(uint32_t token);
uint32_t completed_count(void);

#endif
