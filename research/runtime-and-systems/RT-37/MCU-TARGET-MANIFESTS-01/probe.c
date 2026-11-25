extern float provider(float);

float caller(float value) {
    return provider(value) + 1.0f;
}
