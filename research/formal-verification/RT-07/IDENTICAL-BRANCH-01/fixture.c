#include <stdio.h>

enum result { FALSE_RESULT, TRUE_RESULT, ERROR, DIVERGE, CANCEL, RETURN };
enum variant { ORIGINAL, SEQUENCE, ERASE, DUPLICATE };

struct context {
    unsigned cell;
    unsigned size;
    unsigned trace[3];
};

static enum result guard(struct context *ctx, unsigned update, unsigned visible,
                         enum result status) {
    if (update == 4)
        ctx->cell = (ctx->cell + 1) % 3u;
    else if (update != 0)
        ctx->cell = update - 1;
    if (visible)
        ctx->trace[ctx->size++] = ctx->cell;
    return status;
}

static enum result body(struct context *ctx, unsigned mode, unsigned *value) {
    switch (mode) {
    case 0: *value = ctx->cell; return RETURN;
    case 1: *value = 0; return RETURN;
    case 2:
        ctx->cell = 0;
        ctx->trace[ctx->size++] = 3u;
        *value = 0;
        return RETURN;
    case 3: return ERROR;
    case 4: return DIVERGE;
    default: return CANCEL;
    }
}

static enum result run(enum variant variant, struct context *ctx, unsigned update,
                       unsigned visible, enum result status, unsigned mode, unsigned *value) {
    if (variant == ERASE)
        return body(ctx, mode, value);
    enum result flag = guard(ctx, update, visible, status);
    if (flag >= ERROR)
        return flag;
    if (variant == ORIGINAL) {
        if (flag == TRUE_RESULT)
            return body(ctx, mode, value);
        else
            return body(ctx, mode, value);
    }
    if (variant == DUPLICATE) {
        flag = guard(ctx, update, visible, status);
        if (flag >= ERROR)
            return flag;
    }
    return body(ctx, mode, value);
}

int main(void) {
    unsigned initial, update, visible, status, mode;
    while (scanf("%u %u %u %u %u", &initial, &update, &visible, &status, &mode) == 5) {
        for (enum variant variant = ORIGINAL; variant <= DUPLICATE; ++variant) {
            struct context ctx = {.cell = initial};
            unsigned value = 0;
            enum result outcome = run(variant, &ctx, update, visible, (enum result)status,
                                      mode, &value);
            printf("%u %u %u", outcome, value, ctx.cell);
            for (unsigned i = 0; i < ctx.size; ++i)
                printf(" %u", ctx.trace[i]);
            putchar('\n');
        }
    }
    return ferror(stdin) || ferror(stdout);
}
