#define _GNU_SOURCE
#include "observer.h"

#include <dlfcn.h>
#include <stdio.h>
#include <unwind.h>

/* GNU libgcc interface used only on the pinned Linux ELF profile. */
struct dwarf_eh_bases {
    void *tbase;
    void *dbase;
    void *func;
};
extern const void *_Unwind_Find_FDE(const void *, struct dwarf_eh_bases *);

static uintptr_t code_start;
static uintptr_t direct_pc;
static uintptr_t unwind_pc;
static size_t code_size;
static unsigned callback_count;
static unsigned resumed_to_host;

int callback_fde_registered(void) {
    struct dwarf_eh_bases bases;
    return direct_pc && _Unwind_Find_FDE((const void *)(direct_pc - 1), &bases);
}

static _Unwind_Reason_Code collect(struct _Unwind_Context *frame, void *unused) {
    (void)unused;
    uintptr_t ip = _Unwind_GetIP(frame);
    if (ip > code_start && ip - code_start <= code_size)
        unwind_pc = ip;
    Dl_info symbol;
    if (ip && dladdr((const void *)(ip - 1), &symbol) &&
        symbol.dli_saddr == (const void *)host_call)
        resumed_to_host = 1;
    return _URC_NO_REASON;
}

__attribute__((noinline))
static uint32_t callback(uint32_t input) {
    ++callback_count;
    direct_pc = (uintptr_t)__builtin_extract_return_addr(__builtin_return_address(0));
    _Unwind_Backtrace(collect, NULL);
    return input * 2;
}

__attribute__((noinline))
int host_call(jit_entry entry, size_t size) {
    code_start = (uintptr_t)entry;
    code_size = size;
    direct_pc = 0;
    unwind_pc = 0;
    callback_count = 0;
    resumed_to_host = 0;

    uint32_t result = entry(17, callback);
    if (callback_count != 1 || result != 35 ||
        direct_pc <= code_start || direct_pc - code_start > code_size)
        return 1;
    Dl_info symbol;
    int native_symbol = dladdr((const void *)(direct_pc - 1), &symbol) &&
        symbol.dli_saddr == (const void *)entry;
    int registered = callback_fde_registered();
    printf("host %u %u %d %u %d %d %zu\n", result, callback_count,
           direct_pc == unwind_pc, resumed_to_host, registered, native_symbol,
           (size_t)(direct_pc - 1 - code_start));
    return 0;
}
