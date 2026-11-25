#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const pinned = "7d407636c4a06d1b601376bc66ea96d5a26e0b8f";
const metadataLedger = "research/research-management/RT-00/EXACT-LEDGER-METADATA-01/evidence.json";
const reviewedLines = {
  "research/compiler-and-translation/RT-09/RT-09-INCREMENTAL-TRANSLATION-CLOSURE-2026-11-25.md": [
    29,
    29
  ],
  "research/compiler-and-translation/RT-09/RT-09-WASM-CHECKED-DIVISION-2026-11-25.md": [
    33,
    0
  ],
  "research/compiler-and-translation/RT-13/RT-13-DIRECT-NATIVE-BACKEND-THRESHOLD-2026-11-25.md": [
    45,
    45
  ],
  "research/compiler-and-translation/RT-13/RT-13-FFI-TARGET-PACKAGE-CACHE-2026-11-25.md": [
    26,
    13
  ],
  "research/compiler-and-translation/RT-13/RT-13-FFI-WINDOWS-COFF-PROFILES-2026-11-25.md": [
    26,
    22
  ],
  "research/compiler-and-translation/RT-13/RT-13-LLVM-BITCODE-TOOLCHAIN-2026-11-25.md": [
    29,
    5
  ],
  "research/compiler-and-translation/RT-13/RT-13-LLVM-CORRELATED-FREEZE-2026-11-25.md": [
    30,
    30
  ],
  "research/compiler-and-translation/RT-13/RT-13-PROFILE-GUIDED-COST-RANKING-2026-11-25.md": [
    31,
    0
  ],
  "research/compiler-and-translation/RT-13/RT-13-WASI-REACTOR-WRITE-2026-11-25.md": [
    23,
    0
  ],
  "research/formal-verification/RT-33/RT-33-CHECKED-TRANSFER-2026-11-25.md": [
    41,
    0
  ],
  "research/formal-verification/RT-33/RT-33-SMT-ADAPTER-COMPARISON-2026-11-25.md": [
    38,
    0
  ],
  "research/formal-verification/RT-33/RT-33-TYPED-PROOF-KEYS-2026-11-25.md": [
    43,
    0
  ],
  "research/language-design/RT-01/RT-01-END-TO-END-EXAMPLES-2026-11-25.md": [
    23,
    0
  ],
  "research/language-design/RT-03/RT-03-DOWNSTREAM-EDGE-EVIDENCE-2026-11-25.md": [
    53,
    0
  ],
  "research/language-design/RT-03/RT-03-SEMANTIC-PROFILES-FOR-SYNTHESIS-2026-11-25.md": [
    41,
    0
  ],
  "research/language-design/RT-31/RT-31-FRONTEND-CONTRACT-2026-11-25.md": [
    38,
    0
  ],
  "research/language-design/RT-31/RT-31-HELDOUT-REGRESSION-2026-11-25.md": [
    44,
    0
  ],
  "research/language-design/RT-31/RT-31-HYBRID-PROFILE-2026-11-25.md": [
    38,
    0
  ],
  "research/language-design/RT-31/RT-31-MCP-SESSION-DAG-2026-11-25.md": [
    27,
    0
  ],
  "research/research-management/RT-00/RT-00-C-TIMING-PROVENANCE-2026-11-25.md": [
    35,
    0
  ],
  "research/research-management/RT-00/RT-00-CURRENT-CORPUS-RELATIONSHIPS-2026-11-25.md": [
    52,
    0
  ],
  "research/research-management/RT-00/RT-00-DEPENDENCY-INTEGRATION-CROSSWALK-2026-11-25.md": [
    23,
    23
  ],
  "research/research-management/RT-00/RT-00-FFI-ARCHIVE-REPLAY-2026-11-25.md": [
    26,
    26
  ],
  "research/research-management/RT-00/RT-00-GIT-ARCHIVE-REPLAY-2026-11-25.md": [
    24,
    24
  ],
  "research/research-management/RT-00/RT-00-OBSERVATION-EVIDENCE-DEPENDENCY-RECHECK-2026-11-25.md": [
    27,
    27
  ],
  "research/research-management/RT-00/RT-00-OBSERVATION-PROVENANCE-2026-11-25.md": [
    30,
    30
  ],
  "research/research-management/RT-00/RT-00-REPLACEMENT-AND-CONFLICT-CUE-REVIEW-2026-11-25.md": [
    34,
    0
  ],
  "research/research-management/RT-00/RT-00-TOOLCHAIN-PUBLICATION-DEPENDENCIES-2026-11-25.md": [
    29,
    29
  ],
  "research/research-management/RT-00/RT-00-TRACKED-ARCHIVE-REPLAY-2026-11-25.md": [
    39,
    39
  ],
  "research/research-management/RT-00/RT-00-VERIFICATION-DEPENDENCIES-2026-11-25.md": [
    30,
    0
  ],
  "research/research-management/SCALABILITY-METRICS-2026-11-25.md": [
    29,
    0
  ],
  "research/runtime-and-systems/RT-37/RT-37-ESP32-SCHEDULING-AND-RADIO-2026-11-25.md": [
    32,
    0
  ],
  "research/runtime-and-systems/RT-37/RT-37-EXECUTION-CLOSURE-AND-ALLOCATION-PROFILES-2026-11-25.md": [
    0,
    0
  ],
  "research/runtime-and-systems/RT-37/RT-37-RESOURCE-AND-DEADLINE-BOUNDS-2026-11-25.md": [
    32,
    0
  ],
  "research/runtime-and-systems/RT-38/RT-38-COMPOSED-WAKEUP-AND-REUSE-2026-11-25.md": [
    33,
    0
  ],
  "research/security/RT-16/RT-16-ISOLATION-AND-MEDIATED-EFFECTS-2026-11-25.md": [
    35,
    0
  ],
  "research/security/RT-16/RT-16-PROVENANCE-AND-REBUILD-BOUNDARY-2026-11-25.md": [
    41,
    0
  ],
  "research/semantic-representation/RT-35/RT-35-ANN-CONTRACT-FILTER-2026-11-25.md": [
    33,
    0
  ],
  "research/semantic-representation/RT-35/RT-35-BOUND-NATIVE-CALL-2026-11-25.md": [
    26,
    26
  ],
  "research/semantic-representation/RT-35/RT-35-CHANNEL-COST-AND-CORPUS-2026-11-25.md": [
    0,
    0
  ],
  "research/toolchain-and-collaboration/RT-11/RT-11-BUILD-STAGE-REPLAY-2026-11-25.md": [
    39,
    39
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-BOUNDARIES-2026-11-25.md": [
    40,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-CANDIDATE-AND-TASK-OWNERSHIP-2026-11-25.md": [
    33,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-FIXTURE-SCORING-2026-11-25.md": [
    24,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-IDENTITY-2026-11-25.md": [
    41,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-PROJECTIONS-2026-11-25.md": [
    38,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-CONTEXT-TOKENS-2026-11-25.md": [
    33,
    0
  ],
  "research/toolchain-and-collaboration/RT-14/RT-14-TASK-PRODUCERS-2026-11-25.md": [
    46,
    0
  ],
  "research/toolchain-and-collaboration/RT-19/RT-19-GENERATION-PUBLICATION-2026-11-25.md": [
    36,
    36
  ],
  "research/toolchain-and-collaboration/RT-19/RT-19-INTERCHANGE-AND-PUBLICATION-BOUNDARY-2026-11-25.md": [
    39,
    0
  ],
  "research/toolchain-and-collaboration/RT-19/RT-19-TOOLCHAIN-ROUNDTRIP-2026-11-25.md": [
    33,
    33
  ],
  "research/toolchain-and-collaboration/RT-20/RT-20-CALL-IDENTITY-RECONCILIATION-2026-11-25.md": [
    27,
    0
  ],
  "research/toolchain-and-collaboration/RT-20/RT-20-CONSUMER-FORK-IDENTITY-2026-11-25.md": [
    30,
    0
  ],
  "research/toolchain-and-collaboration/RT-24/RT-24-CONCURRENT-GRAPH-2026-11-25.md": [
    36,
    36
  ],
  "research/toolchain-and-collaboration/RT-24/RT-24-MERGE-ADMISSION-COVERAGE-2026-11-25.md": [
    28,
    0
  ],
  "research/toolchain-and-collaboration/RT-24/RT-24-PURE-MERGE-CORE-2026-11-25.md": [
    35,
    35
  ],
  "research/toolchain-and-collaboration/RT-24/RT-24-TYPED-SEMANTIC-DIFF-2026-11-25.md": [
    29,
    29
  ],
  "research/toolchain-and-collaboration/RT-24/RT-24-WHOLE-GRAPH-REVERSE-AND-CIP-GATE-2026-11-25.md": [
    38,
    0
  ]
};

