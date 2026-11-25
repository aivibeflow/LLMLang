#!/usr/bin/env node
import { execFileSync } from "node:child_process";

const pinned = "7d407636c4a06d1b601376bc66ea96d5a26e0b8f";
const manifest = {
  "research/formal-verification/RT-34/PARALLEL-EXPECTED-OUTPUT-01/evidence.json": {
    "report": "research/formal-verification/RT-34/RT-34-PARALLEL-EXPECTED-OUTPUT-2026-11-25.md",
    "line": 31,
    "command": 34,
    "version": "Lean 4.36.0"
  },
  "research/formal-verification/RT-34/READ-LOWER-AND-QUEUE-01/evidence.json": {
    "report": "research/formal-verification/RT-34/RT-34-READ-LOWER-AND-QUEUE-2026-11-25.md",
    "line": 19,
    "command": 22,
    "version": "Lean 4.36.0"
  },
  "research/formal-verification/RT-34/RESOURCE-CONTRACT-IR-01/evidence.json": {
    "fields": [
      [
        "checker"
      ]
    ]
  },
  "research/language-design/RT-04/ASYNC-RESOURCE-CANCELLATION-01/evidence.json": {
    "fields": [
      [
        "rust"
      ]
    ]
  },
  "research/language-design/RT-04/DEPENDENT-BOUNDARY-VALUES-01/evidence.json": {
    "fields": [
      [
        "rust"
      ]
    ]
  },
  "research/language-design/RT-04/GENERIC-CONTEXT-INFERENCE-01/evidence.json": {
    "fields": [
      [
        "toolchains",
        "go"
      ],
      [
        "toolchains",
        "rust"
      ]
    ]
  },
  "research/language-design/RT-04/PRIMITIVE-ALGEBRAIC-ENCODINGS-01/evidence.json": {
    "fields": [
      [
        "rows",
        "clang/-O0",
        "compiler"
      ],
      [
        "rows",
        "clang/-O2",
        "compiler"
      ],
      [
        "rows",
        "gcc/-O0",
        "compiler"
      ],
      [
        "rows",
        "gcc/-O2",
        "compiler"
      ]
    ]
  },
  "research/language-design/RT-04/SCOPED-MUTABLE-REGIONS-01/evidence.json": {
    "fields": [
      [
        "rust"
      ]
    ]
  },
  "research/language-design/RT-04/TYPED-CAPABILITY-ERRORS-01/evidence.json": {
    "fields": [
      [
        "rust"
      ]
    ]
  },
  "research/runtime-and-systems/RT-10/RESUMABLE-EXECUTION-01/evidence.json": {
    "report": "research/runtime-and-systems/RT-10/RT-10-RESUMABLE-EXECUTION-2026-11-25.md",
    "line": 19,
    "command": 22,
    "version": "CPython 3.12.14"
  },
  "research/runtime-and-systems/RT-37/TARGET-CLOSURE-CROSSWALK-01/evidence.json": {
    "report": "research/runtime-and-systems/RT-37/RT-37-EXECUTION-CLOSURE-AND-ALLOCATION-PROFILES-2026-11-25.md",
    "line": 0,
    "command": 28,
    "version": null
  },
  "research/toolchain-and-collaboration/RT-11/CROSS-LANGUAGE-RECEIPTS-01/evidence.json": {
    "fields": [
      [
        "actions",
        "c-saturate",
        "descriptor",
        "tool_version"
      ],
      [
        "actions",
        "c-wrap",
        "descriptor",
        "tool_version"
      ],
      [
        "actions",
        "rust-saturate",
        "descriptor",
        "tool_version"
      ],
      [
        "actions",
        "rust-wrap",
        "descriptor",
        "tool_version"
      ]
    ]
  },
  "research/toolchain-and-collaboration/RT-11/PACKAGE-CACHE-DELIVERY-01/evidence.json": {
    "report": "research/toolchain-and-collaboration/RT-11/RT-11-PACKAGE-CACHE-DELIVERY-2026-11-25.md",
    "line": 23,
    "command": 26,
    "version": "Lean 4.36.0"
  }
};

function residual(known, manifest, get){
 const plan=get("PLAN.md"), picks=[],totals={ledgers:0,embedded_version:0,companion_version:0,no_version_in_checked_sources:0,plan_mentions:0};
 for(const p of Object.keys(manifest).sort()){
  const fixtureDir=p.slice(0,p.lastIndexOf("/"));
  const fixture=fixtureDir.split("/").at(-1);
  const ledger=get(p);
  const runnerPath=`${fixtureDir}/${fixture==="TARGET-CLOSURE-CROSSWALK-01"?"check.py":"run.py"}`;
  const runner=get(runnerPath);
  const row={path:p,blob:ledger.blob,runner:{path:runnerPath,blob:runner.blob},plan_mentions:plan.text.split("\n").map((x,i)=>x.includes(fixture)?i+1:0).filter(Boolean)};
  totals.ledgers++;
  totals.plan_mentions+=row.plan_mentions.length;
  const choice=manifest[p];
  if(choice.fields){
   const b=JSON.parse(ledger.text);
   row.recorded_tool_strings=choice.fields.map(keys=>{
    const value=keys.reduce((value,key)=>value[key],b);
    if(typeof value!=="string"||!/(?:^|[^\d])\d+\.\d+\.\d+\b/.test(value))throw Error("Version field did not resolve for "+fixture);
    if(!runner.text.includes('"'+keys.at(-1)+'"'))throw Error("Runner no longer names the field for "+fixture);
    return {keys,value};
   });
   row.disposition="embedded-version";
   totals.embedded_version++;
  }else{
   const report=get(choice.report);const lines=report.text.split("\n");
   const command=lines[choice.command-1];
   if(!command.includes(fixtureDir))throw Error("Report command path differs for "+fixture);
   const version=choice.line?lines[choice.line-1]:null;
   if(choice.version&&!version?.includes(choice.version))throw Error("Version declaration differs for "+fixture);
   row.companion={path:choice.report,blob:report.blob,command_line:choice.command,command,version_line:choice.line||null,version};
   row.disposition=choice.version?"companion-version":"no-version-in-checked-sources";
   if(choice.version)totals.companion_version++;
   else totals.no_version_in_checked_sources++;
  }
  picks.push(row);
 }
 return {pinned_tree:known,plan_blob:plan.blob,totals,ledgers:picks};
}

function git(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 }).toString("utf8");
}

function get(path) {
  const blob = git("rev-parse", "--verify", pinned + ":" + path).trim();
  return { blob, text: git("cat-file", "blob", blob) };
}

process.stdout.write(JSON.stringify(residual(pinned, manifest, get), null, 2) + "\n");
