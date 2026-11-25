#ifndef UNIT_WEIGHT
#error UNIT_WEIGHT must be declared
#endif

extern unsigned calls;
extern unsigned units;
extern unsigned charged;

int foreign_step(unsigned count, int item) {
    calls += 1;
    units += count;
    charged += count * UNIT_WEIGHT;
    return (int)count * item;
}
