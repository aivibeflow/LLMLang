"""Compare CLI SMT-LIB and native cvc5/Z3 adapter semantics and lifetimes."""
import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import select
from subprocess import PIPE, Popen, run
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread

import cvc5
import z3

HERE = Path(__file__).resolve().parent
PROFILE = "qf-lia-two-equalities/1"
BASIC = "(set-logic QF_LIA)\n(declare-const x Int)\n"


def integers(value):
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError("expected a non-negative Int in fixture scope")
    return value


@dataclass(frozen=True)
class Query:
    equal: int
    excluded: int

    def smt(self):
        return BASIC + f"(assert (= x {integers(self.equal)}))\n(assert (not (= x {integers(self.excluded)})))\n"


def cli(tool, backend, script):
    return run(cli_args(tool, backend), input=script, text=True, capture_output=True, timeout=10)


def cli_args(tool, backend):
    if backend == "z3":
        return [tool, "-in", "-smt2"]
    return [tool, "--lang=smt2", "--incremental"]


def stdout(result):
    assert result.returncode == 0 and "(error" not in result.stdout, (result.stdout, result.stderr)
    return result.stdout


def make_cvc5(fixture, *, limited=False, proofs=False):
    m = cvc5.TermManager()
    s = cvc5.Solver(m)
    s.setOption("incremental", "true")
    s.setOption("produce-models", "true")
    if proofs:
        s.setOption("produce-proofs", "true")
        s.setOption("proof-alethe-res-pivots", "true")
    if limited:
        s.setOption("rlimit-per", "1")
    s.setLogic("QF_LIA")
    x = m.mkConst(m.getIntegerSort(), "x")
    if fixture is not None:
        s.assertFormula(m.mkTerm(cvc5.Kind.EQUAL, x, m.mkInteger(integers(fixture.equal))))
        s.assertFormula(m.mkTerm(cvc5.Kind.NOT,
                                 m.mkTerm(cvc5.Kind.EQUAL, x, m.mkInteger(integers(fixture.excluded)))))
    return m, s, x


def make_z3(fixture, *, limited=False, proofs=False):
    context = z3.Context(proof=proofs)
    s = z3.Solver(ctx=context)
    if limited:
        s.set(rlimit=1)
    x = z3.Int("x", ctx=context)
    if fixture is not None:
        s.add(x == integers(fixture.equal), x != integers(fixture.excluded))
    return context, s, x


def compare_queries(tools):
    evidence = {}
    for value in (1, 3, 7, 15, 27, 43, 89):
        for excluded in (value, value + 1):
            subject = Query(value, excluded)
            expected = "unsat" if value == excluded else "sat"
            script = "(set-option :produce-models true)\n" + subject.smt() + "(check-sat)\n"
            if expected == "sat":
                script += "(get-value (x))\n"
            script += "(exit)\n"
            cli_results = {tool: stdout(cli(getattr(tools, tool), tool, script)).strip()
                           for tool in ("cvc5", "z3")}
            result_cvc5 = make_cvc5(subject)
            result_z3 = make_z3(subject)
            requests = {"cvc5-cli": cli_results["cvc5"].split()[0], "z3-cli": cli_results["z3"].split()[0],
                        "cvc5-api": str(result_cvc5[1].checkSat()), "z3-api": str(result_z3[1].check())}
            assert set(requests.values()) == {expected}
            models = {}
            if expected == "sat":
                for tool, text in cli_results.items():
                    match = re.search(r"\(\(x (\d+)\)\)", text)
                    assert match
                    models[tool + "-cli"] = int(match[1])
                for tool, (_, solver, symbol) in (("cvc5-api", result_cvc5), ("z3-api", result_z3)):
                    models[tool] = (solver.getValue(symbol).getIntegerValue() if tool == "cvc5-api"
                                    else solver.model().eval(symbol).as_long())
                assert all(item == value and item != excluded for item in models.values())
            evidence[f"{value}/{excluded}"] = {
                "verdicts": requests, "models": models, "wire_sha256": sha256(subject.smt().encode()).hexdigest(),
            }
    return evidence


