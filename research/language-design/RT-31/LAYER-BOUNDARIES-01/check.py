"""Check profile provenance, shared abstract syntax and elaborated meaning."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import platform
import sys


HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "CROSS-PROFILE-SPG-01"
HYBRID = HERE.parent / "HYBRID-PROFILE-01"
sys.path[:0] = [str(LEGACY), str(HYBRID)]



def load():
    spec = importlib.util.spec_from_file_location("profile_layer_fixture", LEGACY / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = load()

import hybrid


def digest(value):
    return sha256(value).hexdigest()


def hash_record(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def parse(profile, source):
    return hybrid.parse(source) if profile == hybrid.VERSION else R.parse(profile, source)


def render(profile, term):
    return hybrid.render(term) if profile == hybrid.VERSION else R.render(profile, term)


def trivia(profile, source):
    return (json.dumps(json.loads(source), indent=2) + "\n" if profile == hybrid.VERSION
            else R.source_variant(profile, source))


def inspect(profile, source, binding, delta, adjustment):
    term = parse(profile, source)
    graph = R.compile_program(R.make_program(binding, term))
    R.validate(graph)
    observations = []
    for value, choose in R.INPUTS:
        observation = R.observe(graph, "entry", (value, choose))
        assert observation == R.oracle("op", binding, delta, adjustment, value, choose)
        observations.append(observation)
    return {"source_provenance": hash_record([profile, digest(source.encode())]),
            "abstract_syntax": hash_record(term), "admitted_ir": digest(R.encode(graph)),
            "observations": hash_record(observations)}


def run():
    delta, adjustment = 2, 1
    term = R.entry_term("op", delta, adjustment)
    profiles = (*R.PROFILES, hybrid.VERSION)
    results = {}
    for profile in profiles:
        rendered = render(profile, term)
        expanded = trivia(profile, rendered)
        snapshots = {f"{binding}/{name}": inspect(profile, source, binding, delta, adjustment)
                     for binding in ("primary", "alternate")
                     for name, source in (("rendered", rendered), ("variant", expanded))}
        for binding in ("primary", "alternate"):
            first, second = (snapshots[f"{binding}/{name}"] for name in ("rendered", "variant"))
            assert first["source_provenance"] != second["source_provenance"]
            assert (first["abstract_syntax"], first["admitted_ir"], first["observations"]) == (
                second["abstract_syntax"], second["admitted_ir"], second["observations"])
        primary, alternate = (snapshots[f"{name}/rendered"] for name in ("primary", "alternate"))
        assert primary["source_provenance"] == alternate["source_provenance"]
        assert primary["abstract_syntax"] == alternate["abstract_syntax"]
        assert primary["admitted_ir"] != alternate["admitted_ir"]
        assert primary["observations"] != alternate["observations"]
        results[profile] = snapshots

    primary_irs = {profiles["primary/rendered"]["admitted_ir"] for profiles in results.values()}
    assert len(primary_irs) == 1

    controls = {}
    try:
        R.parse("infix/2", R.render("infix/1", term))
    except R.FrontendError:
        controls["unknown_concrete_profile"] = "refused-before-elaboration"
    else:
        raise AssertionError("unexpected profile admission")
    try:
        hybrid.parse('{"profile":"hybrid/1","expression":{"kind":"scalar","expr":"x +"}}')
    except hybrid.HybridError as error:
        assert error.path and error.inner_offset is not None
        controls["embedded_error"] = {"path": error.path, "inner_offset": error.inner_offset}
    else:
        raise AssertionError("unexpected hybrid admission")
    return {"python": platform.python_version(), "profiles": results, "controls": controls,
            "observations": len(results) * 4 * len(R.INPUTS),
            "sources": {str(path.relative_to(HERE.parent)): digest(path.read_bytes())
                        for path in (HERE / "check.py", LEGACY / "run.py",
                                     LEGACY / "profiles.py", HYBRID / "hybrid.py")}}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
