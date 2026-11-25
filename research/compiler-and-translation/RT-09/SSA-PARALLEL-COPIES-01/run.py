"""Compare LLVM phi assignments with parallel-copy lowering and a sequential control."""

import argparse
from ctypes import CDLL, POINTER, c_uint32
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


REGISTERS = ("a", "b", "c")
ASSIGNMENTS = tuple(product(REGISTERS, repeat=3))
SEEDS = tuple(product(range(3), repeat=3))
SENTINEL = 0xDEADBEEF


def schedule(mapping):
    pending = {left: right for left, right in zip(REGISTERS, mapping, strict=True) if left != right}
    result = []
    temporary = 0
    while pending:
        sources = set(pending.values())
        ready = next((register for register in pending if register not in sources), None)
        if ready is not None:
            result.append((ready, pending.pop(ready)))
            continue
        save = next(iter(pending))
        name = f"tmp{temporary}"
        temporary += 1
        result.append((name, save))
        pending = {destination: name if source == save else source for destination, source in pending.items()}
    return result


def llvm_function(index, mapping):
    names = dict(zip(REGISTERS, ("x", "y", "z"), strict=True))
    phis = "\n".join(
        f"  %{name} = phi i32 [ %{register}, %entry ], [ %{names[source]}, %step ]"
        for (register, name), source in zip(names.items(), mapping, strict=True)
    )
    return f"""define void @loop_{index}(i32 %a, i32 %b, i32 %c, i32 %steps, ptr %out) {{
entry:
  br label %head
head:
{phis}
  %i = phi i32 [ 0, %entry ], [ %next, %step ]
  %yshift = shl i32 %y, 8
  %zshift = shl i32 %z, 16
  %low = or i32 %x, %yshift
  %frame = or i32 %low, %zshift
  %slot = getelementptr i32, ptr %out, i32 %i
  store i32 %frame, ptr %slot, align 4
  %done = icmp eq i32 %i, %steps
  br i1 %done, label %exit, label %step
step:
  %next = add i32 %i, 1
  br label %head
exit:
  ret void
}}
"""


def c_function(index, moves):
    assignments = "\n".join(
        f"        {'uint32_t ' if left.startswith('tmp') else ''}{left} = {right};"
        for left, right in moves if left != right
    )
    return f"""void loop_{index}(uint32_t a, uint32_t b, uint32_t c, uint32_t steps, uint32_t *out)
{{
    for (uint32_t i = 0; ; ++i) {{
        out[i] = a | (b << 8) | (c << 16);
        if (i == steps)
            break;
{assignments}
    }}
}}
"""


def packed(values):
    return sum(value << (8 * offset) for offset, value in enumerate(values))


def model(mapping, initial, steps, *, sequential=False):
    values = dict(zip(REGISTERS, initial, strict=True))
    frames = [packed(initial)]
    for _ in range(steps):
        updated = values if sequential else {}
        for destination, source in zip(REGISTERS, mapping, strict=True):
            updated[destination] = values[source]
        values = updated
        frames.append(packed(values[name] for name in REGISTERS))
    return frames


def observe(library, index, initial, steps):
    call = getattr(library, f"loop_{index}")
    call.argtypes = [c_uint32] * 4 + [POINTER(c_uint32)]
    call.restype = None
    buffer = (c_uint32 * 7)(*[SENTINEL] * 7)
    call(*initial, steps, buffer)
    assert list(buffer[steps + 1:]) == [SENTINEL] * (6 - steps)
    return list(buffer[:steps + 1])


def study(compiler):
    triple = subprocess.check_output([compiler, "-dumpmachine"], text=True).strip()
    moves = [schedule(mapping) for mapping in ASSIGNMENTS]
    sources = {
        "llvm": f'target triple = "{triple}"\n' + "\n".join(
            llvm_function(index, mapping) for index, mapping in enumerate(ASSIGNMENTS)
        ),
        "scheduled": "#include <stdint.h>\n" + "\n".join(
            c_function(index, steps) for index, steps in enumerate(moves)
        ),
        "sequential": "#include <stdint.h>\n" + "\n".join(
            c_function(index, zip(REGISTERS, mapping, strict=True)) for index, mapping in enumerate(ASSIGNMENTS)
        ),
    }
    builds = {}
    with TemporaryDirectory() as temporary:
        for optimization in (0, 2):
            libraries = {}
            for kind, source in sources.items():
                extension = ".ll" if kind == "llvm" else ".c"
                path = Path(temporary) / (kind + extension)
                path.write_text(source)
                library = Path(temporary) / f"{kind}-O{optimization}.so"
                subprocess.run(
                    [compiler, f"-O{optimization}", "-Wall", "-Wextra", "-Werror",
                     "-shared", "-fPIC", str(path), "-o", str(library)],
                    check=True, timeout=30,
                )
                libraries[kind] = CDLL(str(library))

            differing = 0
            differing_terminal = 0
            for index, mapping in enumerate(ASSIGNMENTS):
                for initial, steps in product(SEEDS, range(5)):
                    reference = model(mapping, initial, steps)
                    assert observe(libraries["llvm"], index, initial, steps) == reference
                    assert observe(libraries["scheduled"], index, initial, steps) == reference
                    naive = observe(libraries["sequential"], index, initial, steps)
                    assert naive == model(mapping, initial, steps, sequential=True)
                    differing += naive != reference
                    differing_terminal += naive[-1] != reference[-1]
            builds[str(optimization)] = {
                "cases_per_lowering": len(ASSIGNMENTS) * len(SEEDS) * 5,
                "scheduled_trace_mismatches": 0,
                "sequential_trace_mismatches": differing,
                "sequential_terminal_mismatches": differing_terminal,
            }

    assert builds["0"] == builds["2"]
    assert builds["0"] == {
        "cases_per_lowering": 3645,
        "scheduled_trace_mismatches": 0,
        "sequential_trace_mismatches": 1050,
        "sequential_terminal_mismatches": 888,
    }
    rotation = ("b", "c", "a")
    return {
        "python": platform.python_version(),
        "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
        "target": triple,
        "builds": builds,
        "moves": [{"mapping": mapping, "schedule": steps} for mapping, steps in zip(ASSIGNMENTS, moves, strict=True)],
        "rotation_witness": {
            "seed": [0, 1, 2],
            "expected_packed_frames": model(rotation, (0, 1, 2), 3),
            "naive_packed_frames": model(rotation, (0, 1, 2), 3, sequential=True),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    print(json.dumps(study(parser.parse_args().clang), indent=2, sort_keys=True))
