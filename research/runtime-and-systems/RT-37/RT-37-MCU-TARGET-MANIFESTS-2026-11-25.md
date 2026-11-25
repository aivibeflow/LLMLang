# RT-37 Vendor-pinned MCU target manifests

The pilot needs exact target profiles before it can compare artifacts or device traces. The [candidate manifests](MCU-TARGET-MANIFESTS-01/manifests.json) bind the board and part, ISA, call convention, SDK and component revisions, reset path, clock profile, interrupts, memory layout, peripheral instances and intended programming procedure. They describe study targets. Board procurement and production target selection remain human decisions.

| Board and part | ABI and pinned SDK | Candidate clock and pilot devices |
|---|---|---|
| NUCLEO-F103RB MB1136, STM32F103RBT6 | Cortex-M3 Thumb-2, AAPCS32 soft, STM32CubeF1 v1.8.6 | 64 MHz from HSI PLL, LD2 on PA5, TIM2, USART2 on PA2/PA3 |
| STM32F407G-DISC1 MB997, STM32F407VGT6 | Cortex-M4 Thumb-2, FPv4-SP-D16, AAPCS32 hard, STM32CubeF4 v1.28.3 | 168 MHz from HSE PLL, LD4 on PD12, TIM2, USART2 on PA2/PA3 using an external adapter |
| ESP32-DevKitC V4 with ESP32-WROOM-32E-N4 | Dual-core Xtensa LX6, windowed ABI, ESP-IDF v5.5.3 | 160 MHz SDK profile, GPIO18, GPTimer, UART0 via onboard bridge |

Board documents establish the nominal parts and connections. The ESP32 manifest identifies the 4 MiB, no-PSRAM module and the expected ESP32-D0WD-V3 interpretation. Exact fitted devices, board revisions and wiring still need physical inspection. [NUCLEO board manual](https://www.st.com/resource/en/user_manual/dm00105823.pdf) · [Discovery board manual](https://www.st.com/resource/en/user_manual/dm00039084-stm32f4-discovery-kit-stm32f407vg-mcu-stmicroelectronics.pdf) · [DevKitC board guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html) · [Espressif module data sheet](https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.html)

```mermaid
flowchart LR
  M[Candidate board and SDK manifest] --> P[Pin vendor startup and layout]
  P --> A[Check compiler ABI object]
  A --> F[Build and inspect pilot image]
  F --> B[Physical flash and device traces]
```

## Checked boundaries

The verifier checks the digests of 14 vendor files and validates the ST memory regions and clock prescalers, reset and interrupt entries, Cortex-M4 project flags, ESP32 boot path and linker region markers, factory partition size, CPU default and compiler archive identity. The STM32F1 GNU example linker filename names a different package variant, while its flash and SRAM regions match the medium-density candidate. The ESP32 linker template has separate mapped flash, instruction RAM, data RAM and RTC regions. Its 520 KiB of on-chip SRAM is a chip total. The available static data region depends on the SDK configuration and reservations. A pilot would retain the generated linker map, partition table and flash arguments.

| ABI object | Exact checked observation |
|---|---|
| Cortex-M3 soft | No VFP-register argument tag |
| Cortex-M4 hard | VFP-register argument tag |
| Cortex-M4 softfp control | No VFP-register argument tag |
| ESP32 vendor GCC defaults with the SDK long-call flag | Windowed ABI macro and `callx8` |
| ESP32 forced call0 control | Call0 macro and `callx0` |

Using a shared processor family name or ELF machine would lose the demonstrated ABI distinctions. Choosing hard versus softfp on Cortex-M4 changes argument passing even with the same FPU. Choosing call0 versus the SDK's windowed ABI changes the observed call instruction. No full SDK image, emulated device trace, physical flash or timing result follows from these object checks. Those are separately scoped pilot obligations. [Espressif startup](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-guides/startup.html) · [GCC Xtensa ABI options](https://gcc.gnu.org/onlinedocs/gcc-16.2.0/gcc/Xtensa-Options.html)

## Replay

Use CPython 3.12.14, Debian Clang 19.1.7, GNU readelf 2.44 and Espressif GCC from the x86-64 Linux compiler archive pinned by the manifest verifier. The archive was downloaded and matched its vendor SHA-256 before the two runs. Fresh and cached vendor source reads produced identical [evidence](MCU-TARGET-MANIFESTS-01/evidence.json).

```sh
LC_ALL=C PYTHONHASHSEED=37 python -B research/runtime-and-systems/RT-37/MCU-TARGET-MANIFESTS-01/check.py \
  --cache /tmp/llmlang-mcu-sources --arm /path/to/clang-19 \
  --xtensa /path/to/xtensa-esp32-elf-gcc --xtensa-objdump /path/to/xtensa-esp32-elf-objdump
```
