#define _POSIX_C_SOURCE 200809L
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include "generated.h"

typedef int (*operation)(int);

static int alpha(int x) { return 1000 + x; }
static int beta(int x) { return 2000 + x; }
static operation pointer_table[] = {alpha, beta, alpha, beta};

static void record(const char *site, int key, int result) {
    printf("%s,%d,%d\n", site, key, result);
}

int main(int argc, char **argv) {
    if (argc != 6)
        return 1;
    void *provider = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (provider == NULL)
        return 2;
    for (int key = 0; key < 4; key++) {
        record("direct-alpha", key, alpha(key));
        record("direct-beta", key, beta(key));
        record("indirect", key, pointer_table[key](key));
        record("generated", key, generated_alpha[key] ? alpha(key) : beta(key));
        const char *symbol = argv[key + 2];
        if (strcmp(symbol, "none") == 0) {
            record("dynamic-external", key, 0);
        } else {
            operation external = (operation)dlsym(provider, symbol);
            if (external == NULL)
                return 3;
            record("dynamic-external", key, external(key));
        }
    }
    return dlclose(provider) == 0 ? 0 : 4;
}
