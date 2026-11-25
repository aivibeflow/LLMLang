/* LSP client fixture with transactional edits and a separate outcome oracle. */
const assert = require("node:assert/strict");
const { execFileSync, spawn } = require("node:child_process");
const { once } = require("node:events");
const { mkdtemp, readFile, rm, writeFile } = require("node:fs/promises");
const { createRequire } = require("node:module");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { pathToFileURL } = require("node:url");

const requireSdk = createRequire(join(__dirname, "../WIRE-DIAGNOSTIC-01/client.cjs"));
const {
  createProtocolConnection, StreamMessageReader, StreamMessageWriter,
  InitializeRequest, InitializedNotification, DidOpenTextDocumentNotification,
  DidChangeTextDocumentNotification, CodeActionRequest, ExecuteCommandRequest,
  ApplyWorkspaceEditRequest, ExitNotification, ShutdownRequest,
} = requireSdk("vscode-languageserver-protocol/node");

const policies = ["legacy", "versioned", "workspace", "preflight", "commit-bound"];
const cases = ["baseline", "config-edit", "config-restored", "dependency-before",
               "dependency-during", "unrelated", "wrong-repair"];
const python = process.argv[2] || "python3";
const initialRule = '{"limit":"5"}';
const initialConfig = '{"mode":"legacy"}';
const position = { line: 0, character: 0 };

function expected(policy, name) {
  const scopeChecked = ["workspace", "preflight", "commit-bound"].includes(policy);
  if (["config-edit", "config-restored"].includes(name) && policy !== "legacy") return "document-version";
  if (name === "dependency-before" && scopeChecked) return "stale-scope";
  if (name === "wrong-repair" && scopeChecked) return "behavior-mismatch";
  if (name === "dependency-during" && policy === "commit-bound") return "atomic-read-scope";
  if (name === "unrelated" && policy === "workspace") return "stale-scope";
  return "applied";
}

function applyBatch(edit, current) {
  const edits = edit.documentChanges || Object.entries(edit.changes).map(([uri, items]) => ({
    textDocument: { uri, version: null }, edits: items,
  }));
  let staged = new Map(current);
  for (const [index, doc] of edits.entries()) {
    const { uri, version } = doc.textDocument;
    const prior = current.get(uri);
    if (version !== null && prior.version !== version) {
      return { applied: false, failureReason: "document-version", failedChange: index };
    }
    assert.equal(doc.edits.length, 1);
    const [item] = doc.edits;
    assert.deepEqual(item.range.start, position);
    assert.deepEqual(item.range.end, { line: 0, character: prior.text.length });
    staged.set(uri, { version: prior.version + 1, text: item.newText });
  }
  for (const [uri, doc] of staged) current.set(uri, doc);
  return { applied: true };
}

