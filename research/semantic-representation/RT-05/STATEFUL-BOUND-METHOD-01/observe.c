#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

typedef struct {
    int64_t value;
} Cell;

typedef struct {
    int64_t before;
    int64_t after;
} Trace;

typedef Trace (*Method)(Cell *, int64_t, int, int64_t);

typedef struct {
    Method method;
    Cell *cell;
    int64_t bias;
} Bound;

static Trace step(Cell *cell, int64_t bias, int kind, int64_t input) {
    Trace trace = { .before = cell->value };
    if (kind == 1) {
        cell->value += bias + input;
    } else if (kind == 2) {
        cell->value = input;
    } else {
        assert(kind == 0);
    }
    trace.after = cell->value;
    return trace;
}

int main(void) {
    int shared;
    int count;
    int64_t first;
    int64_t second;
    int64_t bias_left;
    int64_t bias_right;
    while (scanf("%d %" SCNd64 " %" SCNd64 " %" SCNd64 " %" SCNd64 " %d",
                 &shared, &first, &second, &bias_left, &bias_right, &count) == 6) {
        assert(shared == 0 || (shared == 1 && first == second));
        Cell cells[] = {{first}, {second}};
        Bound receivers[] = {{step, &cells[0], bias_left}, {step, &cells[!shared], bias_right}};
        printf("%d %d", receivers[0].method == receivers[1].method, receivers[0].cell == receivers[1].cell);
        for (int i = 0; i < count; i++) {
            int kind;
            int slot;
            int64_t input;
            const int parsed = scanf("%d %d %" SCNd64, &kind, &slot, &input);
            assert(parsed == 3 && slot >= 0 && slot <= 1);
            const Bound bound = receivers[slot];
            const Trace event = bound.method(bound.cell, bound.bias, kind, input);
            printf(" %" PRId64 " %" PRId64, event.before, event.after);
        }
        putchar('\n');
    }
    return 0;
}
