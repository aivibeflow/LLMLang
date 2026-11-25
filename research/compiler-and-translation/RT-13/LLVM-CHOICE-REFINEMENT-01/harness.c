#include <stdio.h>

int stable(int bit, int unknown);
int independent(int bit, int unknown);
int pin(int bit, int unknown);

int main(void) {
    for (int bit = 0; bit < 2; ++bit) {
        for (int unknown = 0; unknown < 2; ++unknown) {
            int fixed = stable(bit, unknown);
            int split = independent(bit, unknown);
            int chosen = pin(bit, unknown);
            printf("%d %d %d %d %d\n", bit, unknown, fixed, split, chosen);
        }
    }
    return ferror(stdout);
}