def sessions(tools):
    script = BASIC + """(assert (= x 3))
(check-sat)
(push 1)
(assert (not (= x 3)))
(check-sat)
(pop 1)
(check-sat)
(reset)
(set-logic QF_LIA)
(declare-const x Int)
(assert (= x 7))
(assert (not (= x 3)))
(check-sat)
(exit)
"""
    outcomes = {route + "-cli": stdout(cli(getattr(tools, route), route, script)).split()
                for route in ("cvc5", "z3")}
    manager, native_c, x = make_cvc5(None)
    equal = manager.mkTerm(cvc5.Kind.EQUAL, x, manager.mkInteger(3))
    native_c.assertFormula(equal)
    cvc = [str(native_c.checkSat())]
    native_c.push()
    native_c.assertFormula(manager.mkTerm(cvc5.Kind.NOT, equal))
    cvc.append(str(native_c.checkSat()))
    native_c.pop()
    cvc.append(str(native_c.checkSat()))
    native_c.resetAssertions()
    native_c.assertFormula(manager.mkTerm(cvc5.Kind.EQUAL, x, manager.mkInteger(7)))
    native_c.assertFormula(manager.mkTerm(cvc5.Kind.NOT, equal))
    cvc.append(str(native_c.checkSat()))
    assert native_c.getValue(x).getIntegerValue() == 7
    outcomes["cvc5-api"] = cvc

    _, native_z, xz = make_z3(None)
    native_z.add(xz == 3)
    zed = [str(native_z.check())]
    native_z.push()
    native_z.add(xz != 3)
    zed.append(str(native_z.check()))
    native_z.pop()
    zed.append(str(native_z.check()))
    native_z.reset()
    native_z.add(xz == 7, xz != 3)
    zed.append(str(native_z.check()))
    assert native_z.model().eval(xz).as_long() == 7
    outcomes["z3-api"] = zed
    assert all(value == ["sat", "unsat", "sat", "sat"] for value in outcomes.values())
    return outcomes


