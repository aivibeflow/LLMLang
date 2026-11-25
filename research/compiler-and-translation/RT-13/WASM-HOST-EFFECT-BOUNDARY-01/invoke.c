__attribute__((import_module("llmlang"), import_name("commit")))
extern void commit(unsigned value);

unsigned invoke(long long requested)
{
    if (requested < 0 || requested > 255)
        return 256;
    unsigned admitted = (unsigned)requested;
    commit(admitted);
    return admitted;
}