function closeReports(ledgers,tree) {
 const nearby={};
 for(const row of ledgers){
  const fixture=row.path.slice(0,row.path.lastIndexOf("/")); const stage=fixture.slice(0,fixture.lastIndexOf("/"));
  nearby[row.path]=Object.keys(tree).filter(path=>/\.(md|mdx)$/i.test(path)&&[fixture,stage].includes(path.slice(0,path.lastIndexOf("/")))).sort();
 }
 return nearby;
}

function normalized(parent, rel){
 const out=parent.split("/");
 for(const part of rel.split("/")){
  if(part==="..")out.pop();
  else if(part&&part!==".")out.push(part);
 }
 return out.join("/");
}

function cites(path, report, source){
 const dir=report.slice(0,report.lastIndexOf("/"));
 const claims=[];
 const lines=source.split("\n");
 for(let n=0;n<lines.length;n++){
  const line=lines[n];
  for(const m of line.matchAll(/\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)/g)){
   let ref=(m[1]??m[2]).split("#",1)[0];
   if(!ref||ref.startsWith("/")||/^[A-Za-z][\w+.-]*:/.test(ref))continue;
   try{ref=decodeURIComponent(ref);}catch{continue;}
   if(normalized(dir,ref)===path)
     claims.push({line:n+1,reference:ref});
  }
 }
 return claims;
}

