"use strict";

const { createHash } = require("node:crypto");
const { readFileSync } = require("node:fs");

const min = -(1n << 63n);
const max = (1n << 63n) - 1n;
const mask = (1n << 64n) - 1n;
const decimal = /^(?:0|-?[1-9][0-9]*)$/;
const hex = /^[0-9a-f]{16}$/;

function textOf(codec, value) {
    if (codec === "number") return value.toString();
    if (codec === "decimal") return JSON.stringify(value.toString());
    return JSON.stringify((value & mask).toString(16).padStart(16, "0"));
}

function canonical(codec, value) {
    return `{"codec":"${codec}","value":${textOf(codec, value)}}`;
}

function observe(label, raw) {
    try {
        let valueToken;
        const decoded = JSON.parse(raw, (key, value, context) => {
            if (key === "value" && typeof value === "number") valueToken = context?.source;
            return value;
        });
        if (Object.keys(decoded).sort().join(",") !== "codec,value") return {status: "shape"};
        const expected = label === "text" ? "decimal" : label === "hex" ? "hex" : "number";
        if (decoded.codec !== expected) return {status: "codec"};

        let value;
        if (label === "number" || label === "safe_number") {
            if (!Number.isInteger(decoded.value)) return {status: "type"};
            if (label === "safe_number" && !Number.isSafeInteger(decoded.value)) return {status: "unsafe"};
            value = BigInt(decoded.value);
        } else if (label === "lexeme") {
            if (typeof valueToken !== "string" || !decimal.test(valueToken)) return {status: "syntax"};
            value = BigInt(valueToken);
        } else if (label === "text") {
            if (typeof decoded.value !== "string" || !decimal.test(decoded.value)) return {status: "syntax"};
            value = BigInt(decoded.value);
        } else {
            if (typeof decoded.value !== "string" || !hex.test(decoded.value)) return {status: "syntax"};
            value = BigInt.asIntN(64, BigInt("0x" + decoded.value));
        }
        if (value < min || value > max) return {status: "range"};
        if (label !== "number" && canonical(expected, value) !== raw) return {status: "noncanonical"};
        const signed = Buffer.alloc(8);
        signed.writeBigInt64BE(value);
        return {
            status: "accepted",
            decimal: value.toString(),
            semantic: createHash("sha256").update("rt05-i64/1\0").update(signed).digest("hex"),
        };
    } catch (error) {
        if (error instanceof SyntaxError || error instanceof TypeError) return {status: "syntax"};
        throw error;
    }
}

const input = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(input.map(([label, raw]) => observe(label, raw))));
