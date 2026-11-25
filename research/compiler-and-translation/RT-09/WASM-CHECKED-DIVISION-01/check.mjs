import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { deepStrictEqual, throws } from "node:assert/strict";

const [file, scope, binding] = process.argv.slice(2);
const binary = readFileSync(file);
if (!WebAssembly.validate(binary)) {
    throw new Error("exact module failed engine validation");
}
const module = new WebAssembly.Module(binary);
const imports = WebAssembly.Module.imports(module);
deepStrictEqual(
    imports,
    scope === "pure" ? [] : [{ module: "host", name: "audit", kind: "function" }],
);

const events = [];
const audit = (tag, first, second) => {
    events.push([binding === "wrong" ? tag + 1 : tag, first, second]);
};
if (binding === "missing") {
    throws(() => new WebAssembly.Instance(module, { host: {} }), WebAssembly.LinkError);
    process.stdout.write(JSON.stringify({ imports, binding: "refused" }));
    process.exit(0);
}
const instance = new WebAssembly.Instance(module, { host: { audit } });
const values = [...new Set([
    -2147483648, -2147483647, -65536,
    ...Array.from({ length: 65 }, (_, i) => i - 32),
    65536, 2147483646, 2147483647,
])];
const counters = {
    cases: 0, accepted: 0, rejected_domain: 0, traps: 0,
    wrong_result: 0, wrong_trace: 0, wrong_domain: 0, wrong: 0,
};
const trace = createHash("sha256");
const restricted = scope.startsWith("restricted");
const admitted = (x, y) => y !== 0 &&
    (scope === "restricted-zero-only" || x > -2147483648 || y !== -1);
for (const x of values) {
    for (const y of values) {
        ++counters.cases;
        const reason = y === 0 ? 1 : x === -2147483648 && y === -1 ? 2 : 0;
        const expected = reason ? [reason, 0] : [0, Number(BigInt(x) / BigInt(y))];
        const expectedDenial = restricted && reason !== 0;
        const actualDenial = restricted && !admitted(x, y);
        const domainDiffers = expectedDenial !== actualDenial;
        counters.wrong_domain += Number(domainDiffers);
        events.length = 0;
        if (actualDenial) {
            ++counters.rejected_domain;
            counters.wrong += Number(domainDiffers);
            trace.update(JSON.stringify([x, y, "out-of-domain", events]) + "\n");
            continue;
        }
        ++counters.accepted;
        let observed;
        try {
            observed = instance.exports.divide(x, y);
        } catch (error) {
            if (!(error instanceof WebAssembly.RuntimeError)) {
                throw error;
            }
            observed = "trap";
            ++counters.traps;
        }
        const expectedEvents = scope === "pure" ? [] : [[11, x, y], [29, ...expected]];
        const resultDiffers = JSON.stringify(observed) !== JSON.stringify(expected);
        const effectsDiffer = JSON.stringify(events) !== JSON.stringify(expectedEvents);
        counters.wrong_result += Number(resultDiffers);
        counters.wrong_trace += Number(effectsDiffer);
        counters.wrong += Number(domainDiffers || resultDiffers || effectsDiffer);
        trace.update(JSON.stringify([x, y, observed, events]) + "\n");
    }
}
process.stdout.write(JSON.stringify({ imports, ...counters, trace_sha256: trace.digest("hex") }));
