#!/usr/bin/env python3
"""Exercise typed native actions and exact scoped test and proof receipts."""

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SCHEMA = {
    "compile": ((("source", "c-source"),), (("object", "native-object"),)),
    "link": ((("driver", "native-object"), ("body", "native-object")),
             (("executable", "native-executable"),)),
    "test": ((("executable", "native-executable"), ("cases", "test-cases")),
             (("observations", "test-evidence"),)),
    "proof": ((("subject", "native-executable"), ("statement", "lean-statement"),
               ("premises", "integer-premises")),
              (("checked", "lean-evidence"),)),
}
DRIVER = r"""#include <stdio.h>
int model(int);
int main(void) {
    int value;
    while (scanf("%d", &value) == 1)
        printf("%d\n", model(value));
    return ferror(stdin) || ferror(stdout);
}
"""


class AdmissionError(ValueError):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(payload):
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class Artifact:
    kind: str
    payload: bytes

    @property
    def address(self):
        return digest(self.payload)


def shape(slots):
    return tuple((role, artifact.kind) for role, artifact in slots)


@dataclass(frozen=True)
class Request:
    action: str
    inputs: tuple[tuple[str, Artifact], ...]
    context: tuple[str, ...]

    def address(self):
        if self.action not in SCHEMA or shape(self.inputs) != SCHEMA[self.action][0]:
            raise AdmissionError("input roles and types")
        return digest(encode(["typed-action/1", self.action, self.context,
                             [(role, artifact.kind, artifact.address) for role, artifact in self.inputs]]))


@dataclass(frozen=True)
class Receipt:
    request: str
    outputs: tuple[tuple[str, Artifact], ...]
    claimed_digests: tuple[str, ...]


def seal(request, *outputs):
    if shape(outputs) != SCHEMA[request.action][1]:
        raise AdmissionError("output roles and types")
    return Receipt(request.address(), outputs, tuple(artifact.address for _, artifact in outputs))


def retrieve(request, receipt):
    if request.address() != receipt.request:
        raise AdmissionError("exact action request")
    if shape(receipt.outputs) != SCHEMA[request.action][1]:
        raise AdmissionError("output roles and types")
    if tuple(artifact.address for _, artifact in receipt.outputs) != receipt.claimed_digests:
        raise AdmissionError("output payload digest")
    return receipt.outputs[0][1]


def refusal(action, reason):
    try:
        action()
    except AdmissionError as error:
        if str(error) != reason:
            raise
        return reason
    raise AssertionError(f"Unexpected admission under {reason}")


class Fixture:
    def __init__(self, directory):
        self.directory = directory
        self.gcc = os.environ.get("CC", "gcc")
        self.lean = os.environ.get("LEAN", "lean")
        self.flags = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror")
        self.gcc_version = self.command(self.gcc, "--version").splitlines()[0]
        self.lean_version = self.command(self.lean, "--version").strip()

    def command(self, *args, data=None):
        result = subprocess.run(args, cwd=self.directory, input=data, text=True,
                                capture_output=True, check=True)
        if result.stderr:
            raise AssertionError(result.stderr)
        return result.stdout

    def compile(self, slug, source):
        request = Request("compile", (("source", Artifact("c-source", source.encode())),),
                          (self.gcc_version, "x86_64-linux-gnu", *self.flags))
        request.address()
        (self.directory / f"{slug}.c").write_text(source)
        self.command(self.gcc, *self.flags, "-c", f"{slug}.c", "-o", f"{slug}.o")
        obj = Artifact("native-object", (self.directory / f"{slug}.o").read_bytes())
        return request, seal(request, ("object", obj))

    def link(self, driver, body):
        request = Request("link", (("driver", driver), ("body", body)),
                          (self.gcc_version, "x86_64-linux-gnu"))
        request.address()
        for role, object_file in request.inputs:
            (self.directory / f"{role}.o").write_bytes(object_file.payload)
        self.command(self.gcc, "driver.o", "body.o", "-o", "app")
        program = Artifact("native-executable", (self.directory / "app").read_bytes())
        return request, seal(request, ("executable", program))

    def test(self, program, inputs, value_offset):
        spec = Artifact("test-cases", encode([(value, value + value_offset) for value in inputs]))
        request = Request("test", (("executable", program), ("cases", spec)),
                          ("native-stdio-test/1", "x86_64-linux-gnu"))
        request.address()
        materialized = self.directory / "test-subject"
        materialized.write_bytes(program.payload)
        materialized.chmod(0o700)
        outputs = self.command("./test-subject", data="".join(f"{value}\n" for value in inputs))
        actual = tuple(map(int, outputs.splitlines()))
        assert actual == tuple(value + value_offset for value in inputs)
        record = Artifact("test-evidence", encode({"disposition": "passed", "observations": actual}))
        return request, seal(request, ("observations", record))

    def proof(self, program, offset, input_max, output_max):
        statement = f"∀ x : Int, x ≤ {input_max} → x + {offset} ≤ {output_max}"
        spec = Artifact("lean-statement", statement.encode())
        premises = Artifact("integer-premises", encode({"max": input_max, "arithmetic": "math-int",
                                                        "source_correspondence": "finite fixture only"}))
        request = Request("proof", (("subject", program), ("statement", spec), ("premises", premises)),
                          (self.lean_version, "fixture-axioms/1"))
        request.address()
        source = f"theorem checked : {statement} := by omega\n#print axioms checked\n"
        (self.directory / "Checked.lean").write_text(source)
        stdout = self.command(self.lean, "-DwarningAsError=true", "Checked.lean")
        result = re.fullmatch(r"'checked' depends on axioms: \[([^\]]*)\]\n", stdout)
        allowed = {"propext", "Classical.choice", "Quot.sound"}
        if not ((result and set(result[1].split(", ")) <= allowed)
                or stdout == "'checked' does not depend on any axioms\n"):
            raise AssertionError(stdout)
        record = Artifact("lean-evidence", encode({"theorem_source_sha256": digest(source.encode()),
                                                   "declaration": "checked",
                                                   "axioms": stdout.splitlines()}))
        return request, seal(request, ("checked", record))


