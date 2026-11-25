"use strict";

const { readFileSync } = require("node:fs");
const binary = new DataView(new ArrayBuffer(8));

function fromBits(raw) {
    binary.setBigUint64(0, BigInt("0x" + raw), false);
    return binary.getFloat64(0, false);
}

function toBits(value) {
    binary.setFloat64(0, value, false);
    return binary.getBigUint64(0, false).toString(16).padStart(16, "0");
}

function numeric(value) {
    const category = Number.isNaN(value) ? "nan" : !Number.isFinite(value) ? "infinite" :
        value === 0 ? "zero" : Math.abs(value) < 2.2250738585072014e-308 ? "subnormal" : "normal";
    const inverse = 1 / value;
    return [category, !Number.isNaN(value), Number.isNaN(inverse) ? "nan" : toBits(inverse)];
}

function strictBinary(raw) {
    let value;
    try {
        value = JSON.parse(raw);
    } catch (error) {
        if (error instanceof SyntaxError) return {status: "syntax"};
        throw error;
    }
    if (!value || Object.keys(value).sort().join() !== "bits,kind" || value.kind !== "f64-bits" ||
        typeof value.bits !== "string" || !/^[0-9a-f]{16}$/.test(value.bits)) return {status: "shape"};
    if (JSON.stringify({kind: "f64-bits", bits: value.bits}) !== raw) return {status: "noncanonical"};
    return {status: "accepted", bits: value.bits, numeric: numeric(fromBits(value.bits))};
}

function numberDecoded(raw) {
    let number;
    try {
        number = JSON.parse(raw);
    } catch (error) {
        if (error instanceof SyntaxError) return {status: "syntax"};
        throw error;
    }
    if (!Number.isFinite(number)) return {status: "nonfinite-or-nonnumber"};
    return {status: "accepted", bits: toBits(number), numeric: numeric(number)};
}

function observe([bits, tagged]) {
    const value = fromBits(bits);
    const scalar = toBits(value);
    const boxed = toBits([value][0]);
    const numberWire = JSON.stringify(value);
    return {scalar, boxed, numeric: numeric(value), tagged: tagged.map(strictBinary),
            numberWire, number: numberDecoded(numberWire)};
}

const { rows, controls } = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify({rows: rows.map(observe),
    nativeSameValueZeroKeys: new Set(rows.map(([bits]) => fromBits(bits))).size,
    controls: controls.map(([policy, raw]) => policy === "tagged" ? strictBinary(raw) : numberDecoded(raw))}));
