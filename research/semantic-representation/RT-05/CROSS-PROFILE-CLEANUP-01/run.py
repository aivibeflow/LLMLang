#!/usr/bin/env python3
"""Compare native and explicit teardown of named owned records in Rust and C++."""

from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore

FIELDS = ("alpha", "beta", "gamma")
SLOT = {name: index for index, name in enumerate(FIELDS)}
ORDERS = tuple(permutations(FIELDS))
PROFILES = ("rust", "cpp")
MODES = ("native", "explicit")
RUST = """
use std::cell::RefCell;
struct Token<'a>(i32, &'a RefCell<Vec<i32>>);
impl Drop for Token<'_> {
    fn drop(&mut self) { self.1.borrow_mut().push(-1 - self.0); }
}
fn acquire(id: i32, mask: u8, events: &RefCell<Vec<i32>>) -> Result<Token<'_>, i32> {
    events.borrow_mut().push(id + 1);
    if mask & (1 << id) != 0 { return Err(id + 1); }
    events.borrow_mut().push(id + 11);
    Ok(Token(id, events))
}
"""
CPP = """
#include <iostream>
#include <optional>
#include <utility>
#include <vector>

struct Failure { int code; };
struct Token {
    int id;
    std::vector<int>* events;
    Token(int value, std::vector<int>& log): id(value), events(&log) {}
    Token(const Token&) = delete;
    Token(Token&& other) noexcept: id(other.id), events(std::exchange(other.events, nullptr)) {}
    ~Token() { if (events != nullptr) events->push_back(-1 - id); }
};
Token acquire(int id, int mask, std::vector<int>& log) {
    log.push_back(id + 1);
    if ((mask & (1 << id)) != 0) throw Failure{id + 1};
    log.push_back(id + 11);
    return Token{id, log};
}
"""


def rust_source(cases):
    chunks = [RUST]
    for callee, order in enumerate(ORDERS):
        fields = ", ".join(f"{name}: Option<Token<'a>>" for name in order)
        chunks.append(f"struct Record{callee}<'a> {{ {fields} }}")
    for index, decl, init, mode in cases:
        acquired = [f"let tmp_{field} = acquire({SLOT[field]}, mask, events)?;" for field in init]
        members = ", ".join(f"{name}: Some(tmp_{name})" for name in FIELDS)
        extracts = "\n".join(f"            {slot} => record.{field}.take()," for field, slot in SLOT.items())
        finalize = "\n        ".join(f"drop(record.{name}.take());" for name in decl) if mode == "explicit" else ""
        setup = "\n        ".join(acquired)
        chunks.append(f"""
fn case_{index}(mask: u8, retain: u8, events: &RefCell<Vec<i32>>) -> Result<(), i32> {{
    let transferred = {{
        {setup}
        let mut record = Record{ORDERS.index(decl)} {{ {members} }};
        events.borrow_mut().push(30);
        let transferred = match retain {{
{extracts}
            _ => None
        }};
        {finalize}
        transferred
    }};
    events.borrow_mut().push(40);
    drop(transferred);
    Ok(())
}}
""")
    routes = ", ".join(f"case_{index}" for index, *_ in cases)
    chunks.append(f"""
fn main() {{
    let cases: &[fn(u8, u8, &RefCell<Vec<i32>>) -> Result<(), i32>] = &[{routes}];
    for (index, case) in cases.iter().enumerate() {{
        for mask in 0..8 {{
            for retain in 0..4 {{
                let events = RefCell::new(Vec::new());
                let status = case(mask, retain, &events).err().unwrap_or(0);
                println!("[{{}}, {{}} , {{}} , [{{}}, {{:?}}]]", index, mask, retain, status, events.into_inner());
            }}
        }}
    }}
}}
""")
    return "\n".join(chunks)


def cpp_source(cases):
    chunks = [CPP]
    for index, order in enumerate(ORDERS):
        fields = " ".join(f"std::optional<Token> {name};" for name in order)
        chunks.append(f"struct Record{index} {{ {fields} }};")
    for index, decl, init, mode in cases:
        acquired = [f"auto tmp_{field} = acquire({SLOT[field]}, mask, events);" for field in init]
        members = ", ".join(f"std::move(tmp_{name})" for name in decl)
        extracts = "\n".join(
            f"        case {slot}: transferred.emplace(std::move(*record.{field})); record.{field}.reset(); break;"
            for field, slot in SLOT.items())
        finalize = "\n        ".join(f"record.{field}.reset();" for field in decl) if mode == "explicit" else ""
        setup = "\n        ".join(acquired)
        chunks.append(f"""
void case_{index}(int mask, int retain, std::vector<int>& events) {{
    std::optional<Token> transferred;
    {{
        {setup}
        auto record = Record{ORDERS.index(decl)}{{ {members} }};
        events.push_back(30);
        switch (retain) {{
{extracts}
        }}
        {finalize}
    }}
    events.push_back(40);
    transferred.reset();
}}
""")
    routes = ", ".join(f"case_{index}" for index, *_ in cases)
    chunks.append(f"""
int main() {{
    void (*cases[])(int, int, std::vector<int>&) = {{ {routes} }};
    for (unsigned index = 0; index < sizeof(cases) / sizeof(cases[0]); ++index)
        for (int mask = 0; mask < 8; ++mask)
            for (int retain = 0; retain < 4; ++retain) {{
                int status = 0;
                std::vector<int> events;
                events.reserve(16);
                try {{ cases[index](mask, retain, events); }}
                catch (Failure error) {{ status = error.code; }}
                std::cout << "[" << index << "," << mask << "," << retain << ",[" << status << ",[";
                for (unsigned i = 0; i < events.size(); ++i) {{
                    if (i) std::cout << ",";
                    std::cout << events[i];
                }}
                std::cout << "]]]" << std::endl;
            }}
}}
""")
    return "\n".join(chunks)


