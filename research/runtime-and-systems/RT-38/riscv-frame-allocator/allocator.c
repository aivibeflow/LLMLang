enum { frame_count = 3, slot_count = 4, words_per_page = 512, command_count = 17 };
enum { free_frame, reserved_frame, published_frame };
enum { zero_on_allocation, zero_on_release, dirty_publication, lost_reservation, double_publication };

static volatile unsigned long frames[frame_count][words_per_page]
    __attribute__((section(".data.protected"), aligned(4096))) = {{0x1234abcd}};

struct allocator {
    volatile unsigned long *leaf;
    unsigned char ownership[frame_count];
    unsigned int scrubbed;
    unsigned int published_dirty;
};

static void emit(char value) {
    volatile unsigned char *const uart = (volatile unsigned char *)0x10000000;
    while (!(uart[5] & 0x20)) {}
    uart[0] = (unsigned char)value;
}

static unsigned long mapping(unsigned int frame) {
    return (((unsigned long)frames[frame] >> 12) << 10) | 0xd7;
}

static unsigned int mapped_frame(unsigned long entry) {
    for (unsigned int frame = 0; frame < frame_count; ++frame)
        if (entry == mapping(frame))
            return frame;
    return frame_count;
}

static void fill(unsigned int frame, unsigned long value) {
    for (unsigned int word = 0; word < words_per_page; ++word)
        frames[frame][word] = value;
}

static void scrub(struct allocator *pool, unsigned int frame) {
    fill(frame, 0);
    ++pool->scrubbed;
}

static void reset(struct allocator *pool) {
    pool->scrubbed = 0;
    pool->published_dirty = 0;
    for (unsigned int slot = 0; slot < slot_count; ++slot)
        pool->leaf[slot] = 0;
    for (unsigned int frame = 0; frame < frame_count; ++frame) {
        pool->ownership[frame] = free_frame;
        fill(frame, 0x1234abcd);
        if (POLICY == zero_on_release)
            scrub(pool, frame);
    }
}

static void publish(struct allocator *pool, unsigned int slot, unsigned int frame) {
    for (unsigned int word = 0; word < words_per_page; ++word)
        if (frames[frame][word])
            pool->published_dirty = 1;
    pool->leaf[slot] = mapping(frame);
    pool->ownership[frame] = published_frame;
}

static char allocate(struct allocator *pool, unsigned int slot, unsigned int fault) {
    if (pool->leaf[slot])
        return 'E';
    unsigned int frame = 0;
    if (POLICY != double_publication) {
        while (frame < frame_count && pool->ownership[frame] != free_frame)
            ++frame;
        if (frame == frame_count)
            return 'F';
    }
    pool->ownership[frame] = reserved_frame;
    if (fault == 1) {
        pool->ownership[frame] = free_frame;
        return 'B';
    }
    if (POLICY != zero_on_release && POLICY != dirty_publication)
        scrub(pool, frame);
    if (fault == 2) {
        if (POLICY != lost_reservation)
            pool->ownership[frame] = free_frame;
        return 'L';
    }
    publish(pool, slot, frame);
    return 'A';
}

static char release(struct allocator *pool, unsigned int slot) {
    const unsigned int frame = mapped_frame(pool->leaf[slot]);
    if (frame == frame_count)
        return 'N';
    // Simulate bytes written by the old owner before releasing its mapping.
    fill(frame, 0x1234abcd);
    pool->leaf[slot] = 0;
    if (POLICY == zero_on_release)
        scrub(pool, frame);
    pool->ownership[frame] = free_frame;
    return 'R';
}

static void step(struct allocator *pool, unsigned int command) {
    const unsigned int before = pool->scrubbed;
    pool->published_dirty = 0;
    char status = 'I';
    if (command < 12)
        status = allocate(pool, command % slot_count, command / slot_count);
    else if (command < 16)
        status = release(pool, command - 12);

    emit(status);
    for (unsigned int slot = 0; slot < slot_count; ++slot) {
        const unsigned long entry = pool->leaf[slot];
        const unsigned int frame = mapped_frame(entry);
        emit(entry && frame == frame_count ? 'X' : (char)('0' + (entry ? frame + 1 : 0)));
    }
    for (unsigned int frame = 0; frame < frame_count; ++frame)
        emit((char)('0' + pool->ownership[frame]));
    emit((char)('0' + pool->scrubbed - before));
    emit((char)('0' + pool->published_dirty));
}

__attribute__((section(".text.trap")))
void run_allocator(volatile unsigned long *leaves) {
    struct allocator pool;
    pool.leaf = leaves;
    reset(&pool);
    emit((char)('0' + pool.scrubbed));
    for (unsigned int a = 0; a < command_count; ++a)
        for (unsigned int b = 0; b < command_count; ++b)
            for (unsigned int c = 0; c < command_count; ++c) {
                reset(&pool);
                step(&pool, a);
                step(&pool, b);
                step(&pool, c);
            }
    reset(&pool);
    step(&pool, 0);
    step(&pool, 1);
    step(&pool, 2);
    step(&pool, 3);  // Exhaustion with all three frames published.
    step(&pool, 12);
    step(&pool, 11); // Abort after scrub for a frame that was previously owned.
    step(&pool, 3);  // Recover and reuse.
    reset(&pool);
    allocate(&pool, 0, 0);
}
