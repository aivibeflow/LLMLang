#include "pilot.h"

#include <assert.h>
#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifdef PILOT_INVALID_PIN
#define OUTPUT_PIN GPIO_NUM_34
#else
#define OUTPUT_PIN GPIO_NUM_18
#endif

static void gpio(unsigned level) {
    ESP_ERROR_CHECK(gpio_set_level(OUTPUT_PIN, level));
}

static void uart(char value) {
    int written = uart_write_bytes(UART_NUM_0, &value, 1);
    assert(written == 1);
}

static bool timer_ready(gptimer_handle_t timer, const gptimer_alarm_event_data_t *event, void *context) {
    (void)timer;
    (void)event;
    BaseType_t awaken = pdFALSE;
    vTaskNotifyGiveFromISR((TaskHandle_t)context, &awaken);
    return awaken == pdTRUE;
}

void app_main(void) {
    gpio_config_t gpio_config_value = {.pin_bit_mask = 1ULL << OUTPUT_PIN, .mode = GPIO_MODE_OUTPUT};
    ESP_ERROR_CHECK(gpio_config(&gpio_config_value));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0));

    gptimer_config_t config = {.clk_src = GPTIMER_CLK_SRC_DEFAULT, .direction = GPTIMER_COUNT_UP,
                              .resolution_hz = 1000000};
    gptimer_handle_t timer = NULL;
    ESP_ERROR_CHECK(gptimer_new_timer(&config, &timer));
    gptimer_event_callbacks_t callbacks = {.on_alarm = timer_ready};
    ESP_ERROR_CHECK(gptimer_register_event_callbacks(timer, &callbacks, xTaskGetCurrentTaskHandle()));
    gptimer_alarm_config_t alarm = {.alarm_count = 50000, .reload_count = 0,
                                    .flags.auto_reload_on_alarm = true};
    ESP_ERROR_CHECK(gptimer_set_alarm_action(timer, &alarm));
    ESP_ERROR_CHECK(gptimer_enable(timer));
    ESP_ERROR_CHECK(gptimer_start(timer));

    pilot_state state = {0, gpio, uart};
    for (unsigned tick = 1; tick <= 6; ++tick) {
        if (ulTaskNotifyTake(pdFALSE, pdMS_TO_TICKS(1000)) == 0) {
            uart('!');
            break;
        }
        pilot_result result = pilot_step(&state, tick);
        assert(result == PILOT_OK);
    }
    ESP_ERROR_CHECK(gptimer_stop(timer));
    ESP_ERROR_CHECK(gptimer_disable(timer));
    ESP_ERROR_CHECK(gptimer_del_timer(timer));
    ESP_ERROR_CHECK(uart_wait_tx_done(UART_NUM_0, pdMS_TO_TICKS(1000)));
}
