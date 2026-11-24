/* Independently framed LSP client using the VS Code protocol package. */
const assert = require("node:assert/strict");
const { execFileSync, spawn } = require("node:child_process");
const { once } = require("node:events");
const { mkdtemp, rm, unlink, writeFile } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { pathToFileURL } = require("node:url");

const {
  createProtocolConnection, StreamMessageReader, StreamMessageWriter,
  InitializeRequest, InitializedNotification, DidOpenTextDocumentNotification,
  DidChangeTextDocumentNotification, DidChangeWatchedFilesNotification,
  DiagnosticRefreshRequest, DocumentDiagnosticRequest, PublishDiagnosticsNotification,
  ExitNotification, ShutdownRequest, FileChangeType,
} = require("vscode-languageserver-protocol/node");

const SDK = require("vscode-languageserver-protocol/package.json").version;
const python = process.argv[2] || "python3";

const cases = [
  { name: "unopened-provider", edit: "provider", value: "bool", before: [], after: ["TYPE"] },
  { name: "new-override", edit: "local-provider", value: "bool", before: [], after: ["TYPE"] },
  { name: "removed-override", edit: "local-provider", remove: true, before: ["TYPE"], after: [] },
  { name: "configuration", edit: "config", value: "bool", before: [], after: ["TYPE"] },
  { name: "unrelated", edit: "notes", value: "edited", before: [], after: [] },
  { name: "entry-version", edit: "entry", value: "broken", before: [], after: ["PARSE"] },
];

function codes(items) {
  return items.map(item => item.code);
}

