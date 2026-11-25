"""Resolve nonstandard input labels by producer, with source-only regeneration."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from urllib.request import urlopen

AREA = Path(__file__).resolve().parent.parent
CENSUS = AREA / "STRUCTURED-PROVENANCE-01/census.jsonl"
BASE = "93aa2261b387cc2f05763a84e1f86255991ef2a8"
CI = "d75fd5474950944a2a101bc419316603abb1fb78"
COMPILER = "research/compiler-and-translation"
RUNTIME = "research/runtime-and-systems"
FORMAL = "research/formal-verification/PROOF-OBLIGATION-BENCHMARK"
TLC = f"{FORMAL}/generative/transition"
GRAPH = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src"
RT04 = "research/PROTOTYPES/RT-04-01"
LLVM = f"{COMPILER}/PROTOTYPES/LLVM-PRESERVATION-01"
RT37 = f"{RUNTIME}/RT-37"
RT38 = f"{RUNTIME}/RT-38"
CONTROLLED = "research/language-design/RT-02"
RAW = "https://raw.githubusercontent.com"
CMSIS = f"{RAW}/ARM-software/CMSIS_5/2b7495b8535bdcb306dac29b9ded4cfb679d7e5c"
QEMU = f"{RAW}/qemu/qemu/98f88efe8f07067667b8d9b1a5ce9551d34036c1"
MMIO = {
    "ARMCM3.svd": f"{CMSIS}/Device/ARM/SVD/ARMCM3.svd",
    "CMSIS-SVD.xsd": f"{CMSIS}/CMSIS/Utilities/CMSIS-SVD.xsd",
    "core_cm3.h": f"{CMSIS}/CMSIS/Core/Include/core_cm3.h",
    "TM4C123GH6PM.svd": (
        f"{RAW}/cmsis-svd/cmsis-svd-data/c65f8551e57c770344d229dcaa0bf838fa29aff4/"
        "data/TexasInstruments/TM4C123GH6PM.svd"
    ),
    "armv7m_nvic.c": f"{QEMU}/hw/intc/armv7m_nvic.c",
    "armv7m_systick.c": f"{QEMU}/hw/timer/armv7m_systick.c",
    "pl061.c": f"{QEMU}/hw/gpio/pl061.c",
    "stellaris.c": f"{QEMU}/hw/arm/stellaris.c",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def binding(ledger, label):
    parent = ledger.parent
    name = parent.name
    if "JIT-FRESH-PROCESS-01" in ledger.parts:
        return BASE, f"{COMPILER}/RT-13/{label}"
    if name == "cranelift-checked-add":
        return BASE, f"{LLVM}/{label.replace('-', '_')}"
    if name == "CONTROLLED-REVIEW-01":
        routes = {"protocol": f"{parent}/protocol.json", "study": f"{parent}/study.py",
                  "corpus": "corpus.json", "results": "evidence.json", "pilot_runner": "run.py"}
        path = routes[label]
        return BASE, path if path.startswith("research/") else f"{CONTROLLED}/RECONSTRUCTION-ROUNDTRIP-01/{path}"
    if ledger.name.startswith("RT-00-C-SCENARIO-133-CURRENT-MAIN-REPLAY"):
        return CI, f"{RT04}/{label}"
    if name == "owned-contract-replay":
        return BASE, f"{RT04}/{label}"
    if name.startswith("cortex-m3-"):
        overrides = {
            "stack-run.py": f"{RT37}/cortex-m3-stack/run.py",
            "stack_model.py": f"{RT37}/cortex-m3-stack/stack_model.py",
            "timer-run.py": f"{RT37}/cortex-m3-timer/run.py",
            "timer.s": f"{RT37}/cortex-m3-timer/timer.s",
            "rt04_model.py": f"{RT04}/rt04_model.py",
        }
        if label in overrides:
            return BASE, overrides[label]
        filename = "run.py" if label == "closure-run.py" else label
        return BASE, f"{RT37}/cortex-m3-closure/{filename}"
    if name.startswith("riscv-"):
        if name == "riscv-address-spaces":
            prefix, _, local = label.partition("-")
            fixture = {"scheduler": "riscv-cooperative-scheduler", "ipc": "riscv-ipc"}[prefix]
        else:
            assert label.startswith("base-")
            local = label.removeprefix("base-")
            fixture = "riscv-cooperative-scheduler" if name == "riscv-ipc" else "riscv-trap-isolation"
        return BASE, f"{RT38}/{fixture}/{local}"
    if name == "public-refinement-pilot":
        path = f"{FORMAL}/evidence/{label}" if label == "composition.py" else f"{GRAPH}/{label}"
        return BASE, path
    if name == "evidence":
        if label == "measure.py":
            return BASE, f"{parent.parent}/measure.py"
        if label == "native_build_fixture":
            return BASE, f"{parent.parent.parent}/MULTI-ACTION-HITS-01/run.py"
        return BASE, f"{GRAPH}/{label}"
    raise ValueError((ledger, label))


def regenerate():
    commands = {
        LLVM: """
