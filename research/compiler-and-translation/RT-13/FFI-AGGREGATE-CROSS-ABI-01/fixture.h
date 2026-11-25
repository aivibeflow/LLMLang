#ifndef FIXTURE_H
#define FIXTURE_H

typedef unsigned long word;
typedef struct { double magnitude; word tag; } mixed_value;
typedef struct { double first; double second; } float_pair;
typedef struct { word left; word right; word combined; } wide_value;

_Static_assert(sizeof(word) == 8 && sizeof(double) == 8, "LP64 and binary64");
_Static_assert(sizeof(mixed_value) == 16 && _Alignof(mixed_value) == 8, "mixed carrier");
_Static_assert(sizeof(float_pair) == 16 && _Alignof(float_pair) == 8, "homogeneous carrier");
_Static_assert(sizeof(wide_value) == 24 && _Alignof(wide_value) == 8, "wide carrier");

mixed_value fixture_mixed(mixed_value value);
float_pair fixture_floats(float_pair value);
wide_value fixture_wide(word left, word right);
long fixture_write(const void *data, word length);
_Noreturn void fixture_exit(word status);

#endif
