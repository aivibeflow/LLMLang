#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if LAYOUT == 0
struct wire_record { uint32_t amount; uint32_t category; uint16_t flags; };
#elif LAYOUT == 1
struct wire_record { uint32_t category; uint32_t amount; uint16_t flags; };
#elif LAYOUT == 2
struct wire_record { uint16_t flags; uint32_t amount; uint32_t category; };
#elif LAYOUT == 3
struct __attribute__((packed)) wire_record { uint32_t amount; uint16_t flags; uint32_t category; };
#elif LAYOUT == 4
struct wire_record { uint32_t amount; uint32_t category; uint32_t flags; };
#else
#error Unknown layout
#endif

size_t layout_word(unsigned index) {
    const uint16_t one = 1;
    const unsigned char *byte = (const unsigned char *) &one;
    const size_t fields[] = {
        sizeof(struct wire_record), _Alignof(struct wire_record),
#if STALE_DESCRIPTOR
        0, 4, 8,
#else
        offsetof(struct wire_record, amount), offsetof(struct wire_record, category),
        offsetof(struct wire_record, flags),
#endif
        sizeof(((struct wire_record *) 0)->amount),
        sizeof(((struct wire_record *) 0)->category),
#if STALE_DESCRIPTOR == 2
        2,
#else
        sizeof(((struct wire_record *) 0)->flags),
#endif
        *byte == 1,
    };
    return index < sizeof fields / sizeof *fields ? fields[index] : 0;
}

int score_record(const unsigned char *bytes, size_t size, uint64_t *result) {
    struct wire_record record;
    if (size != sizeof record)
        return 1;
    memcpy(&record, bytes, sizeof record);
    *result = UINT64_C(11) * record.amount + UINT64_C(103) * record.category + UINT64_C(1009) * record.flags;
#if DIFFERENT_BEHAVIOR
    *result += 1;
#endif
    return 0;
}
