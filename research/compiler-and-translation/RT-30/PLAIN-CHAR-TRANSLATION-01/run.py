"""Translate one C-family fixture under explicit plain-char representation profiles."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASELINE = "50c9e9182df585a32ee89145405c25682971ecd2"
FIXTURE = "2952cbda9a483e2a2d5ceb4e66f0122e817e0aa63f68a43a20c76f721802c1f9"
PROFILES = {"signed": (8, -128), "unsigned": (8, 0)}
LANGUAGES = ("c17", "cpp20", "rust2021", "go")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def import_model(source, char_profile):
    if sha(source) != FIXTURE:
        raise ValueError("source grammar outside pinned fixture")
    if char_profile not in PROFILES.values():
        raise ValueError("missing or unsupported exact char profile")
    return {"width_bits": 8, "interpret_high_bit_as_negative": char_profile[1] < 0,
            "bias_nonnegative": 256}


def observe_model(model):
    values = []
    for raw in range(256):
        promoted = raw - 256 if raw >= 128 and model["interpret_high_bit_as_negative"] else raw
        values.append(promoted if promoted < 0 else promoted + model["bias_nonnegative"])
    return values


def invoke(arguments, directory, environment, timeout=60):
    return subprocess.check_output(arguments, cwd=directory, env=environment, timeout=timeout)


def native_c(args, language, mode, source, directory, env):
    compiler = args.cc if language == "c17" else args.cxx
    language_arg = "c" if language == "c17" else "c++"
    standard = "c17" if language == "c17" else "c++20"
    binary = directory / "native-c"
    invoke([compiler, "-x", language_arg, f"-std={standard}", "-O2", "-Wall", "-Wextra",
            "-Werror", f"-f{mode}-char", source, HERE / "observe.c", "-o", binary], directory, env)
    profile, *observations = invoke([binary], directory, env).decode().splitlines()
    return tuple(map(int, profile.split(","))), list(map(int, observations))


def generate_c(model):
    signed = int(model["interpret_high_bit_as_negative"])
    return (
        "#include <stdint.h>\n"
        "int32_t translate(uint8_t raw) {\n"
        "    int32_t value = (int32_t)raw;\n"
        f"    if ({signed} && value >= 128) value -= 256;\n"
        "    return value < 0 ? value : value + 256;\n"
        "}\n"
    )


def generate_rust(model):
    signed = str(model["interpret_high_bit_as_negative"]).lower()
    return f"""fn main() {{
    for raw in 0u8..=255 {{
        let value = i32::from(raw);
        let promoted = if {signed} && value >= 128 {{ value - 256 }} else {{ value }};
        println!("{{}}", if promoted < 0 {{ promoted }} else {{ promoted + 256 }});
    }}
}}
"""


def generate_go(model):
    signed = str(model["interpret_high_bit_as_negative"]).lower()
    return f"""package main
import "fmt"
func main() {{
    for raw := int32(0); raw <= 255; raw++ {{
        promoted := raw
        if {signed} && raw >= 128 {{ promoted -= 256 }}
        if promoted >= 0 {{ promoted += 256 }}
        fmt.Println(promoted)
    }}
}}
"""


def translate(args, model, language, mode, directory, env):
    if language in ("c17", "cpp20"):
        source_text = generate_c(model)
        source = directory / ("generated.c" if language == "c17" else "generated.cpp")
        source.write_text(source_text, encoding="utf-8")
        opposite = "unsigned" if mode == "signed" else "signed"
        target_profile, values = native_c(args, language, opposite, source, directory, env)
        assert target_profile == PROFILES[opposite]
    else:
        if language == "go":
            source_text = generate_go(model)
            source = directory / "generated.go"
            command = [args.go, "build", "-p=2", "-trimpath", "-buildvcs=false"]
        else:
            source_text = generate_rust(model)
            source = directory / "generated.rs"
            command = [args.rustc, "--edition=2021", "-Copt-level=2", "-Coverflow-checks=yes"]
        source.write_text(source_text, encoding="utf-8")
        binary = directory / "target"
        invoke([*command, "-o", binary, source], directory, env)
        values = list(map(int, invoke([binary], directory, env).splitlines()))
        target_profile = None
    assert values == observe_model(model), (language, mode)
    return {"generated_source": source_text, "generated_sha256": sha(source_text.encode()),
            "target_char_probe": target_profile, "outputs": values}


def exercise(args, directory):
    env = os.environ | {"LC_ALL": "C", "TZ": "UTC", "CGO_ENABLED": "0", "GOENV": "off",
                        "GO111MODULE": "off", "GOTOOLCHAIN": "local", "GOPROXY": "off",
                        "GOCACHE": str(directory / "go-cache")}
    source = (HERE / "source.c").read_bytes()
    native, targets, models = {}, {}, {}
    for mode, profile in PROFILES.items():
        model = import_model(source, profile)
        models[mode] = model
        for language in ("c17", "cpp20"):
            work = directory / f"original-{language}-{mode}"
            work.mkdir()
            observed_profile, values = native_c(args, language, mode, HERE / "source.c", work, env)
            assert observed_profile == profile
            assert values == observe_model(model)
            native[f"{language}-{mode}"] = {"char_probe": observed_profile, "outputs": values}
        for language in LANGUAGES:
            work = directory / f"target-{language}-{mode}"
            work.mkdir()
            targets[f"{language}-{mode}"] = translate(args, model, language, mode, work, env)

    refusals = {}
    invalid = {"no-profile": (source, None), "wrong-width": (source, (16, -32768)),
               "unreviewed-source": (source + b"\n", PROFILES["signed"])}
    for name, payload in invalid.items():
        try:
            import_model(*payload)
        except ValueError as error:
            refusals[name] = str(error)
        else:
            raise AssertionError(name)
    signed, unsigned = (observe_model(models[mode]) for mode in ("signed", "unsigned"))
    wrong_profile_inputs = [i for i, (a, b) in enumerate(zip(signed, unsigned, strict=True)) if a != b]
    assert wrong_profile_inputs == list(range(128, 256))
    versions = {
        "gcc": invoke([args.cc, "--version"], directory, env).decode().splitlines()[0],
        "g++": invoke([args.cxx, "--version"], directory, env).decode().splitlines()[0],
        "rustc": invoke([args.rustc, "-vV"], directory, env).decode().splitlines(),
        "go": invoke([args.go, "version"], directory, env).decode().strip(),
    }
    return {
        "baseline": BASELINE, "python": platform.python_version(), "target": platform.machine(),
        "tools": versions, "source_sha256": {
            name: sha((HERE / name).read_bytes()) for name in ("source.c", "observe.c", "run.py")
        },
        "models": models, "native_input": native, "generated_targets": targets,
        "wrong_profile_inputs": wrong_profile_inputs, "refusals": refusals,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--rustc", required=True, type=Path)
    parser.add_argument("--go", required=True, type=Path)
    settings = parser.parse_args()
    settings.rustc = settings.rustc.resolve()
    settings.go = settings.go.resolve()
    with TemporaryDirectory(prefix="llmlang-plain-char-") as temporary:
        print(json.dumps(exercise(settings, Path(temporary)), indent=2))
