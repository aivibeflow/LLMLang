#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef OFFSET
#error "provider offset must be explicit"
#endif

int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    char *end;
    errno = 0;
    long value = strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end || value < -4 || value > 4)
        return 3;
    printf("%ld\n", value + OFFSET);
    return 0;
}
