import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const bytes = readFileSync(process.argv[2]);
const module = new WebAssembly.Module(bytes);
const expectedImports = [{ module: "llmlang", name: "commit", kind: "function" }];
assert.deepEqual(WebAssembly.Module.imports(module), expectedImports);
assert.throws(() => new WebAssembly.Instance(module, { llmlang: {} }), WebAssembly.LinkError);

const limits = { min: -(1n << 63n), max: (1n << 63n) - 1n };
const inputs = [
  ...Array.from({ length: 256 }, (_, i) => BigInt(i)),
  -1n, 256n, 1n << 32n, limits.min, limits.max,
];

function scopedInvoke(operation, input) {
  if (typeof input !== "bigint" || input < limits.min || input > limits.max) {
    return { status: "refused-at-host" };
  }
  return { status: "called", result: operation(input) };
}

const hosts = {
  selected: (effects) => (value) => effects.push(value),
  omittedEffect: () => () => {},
  changedEffectPayload: (effects) => (value) => effects.push(value + 1),
};
const scenarios = {};
for (const [name, build] of Object.entries(hosts)) {
  const effects = [];
  const operation = new WebAssembly.Instance(module, { llmlang: { commit: build(effects) } }).exports.invoke;
  let effectsDiffer = 0;
  const digest = createHash("sha256");
  for (const input of inputs) {
    effects.length = 0;
    const admitted = input >= 0n && input <= 255n;
    const exact = admitted ? Number(input) : 256;
    const oracle = admitted ? [exact] : [];
    const result = scopedInvoke(operation, input);
    assert.deepEqual(result, { status: "called", result: exact });
    effectsDiffer += Number(JSON.stringify(effects) !== JSON.stringify(oracle));
    digest.update(JSON.stringify([input.toString(), result, effects]));
  }
  assert.equal(effectsDiffer, name === "selected" ? 0 : 256);
  scenarios[name] = {
    calls: inputs.length,
    returnMismatches: 0,
    effectMismatches: effectsDiffer,
    transcriptSha256: digest.digest("hex"),
  };
}

const narrowingEffects = [];
const raw = new WebAssembly.Instance(module, { llmlang: { commit: hosts.selected(narrowingEffects) } }).exports.invoke;
assert.throws(() => raw(7), TypeError);
assert.deepEqual(narrowingEffects, []);
const wide = 1n << 64n;
assert.equal(raw(wide), 0);
assert.deepEqual(narrowingEffects.splice(0), [0]);
assert.deepEqual(scopedInvoke(raw, wide), { status: "refused-at-host" });
assert.deepEqual(narrowingEffects, []);
assert.deepEqual(scopedInvoke(raw, 7), { status: "refused-at-host" });
console.log(JSON.stringify({
  imports: expectedImports,
  missingHostImport: "LinkError",
  scenarios,
  narrowedInput: wide.toString(),
  rawNarrowingResult: 0,
  rawNarrowingEffect: [0],
  checkedWideInput: "refused-at-host",
  numberInputRejected: "TypeError",
}));
