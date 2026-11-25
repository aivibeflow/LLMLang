#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#ifdef PILOT_WIFI
#include "esp_wifi.h"
#endif

typedef struct {
    unsigned worker;
    unsigned core;
    unsigned initial;
} observation;

static QueueHandle_t ready_queue;
static QueueHandle_t done_queue;
static atomic_uint split_value;
static unsigned protected_value;
static portMUX_TYPE gate = portMUX_INITIALIZER_UNLOCKED;

static void worker(void *context) {
    observation state = {
        .worker = (unsigned)(uintptr_t)context,
        .core = (unsigned)xPortGetCoreID(),
        .initial = atomic_load(&split_value),
    };
    assert(xQueueSend(ready_queue, &state, portMAX_DELAY) == pdTRUE);
    assert(ulTaskNotifyTake(pdTRUE, portMAX_DELAY) == 1);
    atomic_store(&split_value, state.initial + 1);
    taskENTER_CRITICAL(&gate);
    protected_value++;
    taskEXIT_CRITICAL(&gate);
    assert(xQueueSend(done_queue, &state, portMAX_DELAY) == pdTRUE);
    vTaskDelete(NULL);
}

void app_main(void) {
    ready_queue = xQueueCreate(2, sizeof(observation));
    done_queue = xQueueCreate(2, sizeof(observation));
    assert(ready_queue && done_queue);

    TaskHandle_t tasks[2];
    assert(xTaskCreatePinnedToCore(worker, "worker0", 2048, (void *)0, 3, &tasks[0], 0) == pdPASS);
    BaseType_t second_core = configNUMBER_OF_CORES - 1;
    assert(xTaskCreatePinnedToCore(worker, "worker1", 2048, (void *)1, 3, &tasks[1], second_core) == pdPASS);

    observation state[2];
    for (unsigned i = 0; i < 2; ++i) {
        assert(xQueueReceive(ready_queue, &state[i], portMAX_DELAY) == pdTRUE);
        assert(state[i].initial == 0);
    }
    assert(state[0].worker != state[1].worker);
    xTaskNotifyGive(tasks[0]);
    xTaskNotifyGive(tasks[1]);

    unsigned core_by_worker[2] = {0, 0};
    unsigned completed = 0;
    for (unsigned i = 0; i < 2; ++i) {
        observation result;
        assert(xQueueReceive(done_queue, &result, portMAX_DELAY) == pdTRUE);
        assert(result.worker < 2);
        completed |= 1u << result.worker;
        core_by_worker[result.worker] = result.core;
    }
    assert(completed == 3);
    taskENTER_CRITICAL(&gate);
    unsigned committed = protected_value;
    taskEXIT_CRITICAL(&gate);
    unsigned split = atomic_load(&split_value);
    printf("S:%d:%u:%u:%u:%u\n", configNUMBER_OF_CORES, core_by_worker[0], core_by_worker[1], split, committed);
    assert(core_by_worker[0] == 0 && core_by_worker[1] == (unsigned)second_core);
    assert(split == 1 && committed == 2);

#ifdef PILOT_WIFI
    wifi_init_config_t wifi = WIFI_INIT_CONFIG_DEFAULT();
    printf("W:%d\n", esp_wifi_init(&wifi));
#endif
}
