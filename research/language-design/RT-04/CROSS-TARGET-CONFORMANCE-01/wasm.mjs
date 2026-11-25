import { readFileSync } from "node:fs";

const { instance } = await WebAssembly.instantiate(readFileSync(process.argv[2]), {});
const requests = JSON.parse(readFileSync(0, "utf8"));
const outputs = requests.map(([input, observe]) => instance.exports.bounded_value(input, observe));
process.stdout.write(JSON.stringify(outputs));
