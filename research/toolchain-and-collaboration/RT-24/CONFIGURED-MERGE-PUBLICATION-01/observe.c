#include <stdio.h>

int site(int value);

int main(void) {
    int value;
    while (scanf("%d", &value) == 1) {
        printf("%d\n", site(value));
    }
    return 0;
}