from integer_fixture import SOURCE
print(json.dumps({"fixture-source": sha256(SOURCE.replace("operation", "checked_sadd").encode()).hexdigest()}))
""",
        TLC: """
from tlc_adapter import source, experiment, control
operators, records = experiment()
_, ops, weakened = control(final_only=True)
cases = [
    ("Cases", operators, records),
    ("FinalOnly", ops, [weakened]),
    ("FalseClaim", ops, [{**weakened, "final_only": False}]),
]
print(json.dumps({name: sha256(source(name, operators, records).encode()).hexdigest()
                  for name, operators, records in cases}))
""",
    }
    generated = {}
    with tempfile.TemporaryDirectory(prefix="llmlang-producer-sources-") as temporary:
        subprocess.run(["tar", "-x", "-C", temporary], check=True,
                       input=git("archive", BASE, *commands))
        for folder, command in commands.items():
            output = subprocess.check_output(
                [sys.executable, "-B", "-c", "import json\nfrom hashlib import sha256\n" + command],
                cwd=Path(temporary) / folder,
            )
            generated.update({name: (folder, digest) for name, digest in json.loads(output).items()})
    return generated


def main():
    start, *rows = map(json.loads, CENSUS.read_text().splitlines())
    assert start["base"] == BASE
    generated = regenerate()
    checks = []
    content = {}
    for row in rows:
        ledger = PurePosixPath(row["path"])
        if ledger.name == "evidence.json":
            continue
        for item in row.get("map_labels_without_unique_direct_path", []):
            label = item["label"]
            if ledger.parent.name == "mmio-metadata":
                url = MMIO[label]
                with urlopen(url, timeout=30) as response:
                    actual = sha256(response.read()).hexdigest()
                resolution = {"scope": "pinned_upstream", "source": url, "actual": actual}
            elif label in generated:
                folder, actual = generated[label]
                resolution = {"scope": "regenerated_source", "source": folder,
                              "revision": BASE, "actual": actual}
            else:
                revision, path = binding(ledger, label)
                key = f"{revision}:{path}"
                if key not in content:
                    content[key] = sha256(git("show", key)).hexdigest()
                resolution = {"scope": "tracked_path", "source": path,
                              "revision": revision, "actual": content[key]}
            checks.append({"ledger": str(ledger), **item, **resolution,
                           "matches": item["advertised"] == resolution["actual"]})
    assert len(checks) == 100
    assert all(case["matches"] for case in checks), [case for case in checks if not case["matches"]]
    print(json.dumps({
        "base": BASE, "source_contexts": dict(Counter(case["scope"] for case in checks)),
        "result_counts": dict(Counter("match" if case["matches"] else "differs" for case in checks)),
        "checks": checks,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
