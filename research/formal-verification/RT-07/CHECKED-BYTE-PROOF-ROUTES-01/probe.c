#include <stdio.h>

struct observed {
    int overflow;
    int cell;
    char trace[3];
    int events;
};

static void record(struct observed *observed, char event) {
    observed->trace[observed->events++] = event;
}

static void store(struct observed *observed, int value) {
    observed->cell = value;
    record(observed, 'W');
}

static struct observed checked_add(int left, int right, int variant) {
    int sum = left + right;
    int upper = variant == 1 ? 128 : 127;
    struct observed result = {.cell = -999};
    result.overflow = sum < -128 || sum > upper;
    if (result.overflow) {
        if (variant == 2) {
            store(&result, result.cell);
        } else if (variant == 5) {
            store(&result, sum);
        }
        return result;
    }
    if (variant == 4) {
        record(&result, 'C');
    }
    store(&result, sum);
    if (variant != 3 && variant != 4) {
        record(&result, 'C');
    }
    return result;
}

int main(void) {
    for (int variant = 0; variant < 6; variant++) {
        for (int left = -128; left <= 127; left++) {
            for (int right = -128; right <= 127; right++) {
                struct observed value = checked_add(left, right, variant);
                printf("%d %d %s\n", value.overflow, value.cell, value.events ? value.trace : "-");
            }
        }
    }
    return ferror(stdout) != 0;
}
