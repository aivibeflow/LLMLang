#include "pilot.h"

#ifdef STM32F103xB
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_gpio.h"
#include "stm32f1xx_ll_tim.h"
#include "stm32f1xx_ll_usart.h"
#define LED_PORT GPIOA
#define LED_PIN LL_GPIO_PIN_5
#define PERIPH_CLOCK 8000000u
#elif defined(STM32F407xx)
#include "stm32f4xx_ll_bus.h"
#include "stm32f4xx_ll_gpio.h"
#include "stm32f4xx_ll_tim.h"
#include "stm32f4xx_ll_usart.h"
#define LED_PORT GPIOD
#define LED_PIN LL_GPIO_PIN_12
#define PERIPH_CLOCK 16000000u
#else
#error "A precise supported MCU profile is required"
#endif

/* This freestanding C fixture has no constructors. */
void __libc_init_array(void) {}

static volatile unsigned ready_ticks;

void TIM2_IRQHandler(void) {
    if (LL_TIM_IsActiveFlag_UPDATE(TIM2)) {
        LL_TIM_ClearFlag_UPDATE(TIM2);
        if (ready_ticks < 6)
            ready_ticks++;
    }
}

static void configure(void) {
#ifdef STM32F103xB
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOA | LL_APB2_GRP1_PERIPH_AFIO);
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_2, LL_GPIO_MODE_ALTERNATE);
#else
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA | LL_AHB1_GRP1_PERIPH_GPIOD);
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_2, LL_GPIO_MODE_ALTERNATE);
    LL_GPIO_SetAFPin_0_7(GPIOA, LL_GPIO_PIN_2, LL_GPIO_AF_7);
#endif
    LL_GPIO_SetPinMode(LED_PORT, LED_PIN, LL_GPIO_MODE_OUTPUT);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_USART2 | LL_APB1_GRP1_PERIPH_TIM2);
#ifdef STM32F103xB
    LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_2, LL_GPIO_SPEED_FREQ_HIGH);
    LL_GPIO_SetPinSpeed(LED_PORT, LED_PIN, LL_GPIO_SPEED_FREQ_LOW);
    LL_USART_SetBaudRate(USART2, PERIPH_CLOCK, 115200);
#else
    LL_USART_SetBaudRate(USART2, PERIPH_CLOCK, LL_USART_OVERSAMPLING_16, 115200);
#endif
    LL_USART_SetTransferDirection(USART2, LL_USART_DIRECTION_TX);
    LL_USART_Enable(USART2);
    LL_TIM_SetPrescaler(TIM2, PERIPH_CLOCK / 10000u - 1);
    LL_TIM_SetAutoReload(TIM2, 500u - 1);
    LL_TIM_GenerateEvent_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_EnableIT_UPDATE(TIM2);
    NVIC_EnableIRQ(TIM2_IRQn);
    LL_TIM_EnableCounter(TIM2);
}

static void gpio(unsigned level) {
    if (level)
        LL_GPIO_SetOutputPin(LED_PORT, LED_PIN);
    else
        LL_GPIO_ResetOutputPin(LED_PORT, LED_PIN);
}

static void uart(char value) {
    while (!LL_USART_IsActiveFlag_TXE(USART2)) {}
    LL_USART_TransmitData8(USART2, (uint8_t)value);
}

int main(void) {
    configure();
    pilot_state state = {0, gpio, uart};
    for (unsigned tick = 1; tick <= 6; ++tick) {
        while (ready_ticks < tick)
            __WFI();
        if (pilot_step(&state, tick) != PILOT_OK)
            return 1;
    }
    LL_TIM_DisableCounter(TIM2);
    while (!LL_USART_IsActiveFlag_TC(USART2)) {}
    for (;;) {
        __WFI();
    }
}
