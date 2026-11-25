_Static_assert(sizeof(unsigned int) == 4, "expected a 32-bit unsigned int");

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT unsigned int fixture_reserve(unsigned int quantity) {
#ifdef WRONG_RESERVATION
    return quantity + 2;
#else
    return quantity + 1;
#endif
}

EXPORT unsigned int fixture_quote(unsigned int quantity) {
    return quantity * 3;
}
