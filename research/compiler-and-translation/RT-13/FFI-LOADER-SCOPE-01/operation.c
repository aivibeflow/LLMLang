int fixture_leaf(void);

int apply_v1(int input)
{
    return input + fixture_leaf() + 100;
}

int apply_v2(int input)
{
    return input + fixture_leaf() + 200;
}

#ifndef STATIC_FIXTURE
__asm__(".symver apply_v1,apply@FIXTURE_1.0");
__asm__(".symver apply_v2,apply@@FIXTURE_2.0");

void *fixture_provider_address(void)
{
    return (void *)fixture_leaf;
}
#endif
