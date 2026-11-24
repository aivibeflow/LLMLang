/* Test-only cut immediately after a successful reference-storage rename. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <signal.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int (*rename_fn)(const char *, const char *);

int rename(const char *old_path, const char *new_path)
{
    rename_fn real_rename = (rename_fn)dlsym(RTLD_NEXT, "rename");
    if (real_rename == NULL)
        _exit(126);
    int status = real_rename(old_path, new_path);
    const char *match = getenv("LLMLANG_PAUSE_RENAME_SUFFIX");
    if (status == 0 && match != NULL) {
        size_t end = strlen(new_path);
        size_t suffix = strlen(match);
        if (end >= suffix && strcmp(new_path + end - suffix, match) == 0) {
            unsetenv("LLMLANG_PAUSE_RENAME_SUFFIX");
            raise(SIGSTOP);
        }
    }
    return status;
}
