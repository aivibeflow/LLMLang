/* Independent C execution of the checked fixture configuration. */
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fixture.h"

enum { OK, RETAINED, CONSUMED, INDETERMINATE };
enum { ABSENT, OWNED, USABLE, RECONCILE };

struct outcome {
    uint32_t disposition;
    uint32_t usable_token;
};

void rt_begin(uint32_t physical);
uint32_t rt_acquire(uint32_t slot, uint32_t source, uint32_t destination);
struct outcome rt_release(uint32_t token, uint32_t disposition);
uint64_t rt_finish(void);

struct trace {
    char events[768];
    char errors[256];
};

static const char *const dispositions[] = {
    "ok", "retained_error", "consumed_error", "indeterminate",
};

static void append(char *to, size_t size, const char *first, const char *second, const char *third) {
    size_t used = strlen(to);
    int result = snprintf(to + used, size - used, "%s%s,%s%s%s",
                          used ? ";" : "", first, second, third ? "," : "", third ? third : "");
    assert(result >= 0 && (size_t)result < size - used);
}

static void event(struct trace *trace, const char *kind, const char *role, const char *label) {
    append(trace->events, sizeof(trace->events), kind, role, label);
}

static uint32_t disposition(const char *text) {
    for (uint32_t i = 0; i < sizeof(dispositions) / sizeof(dispositions[0]); ++i) {
        if (strcmp(text, dispositions[i]) == 0)
            return i;
    }
    assert(!"unknown disposition");
    return 0;
}

static uint32_t release(struct trace *trace, const char *slot, uint32_t token, uint32_t request) {
    struct outcome result = rt_release(token, request);
    assert(result.disposition <= INDETERMINATE);
    assert(result.usable_token == (result.disposition == RETAINED ? token : 0));
    const char *label = dispositions[result.disposition];
    event(trace, "release", slot, label);
    if (result.disposition != OK)
        append(trace->errors, sizeof(trace->errors), slot, label, NULL);
    return result.disposition;
}

static unsigned state_after(uint32_t result) {
    switch (result) {
    case RETAINED: return USABLE;
    case INDETERMINATE: return RECONCILE;
    default: return ABSENT;
    }
}

static void obligations(char *buffer, size_t size, unsigned handle, unsigned local) {
    const char *labels[] = {NULL, "owned", "retained", "reconcile"};
    if (handle != ABSENT)
        append(buffer, size, "handle", labels[handle], NULL);
    if (local != ABSENT)
        append(buffer, size, "local", labels[local], NULL);
}

static void execute(char **fields) {
    struct trace trace = {0};
    uint32_t from = (uint32_t)fields[FIRST_SOURCE][0];
    uint32_t to = (uint32_t)fields[FIRST_DESTINATION][0];
    uint32_t later_from = (uint32_t)fields[SECOND_SOURCE][0];
    uint32_t later_to = (uint32_t)fields[SECOND_DESTINATION][0];
    unsigned wants = strcmp(fields[4], "1") == 0;
    rt_begin((uint32_t)(strcmp(fields[8], "1") == 0));

    uint32_t handle_token = rt_acquire(0, from, to);
    if (!handle_token) {
        event(&trace, "check", "handle", "refused");
        printf("||%s|0||not_reached|||%010" PRIx64 "\n", trace.events, rt_finish());
        return;
    }
    event(&trace, "check", "handle", "ok");
    event(&trace, "acquire", "handle", "ok");
    uint32_t local_token = rt_acquire(1, 0, 0);
    assert(local_token);
    event(&trace, "acquire", "local", "ok");

    int early = EARLY_TRANSFER && wants;
    if (early)
        event(&trace, "transfer", "handle", "ok");
    uint32_t local_result = release(&trace, "local", local_token, disposition(fields[5]));
    unsigned local = state_after(local_result);
    unsigned handle = OWNED;
    if (!early && wants && local_result == OK) {
        event(&trace, "transfer", "handle", "ok");
    } else if (!early) {
        handle = state_after(release(&trace, "handle", handle_token, disposition(fields[6])));
    }

    int no_errors = trace.errors[0] == '\0';
    const char *tag;
    if (!wants)
        tag = no_errors ? "Err" : "ErrWithCleanupErrors";
    else if (no_errors)
        tag = "OkWithValue";
    else
        tag = early ? "CleanupFailedWithValue" : "StagedCleanupFailedWithoutValue";

    char returned[64] = {0}, forwarded[64] = {0}, reservations[64] = {0};
    obligations(returned, sizeof(returned), handle, local);
    int successful = strcmp(tag, "OkWithValue") == 0;
    if (successful) {
        event(&trace, "match", "success", "preserve");
    } else if (handle == OWNED || handle == USABLE) {
        event(&trace, "match", "error_with_handle", RECOVER_HANDLE ? "release_first" : "preserve");
        if (RECOVER_HANDLE)
            handle = state_after(release(&trace, "caller_handle", handle_token, disposition(fields[7])));
    } else if (handle == RECONCILE) {
        event(&trace, "match", "error_reconcile", "preserve");
    } else {
        event(&trace, "match", "error_without_handle", "preserve");
    }
    obligations(forwarded, sizeof(forwarded), handle, local);
    char first_source[] = {(char)from, 0}, first_destination[] = {(char)to, 0};
    char second_source[] = {(char)later_from, 0}, second_destination[] = {(char)later_to, 0};
    if (handle != ABSENT)
        append(reservations, sizeof(reservations), "handle", first_source, first_destination);
    int start = rt_acquire(2, later_from, later_to) != 0;
    event(&trace, "check", "second", start ? "ok" : "refused");
    if (start) {
        event(&trace, "acquire", "second", "ok");
        append(reservations, sizeof(reservations), "second", second_source, second_destination);
    }
    printf("%s|%s|%s|%u|%s|%s|%s|%s|%010" PRIx64 "\n",
           tag, returned, trace.events, (unsigned)!wants, trace.errors,
           start ? "started" : "refused", reservations, forwarded, rt_finish());
}

int main(void) {
    char line[256];
    while (fgets(line, sizeof(line), stdin)) {
        char *fields[9];
        size_t count = 0;
        for (char *item = strtok(line, ",;\n"); item; item = strtok(NULL, ",;\n")) {
            assert(count < sizeof(fields) / sizeof(fields[0]));
            fields[count++] = item;
        }
        assert(count == sizeof(fields) / sizeof(fields[0]));
        execute(fields);
    }
    return ferror(stdin);
}
