#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

#define LIMIT 257

struct counters {
    size_t output_writes;
    size_t copyback_writes;
    size_t comparisons;
};

static bool sort(int *array, int *temporary, size_t size, bool invalid_split,
                 struct counters *counts)
{
    if (size < 2) {
        return true;
    }
    size_t left_size = invalid_split ? 0 : size / 2;
    if (left_size == 0 || left_size >= size) {
        return false;
    }
    if (!sort(array, temporary, left_size, invalid_split, counts) ||
        !sort(array + left_size, temporary + left_size, size - left_size,
              invalid_split, counts)) {
        return false;
    }

    size_t left = 0;
    size_t right = left_size;
    for (size_t output = 0; output < size; ++output) {
        if (left == left_size) {
            temporary[output] = array[right++];
        } else if (right == size) {
            temporary[output] = array[left++];
        } else {
            ++counts->comparisons;
            if (array[left] <= array[right]) {
                temporary[output] = array[left++];
            } else {
                temporary[output] = array[right++];
            }
        }
        ++counts->output_writes;
    }
    for (size_t i = 0; i < size; ++i) {
        array[i] = temporary[i];
        ++counts->copyback_writes;
    }
    return true;
}

int main(void)
{
    size_t index;
    size_t size;
    int invalid;
    int array[LIMIT];
    int temporary[LIMIT];
    int fields;

    while ((fields = scanf("%zu %zu %d", &index, &size, &invalid)) == 3) {
        if (size > LIMIT || (invalid != 0 && invalid != 1)) {
            return 1;
        }
        for (size_t i = 0; i < size; ++i) {
            if (scanf("%d", &array[i]) != 1) {
                return 2;
            }
        }
        struct counters counts = {0};
        bool ok = sort(array, temporary, size, invalid != 0, &counts);
        printf("%zu %d %zu %zu %zu", index, (int)ok, counts.output_writes,
               counts.copyback_writes, counts.comparisons);
        for (size_t i = 0; i < size; ++i) {
            printf(" %d", array[i]);
        }
        putchar('\n');
    }
    return fields == EOF ? 0 : 3;
}
