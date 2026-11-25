/* Compare versioned range application policies using the pinned LSP protocol client. */
const assert = require("node:assert/strict");
const { execFileSync, spawn } = require("node:child_process");
const { once } = require("node:events");
const { readFileSync } = require("node:fs");
const { createRequire } = require("node:module");
const { join } = require("node:path");

const SDK = join(__dirname, "../WIRE-DIAGNOSTIC-01");
const requireSdk = createRequire(join(SDK, "client.cjs"));
const {
  createProtocolConnection, StreamMessageReader, StreamMessageWriter,
  InitializeRequest, InitializedNotification, DidOpenTextDocumentNotification,
  DidChangeTextDocumentNotification, CodeActionRequest, ExecuteCommandRequest,
  ApplyWorkspaceEditRequest, ExitNotification, ShutdownRequest,
} = requireSdk("vscode-languageserver-protocol/node");

const primary = "file:///fixture/program.ll";
const companion = "file:///fixture/options.ll";
const python = process.argv[2] || "python3";
const wantedEncodings = ["utf-8", "utf-16", "utf-32", "default"];
const servers = ["negotiated", "codepoint", "fixed16"];
const clients = ["range", "token", "occurrence"];
const cases = {
  ascii: "first bad || bad suffix\n",
  astral: "a😀bq bad || bad suffix\n",
  combining: "Cafe\u0301 bad || bad suffix\n",
  crlf: "heading\r\n😀éq bad || bad suffix\r\n",
  "malformed-unit": "😀q bad || bad suffix\n",
  "wrong-occurrence": "bad || bad suffix\n",
  stale: "old header\r\none bad || bad suffix\r\n",
};
const optionsText = "set old options\n";

function coordinate(text, position, encoding) {
  if (!Number.isSafeInteger(position.line) || !Number.isSafeInteger(position.character)) return null;
  const lines = text.split(/(?<=\n)/);
  if (position.line < 0 || position.line >= lines.length || position.character < 0) return null;
  const offset = lines.slice(0, position.line).reduce((sum, line) => sum + line.length, 0);
  const content = lines[position.line].replace(/\r?\n$/, "");
  let index = 0;
  let units = 0;
  for (const scalar of content) {
    if (units === position.character) return offset + index;
    units += encoding === "utf-8" ? Buffer.byteLength(scalar) : encoding === "utf-16" ? scalar.length : 1;
    index += scalar.length;
    if (units > position.character) return null;
  }
  return units === position.character ? offset + index : null;
}

function decide(edit, documents, encoding, client) {
  const staged = new Map(documents);
  for (const [index, change] of edit.documentChanges.entries()) {
    const { uri, version } = change.textDocument;
    const current = documents.get(uri);
    if (version !== current.version) return { applied: false, failureReason: "version", failedChange: index };
    const [item] = change.edits;
    const start = coordinate(current.text, item.range.start, encoding);
    const end = coordinate(current.text, item.range.end, encoding);
    if (start === null || end === null || start > end) {
      return { applied: false, failureReason: "range", failedChange: index };
    }
    const oldToken = uri === primary ? "bad" : "old";
    const expectedStart = current.text.indexOf(oldToken);
    if (client !== "range" && current.text.slice(start, end) !== oldToken) {
      return { applied: false, failureReason: "token", failedChange: index };
    }
    if (client === "occurrence" && start !== expectedStart) {
      return { applied: false, failureReason: "occurrence", failedChange: index };
    }
    const next = current.text.slice(0, start) + item.newText + current.text.slice(end);
    staged.set(uri, { text: next, version: current.version + 1 });
  }
  for (const [uri, item] of staged) documents.set(uri, item);
  return { applied: true };
}

