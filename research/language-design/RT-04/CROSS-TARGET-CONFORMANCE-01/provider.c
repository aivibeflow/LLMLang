int bounded_value(int input, int observe) {
    int result = input;
    if (input < 0) {
        result = 0;
    } else if (input > 3) {
        result = 3;
    }
#ifndef OMIT_EVENT
    int event = observe && result != input;
#else
    (void)observe;
    int event = 0;
#endif
    return result * 2 + event;
}
