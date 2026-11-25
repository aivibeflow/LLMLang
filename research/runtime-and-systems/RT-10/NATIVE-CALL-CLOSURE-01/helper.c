#include <stdint.h>

uint32_t helper_increment(uint32_t operand)
{
    return operand + STEP;
}

uint32_t helper_build_revision(void)
{
    return REVISION;
}
