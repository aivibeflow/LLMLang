#ifndef VARIADIC_FIXTURE_H
#define VARIADIC_FIXTURE_H

typedef unsigned long word;
typedef struct { word marker; long small; double magnitude; word promoted_bits; word tag; } input_record;
typedef struct { word marker; word integer; word binary64; word tag; } output_record;

_Static_assert(sizeof(word) == 8 && sizeof(long) == 8, "LP64");
_Static_assert(sizeof(float) == 4 && sizeof(double) == 8, "floating value carriers");
_Static_assert(sizeof(input_record) == 40 && sizeof(output_record) == 32, "public protocol records");

#if defined(MS_ABI)
#define VARIADIC_ABI __attribute__((ms_abi))
#else
#define VARIADIC_ABI
#endif
VARIADIC_ABI void fixture_var(output_record *output, unsigned int marker, ...);
void manual_call(output_record *output, const input_record *input);
long fixture_write(const void *data, word length);
_Noreturn void fixture_exit(word status);

#endif