async function runCase(wanted, server, client, name) {
  const child = spawn(python, [join(__dirname, "server.py"), server, name], {
    stdio: ["pipe", "pipe", "inherit"], timeout: 10000,
  });
  const exit = once(child, "exit");
  const lsp = createProtocolConnection(new StreamMessageReader(child.stdout), new StreamMessageWriter(child.stdin));
  const original = new Map([[primary, { text: cases[name], version: 1 }],
                            [companion, { text: optionsText, version: 1 }]]);
  const documents = new Map(original);
  const goal = [cases[name].replace("bad", "good"), optionsText.replace("old", "new")];
  const position = { line: 0, character: 0 };
  let encoding;
  let requestCount = 0;
  let primaryRange;
  lsp.onRequest(ApplyWorkspaceEditRequest.type, ({ edit }) => {
    requestCount += 1;
    primaryRange = edit.documentChanges[0].edits[0].range;
    return decide(edit, documents, encoding, client);
  });
  lsp.listen();
  try {
    const optional = wanted === "default" ? {} : { general: { positionEncodings: [wanted] } };
    const init = await lsp.sendRequest(InitializeRequest.type, {
      rootUri: "file:///fixture/", processId: null, capabilities: {
        ...optional, workspace: { applyEdit: true, workspaceEdit: {
          documentChanges: true, failureHandling: "transactional",
        } },
      },
    });
    encoding = init.capabilities.positionEncoding ?? "utf-16";
    assert.equal(encoding, wanted === "default" ? "utf-16" : wanted);
    if (wanted === "default") assert.equal(init.capabilities.positionEncoding, undefined);
    await lsp.sendNotification(InitializedNotification.type, {});
    for (const [uri, value] of documents) {
      await lsp.sendNotification(DidOpenTextDocumentNotification.type, {
        textDocument: { uri, languageId: "rt17", ...value },
      });
    }
    const [action] = await lsp.sendRequest(CodeActionRequest.type, {
      textDocument: { uri: primary }, range: { start: position, end: position }, context: { diagnostics: [] },
    });
    if (name === "stale") {
      documents.set(companion, { text: optionsText, version: 2 });
      await lsp.sendNotification(DidChangeTextDocumentNotification.type, {
        textDocument: { uri: companion, version: 2 }, contentChanges: [{ text: optionsText }],
      });
    }
    const before = new Map(documents);
    const applied = await lsp.sendRequest(ExecuteCommandRequest.type, action.command);
    assert.equal(requestCount, 1);
    const outputs = [...documents.values()].map(row => row.text);
    if (!applied.applied) assert.deepEqual(documents, before);
    const outcome = !applied.applied ? applied.failureReason
      : outputs.every((output, index) => output === goal[index]) ? "correct" : "wrong";
    if (name === "stale") assert.equal(outcome, "version");
    if (name === "wrong-occurrence") {
      assert.equal(outcome, client === "occurrence" ? "occurrence" : "wrong");
    }
    if (server === "negotiated" && !["malformed-unit", "wrong-occurrence", "stale"].includes(name)) {
      assert.equal(outcome, "correct");
    }
    await lsp.sendRequest(ShutdownRequest.type);
    await lsp.sendNotification(ExitNotification.type);
    assert.deepEqual(await exit, [0, null]);
    return { requested: wanted, advertised: init.capabilities.positionEncoding ?? null, server, client,
             scenario: name, range: primaryRange, outcome, outputs };
  } finally {
    lsp.dispose();
    if (child.exitCode === null && child.signalCode === null) child.kill();
    await exit;
  }
}

(async () => {
  const sdk = JSON.parse(readFileSync(join(SDK, "node_modules/vscode-languageserver-protocol/package.json")));
  assert.equal(sdk.version, "3.17.5");
  const serverPython = execFileSync(python, ["--version"], { encoding: "utf8" }).trim();
  const rows = [];
  const outcomeCount = Object.fromEntries(clients.map(client => [client, {}]));
  for (const wanted of wantedEncodings) {
    for (const server of servers) {
      for (const name of Object.keys(cases)) {
        for (const client of clients) {
          const row = await runCase(wanted, server, client, name);
          rows.push(row);
          const counts = outcomeCount[client];
          counts[row.outcome] = (counts[row.outcome] ?? 0) + 1;
        }
      }
    }
  }
  assert.equal(outcomeCount.occurrence.wrong ?? 0, 0);
  assert(outcomeCount.range.wrong > outcomeCount.token.wrong && outcomeCount.token.wrong > 0);
  process.stdout.write(JSON.stringify({ format: "rt17-lsp-wire-positions/1", node: process.version,
                                      sdk: sdk.version, python: serverPython, outcomes: outcomeCount, sessions: rows }, null, 2) + "\n");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
