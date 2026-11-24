import { createHash } from "node:crypto";
import readline from "node:readline";

const domains = new Set(["contract", "operation", "implementation", "class", "candidate-set", "evidence"]);

function requireValue(condition) {
  if (!condition) throw new TypeError("outside typed fixture");
}

function scalarText(text) {
  requireValue(typeof text === "string" && text.isWellFormed());
  return text;
}

function normalize(term) {
  requireValue(Array.isArray(term) && term.length === 2);
  const [tag, val] = term;
  switch (tag) {
    case "int":
      requireValue(typeof val === "string" && /^(-?[1-9][0-9]*|0)$/u.test(val));
      return [tag, val];
    case "bool":
      requireValue(typeof val === "boolean");
      return [tag, val];
    case "text":
      return [tag, scalarText(val)];
    case "list":
      requireValue(Array.isArray(val));
      return [tag, val.map(normalize)];
    case "map": {
      requireValue(Array.isArray(val));
      const seen = new Set();
      const rows = val.map((row) => {
        requireValue(Array.isArray(row) && row.length === 2);
        const key = scalarText(row[0]);
        requireValue(!seen.has(key));
        seen.add(key);
        return [key, normalize(row[1])];
      });
      rows.sort(([left], [right]) => Buffer.compare(Buffer.from(left), Buffer.from(right)));
      return [tag, rows];
    }
    default:
      throw new TypeError("unknown type");
  }
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  let result = null;
  try {
    const record = JSON.parse(line);
    requireValue(Array.isArray(record) && record.length === 2 && domains.has(record[0]));
    const bytes = JSON.stringify(["llmlang.identity-fixture/1", record[0], normalize(record[1])]);
    result = [bytes, createHash("sha256").update(bytes, "utf8").digest("hex")];
  } catch (error) {
    if (!(error instanceof TypeError || error instanceof SyntaxError)) throw error;
  }
  console.log(JSON.stringify(result));
}
