#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

struct tagged {
    uint32_t tag;
    uint32_t bits;
};

uint32_t niche_identity(uint32_t value);
uint32_t niche_is_present(uint32_t value);
uint64_t inspect_tagged(struct tagged value);
size_t tagged_size(void);
size_t tagged_alignment(void);

static void observe(uint32_t value)
{
    printf("niche:%" PRIu32 ":%" PRIu32 ":%" PRIu32 "\n",
           value, niche_identity(value), niche_is_present(value));
    uint32_t tags[] = {0, 1, 2, 255};
    for (size_t index = 0; index < sizeof(tags) / sizeof(tags[0]); ++index) {
        struct tagged encoded = {tags[index], value};
        printf("tagged:%" PRIu32 ":%" PRIu32 ":%" PRIu64 "\n",
               encoded.tag, encoded.bits, inspect_tagged(encoded));
    }
}

int main(void)
{
    assert(tagged_size() == sizeof(struct tagged));
    assert(tagged_alignment() == _Alignof(struct tagged));
    printf("layout:%zu:%zu\n", sizeof(struct tagged), _Alignof(struct tagged));
    for (uint32_t value = 0; value < 256u; ++value)
        observe(value);
    uint32_t boundaries[] = {0x10000u, 0x7fffffffu, 0x80000000u, UINT32_MAX};
    for (size_t index = 0; index < sizeof(boundaries) / sizeof(boundaries[0]); ++index)
        observe(boundaries[index]);
    return 0;
}