function results(nearby, matches, manifest, input) {
 const docs=new Set(Object.values(nearby).flat());
 const totals={ledgers:0,nearby_reports_scanned:docs.size,exact_linked_reports:Object.keys(matches).length,ledgers_with_direct_link:0,documented_tools:0,patch_specific_tool_version:0,doc_host:0,tool_and_host:0,linked_but_no_replay_tool:0,no_direct_link:0};
 const ledgers=[];
 for(const {path,blob} of input.sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0)){
  const reports=[];
  for(const report of nearby[path]){
   const found=matches[report];
   if(!found?.citations[path]?.length)continue;
   const reviewed=manifest[report];
   if(!reviewed)throw Error("Missing review of "+report);
   const [v,h]=reviewed;
   const lines=found.content.split("\n");
   const metadata=(n)=>n?{line:n,text:lines[n-1]}:null;
   const tool=metadata(v);
   const host=metadata(h);
   if(tool&&!/\b\d+\.\d+\b/.test(tool.text))throw Error("Missing tool version in "+report);
   if(host&&!/\b(Linux|Debian|Ubuntu|overlayfs)\b/i.test(host.text))throw Error("Missing host identifier in "+report);
   reports.push({path:report,blob:found.blob,citations:found.citations[path],tool,host});
  }
  const hasLink=reports.length>0;
  const hasTool=reports.some(r=>r.tool);
  const hasHost=reports.some(r=>r.host);
  const patch=reports.some(r=>r.tool&&/\b\d+\.\d+\.\d+\b/.test(r.tool.text));
  totals.ledgers++;
  totals.ledgers_with_direct_link+=Number(hasLink);
  totals.documented_tools+=Number(hasTool);
  totals.patch_specific_tool_version+=Number(patch);
  totals.doc_host+=Number(hasHost);
  totals.tool_and_host+=Number(hasTool&&hasHost);
  totals.linked_but_no_replay_tool+=Number(hasLink&&!hasTool);
  totals.no_direct_link+=Number(!hasLink);
  ledgers.push({path,blob,reports});
 }
 return {pinned_tree:"7d407636c4a06d1b601376bc66ea96d5a26e0b8f",totals,ledgers};
}

function git(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 }).toString("utf8");
}

const files = {};
for (const entry of git("ls-tree", "-rz", pinned, "research").split("\0").filter(Boolean)) {
  const tab = entry.indexOf("\t");
  const [, type, blob] = entry.slice(0, tab).split(" ");
  if (type === "blob") files[entry.slice(tab + 1)] = blob;
}

const input = JSON.parse(readFileSync(metadataLedger, "utf8"));
if (input.pinned_tree !== pinned) throw Error("Metadata selection refers to another tree");
const subjects = input.ledgers.filter(row => !Object.keys(row.version).length &&
  !Object.keys(row.host).length && !Object.keys(row.digest).length);
if (subjects.length !== 69) throw Error("Unexpected ledger population");
for (const row of subjects) {
  if (row.blob !== files[row.path]) throw Error("Historical ledger blob changed: " + row.path);
}
const nearby = closeReports(subjects, files);
const inverse = {};
for (const [ledger, reports] of Object.entries(nearby)) {
  for (const report of reports) (inverse[report] ??= []).push(ledger);
}

const found = {};
for (const report of Object.keys(inverse).sort()) {
  const blob = files[report];
  const content = git("cat-file", "blob", blob);
  const citations = {};
  for (const path of inverse[report]) {
    const links = cites(path, report, content);
    if (links.length) citations[path] = links;
  }
  if (Object.keys(citations).length) found[report] = { blob, citations, content };
}
process.stdout.write(JSON.stringify(results(nearby, found, reviewedLines, subjects), null, 2) + "\n");
