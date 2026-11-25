#include <stdio.h>
#include <stdlib.h>

int apply_v1(int input);
int apply_v2(int input);

int main(int argc, char **argv)
{
    if (argc != 2)
        return 1;
    int input = atoi(argv[1]);
    printf("%d\t%d\n", apply_v1(input), apply_v2(input));
    return 0;
}
