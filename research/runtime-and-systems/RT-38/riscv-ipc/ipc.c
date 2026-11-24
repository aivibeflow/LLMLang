enum { send = 1, receive = 2, delegate = 3, revoke = 4 };
enum { right_send = 1, right_receive = 2 };

struct endpoint {
    unsigned long held_generation;
    unsigned long next_generation;
    unsigned long rights;
    unsigned long pending;
    unsigned long value;
};

static volatile struct endpoint endpoint __attribute__((section(".data.kernel"))) = {0, 1, 0, 0, 0};

static void emit(unsigned long byte) {
    volatile unsigned char *const uart = (volatile unsigned char *)0x10000000;
    while (!(uart[5] & 0x20)) {}
    uart[0] = (unsigned char)byte;
}

__attribute__((section(".text.boot")))
unsigned long ipc_request(unsigned long actor, unsigned long operation,
                          unsigned long handle, unsigned long value) {
    unsigned long result = 'I';
    if (operation == delegate && actor == 0) {
        if (!value || value & ~(unsigned long)(right_send | right_receive))
            result = 'D';
        else if (endpoint.rights)
            result = 'F';
        else if (!endpoint.next_generation)
            result = 'O';
        else {
            endpoint.held_generation = endpoint.next_generation;
            endpoint.next_generation = endpoint.held_generation == GENERATION_MAX ? 0 : endpoint.held_generation + 1;
            endpoint.rights = value;
            result = 'G';
        }
    } else if (operation == revoke && actor == 0) {
        if (endpoint.rights) {
            endpoint.rights = 0;
            result = 'R';
        } else
            result = 'N';
    } else if (operation == send || operation == receive) {
        if (actor == 1 && !endpoint.rights)
            result = 'N';
        else if (actor == 1 && GENERATIONS && endpoint.held_generation != handle)
            result = 'S';
        else if (actor == 1 && !(endpoint.rights & operation))
            result = 'D';
        else if (operation == send) {
            if (endpoint.pending)
                result = 'F';
            else {
                endpoint.value = value;
                endpoint.pending = 1;
                result = 'A';
            }
        } else if (endpoint.pending) {
            result = endpoint.value;
            endpoint.pending = 0;
        } else
            result = 'E';
    }
    emit(actor ? 'B' : 'A');
    emit(result);
    return result;
}
