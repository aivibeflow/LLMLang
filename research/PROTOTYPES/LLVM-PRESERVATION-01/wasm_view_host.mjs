import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const { cases, bytes, views, names } = JSON.parse(readFileSync(0, "utf8"));
const module = new WebAssembly.Module(readFileSync(process.argv[2]));
const { exports } = new WebAssembly.Instance(module);
const slab = 2048;
const output = 4096;
const memory = new Uint8Array(exports.memory.buffer);
const data = new DataView(exports.memory.buffer);
memory.set(bytes, slab);
const sentinel = (1n << 64n) - 1n;
for (const [op, origin, expected, offset, delta, expectedStatus, expectedValue] of cases) {
  const [start, length] = views[origin];
  data.setBigUint64(output, sentinel, true);
  const status = names[exports[op + "_view"](slab + start, BigInt(length), origin, expected,
                                           BigInt(offset), BigInt(delta), output)];
  const value = data.getBigUint64(output, true);
  const observed = status === "ok" ? Number(op === "form" ? value - BigInt(slab) : value) : null;
  if (status !== "ok") assert.equal(value, sentinel, String([op, origin, expected, offset, delta]));
  assert.deepEqual([status, observed], [expectedStatus, expectedValue],
                   String([op, origin, expected, offset, delta]));
}
assert.deepEqual([...memory.subarray(slab, slab + bytes.length)], bytes);
console.log(`${cases.length} comparisons passed`);
