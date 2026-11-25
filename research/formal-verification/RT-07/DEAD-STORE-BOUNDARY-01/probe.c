#include <stdio.h>

static void evaluate(int visible, int route, int removed, int target, int other, int first, int last)
{
    int trace[2];
    int writes = 0;
    if (!removed) {
        target = first;
        if (visible)
            trace[writes++] = target;
    }

    const int *reader = route == 1 ? &target : &other;
    int intermediate = route == 0 ? -1 : *reader;
    target = last;
    if (visible)
        trace[writes++] = target;

    printf("%d %d %d", target, other, intermediate);
    for (int i = 0; i < writes; ++i)
        printf(" %d", trace[i]);
    putchar('\n');
}

int main(void)
{
    int visible, route, removed, target, other, first, last;
    while (scanf("%d %d %d %d %d %d %d", &visible, &route, &removed, &target, &other, &first, &last) == 7) {
        if (visible < 0 || visible > 1 || route < 0 || route > 2 || removed < 0 || removed > 1)
            return 2;
        evaluate(visible, route, removed, target, other, first, last);
    }
    return feof(stdin) ? 0 : 3;
}
