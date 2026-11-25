"use strict";

const { readFileSync } = require("node:fs");
const view = new DataView(new ArrayBuffer(8));
const lower = -(1n << 63n);
const exclusive = 1n << 63n;
const maxApproximation = Number(exclusive - 1n);

function integralThenWrap(value, expectedRefusal) {
    let integer;
    try {
        integer = BigInt(value);
    } catch (error) {
        if (!(error instanceof RangeError) || expectedRefusal === null) throw error;
        return expectedRefusal;
    }
    if (expectedRefusal !== null) throw new Error("BigInt accepted an inadmissible Number");
    return "v" + BigInt.asIntN(64, integer);
}

function observe(bits) {
    view.setBigUint64(0, BigInt("0x" + bits), false);
    const value = view.getFloat64(0, false);
    const finite = Number.isFinite(value);
    const weak = finite && value >= Number(lower) && value <= maxApproximation;
    const integral = Number.isInteger(value);
    if (!finite) {
        return ["nonfinite", "nonfinite", integralThenWrap(value, "nonfinite"), weak];
    }
    const wrap = integralThenWrap(value, integral ? null : "fraction");
    const integer = BigInt(Math.trunc(value));
    const inRange = integer >= lower && integer < exclusive;
    const checked = inRange ? "v" + integer : "range";
    return [checked, integral ? checked : "fraction", wrap, weak];
}

const words = JSON.parse(readFileSync(0, "utf8"));
view.setFloat64(0, maxApproximation, false);
const roundedMax = view.getBigUint64(0, false).toString(16).padStart(16, "0");
process.stdout.write(JSON.stringify({ roundedMax, rows: words.map(observe) }));
