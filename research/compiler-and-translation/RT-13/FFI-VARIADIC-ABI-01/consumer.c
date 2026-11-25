#include "fixture.h"

extern const word input_count;
extern const input_record input_vectors[];

static output_record output[32];

_Noreturn void fixture_start(void)
{
    if (input_count > sizeof(output) / sizeof(*output))
        fixture_exit(2);
    for (word index = 0; index < input_count; index++) {
        const input_record *input = &input_vectors[index];
#if defined(ASSEMBLY_CONSUMER)
        manual_call(&output[index], input);
#else
        signed char small = (signed char)input->small;
#if defined(WRONG_SOURCE_CARRIER)
        double narrow = input->magnitude;
#else
        float narrow = (float)input->magnitude;
#endif
        fixture_var(&output[index], (unsigned int)input->marker, small, narrow, input->tag);
#endif
    }
    word size = input_count * sizeof(*output);
    fixture_exit(fixture_write(output, size) == (long)size ? 0 : 3);
}
