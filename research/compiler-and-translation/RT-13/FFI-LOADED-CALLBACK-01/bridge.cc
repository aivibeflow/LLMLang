#include "provider.h"

namespace {
struct callback_failure {};
}

extern "C" int32_t bridge(void *raw, uint32_t token, int32_t value) noexcept {
    const auto *context = static_cast<const struct context *>(raw);
    try {
        const int32_t from_worker = context->peek(token);
        if (from_worker < 0) {
            return from_worker;
        }
        if (context->fail) {
            throw callback_failure{};
        }
        return from_worker + value;
    } catch (const callback_failure &) {
        return 70;
    }
}
