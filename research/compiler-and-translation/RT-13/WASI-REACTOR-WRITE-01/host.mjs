import { deepStrictEqual, throws } from "node:assert/strict";
import { createHash } from "node:crypto";
import { closeSync, openSync, readFileSync } from "node:fs";
import { WASI } from "node:wasi";

const [wasm, output] = process.argv.slice(2);
const module = new WebAssembly.Module(readFileSync(wasm));
const inputs = [];
for (const fd of [1, 9]) {
    for (const a of [0, 1, 2, 7, 8, 9, 0xffffffff]) {
        for (const b of [0, 1, 2, 7, 8, 9, 0xffffffff]) {
            for (const seed of [0, 37, 127, 250, 255, 0xffffffff]) {
                inputs.push([fd, a, b, seed]);
            }
        }
    }
}
const hash = data => createHash("sha256").update(data).digest("hex");
const contract = ([fd, a, b, seed], policy) => {
    if (a > 8 || b > 8) {
        return [255 << 16, []];
    }
    if (fd !== 1) {
        return [8 << 16, []];
    }
    const bytes = [
        ...Array.from({ length: a }, (_, index) => (seed + index) & 255),
        ...Array.from({ length: b }, (_, index) => (seed + 32 + index) & 255),
    ];
    if (policy === "over-report") {
        return [254 << 16, []];
    }
    const accepted = policy === "partial" ? bytes.slice(0, 3) : bytes;
    return [accepted.length, accepted];
};
const imports = WebAssembly.Module.imports(module);
deepStrictEqual(imports, [
    { module: "wasi_snapshot_preview1", name: "fd_write", kind: "function" },
]);
throws(() => new WebAssembly.Instance(module, { wasi_snapshot_preview1: {} }), WebAssembly.LinkError);
const stream = openSync(output, "w");
const createWasi = () => new WASI({ version: "preview1", args: [], env: {}, preopens: {}, stdout: stream });
const commandWasi = createWasi();
const reactor = new WebAssembly.Instance(module, commandWasi.getImportObject());
throws(() => commandWasi.start(reactor));
const wasi = createWasi();
const instance = new WebAssembly.Instance(module, wasi.getImportObject());
deepStrictEqual(instance.exports.emit(1, 1, 1, 0), 253 << 16);
wasi.initialize(instance);
const expectedStream = [];
const real = [];
for (const input of inputs) {
    const [status, bytes] = contract(input, "full");
    const observed = instance.exports.emit(...input) >>> 0;
    deepStrictEqual(observed, status, JSON.stringify(input));
    real.push(observed);
    expectedStream.push(...bytes);
}
closeSync(stream);
const written = readFileSync(output);
deepStrictEqual(written, Buffer.from(expectedStream));

const simulated = {};
for (const policy of ["partial", "over-report"]) {
    let mock;
    let emitted = [];
    let invocations = 0;
    const fd_write = (fd, vectors, count, written) => {
        ++invocations;
        if (fd !== 1) {
            return 8;
        }
        deepStrictEqual(count, 2);
        const memory = mock.exports.memory.buffer;
        const view = new DataView(memory);
        const requested = [];
        for (let i = 0; i < count; ++i) {
            const position = view.getUint32(vectors + i * 8, true);
            const length = view.getUint32(vectors + i * 8 + 4, true);
            requested.push(...new Uint8Array(memory, position, length));
        }
        if (policy === "partial") {
            emitted = requested.slice(0, 3);
            view.setUint32(written, emitted.length, true);
        } else {
            view.setUint32(written, requested.length + 1, true);
        }
        return 0;
    };
    mock = new WebAssembly.Instance(module, { wasi_snapshot_preview1: { fd_write } });
    deepStrictEqual(mock.exports.emit(1, 1, 1, 0), 253 << 16);
    deepStrictEqual(invocations, 0);
    mock.exports._initialize();
    const observations = [];
    for (const input of inputs) {
        emitted = [];
        const before = invocations;
        const returned = mock.exports.emit(...input) >>> 0;
        const result = [returned, emitted];
        deepStrictEqual(result, contract(input, policy), JSON.stringify(input));
        deepStrictEqual(invocations - before, Number(input[1] <= 8 && input[2] <= 8));
        observations.push(result);
    }
    simulated[policy] = {
        observations: observations.length, host_calls: invocations, trace_sha256: hash(JSON.stringify(observations)),
    };
}
process.stdout.write(JSON.stringify({
    inputs: inputs.length,
    output_bytes: written.length,
    output_sha256: hash(written),
    real_status_sha256: hash(JSON.stringify(real)),
    missing_import: "refused", reactor_as_command: "refused", uninitialized_emit: "refused",
    simulated,
}));