async function runCase(policy, test) {
  const directory = await mkdtemp(join(tmpdir(), "rt17-lsp-fixture-"));
  const closeTasks = [];
  try {
    for (const [name, value] of Object.entries({ provider: "int", config: "int", notes: "initial" })) {
      await writeFile(join(directory, name), value);
    }
    if (test.remove) await writeFile(join(directory, "local-provider"), "bool");
    const uri = pathToFileURL(join(directory, "entry")).href;
    const child = spawn(python, [join(__dirname, "server.py"), directory, policy], {
      stdio: ["pipe", "pipe", "inherit"], timeout: 10000,
    });
    const exited = once(child, "exit");
    closeTasks.push(async () => {
      if (child.exitCode === null && child.signalCode === null) child.kill();
      await exited;
    });
    const lsp = createProtocolConnection(
      new StreamMessageReader(child.stdout), new StreamMessageWriter(child.stdin),
    );
    closeTasks.push(async () => lsp.dispose());
    const pushes = [];
    let refreshCount = 0;
    lsp.onNotification(PublishDiagnosticsNotification.type, result => {
      assert.equal(result.uri, uri);
      pushes.push({ version: result.version, codes: codes(result.diagnostics) });
    });
    lsp.onRequest(DiagnosticRefreshRequest.type, () => {
      refreshCount++;
      return null;
    });
    lsp.listen();
    const initialized = await lsp.sendRequest(InitializeRequest.type, {
      processId: null, rootUri: pathToFileURL(directory).href,
      capabilities: { workspace: { diagnostics: { refreshSupport: true } } },
    });
    assert.equal(initialized.capabilities.diagnosticProvider.interFileDependencies, true);
    await lsp.sendNotification(InitializedNotification.type, {});
    await lsp.sendNotification(DidOpenTextDocumentNotification.type, {
      textDocument: { uri, languageId: "rt17", version: 1, text: "call" },
    });

    async function pull(previousResultId) {
      return lsp.sendRequest(DocumentDiagnosticRequest.type, { textDocument: { uri }, previousResultId });
    }

    const first = await pull();
    assert.equal(first.kind, "full");
    assert.deepEqual(codes(first.items), test.before);
    assert.deepEqual(await pull(first.resultId), { kind: "unchanged", resultId: first.resultId });
    await lsp.sendRequest("rt17/testCapture", {});
    const version = test.edit === "entry" ? 2 : 1;
    if (version === 2) {
      await lsp.sendNotification(DidChangeTextDocumentNotification.type, {
        textDocument: { uri, version }, contentChanges: [{ text: test.value }],
      });
    } else {
      const editedPath = join(directory, test.edit);
      if (test.remove) await unlink(editedPath);
      else await writeFile(editedPath, test.value);
      const type = test.remove ? FileChangeType.Deleted :
        test.name === "new-override" ? FileChangeType.Created : FileChangeType.Changed;
      await lsp.sendNotification(DidChangeWatchedFilesNotification.type, {
        changes: [{ uri: pathToFileURL(editedPath).href, type }],
      });
    }
    const stale = await lsp.sendRequest("rt17/testFinish", { complete: true });
    const second = await pull(first.resultId);
    const changed = test.name === "unrelated" ? policy === "workspace" :
      version === 2 || policy !== "document";
    assert.equal(stale.published, !changed);
    assert.equal(second.kind, changed ? "full" : "unchanged");
    assert.equal(refreshCount, Number(changed));
    const displayed = second.kind === "full" ? codes(second.items) : codes(first.items);
    if (changed) assert.notEqual(second.resultId, first.resultId);
    else assert.equal(second.resultId, first.resultId);
    assert.deepEqual(displayed, changed ? test.after : test.before);
    const oldPush = stale.published ? pushes[0] : null;
    if (oldPush !== null) assert.deepEqual(oldPush, { version: 1, codes: test.before });

    // Unconditional pull and a fresh worker independently check the current view.
    const fresh = await pull("unknown-result-id");
    assert.equal(fresh.kind, "full");
    assert.deepEqual(codes(fresh.items), test.after);
    await lsp.sendRequest("rt17/testCapture", {});
    const partial = await lsp.sendRequest("rt17/testFinish", { complete: false });
    assert.equal(partial.published, false);
    assert.equal(pushes.length, Number(stale.published));
    await lsp.sendRequest("rt17/testCapture", {});
    const full = await lsp.sendRequest("rt17/testFinish", { complete: true });
    assert.equal(full.published, true);
    assert.equal(pushes.length, Number(stale.published) + 1);
    assert.deepEqual(pushes.at(-1), { version, codes: test.after });

    await lsp.sendRequest(ShutdownRequest.type);
    await lsp.sendNotification(ExitNotification.type);
    assert.deepEqual(await exited, [0, null]);
    return {
      case: test.name, policy, documentVersion: version, expected: test.after,
      stalePush: oldPush, conditionalPull: second.kind, resultIdReused: second.resultId === first.resultId,
      displayed, refreshCount, freshPush: pushes.at(-1), partialPublished: partial.published,
      wrongPull: JSON.stringify(displayed) !== JSON.stringify(test.after),
      wrongPush: oldPush !== null && JSON.stringify(oldPush.codes) !== JSON.stringify(test.after),
      unnecessaryInvalidation: test.name === "unrelated" && changed,
    };
  } finally {
    for (const close of closeTasks.reverse()) await close();
    await rm(directory, { recursive: true, force: true });
  }
}

async function main() {
  const results = [];
  for (const policy of ["document", "workspace", "projection"]) {
    for (const test of cases) results.push(await runCase(policy, test));
  }
  const totals = {};
  for (const row of results) {
    const counts = totals[row.policy] ||= { wrongPush: 0, wrongPull: 0, unnecessaryInvalidation: 0 };
    for (const key of Object.keys(counts)) counts[key] += Number(row[key]);
  }
  assert.deepEqual(totals, {
    document: { wrongPush: 4, wrongPull: 4, unnecessaryInvalidation: 0 },
    workspace: { wrongPush: 0, wrongPull: 0, unnecessaryInvalidation: 1 },
    projection: { wrongPush: 0, wrongPull: 0, unnecessaryInvalidation: 0 },
  });
  const pythonVersion = execFileSync(python, ["--version"], { encoding: "utf8" }).trim();
  console.log(JSON.stringify({ format: "rt17-wire-diagnostic/1", sdk: SDK, node: process.version,
                             python: pythonVersion, totals, results }, null, 2));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
