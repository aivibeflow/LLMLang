#include <cstdio>
#include <vector>

struct Failure { unsigned stage; };

struct Context {
    unsigned cell;
    std::vector<unsigned> trace;
};

unsigned operand(Context &ctx, unsigned stage, unsigned behavior) {
    const unsigned before = ctx.cell;
    if (behavior == 1 || behavior == 2)
        ctx.cell ^= 1u;
    ctx.trace.push_back(4 * stage + 2 * before + ctx.cell);
    if (behavior >= 2)
        throw Failure{stage};
    return ctx.cell;
}

struct Callee {
    Context &ctx;
    unsigned operator()(unsigned left, unsigned right) const {
        operand(ctx, 3, 0);
        return 2 * left + right;
    }
};

Callee target(Context &ctx, unsigned behavior) {
    operand(ctx, 0, behavior);
    return {ctx};
}

int main() {
    unsigned initial, receiver, left, right;
    while (std::scanf("%u %u %u %u", &initial, &receiver, &left, &right) == 4) {
        Context ctx{initial, {}};
        try {
            const unsigned result = target(ctx, receiver)(
                operand(ctx, 1, left), operand(ctx, 2, right));
            std::printf("return %u", result);
        } catch (Failure error) {
            std::printf("error %u", error.stage);
        }
        std::printf(" %u", ctx.cell);
        for (unsigned event : ctx.trace)
            std::printf(" %u", event);
        std::putchar('\n');
    }
    return 0;
}
