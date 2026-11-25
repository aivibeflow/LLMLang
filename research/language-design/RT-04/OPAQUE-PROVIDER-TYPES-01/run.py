"""Check opaque and erased provider revisions with separate Rust compilation."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


PROFILES = {
    "opaque": ("impl Value", False, False),
    "opaque_send": ("impl Value + Send", False, True),
    "erased": ("Box<dyn Value>", True, False),
    "erased_send": ("Box<dyn Value + Send>", True, True),
}
LAYOUTS = {"inline_array": ("[1, 2, 3, 4]", 4), "shared_rc": ("Rc::new([1, 2, 3, 4])", 8)}


def compile_rust(compiler, *args):
    return subprocess.run(
        [compiler, "--edition=2021", "--error-format=json", *args],
        check=False, capture_output=True, text=True, timeout=30,
    )


def require_not_send(result):
    assert result.returncode != 0
    diagnostics = [json.loads(line) for line in result.stderr.splitlines()]
    errors = [row["code"]["code"] for row in diagnostics if row.get("level") == "error" and row.get("code")]
    assert errors == ["E0277"], diagnostics
    assert "cannot be sent between threads safely" in result.stderr, diagnostics
    return {"status": "refused", "diagnostic": errors[0]}


def client(compiler, source, work, library, require_send, should_accept, native_size):
    flags = ["--cfg", "require_send"] if require_send else []
    binary = work / "client"
    built = compile_rust(compiler, str(source), "--extern", f"provider={library}", "-o", str(binary), *flags)
    if not should_accept:
        return require_not_send(built)
    assert built.returncode == 0, built.stderr
    result = subprocess.check_output([binary], text=True, timeout=10).strip()
    assert result == f"10:{native_size}", result
    return {"status": "accepted", "sum": 10, "native_size": native_size}


def study(compiler):
    version = subprocess.check_output([compiler, "-Vv"], text=True).splitlines()
    assert "host: x86_64-unknown-linux-gnu" in version
    folder = Path(__file__).resolve().parent
    source = (folder / "provider.in").read_text()
    results = {}
    with TemporaryDirectory() as temporary:
        for profile, (returns, boxed, requires_send) in PROFILES.items():
            results[profile] = {}
            for layout, (expression, inline_size) in LAYOUTS.items():
                work = Path(temporary) / f"{profile}-{layout}"
                work.mkdir()
                body = f"Box::new({expression})" if boxed else expression
                provider = work / "provider.rs"
                provider.write_text(source.replace("@RESULT@", returns).replace("@BODY@", body))
                library = work / "libprovider.rlib"
                built = compile_rust(compiler, "--crate-name", "provider", "--crate-type", "rlib",
                                     str(provider), "-o", str(library))
                if requires_send and layout == "shared_rc":
                    results[profile][layout] = {"provider": require_not_send(built)}
                    continue
                assert built.returncode == 0, built.stderr
                native_size = 16 if boxed else inline_size
                send_client_allowed = requires_send or (not boxed and layout == "inline_array")
                args = compiler, folder / "client.rs", work, library
                results[profile][layout] = {
                    "provider": {"status": "accepted"},
                    "operation_client": client(*args, False, True, native_size),
                    "send_client": client(*args, True, send_client_allowed, native_size),
                }
    return {"python": platform.python_version(), "rustc": version, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    print(json.dumps(study(parser.parse_args().rustc), indent=2, sort_keys=True))
