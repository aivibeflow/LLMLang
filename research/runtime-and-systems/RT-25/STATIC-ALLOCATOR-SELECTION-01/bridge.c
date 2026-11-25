#define _GNU_SOURCE
#include <dlfcn.h>
#include <mimalloc.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

void *libc_allocate(size_t size, size_t align) {
    void *address = NULL;
    if (posix_memalign(&address, align, size) != 0) {
        return NULL;
    }
    return address;
}

void libc_dispose(void *address) {
    free(address);
}

int public_malloc_from_executable(void) {
    Dl_info info, bridge;
    if (!dladdr((void *)(uintptr_t)&malloc, &info) ||
        !dladdr((void *)(uintptr_t)&public_malloc_from_executable, &bridge)) {
        return -1;
    }
    if (info.dli_fbase == bridge.dli_fbase) {
        return 1;
    }
    const char *stem = info.dli_fname;
    for (const char *position = stem; *position; ++position) {
        if (*position == '/') {
            stem = position + 1;
        }
    }
    return strncmp(stem, "libc.so", 7) == 0 ? 0 : -1;
}

int mimalloc_region(const void *address) {
    return mi_is_in_heap_region(address);
}

int heap_owned_by(mi_heap_t *heap, const void *address) {
#if MI_MALLOC_VERSION >= 30000
    return mi_heap_contains(heap, address);
#else
    return mi_heap_check_owned(heap, address);
#endif
}

int try_heap_release(mi_heap_t *heap, void *address) {
    if (!heap_owned_by(heap, address)) {
        return 0;
    }
    mi_free(address);
    return 1;
}
