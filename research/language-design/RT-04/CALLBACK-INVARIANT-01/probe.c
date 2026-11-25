#include <stdio.h>

struct bounds {
    int lower;
    int upper;
};

struct observation {
    struct bounds final;
    struct bounds callback;
    int status;
};

static struct bounds read_public(const struct bounds *receiver) {
    return *receiver;
}

static struct bounds callback(const struct bounds *receiver) {
    return read_public(receiver);
}

static struct observation update(struct bounds before, struct bounds after, int lower_first,
                                 int observe, int fail) {
    struct observation result = {.final = before, .callback = {-1, -1}};
    if (before.lower > before.upper || after.lower > after.upper) {
        result.status = 2;
        return result;
    }
    if (lower_first) {
        result.final.lower = after.lower;
    } else {
        result.final.upper = after.upper;
    }
    if (observe) {
        result.callback = callback(&result.final);
    }
    if (fail) {
        result.final = before;
        result.status = 1;
    } else if (lower_first) {
        result.final.upper = after.upper;
    } else {
        result.final.lower = after.lower;
    }
    return result;
}

int main(void) {
    struct bounds before, after;
    int lower_first, observe, fail;
    while (scanf("%d %d %d %d %d %d %d", &before.lower, &before.upper, &after.lower,
                 &after.upper, &lower_first, &observe, &fail) == 7) {
        struct observation seen = update(before, after, lower_first, observe, fail);
        printf("%d %d %d %d %d\n", seen.status, seen.final.lower, seen.final.upper,
               seen.callback.lower, seen.callback.upper);
    }
    return ferror(stdout) != 0;
}
