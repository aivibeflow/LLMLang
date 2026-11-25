#ifndef FIXTURE_H
#define FIXTURE_H
#include <stdint.h>

typedef struct session session;
typedef int (*callback)(session *, uint64_t, int, void *);

enum outcome { OK, STALE, BUSY, INVALID, SYSTEM_ERROR };
enum call_result { CALLBACK_ERROR = -77, CALLBACK_PROTOCOL_ERROR = -88 };

session *fixture_create(void);
int fixture_destroy(session *self);
int fixture_register(session *self, callback call, void *context, uint64_t *ticket);
int fixture_retire(session *self, uint64_t ticket);
int fixture_thread(session *self, uint64_t ticket, int *kind);
int fixture_inline(session *self, uint64_t ticket, int payload, int *result);
int fixture_start(session *self, uint64_t ticket, int payload);
int fixture_finish(session *self, uint64_t ticket, int *result);
int fixture_drive(callback call, void *context, void *peer, int payload, int profile);

#endif