async function runCase(policy, name) {
  const directory = await mkdtemp(join(tmpdir(), "rt17-wire-repair-"));
  const close = [];
  try {
    const rule = pathToFileURL(join(directory, "rule")).href;
    const config = pathToFileURL(join(directory, "config")).href;
    const provider = join(directory, "provider");
    const notes = join(directory, "notes");
    await writeFile(provider, "5");
    await writeFile(notes, "initial");
    const documents = new Map([[rule, { text: initialRule, version: 1 }],
                               [config, { text: initialConfig, version: 1 }]]);
    const process = spawn(python, [join(__dirname, "server.py"), directory, policy, name], {
      stdio: ["pipe", "pipe", "inherit"], timeout: 10000,
    });
    const exited = once(process, "exit");
    close.push(async () => {
      if (process.exitCode === null && process.signalCode === null) process.kill();
      await exited;
    });
    const lsp = createProtocolConnection(
      new StreamMessageReader(process.stdout), new StreamMessageWriter(process.stdin),
    );
    close.push(async () => lsp.dispose());
    let editRequests = 0;
    let versioned = null;
    let clientBefore = null;
    const pinnedProvider = await readFile(provider, "utf8");
    lsp.onRequest(ApplyWorkspaceEditRequest.type, async ({ edit }) => {
      editRequests++;
      versioned = Boolean(edit.documentChanges);
      clientBefore = [...documents.values()].map(row => row.version);
      if (name === "dependency-during") await writeFile(provider, "3");
      if (policy === "commit-bound" && await readFile(provider, "utf8") !== pinnedProvider) {
        return { applied: false, failureReason: "atomic-read-scope" };
      }
      return applyBatch(edit, documents);
    });
    lsp.listen();
    const init = await lsp.sendRequest(InitializeRequest.type, {
      processId: null, rootUri: pathToFileURL(directory).href,
      capabilities: { workspace: { applyEdit: true, workspaceEdit: {
        documentChanges: true, failureHandling: "transactional",
      } } },
    });
    assert.equal(init.capabilities.codeActionProvider, true);
    await lsp.sendNotification(InitializedNotification.type, {});
    for (const [uri, fields] of documents) {
      await lsp.sendNotification(DidOpenTextDocumentNotification.type, {
        textDocument: { uri, languageId: "rt17", ...fields },
      });
    }
    const [action] = await lsp.sendRequest(CodeActionRequest.type, {
      textDocument: { uri: rule }, range: { start: position, end: position }, context: { diagnostics: [] },
    });
    async function updateConfig(text) {
      const version = documents.get(config).version + 1;
      documents.set(config, { version, text });
      await lsp.sendNotification(DidChangeTextDocumentNotification.type, {
        textDocument: { uri: config, version }, contentChanges: [{ text }],
      });
    }
    if (["config-edit", "config-restored"].includes(name)) await updateConfig('{"mode":"manual"}');
    if (name === "config-restored") await updateConfig(initialConfig);
    if (name === "dependency-before") await writeFile(provider, "3");
    if (name === "unrelated") await writeFile(notes, "updated");
    const before = JSON.stringify([...documents.values()]);
    const outcome = await lsp.sendRequest(ExecuteCommandRequest.type, {
      command: action.command.command, arguments: action.command.arguments,
    });
    const decision = outcome.applied ? "applied" : (outcome.reason || outcome.failureReason);
    assert.equal(decision, expected(policy, name), { policy, name, outcome });
    assert.equal(editRequests, Number(outcome.stage === "client"));
    if (outcome.stage === "client") assert.equal(versioned, policy !== "legacy");
    if (decision === "document-version") assert.equal(outcome.failedChange, 1);
    assert.equal(JSON.stringify([...documents.values()]) !== before, Boolean(outcome.applied));

    const tested = Array.from({ length: 11 }, (_, index) => index);
    let behaviorDifferences = [];
    if (outcome.applied) {
      const limit = JSON.parse(documents.get(rule).text).limit;
      const mode = JSON.parse(documents.get(config).text).mode;
      const oracle = Number(await readFile(provider, "utf8"));
      assert.equal(typeof limit, "number");
      assert.equal(mode, "strict");
      behaviorDifferences = tested.filter(n => (n <= limit) !== (n <= oracle));
    }
    await lsp.sendRequest(ShutdownRequest.type);
    await lsp.sendNotification(ExitNotification.type);
    assert.deepEqual(await exited, [0, null]);
    return {
      policy, case: name, decision, editRequests, versioned, clientBefore, behaviorDifferences,
      atomicRejection: !outcome.applied && JSON.stringify([...documents.values()]) === before,
      staleApplication: Boolean(outcome.applied) && ["config-edit", "config-restored"].includes(name),
      unnecessaryRejection: !outcome.applied && name === "unrelated",
    };
  } finally {
    for (const callback of close.reverse()) await callback();
    await rm(directory, { recursive: true, force: true });
  }
}

async function main() {
  const results = [];
  const summaries = {};
  for (const policy of policies) {
    const rows = [];
    for (const name of cases) rows.push(await runCase(policy, name));
    results.push(...rows);
    summaries[policy] = {
      staleApplications: rows.filter(row => row.staleApplication).length,
      wrongBehavior: rows.filter(row => row.behaviorDifferences.length).length,
      unnecessaryRejections: rows.filter(row => row.unnecessaryRejection).length,
    };
  }
  assert.deepEqual(Object.values(summaries).map(row => Object.values(row)),
                   [[2, 3, 0], [0, 3, 0], [0, 1, 1], [0, 1, 0], [0, 0, 0]]);
  const version = requireSdk("vscode-languageserver-protocol/package.json").version;
  console.log(JSON.stringify({ format: "rt17-wire-repair/1", node: process.version, sdk: version,
    python: execFileSync(python, ["--version"], { encoding: "utf8" }).trim(), summaries, results }, null, 2));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
