"""Cross-check independently authored syntax strings with a direct observation oracle."""

from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
RT31 = HERE.parents[2] / "language-design" / "RT-31" / "CROSS-PROFILE-SPG-01"
BASELINE = "cfed7169d95ba816b98ce77a59f5f339fcf3c141"
sys.path.insert(0, str(RT31))

from run import make_program, compile_program, observe, encode, parse, validate


def replay():
    sources = json.loads((HERE / "sources.json").read_bytes())
    variants = {}
    for call, binding in product(sources, ("primary", "alternate")):
        encoded = []
        observations = []
        for profile, text in sources[call].items():
            graph = compile_program(make_program(binding, parse(profile, text)))
            validate(graph)
            encoded.append(encode(graph))
            for value, choose in product((-17, -2, -1, 0, 1, 7, 23), (False, True)):
                expected = (value - 2, ("fallback",))
                if choose:
                    result = 8 if call == "operation" and binding == "alternate" else -3
                    expected = (result, ("left", "right", "compute"))
                observed = observe(graph, "entry", (value, choose))
                assert observed == expected, (profile, call, binding, value, choose)
                observations.append({"profile": profile, "input": [value, choose], "value": observed[0],
                                     "ordered_trace": observed[1]})
        assert len(set(encoded)) == 1
        variants[f"{call}:{binding}"] = {"graph": sha256(encoded[0]).hexdigest(), "observations": observations}
    assert all(variants[f"operation:{binding}"]["graph"] != variants[f"pin:{binding}"]["graph"]
               for binding in ("primary", "alternate"))
    assert variants["operation:primary"]["observations"] == variants["pin:primary"]["observations"]
    assert variants["operation:alternate"]["observations"] != variants["pin:alternate"]["observations"]
    return {
        "schema": "rt05-hand-authored-syntax-spg-replay-v1", "baseline": BASELINE,
        "python": platform.python_version(),
        "fixture_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                           for path in (HERE / "observe.py", HERE / "sources.json", RT31 / "run.py", RT31 / "profiles.py")},
        "upstream_ledger_sha256": sha256((RT31 / "evidence.json").read_bytes()).hexdigest(),
        "variants": variants,
    }


if __name__ == "__main__":
    print(json.dumps(replay(), sort_keys=True, indent=2))
