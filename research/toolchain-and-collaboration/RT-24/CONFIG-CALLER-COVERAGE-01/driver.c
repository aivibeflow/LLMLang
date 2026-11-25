#include <stdio.h>

int site_primary(void);
int site_secondary(void);
int site_optional(void);

int main(void) {
    const int primary = site_primary();
    const int secondary = site_secondary();
    const int optional = site_optional();
    printf("%d %d %d\n", primary, secondary, optional);
    return 0;
}
