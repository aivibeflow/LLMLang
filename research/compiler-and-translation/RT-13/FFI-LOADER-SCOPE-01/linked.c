#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

int apply(int input);
void *fixture_provider_address(void);

int main(int argc, char **argv)
{
    Dl_info info;
    if (argc != 2 || !dladdr(fixture_provider_address(), &info))
        return 1;
    printf("%d\t%s\n", apply(atoi(argv[1])), info.dli_fname);
    return 0;
}