def compare(fixture):
    driver_req, driver_receipt = fixture.compile("driver", DRIVER)
    driver = retrieve(driver_req, driver_receipt)
    strategies = {
        "baseline": ("n+(1+1)", 2, (0, 1, 4), 8, 10),
        "equivalent_source": ("n+2", 2, (0, 1, 4), 8, 10),
        "changed_implementation": ("n+3", 3, (0, 1, 4), 8, 11),
        "changed_tests": ("n+(1+1)", 2, (-1, 0, 4), 8, 10),
        "changed_premise": ("n+(1+1)", 2, (0, 1, 4), 6, 10),
    }
    batches, records = {}, {}
    for name, (expr, offset, inputs, maximum, bound) in strategies.items():
        compile_req, compile_rcpt = fixture.compile("body", f"int model(int n) {{ return {expr}; }}\n")
        handle = retrieve(compile_req, compile_rcpt)
        link_req, link_rcpt = fixture.link(driver, handle)
        subject = retrieve(link_req, link_rcpt)
        test = fixture.test(subject, inputs, offset)
        proof = fixture.proof(subject, offset, maximum, bound)
        group = (compile_req, compile_rcpt), (link_req, link_rcpt), test, proof
        batches[name] = {request.action: (request, receipt) for request, receipt in group}
        records[name] = {request.action: {"key": request.address(),
                                         "artifact": retrieve(request, receipt).address}
                         for request, receipt in group}

    base = records["baseline"]
    changes = {name: [stage for stage in base if base[stage]["key"] != row[stage]["key"]]
               for name, row in records.items()}
    assert changes == {"baseline": [], "equivalent_source": ["compile"],
                       "changed_implementation": ["compile", "link", "test", "proof"],
                       "changed_tests": ["test"], "changed_premise": ["proof"]}
    assert records["equivalent_source"]["compile"]["artifact"] == base["compile"]["artifact"]

    test_req, test_rcpt = batches["baseline"]["test"]
    proof_req, proof_rcpt = batches["baseline"]["proof"]
    premise_data = json.loads(proof_req.inputs[2][1].payload)
    premise_data["source_correspondence"] = "different requested applicability"
    new_premise = replace(proof_req, inputs=(
        *proof_req.inputs[:2], ("premises", Artifact("integer-premises", encode(premise_data))),
    ))
    wrong_kind = replace(test_req, inputs=(test_req.inputs[0],
                                           ("cases", Artifact("integer-premises", test_req.inputs[1][1].payload))))
    wrong_output = replace(test_rcpt, outputs=proof_rcpt.outputs)
    link_req, link_rcpt = batches["baseline"]["link"]
    swapped_inputs = replace(link_req, inputs=(("driver", link_req.inputs[1][1]),
                                              ("body", link_req.inputs[0][1])))
    wrong_bytes = Artifact("test-evidence", b"different")
    controls = {
        "input_exact_bytes_wrong_kind": refusal(wrong_kind.address, "input roles and types"),
        "input_missing": refusal(replace(test_req, inputs=test_req.inputs[:1]).address,
                                 "input roles and types"),
        "input_reversed": refusal(replace(proof_req, inputs=tuple(reversed(proof_req.inputs))).address,
                                  "input roles and types"),
        "output_wrong_role": refusal(lambda: retrieve(test_req, wrong_output), "output roles and types"),
        "mismatched_output_digest": refusal(
            lambda: retrieve(test_req, replace(test_rcpt, outputs=(("observations", wrong_bytes),))),
            "output payload digest"),
        "test_changed_cases": refusal(lambda: retrieve(batches["changed_tests"]["test"][0], test_rcpt),
                                      "exact action request"),
        "proof_changed_premise": refusal(lambda: retrieve(batches["changed_premise"]["proof"][0], proof_rcpt),
                                        "exact action request"),
        "same_statement_changed_applicability": refusal(lambda: retrieve(new_premise, proof_rcpt),
                                                         "exact action request"),
        "proof_changed_subject": refusal(
            lambda: retrieve(batches["changed_implementation"]["proof"][0], proof_rcpt),
            "exact action request"),
        "different_same_kind_object_role": refusal(lambda: retrieve(swapped_inputs, link_rcpt),
                                                   "exact action request"),
        "test_as_proof": refusal(lambda: retrieve(proof_req, test_rcpt), "exact action request"),
    }
    return records, changes, controls


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as path:
        fixture = Fixture(Path(path))
        cases, changes, controls = compare(fixture)
    print(json.dumps({
        "schema": "llmlang-typed-action-receipts/1", "python": platform.python_version(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "tools": {"gcc": fixture.gcc_version, "lean": fixture.lean_version},
        "cases": cases, "changed_keys": changes, "refused": controls,
    }, indent=2))
