#include <stdio.h>

struct observation {
    int cell;
    int failed;
    int trace[6];
    int used;
};

static int operand(struct observation *state, int action)
{
    switch (action) {
    case 0:
        return 0;
    case 1:
        return 1;
    case 2:
        state->trace[state->used++] = 100 + state->cell;
        return state->cell != 0;
    case 3:
        state->cell = 1;
        state->trace[state->used++] = 201;
        return 1;
    case 4: {
        int before = state->cell;
        state->cell = (before + 1) % 3;
        state->trace[state->used++] = 200 + state->cell;
        state->cell = before;
        state->trace[state->used++] = 200 + before;
        return 1;
    }
    case 5:
        state->failed = 1;
        state->trace[state->used++] = 300;
        return 0;
    case 6:
        state->cell = 2;
        state->trace[state->used++] = 202;
        state->failed = 1;
        state->trace[state->used++] = 300;
        return 0;
    default:
        return -1;
    }
}

static int evaluate(struct observation *state, int disjunction, int eager, int left, int right)
{
    int lhs = operand(state, left);
    if (state->failed)
        return -1;
    int result;
    if (eager) {
        int rhs = operand(state, right);
        result = disjunction ? lhs || rhs : lhs && rhs;
    } else if (disjunction) {
        result = lhs || operand(state, right);
    } else {
        result = lhs && operand(state, right);
    }
    return state->failed ? -1 : result;
}

int main(void)
{
    int cell, disjunction, eager, left, right;
    while (scanf("%d %d %d %d %d", &cell, &disjunction, &eager, &left, &right) == 5) {
        if (cell < 0 || cell > 2 || disjunction < 0 || disjunction > 1 ||
            eager < 0 || eager > 1 || left < 0 || left > 6 || right < 0 || right > 6)
            return 2;
        struct observation state = {.cell = cell};
        int result = evaluate(&state, disjunction, eager, left, right);
        printf("%d %d", result, state.cell);
        for (int i = 0; i < state.used; ++i)
            printf(" %d", state.trace[i]);
        putchar('\n');
    }
    return feof(stdin) ? 0 : 3;
}
