#include "entry.h"

#include <dlfcn.h>
#include <inttypes.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    if (argc != 2) {
        return 2;
    }
    void *provider = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (provider == NULL) {
        return 3;
    }
    step_fn step = (step_fn)dlsym(provider, "step");
    if (step == NULL) {
        dlclose(provider);
        return 4;
    }

    struct record input;
    uint64_t salt;
    int fields;
    while ((fields = scanf("%" SCNu64 " %" SCNu64 " %" SCNu64,
                           &input.first, &input.second, &salt)) == 3) {
        const struct record result = step(input, salt);
        printf("%" PRIu64 " %" PRIu64 "\n", result.first, result.second);
    }
    return dlclose(provider) == 0 && fields == EOF && feof(stdin) ? 0 : 5;
}
