#ifdef _WIN32
__declspec(dllexport)
#endif
unsigned pipeline_provider(unsigned value) {
    return (value ^ 17u) + 9u;
}
