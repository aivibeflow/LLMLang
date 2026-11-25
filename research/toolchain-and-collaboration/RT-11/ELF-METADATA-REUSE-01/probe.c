#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int emit_self_digest(void) {
    FILE *input = fopen("/proc/self/exe", "rb");
    if (input == NULL)
        return 2;
    uint64_t hash = UINT64_C(14695981039346656037);
    for (int byte; (byte = fgetc(input)) != EOF;) {
        hash ^= (unsigned char)byte;
        hash *= UINT64_C(1099511628211);
    }
    int failed = ferror(input);
    if (fclose(input) != 0 || failed)
        return 3;
    printf("%016" PRIx64 "\n", hash);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--self") == 0)
        return emit_self_digest();
    for (int n = -4; n <= 4; ++n)
        printf("%d\n", n + 2);
    return ferror(stdout);
}