def checked_certificates(tools, directory):
    source = Query(3, 3)
    problem = directory / "spec.smt2"
    proof_file = directory / "proof.alethe"
    with problem.open("w") as saved:
        saved.write(source.smt() + "(check-sat)\n(exit)\n")
    command = [tools.cvc5, "--produce-proofs", "--proof-format-mode=alethe",
               "--proof-alethe-res-pivots", "--dump-proofs", problem]
    cli_proof = stdout(run(command, capture_output=True, text=True, timeout=10)).splitlines()
    assert cli_proof[:2] == ["unsat", "("] and cli_proof[-1] == ")"
    _, native, _ = make_cvc5(source, proofs=True)
    assert native.checkSat().isUnsat()
    checked, = native.getProof()
    native_proof = native.proofToString(checked, cvc5.ProofFormat.ALETHE).decode().splitlines()
    assert native_proof[0] == "(" and native_proof[-1] == ")"
    evidence = {}
    for route, script in (("cvc5-cli", cli_proof[2:-1]), ("cvc5-api", native_proof[1:-1])):
        proof_file.write_text("\n".join(script) + "\n")
        result = run([tools.carcara, "check", proof_file, problem], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and result.stdout.strip() == "valid"
        evidence[route] = {"status": "checked", "artifact": sha256(proof_file.read_bytes()).hexdigest()}
        wrong = directory / "different.smt2"
        wrong.write_text(Query(7, 7).smt() + "(check-sat)\n(exit)\n")
        mismatch = run([tools.carcara, "check", proof_file, wrong], capture_output=True, text=True, timeout=10)
        assert mismatch.stdout.strip() != "valid"
    _, zed, _ = make_z3(source, proofs=True)
    assert zed.check() == z3.unsat and zed.proof() is not None
    evidence["z3-api"] = {"status": "raw-proof-only"}
    return evidence


def resource_controls(tools):
    source = Query(3, 4)
    cvc = stdout(cli(tools.cvc5, "cvc5", "(set-option :rlimit-per 1)\n" + source.smt() + "(check-sat)\n(exit)\n"))
    zed = stdout(cli(tools.z3, "z3", "(set-option :rlimit 1)\n" + source.smt() + "(check-sat)\n(exit)\n"))
    native_cvc = str(make_cvc5(source, limited=True)[1].checkSat()).split()[0]
    native_zed = str(make_z3(source, limited=True)[1].check())
    rows = {"cvc5-cli": cvc.strip(), "z3-cli": zed.strip(),
            "cvc5-api": native_cvc, "z3-api": native_zed}
    assert all(value == "unknown" for value in rows.values()), rows
    invalid = Query(True, 4)
    for name, translate in (("smt", Query.smt), ("cvc5", make_cvc5), ("z3", make_z3)):
        try:
            translate(invalid)
        except ValueError:
            rows[f"invalid-literal-{name}"] = "input-refused"
        else:
            raise AssertionError("Boolean admitted as integer")
    raw = ("(set-option :produce-models true)\n" + BASIC
           + "(assert (= x true))\n(check-sat)\n(get-value (x))\n(exit)\n")
    strict = cli(tools.cvc5, "cvc5", raw)
    assert strict.returncode or "(error" in strict.stdout
    translated = stdout(cli(tools.z3, "z3", raw))
    assert translated.split() == ["sat", "((x", "1))"]
    _, native_z, integer = make_z3(None)
    native_z.add(integer == True)
    assert native_z.check() == z3.sat and native_z.model().eval(integer).as_long() == 1
    rows["raw-z3-coerces-boolean-to-int"] = 1
    rows["raw-cvc5-rejects-mixed-sorts"] = "protocol-failure"
    for name in ("cvc5", "z3"):
        malformed = cli(getattr(tools, name), name, BASIC + "(assert @invalid)\n(check-sat)\n(exit)\n")
        assert malformed.returncode or "(error" in malformed.stdout
        rows[f"malformed-wire-{name}"] = "protocol-failure"
    return rows


def hard_clauses(n):
    symbols = [[f"p{i}_{j}" for j in range(n - 1)] for i in range(n)]
    one = [[(name, True) for name in row] for row in symbols]
    separate = [[(symbols[i][j], False), (symbols[k][j], False)]
                for i in range(n) for k in range(i) for j in range(n - 1)]
    return [name for row in symbols for name in row], one + separate


def native_worker(backend):
    names, clauses = hard_clauses(20)
    entered = Event()
    if backend == "z3":
        context = z3.Context()
        solver = z3.Solver(ctx=context)
        variables = {name: z3.Bool(name, ctx=context) for name in names}
        for clause in clauses:
            solver.add(z3.Or(*(variables[name] if positive else z3.Not(variables[name])
                              for name, positive in clause)))

        def worker():
            entered.set()
            answer = solver.check()
            print(str(answer), flush=True)
            if answer == z3.unknown:
                print(solver.reason_unknown(), flush=True)

        running = Thread(target=worker)
        running.start()
        assert entered.wait(3)
        print("ready", flush=True)
        assert sys.stdin.readline().strip() == "interrupt"
        for _ in range(200):
            context.interrupt()
            running.join(timeout=0.01)
            if not running.is_alive():
                return
        raise TimeoutError("cooperative interruption")
    manager = cvc5.TermManager()
    solver = cvc5.Solver(manager)
    solver.setLogic("QF_UF")
    variables = {name: manager.mkConst(manager.getBooleanSort(), name) for name in names}
    for clause in clauses:
        solver.assertFormula(manager.mkTerm(cvc5.Kind.OR, *(variables[name] if positive else
            manager.mkTerm(cvc5.Kind.NOT, variables[name]) for name, positive in clause)))
    print("ready", flush=True)
    print(str(solver.checkSat()), flush=True)


def wait_marker(process):
    assert select.select([process.stdout], [], [], 8)[0], "no cancellation handshake"
    marker = process.stdout.readline().strip().strip('"')
    assert marker == "ready", marker


def process_lifetime(tools):
    results = {}
    for route in ("cvc5-api", "z3-api", "cvc5-cli", "z3-cli"):
        is_api = route.endswith("api")
        name = route.split("-")[0]
        args = ([sys.executable, "-B", __file__, "--worker", name]
                if is_api else cli_args(getattr(tools, name), name))
        with Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True) as process:
            try:
                if not is_api:
                    names, clauses = hard_clauses(20)
                    script = ["(set-logic QF_UF)"]
                    script += [f"(declare-const {symbol} Bool)" for symbol in names]
                    script += ["(assert (or " + " ".join(symbol if positive else f"(not {symbol})"
                               for symbol, positive in clause) + "))" for clause in clauses]
                    process.stdin.write("\n".join([*script, '(echo "ready")', "(check-sat)", ""]))
                    process.stdin.flush()
                wait_marker(process)
                if route == "z3-api":
                    remaining, _ = process.communicate("interrupt\n", timeout=8)
                    assert process.returncode == 0 and remaining.startswith("unknown\n")
                    assert any(word in remaining.lower() for word in ("interrupt", "cancel")), remaining
                    results[route] = "native-context-unknown-after-interrupt"
                else:
                    process.terminate()
                    remaining, _ = process.communicate(timeout=5)
                    assert process.returncode == -15 and not remaining.strip(), (process.returncode, remaining)
                    results[route] = "worker-terminated-without-verdict"
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        fresh = Query(2, 1)
        if route.endswith("cli"):
            assert stdout(cli(getattr(tools, name), name,
                              fresh.smt() + "(check-sat)\n(exit)\n")).strip() == "sat"
        else:
            fresh_solver = (make_cvc5(fresh)[1] if name == "cvc5" else make_z3(fresh)[1])
            assert str(fresh_solver.checkSat() if name == "cvc5" else fresh_solver.check()) == "sat"
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("z3", "cvc5"))
    for name in ("cvc5", "z3", "carcara", "output"):
        parser.add_argument("--" + name, type=Path)
    tools = parser.parse_args()
    if tools.worker:
        return native_worker(tools.worker)
    versions = {}
    for name in ("cvc5", "z3", "carcara"):
        exe = getattr(tools, name).resolve(strict=True)
        setattr(tools, name, exe)
        result = run([exe, "--version"], capture_output=True, text=True, check=True)
        versions[name] = {"version": result.stdout.splitlines()[0], "sha256": sha256(exe.read_bytes()).hexdigest()}
    shared_cvc5, = Path(cvc5.__file__).parent.glob("cvc5_python_base*.so")
    shared_z3 = Path(z3.__file__).parent / "lib/libz3.so"
    cvc5_dependencies = Path(cvc5.__file__).parents[1] / "cvc5.libs"
    layered_library_hashes = {path.name: sha256(path.read_bytes()).hexdigest()
                             for path in sorted(cvc5_dependencies.glob("*.so.*"))}
    assert layered_library_hashes
    assert not hasattr(cvc5.Solver, "interrupt") and hasattr(z3.Context, "interrupt")
    with TemporaryDirectory() as scratch:
        result = {
            "profile": PROFILE, "executables": versions,
            "libraries": {"cvc5": {"version": cvc5.Solver().getVersion().decode(),
                                   "shared_dependencies": layered_library_hashes,
                                   "sha256": sha256(shared_cvc5.read_bytes()).hexdigest()},
                          "z3": {"version": z3.get_full_version(), "sha256": sha256(shared_z3.read_bytes()).hexdigest()}},
            "capabilities": {"cvc5-api-public-interrupt": False, "z3-api-public-interrupt": True,
                             "cvc5-alethe-independent-check": True, "z3-proof-independent-check": False},
            "queries": compare_queries(tools), "protocol_sessions": sessions(tools),
            "certificate_checks": checked_certificates(tools, Path(scratch)),
            "resource_and_type": resource_controls(tools), "cancellation": process_lifetime(tools),
        }
    tools.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
