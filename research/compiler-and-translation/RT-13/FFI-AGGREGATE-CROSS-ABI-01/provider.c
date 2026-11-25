#include "fixture.h"

mixed_value fixture_mixed(mixed_value value)
{
    return (mixed_value){value.magnitude + 1.5, value.tag ^ 0x13579bdfUL};
}

float_pair fixture_floats(float_pair value)
{
    return (float_pair){value.first + 2.0, -value.second};
}

wide_value fixture_wide(word left, word right)
{
    return (wide_value){left, right, left ^ right};
}
