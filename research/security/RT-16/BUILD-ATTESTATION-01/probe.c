const char *fixture_filename(void) {
    return __FILE__;
}

const char *fixture_timestamp(void) {
    return __DATE__ " " __TIME__;
}

int fixture_value(void) {
    return 42; /* original comment */
}
