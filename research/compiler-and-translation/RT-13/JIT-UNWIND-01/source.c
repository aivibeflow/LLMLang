typedef unsigned int u32;

u32 jit_step(u32 input, u32 (*callback)(u32)) {
    u32 observed = callback(input);
    return observed + 1;
}