def oracle(decl, init, mode, profile, mask, retain):
    sequence = [SLOT[name] for name in init]
    failing = next((index for index, slot in enumerate(sequence) if mask & (1 << slot)), None)
    started = sequence if failing is None else sequence[:failing]
    events = [event for slot in started for event in (slot + 1, slot + 11)]
    if failing is not None:
        failed = sequence[failing] + 1
        return [failed, [*events, failed, *[-slot - 1 for slot in started[::-1]]]]
    drop_fields = decl[::-1] if profile == "cpp" and mode == "native" else decl
    drop_ids = [SLOT[name] for name in drop_fields if SLOT[name] != retain]
    late = [-retain - 1] if retain < len(FIELDS) else []
    return [0, [*events, 30, *[-slot - 1 for slot in drop_ids], 40, *late]]


def bind(store, decl, init, mode, profile):
    order = decl[::-1] if profile == "cpp" and mode == "native" else decl
    graph = {
        "type": "named-owned-token-record", "roles": SLOT, "acquisition": init,
        "on_failure": "drop_reverse_prefix", "on_success": order,
        "transfer": "release_after_record_scope",
    }
    return store.put("rt05-cross-record-profile-v1", graph)


def evaluate(graph, mask, retain):
    events, owned = [], []
    roles = graph["roles"]
    for role in graph["acquisition"]:
        slot = roles[role]
        events.append(slot + 1)
        if mask & (1 << slot):
            while owned:
                events.append(-1 - owned.pop())
            return [slot + 1, events]
        owned.append(slot)
        events.append(slot + 11)
    events.append(30)
    for role in graph["on_success"]:
        slot = roles[role]
        if slot != retain:
            events.append(-1 - slot)
    events.append(40)
    if retain in owned:
        events.append(-1 - retain)
    return [0, events]


def native(path, compiler, opt, directory):
    exe = directory / f"{path.stem}-{opt}"
    flags = ["--edition=2021", "-C", f"opt-level={opt}"] if compiler == "rustc" else ["-std=c++20", f"-O{opt}"]
    subprocess.run([compiler, *flags, str(path), "-o", str(exe)], check=True)
    data = [json.loads(line) for line in subprocess.check_output([str(exe)], text=True).splitlines()]
    result = {(index, mask, retain): observation for index, mask, retain, observation in data}
    assert len(result) == len(data)
    return result


def run(directory):
    cases = [(index, decl, init, mode) for index, (decl, init, mode) in
             enumerate(product(ORDERS, ORDERS, MODES))]
    sources = {"rust": directory / "records.rs", "cpp": directory / "records.cc"}
    compilers = {"rust": "rustc", "cpp": "g++"}
    sources["rust"].write_text(rust_source(cases), encoding="utf-8")
    sources["cpp"].write_text(cpp_source(cases), encoding="utf-8")
    measured = {(profile, opt): native(sources[profile], compilers[profile], opt, directory)
                for profile, opt in product(PROFILES, (0, 3))}
    assert all(len(results) == len(cases) * 32 for results in measured.values())
    assert all(measured[profile, 0] == measured[profile, 3] for profile in PROFILES)

    store = ContentStore()
    metrics = {mode: Counter() for mode in MODES}
    evidence = []
    for index, decl, init, mode in cases:
        hashes = {profile: bind(store, decl, init, mode, profile) for profile in PROFILES}
        metrics[mode]["identical_hash_pairs"] += hashes["rust"] == hashes["cpp"]
        observations = []
        for mask, retain in product(range(8), range(4)):
            checked = {}
            for profile in PROFILES:
                result = measured[profile, 0][index, mask, retain]
                expected = oracle(decl, init, mode, profile, mask, retain)
                graph = store.get(hashes[profile]).payload
                assert result == expected == evaluate(graph, mask, retain)
                acquired = sorted(event - 11 for event in result[1] if 11 <= event <= 13)
                released = sorted(-1 - event for event in result[1] if event < 0)
                assert acquired == released
                checked[profile] = result
            if checked["rust"] != checked["cpp"]:
                metrics[mode]["abort_differences" if mask else "completed_differences"] += 1
            observations.append(checked)
        evidence.append({"case": index, "declaration": decl, "acquisition": init, "mode": mode,
                         "exact_graphs": hashes, "observations": observations})

    assert metrics["native"]["identical_hash_pairs"] == metrics["native"]["abort_differences"] == 0
    assert metrics["native"]["completed_differences"] > 0
    assert metrics["explicit"]["identical_hash_pairs"] == len(cases) // 2
    assert metrics["explicit"]["completed_differences"] == metrics["explicit"]["abort_differences"] == 0
    return {
        "schema": "llmlang-rt05-cross-profile-cleanup/1", "python": platform.python_version(),
        "compiler_versions": {"rust": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
                              "cpp": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]},
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {profile: sha256(sources[profile].read_bytes()).hexdigest() for profile in PROFILES},
        "source_cases_per_profile": len(cases), "masks": list(range(8)), "retains": [*FIELDS, "none"],
        "native_observations": sum(map(len, measured.values())),
        "cpp_target": subprocess.check_output(["g++", "-dumpmachine"], text=True).strip(),
        "metrics": {mode: {key: metrics[mode][key] for key in
                          ("identical_hash_pairs", "abort_differences", "completed_differences")} for mode in MODES},
        "observations": evidence,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-cross-record-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
