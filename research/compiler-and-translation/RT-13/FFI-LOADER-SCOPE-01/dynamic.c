#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*operation)(int);
typedef void *(*provider_address)(void);

static void fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
    exit(1);
}

static void *load(bool separate, bool keep, const char *path)
{
    const int flags = RTLD_LOCAL | RTLD_NOW | (keep ? RTLD_NODELETE : 0);
    void *handle = separate ? dlmopen(LM_ID_NEWLM, path, flags) : dlopen(path, flags);
    if (!handle)
        fail(dlerror());
    return handle;
}

static const char *leaf_path(void *handle)
{
    provider_address address = (provider_address)dlsym(handle, "fixture_provider_address");
    Dl_info info;
    if (!address || !dladdr(address(), &info) || !info.dli_fname)
        fail("Cannot identify resolved leaf address");
    return info.dli_fname;
}

static void inspect(const char *phase, void *handle, int input)
{
    Lmid_t ns;
    if (dlinfo(handle, RTLD_DI_LMID, &ns))
        fail(dlerror());
    operation current = (operation)dlsym(handle, "apply");
    operation old = (operation)dlvsym(handle, "apply", "FIXTURE_1.0");
    operation versioned = (operation)dlvsym(handle, "apply", "FIXTURE_2.0");
    dlerror();
    void *missing = dlvsym(handle, "apply", "FIXTURE_3.0");
    bool missing_reported = dlerror() != NULL;
    if (!current || !old || !versioned || missing || !missing_reported)
        fail("Unexpected versioned lookup");
    printf("call\t%s\t%ld\t%d\t%d\t%d\t%s\n", phase, (long)ns,
           current(input), old(input), versioned(input), leaf_path(handle));
}

static bool mapped(const char *path)
{
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps)
        fail("Cannot read process mappings");
    char *line = NULL;
    size_t size = 0;
    bool found = false;
    while (getline(&line, &size, maps) >= 0) {
        const char *entry = strchr(line, '/');
        if (entry && strlen(entry) == strlen(path) + 1 &&
            memcmp(entry, path, strlen(path)) == 0) {
            found = true;
            break;
        }
    }
    free(line);
    fclose(maps);
    return found;
}

static void snapshot(const char *phase, char **paths)
{
    printf("maps\t%s", phase);
    for (int index = 0; index < 4; index++)
        printf("\t%d", mapped(paths[index]));
    puts("");
}

int main(int argc, char **argv)
{
    if (argc != 7)
        fail("usage: dynamic base|base-keep|separate ORDERED_PLUGIN_1 PLUGIN_2 LEAF_1 LEAF_2 input");

    const bool separate = strcmp(argv[1], "separate") == 0;
    const bool keep = strcmp(argv[1], "base-keep") == 0;
    if (!separate && !keep && strcmp(argv[1], "base") != 0)
        fail("unknown loader path");
    int input = atoi(argv[6]);
    char **paths = argv + 2;

    void *first = load(separate, keep, paths[0]);
    inspect("first", first, input);
    void *second = load(separate, false, paths[1]);
    inspect("second", second, input);
    snapshot("both", paths);
    if (dlclose(first))
        fail(dlerror());
    snapshot("close-first", paths);
    inspect("survivor", second, input);
    if (dlclose(second))
        fail(dlerror());
    snapshot("close-both", paths);
    return 0;
}
