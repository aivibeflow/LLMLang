#!/usr/bin/env python3
"""Compare exact temporal requests on TLC CLI/Java and Apalache CLI/Shai gRPC."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from shutil import which
import signal
import socket
import subprocess
import sys
import tempfile
import time

import grpc
import google.protobuf
import cmdExecutor_pb2 as messages
import cmdExecutor_pb2_grpc as service


HERE = Path(__file__).resolve().parent
CAPABILITIES = {
    "tlc-cli": ("finite-safety", "finite-liveness"),
    "tlc-java": ("finite-safety", "finite-liveness"),
    "apalache-cli": ("bounded-safety",),
    "apalache-grpc": ("bounded-safety",),
}
MODEL = (HERE / "Probe.tla").read_text()
INHERITED_TOOL_SETTINGS = {
    "APALACHE_JAR", "CONFIG_FILE", "OUT_DIR", "RUN_DIR", "SMT_ENCODING", "SMT_SOLVER",
    "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "JVM_GC_ARGS", "TMPDIR",
}
ENV = {key: value for key, value in os.environ.items() if key not in INHERITED_TOOL_SETTINGS}
ENV.update({"LC_ALL": "C", "TZ": "UTC", "JVM_ARGS": "-Xmx512m"})
TLC_FLAGS = ["-workers", "1", "-fp", "0", "-seed", "811", "-checkpoint", "0"]


@dataclass(frozen=True)
class Task:
    kind: str
    property: str
    bound: int | None = None
    weak_fairness: bool = True


def digest(data):
    return sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def source(task):
    return MODEL if task.weak_fairness else MODEL.replace(" /" + chr(92) + " WF_x(Next)", "")


def supports(route, task):
    bound_valid = (type(task.bound) is int and task.bound >= 0 if task.kind == "bounded-safety"
                   else task.bound is None)
    return bound_valid and task.kind in CAPABILITIES[route]


def request_digest(route, task, model):
    envelope = {"route": route, "task": asdict(task), "source_sha256": digest(model.encode())}
    return digest(canonical(envelope).encode())


def next_value(value):
    return min(4, value + 1)


def oracle(task):
    if task.property == "Missing":
        return "missing-property"
    if task.kind == "finite-liveness":
        # A single stuttering self-loop below the target violates weak fairness
        # because Next can advance continuously there. Without fairness it is allowed.
        possible_cycles = range(4)
        violating_cycles = [x for x in possible_cycles
                            if not task.weak_fairness or next_value(x) == x]
        return "temporal-violation" if violating_cycles else "checked"
    last = 4 if task.bound is None else task.bound
    limit = {"Safe": 4, "TooLow": 2}[task.property]
    reachable = [0]
    for _ in range(last):
        reachable.append(next_value(reachable[-1]))
    return "safety-violation" if max(reachable) > limit else "checked"


def check_witness(task, values, loop=None):
    assert values and all(type(value) is int for value in values)
    assert values[0] == 0
    assert all(next_value(left) == right for left, right in zip(values, values[1:]))
    assert task.bound is None or len(values) <= task.bound + 1
    if loop is not None:
        assert not task.weak_fairness and loop == len(values) - 1 and all(x < 4 for x in values)
    else:
        limit = {"Safe": 4, "TooLow": 2}[task.property]
        assert all(x <= limit for x in values[:-1]) and values[-1] > limit


def itf_values(trace):
    assert trace["vars"] == ["x"] and trace["#meta"]["varTypes"] == {"x": "Int"}
    indices = [item["#meta"]["index"] for item in trace["states"]]
    assert indices == list(range(len(indices)))
    values = [item["x"]["#bigint"] for item in trace["states"]]
    assert all(isinstance(value, str) and re.fullmatch(r"0|-?[1-9]\d*", value)
               for value in values)
    return [int(value) for value in values]


def capture(command, directory):
    result = subprocess.run(command, cwd=directory, env=ENV, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=40)
    return result.returncode, result.stdout


def config_tlc(task):
    selection = (f"SPECIFICATION Spec\nPROPERTY {task.property}\n" if task.kind == "finite-liveness"
                 else f"INIT Init\nNEXT Next\nINVARIANT {task.property}\n")
    return selection + "CHECK_DEADLOCK FALSE\n"


def tlc_command(args, route):
    entry = "tlc2.TLC" if route == "tlc-cli" else HERE / "TlcDriver.java"
    return [args.java, "-Xmx512m", "-XX:+UseParallelGC", "-cp", args.tlc, entry,
            *TLC_FLAGS, "-metadir", "states", "-dumpTrace", "json", "trace.json",
            "-config", "Probe.cfg", "Probe.tla"]


def tlc_case(args, route, task, directory):
    cfg = config_tlc(task)
    (directory / "Probe.cfg").write_text(cfg)
    code, output = capture(tlc_command(args, route), directory)
    row = {"exit": code, "native_config_sha256": digest(cfg.encode())}
    if route == "tlc-java":
        [raw_code] = re.findall(r"^TLC_DRIVER_RESULT (\d+)$", output, re.M)
        row["java_result_code"] = int(raw_code)
    if code == 0:
        assert "Model checking completed. No error has been found." in output
        assert "5 distinct states found, 0 states left on queue." in output
        if task.kind == "finite-liveness":
            assert "Checking temporal properties for the complete state space" in output
        return {**row, "disposition": "checked", "reachable_states": 5}
    if task.property == "Missing":
        assert "Missing" in output and not (directory / "trace.json").exists(), output
        return {**row, "disposition": "missing-property"}
    raw = json.loads((directory / "trace.json").read_text())
    assert raw["vars"] == ["x"]
    violation = raw["counterexample"]
    indices = [index for index, _ in violation["state"]]
    assert indices == list(range(1, len(indices) + 1))
    values = [state["x"] for _, state in violation["state"]]
    for start, action, end in violation["action"]:
        assert action["name"] == "Next"
        assert start[1] == {"x": values[start[0] - 1]} and end[1] == {"x": values[end[0] - 1]}
    action_pairs = [(start[0], end[0]) for start, _, end in violation["action"]]
    assert action_pairs[:len(values) - 1] == list(zip(indices, indices[1:]))
    if "Temporal property Eventually was violated" in output:
        assert "Stuttering" in output and action_pairs[-1] == (indices[-1], indices[-1])
        check_witness(task, values, loop=len(values) - 1)
        return {**row, "disposition": "temporal-violation", "states": values,
                "action_pairs": action_pairs, "stuttering_at": len(values) - 1}
    assert f"Invariant {task.property} is violated." in output and len(action_pairs) == len(values) - 1
    check_witness(task, values)
    return {**row, "disposition": "safety-violation", "states": values, "action_pairs": action_pairs}


def apa_command(args, task):
    return [args.apalache, "--out-dir=analysis", "check", "--init=Init", "--next=Next",
            f"--length={task.bound}", f"--inv={task.property}", "--no-deadlock=true", "Probe.tla"]


def apa_case(args, task, directory):
    command = apa_command(args, task)
    code, output = capture(command, directory)
    row = {"exit": code, "native_arguments": command[1:]}
    if code == 0:
        assert "Checker reports no error up to computation length" in output
        return {**row, "disposition": "checked", "bound": task.bound}
    if task.property == "Missing":
        assert "Operator Missing not found (used as an invariant)" in output
        return {**row, "disposition": "missing-property"}
    assert code == 12 and "state invariant 0 violated" in output
    [trace] = (directory / "analysis").rglob("violation1.itf.json")
    values = itf_values(json.loads(trace.read_text()))
    check_witness(task, values)
    return {**row, "disposition": "safety-violation", "states": values}


def rpc_config(task):
    return {"source": {"content": source(task)},
            "checker": {"init": "Init", "next": "Next", "length": task.bound,
                        "inv": [task.property], "no-deadlock": True}}


def rpc_case(stub, task):
    assert supports("apalache-grpc", task)
    config = canonical(rpc_config(task))
    request = messages.CmdRequest(cmd=messages.CHECK, config=config)
    response, call = stub.run.with_call(request, timeout=20)
    assert call.code() == grpc.StatusCode.OK
    row = {"transport": "OK", "config_sha256": digest(config.encode())}
    result = response.WhichOneof("result")
    if result == "success":
        data = json.loads(response.success)
        assert data["name"] == "ApalacheIR" and data["version"] == "1.0"
        assert [item["name"] for item in data["modules"]] == ["Probe"]
        return {**row, "disposition": "checked", "bound": task.bound}
    assert result == "failure"
    data = json.loads(response.failure.data)
    row["application_error"] = messages.CmdErrorType.Name(response.failure.errorType)
    if task.property == "Missing":
        assert row["application_error"] == "UNEXPECTED" and "Operator Missing not found" in data["msg"]
        return {**row, "disposition": "missing-property"}
    assert row["application_error"] == "PASS_FAILURE" and data["pass_name"] == "BoundedChecker"
    assert data["exit_code"] == 12 and data["error_data"]["checking_result"] == "Error"
    [trace] = data["error_data"]["counterexamples"]
    values = itf_values(trace)
    check_witness(task, values)
    return {**row, "disposition": "safety-violation", "states": values}


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        return process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        return process.wait(timeout=6)


def local_server(args, root, cases):
    directory = root / "rpc"
    directory.mkdir()
    library = directory / "loopback.so"
    subprocess.run([args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-shared",
                    "-fPIC", HERE / "loopback.c", "-o", library], check=True)
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    env = {**ENV, "LD_PRELOAD": str(library),
           "JVM_ARGS": ENV["JVM_ARGS"] + " -Djava.net.preferIPv4Stack=true"
           " -Dio.grpc.netty.shaded.io.netty.transport.noNative=true"}
    with (directory / "server.log").open("w") as output:
        process = subprocess.Popen([args.apalache, "--out-dir=analysis", "server",
                                    "--server-type=checker", f"--port={port}"],
                                   cwd=directory, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
                grpc.channel_ready_future(channel).result(20)
                endpoints = []
                for table in ("/proc/net/tcp", "/proc/net/tcp6"):
                    for line in Path(table).read_text().splitlines()[1:]:
                        _, local, _, state, *_ = line.split()
                        if local.endswith(f":{port:04X}") and state == "0A":
                            endpoints.append(local.split(":")[0])
                assert endpoints == ["0100007F"], endpoints
                stub = service.CmdExecutorStub(channel)
                assert stub.ping(messages.PingRequest(), timeout=5) == messages.PongResponse()
                results = {key: rpc_case(stub, task) for key, task in cases.items()}
                try:
                    stub.run(messages.CmdRequest(cmd=messages.CHECK,
                                                 config='{"source":"Probe.tla"}'), timeout=5)
                except grpc.RpcError as error:
                    assert error.code() == grpc.StatusCode.INVALID_ARGUMENT and "$.source" in error.details()
                else:
                    raise AssertionError("a file-backed request unexpectedly succeeded")
                valid = messages.CmdRequest(cmd=messages.CHECK,
                                            config=canonical(rpc_config(cases["safe"])))
                try:
                    stub.run(valid, timeout=0.001)
                except grpc.RpcError as error:
                    assert error.code() == grpc.StatusCode.DEADLINE_EXCEEDED
                else:
                    raise AssertionError("the 1 ms client deadline unexpectedly yielded a result")
                assert stub.ping(messages.PingRequest(), timeout=5) == messages.PongResponse()
                assert rpc_case(stub, cases["safe"])["disposition"] == "checked"
                return results, {"listener": "IPv4 loopback", "file_source": "INVALID_ARGUMENT",
                                 "deadline_1ms": "DEADLINE_EXCEEDED", "following_ping_and_check": "ok"}
        finally:
            terminate(process)


def cancel_cli(args, root, route):
    directory = root / f"{route}-cancel"
    directory.mkdir()
    model = MODEL.replace("x < 4", "x < 100000000").replace("x <= 4", "x <= 100000000")
    (directory / "Probe.tla").write_text(model)
    if route == "apalache-cli":
        command = apa_command(args, Task("bounded-safety", "Safe", 100000))
        ready = ": BoundedChecker"
    else:
        (directory / "Probe.cfg").write_text(config_tlc(Task("finite-safety", "Safe")))
        command = tlc_command(args, route)
        ready = "Finished computing initial states:"
    log = directory / "cancel.log"
    with log.open("w") as output:
        process = subprocess.Popen(command, cwd=directory, env=ENV, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 35
            while ready not in log.read_text():
                assert process.poll() is None and time.monotonic() < deadline, log.read_text()
                time.sleep(0.01)
            assert process.poll() is None
        finally:
            code = terminate(process)
    content = log.read_text()
    assert code != 0 and "Checker reports no error" not in content and "No error has been found" not in content
    return {"observed_start": ready, "exit": code, "disposition": "host-cancelled"}


def run(args, root):
    cases = {
        "safe": Task("bounded-safety", "Safe", 4),
        "shallow": Task("bounded-safety", "TooLow", 2),
        "violation": Task("bounded-safety", "TooLow", 3),
        "missing": Task("bounded-safety", "Missing", 4),
    }
    finite = {name: replace(task, kind="finite-safety", bound=None) for name, task in cases.items()
              if name != "shallow"}
    finite.update({"fair": Task("finite-liveness", "Eventually"),
                   "unfair": Task("finite-liveness", "Eventually", weak_fairness=False)})

    def local_route(route):
        rows = {}
        for key, task in (cases if route == "apalache-cli" else finite).items():
            assert supports(route, task)
            directory = root / f"{route}-{key}"
            directory.mkdir()
            (directory / "Probe.tla").write_text(source(task))
            rows[key] = (apa_case(args, task, directory) if route == "apalache-cli"
                         else tlc_case(args, route, task, directory))
        return rows

    with ThreadPoolExecutor(max_workers=2) as pool:
        routes = list(CAPABILITIES)[:3]
        outcomes = dict(zip(routes, pool.map(local_route, routes)))
    outcomes["apalache-grpc"], protocol_controls = local_server(args, root, cases)
    for route, rows in outcomes.items():
        for key, row in rows.items():
            task = (cases if route.startswith("apalache") else finite)[key]
            assert row["disposition"] == oracle(task), (route, key, row)
            row.update({"request": asdict(task), "source_sha256": digest(source(task).encode()),
                        "request_sha256": request_digest(route, task, source(task))})
    for routes in (("tlc-cli", "tlc-java"), ("apalache-cli", "apalache-grpc"),
                   ("tlc-cli", "apalache-cli")):
        assert outcomes[routes[0]]["violation"]["states"] == outcomes[routes[1]]["violation"]["states"]
    refused_requests = [
        ("tlc-cli", cases["shallow"]),
        ("tlc-java", cases["shallow"]),
        ("apalache-cli", finite["fair"]),
        ("apalache-grpc", finite["fair"]),
        ("apalache-cli", replace(cases["safe"], bound=None)),
        ("apalache-grpc", replace(cases["safe"], bound=-1)),
    ]
    assert all(not supports(route, task) for route, task in refused_requests)
    task = cases["violation"]
    original_id = outcomes["apalache-grpc"]["violation"]["request_sha256"]
    changed = {
        "route": request_digest("apalache-cli", task, source(task)),
        "bound": request_digest("apalache-grpc", replace(task, bound=2), source(task)),
        "property": request_digest("apalache-grpc", replace(task, property="Safe"), source(task)),
        "source": request_digest("apalache-grpc", task, source(task) + "\n"),
    }
    assert all(identity != original_id for identity in changed.values())
    rejected_traces = {
        "wrong-type": [0, 1, 2, "3"],
        "bad-transition": [0, 2, 3],
        "no-violation": [0, 1, 2],
        "longer-than-bound": [0, 1, 2, 3, 4],
    }
    for values in rejected_traces.values():
        try:
            check_witness(task, values)
        except AssertionError:
            pass
        else:
            raise AssertionError(("accepted malformed witness", values))
    return {"capabilities": CAPABILITIES, "observations": outcomes, "grpc_controls": protocol_controls,
            "refused_requests": [{"route": route, "request": asdict(task)} for route, task in refused_requests],
            "request_identity_mutations": changed,
            "rejected_trace_mutations": rejected_traces,
            "host_cancellation": {route: cancel_cli(args, root, route) for route in CAPABILITIES
                                  if route != "apalache-grpc"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", default=which("java"))
    parser.add_argument("--cc", default=which("cc"))
    parser.add_argument("--tlc", type=lambda s: Path(s).resolve(), required=True)
    parser.add_argument("--apalache", type=lambda s: Path(s).resolve(), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert digest(args.tlc.read_bytes()) == "fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713"
    args.java = str(Path(args.java).resolve())
    ENV["PATH"] = str(Path(args.java).parent) + os.pathsep + ENV["PATH"]
    jar = args.apalache.parent.parent / "lib" / "apalache.jar"
    assert digest(jar.read_bytes()) == "f2d43f2e279a657be50b2ecec3a013ba2915266008a2562b38412c3269347dc9"
    ENV["APALACHE_JAR"] = str(jar)
    assert grpc.__version__ == "1.80.0" and google.protobuf.__version__ == "6.33.6"
    with tempfile.TemporaryDirectory(prefix="rt33-temporal-adapters-") as scratch:
        directory = Path(scratch)
        code, java = capture([args.java, "-version"], directory)
        assert code == 0 and "21.0.13" in java
        assert (3, 12) == sys.version_info[:2]
        result = run(args, directory)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
