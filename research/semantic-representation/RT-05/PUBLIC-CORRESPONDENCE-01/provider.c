#include <stdio.h>

struct Observation {
    int status;
    int result;
    int trace;
    int work;
};

static struct Observation execute(int profile, int grant, int fuel, int units) {
    int adjustment = profile == 1 ? 2 : 1;
    if (!grant && profile != 4) {
        return (struct Observation){1, 0, 0, 0};
    }
    if (fuel < 2) {
        return (struct Observation){2, 0, 0, 0};
    }
    if (units < 0) {
        return (struct Observation){3, 0, 1, 1};
    }
    return (struct Observation){
        0, units + adjustment, profile == 2 ? 3 : 2, profile == 3 ? 4 : 2
    };
}

int main(void) {
    for (int profile = 0; profile < 5; ++profile) {
        for (int grant = 0; grant < 2; ++grant) {
            for (int fuel = 0; fuel < 4; ++fuel) {
                for (int units = -2; units < 6; ++units) {
                    struct Observation observed = execute(profile, grant, fuel, units);
                    printf("%d %d %d %d %d %d %d %d\n", profile, grant, fuel, units,
                           observed.status, observed.result, observed.trace, observed.work);
                }
            }
        }
    }
    return 0;
}
