#include "mock_api.h"
#include <assert.h>
#include <stdio.h>

HANDLE open_reader(LPCWSTR path, DWORD *error);
BOOL close_owned(HANDLE handle, DWORD *error);

static DWORD last_error;
static unsigned captures;
static BOOL open_succeeds, close_succeeds;
static int token;

HANDLE CreateFileW(LPCWSTR path, DWORD access, DWORD sharing, void *security,
                   DWORD disposition, DWORD flags, HANDLE template_file) {
    assert(*path == 70 && access == GENERIC_READ && sharing == FILE_SHARE_READ);
    assert(!security && disposition == OPEN_EXISTING && !flags && !template_file);
    if (open_succeeds)
        return &token;
    last_error = 5;
    return INVALID_HANDLE_VALUE;
}

DWORD GetLastError(void) {
    captures++;
    return last_error;
}

BOOL CloseHandle(HANDLE handle) {
    assert(handle == &token);
    if (!close_succeeds)
        last_error = 6;
    return close_succeeds;
}

int main(void) {
    const uint16_t path[] = {70, 0};
    for (int prior = 0; prior < 2; ++prior) {
        for (open_succeeds = 0; open_succeeds < 2; ++open_succeeds) {
            for (close_succeeds = 0; close_succeeds < 2; ++close_succeeds) {
                last_error = prior ? 87 : 0;
                captures = 0;
                DWORD error;
                HANDLE handle = open_reader(path, &error);
                printf("open:%d:%u:%u", handle != INVALID_HANDLE_VALUE, error, captures);
                if (handle != INVALID_HANDLE_VALUE) {
                    BOOL result = close_owned(handle, &error);
                    printf(":close:%d:%u:%u", result, error, captures);
                }
                putchar('\n');
            }
        }
    }
}
