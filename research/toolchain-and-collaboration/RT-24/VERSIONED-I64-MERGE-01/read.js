"use strict";

const { createHash } = require("node:crypto");
const { readFileSync } = require("node:fs");

const lower = -(1n << 63n);
const upper = 1n << 63n;
const integer = /^(?:0|-?[1-9][0-9]*)$/;
const hex = /^[0-9a-f]{16}$/;
const slots = ["a", "b"];

function semanticRoot(values) {
    const hash = createHash("sha256").update("rt24-versioned-i64-graph/1\0");
    for (const slot of slots) {
        const bytes = Buffer.alloc(8);
        bytes.writeBigInt64BE(values[slot]);
        hash.update(slot + "\0").update(bytes);
    }
    return hash.digest("hex");
}

function canonical(version, values, root) {
    const encoded = slots.map(slot => {
        const value = values[slot];
        const token = version === 1 ? value.toString() :
            JSON.stringify(BigInt.asUintN(64, value).toString(16).padStart(16, "0"));
        return `"${slot}":${token}`;
    });
    return `{"version":${version},"nodes":{${encoded.join(",")}},"root":${JSON.stringify(root)}}\n`;
}

function observe(policy, raw) {
    let object;
    const tokens = new Map();
    try {
        object = JSON.parse(raw, (key, value, context) => {
            if (slots.includes(key) && typeof value === "number") tokens.set(key, context?.source);
            return value;
        });
    } catch (error) {
        if (error instanceof SyntaxError) return {status: "syntax"};
        throw error;
    }
    if (!object || Object.keys(object).sort().join() !== "nodes,root,version" ||
        !object.nodes || Object.keys(object.nodes).sort().join() !== "a,b" ||
        typeof object.root !== "string" || !/^[0-9a-f]{64}$/.test(object.root)) return {status: "shape"};
    const {version, nodes, root} = object;
    if (version !== 2 && (version !== 1 || policy === "single_v2")) return {status: "version"};
    const values = {};
    for (const slot of slots) {
        const value = nodes[slot];
        if (version === 2) {
            if (typeof value !== "string" || !hex.test(value)) return {status: "syntax"};
            values[slot] = BigInt.asIntN(64, BigInt("0x" + value));
        } else if (policy === "rounded") {
            if (!Number.isInteger(value)) return {status: "syntax"};
            values[slot] = BigInt(value);
        } else {
            const token = tokens.get(slot);
            if (typeof token !== "string" || !integer.test(token)) return {status: "syntax"};
            values[slot] = BigInt(token);
        }
        if (values[slot] < lower || values[slot] >= upper) return {status: "range"};
    }
    if (policy !== "rounded" && raw !== canonical(version, values, root)) return {status: "noncanonical"};
    const actual = semanticRoot(values);
    if ((policy === "exact_bound" || policy === "single_v2") && root !== actual) return {status: "root"};
    return {status: "accepted", version, digest: actual, nodes: slots.map(slot => values[slot].toString())};
}

const rows = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(rows.map(([policy, raw]) => observe(policy, raw))));
