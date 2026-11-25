#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>

extern uint32_t helper_increment(uint32_t operand);

uint32_t invoke(uint32_t operand)
{
    return helper_increment(operand);
}

const char *loaded_helper(void)
{
    Dl_info info;
    if (dladdr((void *)helper_increment, &info) == 0)
        return 0;
    return info.dli_fname;
}
