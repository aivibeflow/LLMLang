#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

#define LIMIT 257

enum outcome { MISS, HIT, NONHALVING, STALLED };

struct result {
    enum outcome status;
    size_t probes;
    size_t tests;
    size_t last_size;
    size_t next_size;
};

static struct result search(const int *values, size_t size, int target, bool bad_update)
{
    size_t lower = 0;
    size_t upper = size;
    struct result result = {.status = MISS};
    while (lower < upper) {
        size_t interval = upper - lower;
        size_t middle = lower + interval / 2;
        int current = values[middle];
        result.last_size = interval;
        ++result.probes;
        ++result.tests;
        if (current == target) {
            result.status = HIT;
            result.next_size = 0;
            return result;
        }

        ++result.tests;
        if (current < target) {
            lower = bad_update ? middle : middle + 1;
        } else {
            upper = middle;
        }

        result.next_size = upper - lower;
        if (result.next_size > interval / 2) {
            result.status = result.next_size >= interval ? STALLED : NONHALVING;
            return result;
        }
    }
    return result;
}

static void output(const char *shape, size_t n, int target, bool bad_update, struct result row)
{
    printf("%s %zu %d %d %d %zu %zu %zu %zu\n", shape, n, target, (int)bad_update,
           (int)row.status, row.probes, row.tests, row.last_size, row.next_size);
}

int main(void)
{
    const size_t boundary_sizes[] = {127, 128, 129, 255, 256, 257};
    const size_t boundary_count = sizeof(boundary_sizes) / sizeof(boundary_sizes[0]);
    int values[LIMIT];
    for (size_t i = 0; i < 65 + boundary_count; ++i) {
        size_t size = i < 65 ? i : boundary_sizes[i - 65];
        for (int duplicated = 0; duplicated < 2; ++duplicated) {
            for (size_t index = 0; index < size; ++index) {
                size_t unique = duplicated != 0 ? index / 3 : index;
                values[index] = 2 * (int)unique;
            }
            const char *shape = duplicated != 0 ? "duplicates" : "distinct";
            for (int target = -1; target <= 2 * (int)size + 1; ++target) {
                for (int mutated = 0; mutated < 2; ++mutated) {
                    bool bad_update = mutated != 0;
                    output(shape, size, target, bad_update, search(values, size, target, bad_update));
                }
            }
        }
    }

    const int unsorted[] = {8, 2, 4, 6};
    output("unsorted", 4, 8, false, search(unsorted, 4, 8, false));
    return 0;
}
