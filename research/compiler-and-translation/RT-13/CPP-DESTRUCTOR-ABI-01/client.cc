#include "record.h"

#include <stddef.h>
#include <stdio.h>

int main()
{
    static_assert(__is_standard_layout(Record));
    printf("layout=%zu,%zu,%zu,%zu\n", sizeof(Record), alignof(Record),
                offsetof(Record, first), offsetof(Record, second));
    for (uint32_t input = 0; input < 16; ++input) {
        const Record value = make_record(input);
        printf("%u,%u\n", value.first, value.second);
    }
    printf("retired=%u\n", retirement_count());
}
