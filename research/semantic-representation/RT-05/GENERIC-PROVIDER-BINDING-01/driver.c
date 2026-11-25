#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

extern int64_t route_static(uint8_t, int64_t);
extern int64_t route_linked(uint8_t, int64_t);
extern int64_t route_trait(uint8_t, int64_t);
extern int64_t route_dictionary(uint8_t, int64_t);
extern int64_t unrelated(void);

int main(void) {
    unsigned int tag;
    int64_t value;
    printf("provider %" PRId64 "\n", unrelated());
    while (scanf("%u %" SCNd64, &tag, &value) == 2) {
        const int64_t direct = route_static((uint8_t)tag, value);
        const int64_t linked = route_linked((uint8_t)tag, value);
        const int64_t trait = route_trait((uint8_t)tag, value);
        const int64_t table = route_dictionary((uint8_t)tag, value);
        printf("%" PRId64 " %" PRId64 " %" PRId64 " %" PRId64 "\n", direct, linked, trait, table);
    }
    return 0;
}
