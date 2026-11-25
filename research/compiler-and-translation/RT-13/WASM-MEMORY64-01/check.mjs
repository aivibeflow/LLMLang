import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const [artifact, policy] = process.argv.slice(2);
const moduleBytes = readFileSync(artifact);
const supported = WebAssembly.validate(moduleBytes);
if (policy === "admission") {
    process.stdout.write(JSON.stringify({ supported }));
    process.exit(0);
}
if (!supported) throw new Error("the engine refused the memory64 profile");
const { exports } = new WebAssembly.Instance(new WebAssembly.Module(moduleBytes));
const memory = new Uint8Array(exports.memory.buffer);
if (memory.length !== 131072) throw new Error("unexpected memory extent");
const capacity = BigInt(memory.length);
const testBytes = new Map([[0n, 211], [256n, 19], [257n, 241], [65535n, 37], [65536n, 189], [capacity - 1n, 173]]);
for (const [address, byte] of testBytes) memory[Number(address)] = byte;

const limit = 1n << 64n;
const points = [
    0n, 1n, 2n, 255n, 256n, 257n, 65535n, 65536n, 65537n,
    capacity - 1n, capacity, capacity + 1n, (1n << 32n) - 1n,
    1n << 32n, (1n << 32n) + 256n, 1n << 63n, limit - 256n, limit - 1n,
];

function expected(base, span, offset) {
    // Use unbounded integers and an exclusive end for the independent oracle.
    if (offset >= span || base + span > capacity) return -1;
    return testBytes.get(base + offset) ?? 0;
}

function observe(base, span, offset) {
    try {
        return exports.view_byte(base, span, offset);
    } catch (error) {
        if (!(error instanceof WebAssembly.RuntimeError)) throw error;
        return "trap";
    }
}

const counts = { checked: 0, bytes: 0, rejected: 0, wrong: 0, traps: 0 };
const receipt = createHash("sha256");
let firstWrong;
for (const base of points) {
    for (const span of points) {
        for (const offset of points) {
            const want = expected(base, span, offset);
            const got = observe(base, span, offset);
            counts.checked++;
            counts[want === -1 ? "rejected" : "bytes"]++;
            if (got !== want) {
                counts.wrong++;
                if (got === "trap") counts.traps++;
                firstWrong ??= { base: String(base), span: String(span), offset: String(offset), want, got };
            }
            receipt.update(`${base}/${span}/${offset}/${want}/${got}\n`);
        }
    }
}

const rawOverflow = observe(limit + 256n, 2n, 1n);
const importedUnsigned = args => {
    if (args.some(value => typeof value !== "bigint" || value < 0n || value >= limit)) {
        return "rejected-host";
    }
    return observe(...args);
};
const hostControls = {
    rawOverflow,
    guardedOverflow: importedUnsigned([limit + 256n, 2n, 1n]),
    guardedNegative: importedUnsigned([-1n, 2n, 1n]),
    guardedNumber: importedUnsigned([256, 2n, 1n]),
    guardedValid: importedUnsigned([256n, 2n, 1n]),
};
if (rawOverflow !== 241 || hostControls.guardedValid !== 241 ||
    Object.values(hostControls).filter(result => result === "rejected-host").length !== 3) {
    throw new Error("failed the host-domain comparison");
}
process.stdout.write(JSON.stringify({
    supported, counts, hostControls, firstWrong: firstWrong ?? null, signature: receipt.digest("hex"),
}));
