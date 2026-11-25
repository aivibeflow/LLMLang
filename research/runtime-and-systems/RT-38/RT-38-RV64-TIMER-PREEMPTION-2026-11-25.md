# RV64 timer-driven preemption and saved user state

[GitHub #441](https://github.com/aivibeflow/LLMLang/issues/441) · 2026-11-25

The experiment extends the repository's cooperative context fixture with machine timer interrupts. Two U-mode tasks loop without a yield syscall. Each checks a saved register, a temporary register and a marker on its own stack. M-mode dispatch accepts the exact timer cause, validates the interrupted program counter and records a delivery credit in the saved user context. The task exits through a checked syscall after receiving its configured credits.

The timer is rearmed for the selected task only while credits remain. A timer interrupt resumes the interrupted instruction. The terminal syscall uses its own PC and cause checks. The linker and instruction audit verify the complete integer save/restore pattern, matching freestanding load boundaries, exact user code, absence of yield and hosted symbols, and absence of linked relocations.

## QEMU observations

The guest uses QEMU 10.0.13, RV64 `virt`, one hart, no firmware image, and a fixed virtual instruction clock. An independent queue model predicts a capital letter on delivery, a lower-case letter on completion and `!` once both tasks finish.

| Timer credits A, B | Round robin after each interrupt | Keep the current task until completion |
| --- | --- | --- |
| 1, 1 | `ABab!` | `AaBb!` |
| 1, 3 | `ABaBBb!` | `AaBBBb!` |
| 3, 1 | `ABAbAa!` | `AAAaBb!` |
| 3, 3 | `ABABABab!` | `AAAaBBBb!` |

The eight preserving ELF images match the model. Two additional images keep identical user bytes. Clearing a saved register after a timer delivery reaches the register control `ABS`. Replacing the interrupted instruction address with the fixture's fault continuation reaches `ABT`. The baseline and both controls reach their predicted trace in repeated clean builds.

## Conditional progress

Lean checks four propositions over delivered credits, remaining budget and completion. A valid tick stays within budget and strictly decreases joint remaining work. A ready completion consumes the final obligation. Two theorems use propositional extensionality and two report no axioms. The proof assumes delivery and an admitted runnable context. It leaves temporal fairness of physical delivery, concrete code correspondence, blocking IPC with timer interrupts, SMP and latency measurement open.

## Replay

Use CPython 3.12.14, LLVM/LLD 19.1.7, QEMU 10.0.13 and Lean 4.36.0. Pass `--qemu-data` when machine data is installed outside QEMU's default path.

```sh
fixture=research/runtime-and-systems/RT-38/RV64-TIMER-PREEMPTION-01
python -B "$fixture/run.py" --qemu /path/to/qemu-system-riscv64 \
  --output /tmp/rt38-timer.json
cmp "$fixture/evidence.json" /tmp/rt38-timer.json
```

Two full replays produced identical [evidence ledgers](RV64-TIMER-PREEMPTION-01/evidence.json).
