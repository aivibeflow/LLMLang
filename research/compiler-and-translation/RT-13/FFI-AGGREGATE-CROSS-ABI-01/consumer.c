#include "fixture.h"

struct in_case {
    mixed_value mixed;
    float_pair floats;
    word left;
    word right;
};

struct out_case {
    mixed_value mixed;
    float_pair floats;
    wide_value wide;
};

_Static_assert(sizeof(struct in_case) == 48, "binary input record");
_Static_assert(sizeof(struct out_case) == 56, "binary output record");

extern const word input_count;
extern const struct in_case input_vectors[];

static struct out_case output[32];

_Noreturn void _start(void)
{
    if (input_count > sizeof(output) / sizeof(*output))
        fixture_exit(2);
    for (word index = 0; index < input_count; index++) {
        const struct in_case *input = &input_vectors[index];
        output[index] = (struct out_case){
            fixture_mixed(input->mixed),
            fixture_floats(input->floats),
            fixture_wide(input->left, input->right)
        };
    }
    word size = input_count * sizeof(*output);
    fixture_exit(fixture_write(output, size) == (long)size ? 0 : 3);
}
