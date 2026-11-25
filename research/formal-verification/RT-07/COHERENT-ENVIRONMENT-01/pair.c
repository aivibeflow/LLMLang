#include <stdio.h>

/*
 * Test fixture for an ordered sequence of publications. The driver injects
 * when each reader step runs. A publication replaces an entire packed image.
 */
int main(void) {
    unsigned image[5];
    unsigned generation[4];
    while (scanf("%u %u %u %u %u %u %u %u %u",
                 &image[0], &image[1], &image[2], &image[3], &image[4],
                 &generation[0], &generation[1], &generation[2], &generation[3]) == 9) {
        if (generation[0] > generation[1] || generation[1] > generation[2] ||
            generation[2] > generation[3] || generation[3] >= 5u) {
            return 1;
        }
        const unsigned first = generation[0];
        const unsigned last = generation[3];
        const unsigned left_image = image[generation[1]];
        const unsigned right_image = image[generation[2]];
        const unsigned mixed = (left_image & 2u) | (right_image & 1u);
        const unsigned pinned = image[first];
        printf("%u %u %u %u %u %u\n", mixed, pinned,
               first == last,
               first % 2u == last % 2u,
               first % 4u == last % 4u,
               generation[1] == generation[2]);
    }
    return ferror(stdin) || ferror(stdout);
}
