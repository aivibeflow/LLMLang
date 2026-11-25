"use strict";

const { readFileSync } = require("node:fs");
const view = new DataView(new ArrayBuffer(8));

function fromBits(bits) {
    view.setBigUint64(0, BigInt("0x" + bits), false);
    return view.getFloat64(0, false);
}

function toBits(value) {
    view.setFloat64(0, value, false);
    return view.getBigUint64(0, false).toString(16).padStart(16, "0");
}

const rows = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(rows.map(([a, b]) => {
    const left = fromBits(a);
    const right = fromBits(b);
    return [toBits(Math.min(left, right)), toBits(Math.max(left, right))];
})));
