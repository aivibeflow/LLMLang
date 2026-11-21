// Compare a memory32 lowering with an exact-integer logical view model.
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const wat = `(module
  (memory (export "mem") 1)
  (func (export "access") (param $base i32) (param $len i32)
    (param $origin i32) (param $expected i32)
    (param $offset i64) (param $delta i64) (param $write i32) (result i32)
    (local $sum i64) (local $address i32) (local $previous i32)
    (if (i32.ne (local.get $origin) (local.get $expected))
      (then (return (i32.const -1))))
    (local.set $sum (i64.add (local.get $offset) (local.get $delta)))
    (if (i64.lt_s (i64.and (i64.xor (local.get $sum) (local.get $offset))
                         (i64.xor (local.get $sum) (local.get $delta))) (i64.const 0))
      (then (return (i32.const -2))))
    (if (i64.ge_u (local.get $sum) (i64.extend_i32_u (local.get $len)))
      (then (return (i32.const -3))))
    (local.set $address (i32.add (local.get $base) (i32.wrap_i64 (local.get $sum))))
    (local.set $previous (i32.load8_u (local.get $address)))
    (if (local.get $write)
      (then (i32.store8 (local.get $address) (i32.const 201))))
    (local.get $previous)))`;

const slab = [11, 22, 33, 44, 55, 66];
const views = [[0, 3], [3, 3], [1, 4], [2, 3], [6, 0]];
const base = 32;
const min = -(1n << 63n);
const max = (1n << 63n) - 1n;
const shifts = [min, min + 1n, max - 1n, max, -(1n << 32n), -(1n << 32n) + 1n,
                -1n, 0n, 1n, 2n, 3n, 4n, 5n, 6n, 1n << 32n, (1n << 32n) + 1n];

function reference(origin, expected, offset, delta, write) {
  const bytes = slab.slice();
  if (origin !== expected) return [-1, bytes];
  const index = offset + delta;
  if (index < min || index > max) return [-2, bytes];
  const [start, length] = views[origin];
  if (index < 0n || index >= BigInt(length)) return [-3, bytes];
  const position = start + Number(index);
  const old = bytes[position];
  if (write) bytes[position] = 201;
  return [old, bytes];
}

function compile(tool, folder, label, source) {
  const sourceFile = join(folder, label + ".wat");
  const binary = join(folder, label + ".wasm");
  writeFileSync(sourceFile, source);
  const built = spawnSync(tool, [sourceFile, "-o", binary], { encoding: "utf8", timeout: 10000 });
  assert.equal(built.status, 0, built.stderr);
  return new WebAssembly.Instance(new WebAssembly.Module(readFileSync(binary))).exports;
}

function observe(module, origin, expected, offset, delta, write) {
  const memory = new Uint8Array(module.mem.buffer);
  memory.set(slab, base);
  memory[base - 1] = 77;
  memory[base + slab.length] = 88;
  const [start, length] = views[origin];
  const result = module.access(base + start, length, origin, expected, offset, delta, write);
  assert.equal(memory[base - 1], 77);
  assert.equal(memory[base + slab.length], 88);
  return [result, [...memory.subarray(base, base + slab.length)]];
}

const tool = process.argv[2] ?? "wat2wasm";
const folder = mkdtempSync(join(tmpdir(), "llmlang-wasm-"));
try {
  const good = compile(tool, folder, "checked", wat);
  let count = 0;
  for (let origin = 0; origin < views.length; ++origin) {
    for (let expected = 0; expected < views.length; ++expected) {
      for (const offset of shifts) {
        for (const delta of shifts) {
          for (const write of [0, 1]) {
            const args = [origin, expected, offset, delta, write];
            assert.deepEqual(observe(good, ...args), reference(...args), String(args));
            ++count;
          }
        }
      }
    }
  }
  const narrow = compile(tool, folder, "narrow-first", wat.replace(
    "(i64.ge_u (local.get $sum) (i64.extend_i32_u (local.get $len)))",
    "(i32.ge_u (i32.wrap_i64 (local.get $sum)) (local.get $len))"));
  const widen = [0, 0, (1n << 32n) + 1n, 0n, 1];
  assert.deepEqual(reference(...widen), [-3, slab]);
  assert.deepEqual(observe(narrow, ...widen), [22, [11, 201, 33, 44, 55, 66]]);

  const globalOnly = compile(tool, folder, "global-only", wat.replace(
    "(i64.ge_u (local.get $sum) (i64.extend_i32_u (local.get $len)))", "(i32.const 0)"));
  const neighboring = [0, 0, 3n, 0n, 1];
  assert.deepEqual(reference(...neighboring), [-3, slab]);
  assert.deepEqual(observe(globalOnly, ...neighboring), [44, [11, 22, 33, 201, 55, 66]]);
  console.log(`${count} observations matched; both weakened guards violate the source view contract`);
  console.log("WAT SHA-256", createHash("sha256").update(wat).digest("hex"));
} finally {
  rmSync(folder, { force: true, recursive: true });
}
