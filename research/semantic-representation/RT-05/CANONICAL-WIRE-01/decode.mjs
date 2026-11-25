import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const profile = "llmlang.identity-fixture/1";
const worker = fileURLToPath(new URL("../../PROTOTYPES/IDENTITY-BYTES-01/encode.mjs", import.meta.url));
const input = JSON.parse(readFileSync(0, "utf8"));
const utf8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");

function parse(frame) {
  const raw = Buffer.from(frame.raw_hex, "hex");
  let wire;
  try {
    wire = JSON.parse(utf8.decode(raw));
  } catch (error) {
    if (error instanceof TypeError || error instanceof SyntaxError) return { raw, diagnostic: "malformed" };
    throw error;
  }
  if (!Array.isArray(wire) || wire.length !== 3 || wire[0] !== profile) {
    return { raw, diagnostic: "envelope" };
  }
  if (wire[1] !== frame.expected_domain) return { raw, diagnostic: "domain" };
  return { raw, record: wire.slice(1) };
}

const parsed = input.map(parse);
const records = parsed.filter((item) => item.record).map((item) => JSON.stringify(item.record));
const processResult = spawnSync(process.execPath, [worker], {
  input: records.join("\n") + "\n", encoding: "utf8", timeout: 20000,
});
if (processResult.status !== 0) throw new Error(processResult.stderr || String(processResult.error));
const outcomes = processResult.stdout.split("\n").filter(Boolean).map((line) => JSON.parse(line));
let index = 0;

function strict(frame, item, normalized) {
  if (item.diagnostic) return [item.diagnostic, item.diagnostic];
  if (normalized === null) return ["typed", "typed"];
  if (frame.algorithm !== "sha256") return ["algorithm", "algorithm"];
  if (!/^[0-9a-f]{64}$/u.test(frame.digest)) return ["address", "address"];
  const [canonical, address] = normalized;
  const normalizing = frame.digest === address ? "accept" : "digest";
  if (!item.raw.equals(Buffer.from(canonical, "utf8"))) return ["noncanonical", normalizing];
  return [normalizing, normalizing];
}

const results = input.map((frame, number) => {
  const item = parsed[number];
  const statuses = strict(frame, item, item.record ? outcomes[index++] : null);
  const rawOnly = frame.algorithm === "sha256" && frame.digest === hash(item.raw)
    ? "accept" : "digest";
  return [...statuses, rawOnly];
});
if (index !== outcomes.length) throw new Error("Incorrect number of canonical worker replies");
console.log(JSON.stringify(results));
