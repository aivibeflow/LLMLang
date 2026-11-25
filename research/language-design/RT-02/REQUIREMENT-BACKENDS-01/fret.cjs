const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const root = process.argv[2];
const cases = JSON.parse(readFileSync(resolve(__dirname, "requirements.json"), "utf8"));
const { compile } = require(resolve(root, "fret-electron/app/parser/FretSemantics.js"));

const results = Object.fromEntries(Object.entries(cases).map(([id, sentence]) => {
    const output = compile(sentence);
    if (output.parseErrors) return [id, { outcome: "parse-error", diagnostic: output.parseErrors }];
    const semantics = output.collectedSemantics;
    if (!semantics.ftExpanded) return [id, { outcome: "saved-without-formula", type: semantics.type }];
    return [id, {
        outcome: "formalized",
        finite: semantics.ftExpanded,
        infinite: semantics.ftInfAUExpanded,
        variables: semantics.variables,
        explanation: semantics.description,
    }];
}));
console.log(JSON.stringify(results));
