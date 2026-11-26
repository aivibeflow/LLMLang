#define _DEFAULT_SOURCE
#include <sys/reboot.h>
#include <time.h>

static int drain_before_reboot(int command)
{
    // Bochs powers off immediately while its emulated UART can still be transmitting.
    const struct timespec drain = { .tv_sec = 0, .tv_nsec = 100000000 };
    nanosleep(&drain, NULL);
    return reboot(command);
}

#define reboot drain_before_reboot
#include "init.c"
