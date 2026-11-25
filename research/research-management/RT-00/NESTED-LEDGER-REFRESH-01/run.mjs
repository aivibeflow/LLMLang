#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const pinned = "7d407636c4a06d1b601376bc66ea96d5a26e0b8f";
const subjects = [
  "research/research-management/SCALABILITY-METRICS-01/evidence.json",
  "research/research-management/planning-and-synthesis/CONCURRENT-RELEASE-01/evidence.json",
  "research/runtime-and-systems/RT-10/POSIX-PROFILE-EVIDENCE-01/evidence.json",
  "research/toolchain-and-collaboration/RT-14/SOURCE-INVENTORY-01/evidence.json"
];

function nestedCandidates(path, body, pin) {
 const fixture=path.split("/").at(-2);
 const stage=path.split("/").slice(0,-2).join("/");
 const cases=[];
 for(const [label, value] of Object.entries(body.sources).sort(([a],[b])=>a<b?-1:a>b?1:0)){
  if(fixture==="SCALABILITY-METRICS-01"){
   const samples=`research/${value.samples}`;
   const dir=samples.slice(0,samples.lastIndexOf("/"));
   cases.push({label,kind:"timing-set",rows:value.rows,building:[["samples",samples,value.samples_sha256],["config",`${dir}/config.json`,value.config_sha256],["summary",`${dir}/summary.json`,value.summary_sha256]].map(([role,source,sha256])=>({role,source,revision:pin,sha256}))});
  }else if(fixture==="CONCURRENT-RELEASE-01"){
   const sibling=label.startsWith(`${stage}/EXACT-PROVIDER-RELEASE-01/`);
   cases.push({label,kind:"git-source",building:[{role:"source",source:label,revision:sibling?body.base:"685c3a13ef600ce76bfe9d36446b970cc7c6c3da",git_blob:value}]});
  }else if(fixture==="POSIX-PROFILE-EVIDENCE-01"){
   cases.push({label,kind:"pinned-posix-ledger",building:[{role:"ledger",source:`${stage}/${value[0]}`,revision:pin,sha256:value[1]}]});
  }else if(fixture==="SOURCE-INVENTORY-01"){
   const anchors={
    specification:"# 0003 — Integer Calculator",
    design:"# RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge",
    implementation:"operation parse_expression(line: String) -> Result<Expression, CalcError>:",
    contract:"| ContractHash | Exact contract value |",
    requirement:'"failure_frame": "BankAccount shall always satisfy !success -> (new_balance = old_balance)"',
    dependency:'"difference_id": "4da4012b6d1f7953a26362a17b277fb094df8e310b47bb63c74d10883df57030"',
    diagnostic:"error: Tactic `decide` proved that the proposition",
    test:"def test_all_added_edges_and_all_removed_paths_need_an_explicit_account",
    "proof-evidence":'"status": "kernel-checked"',
    documentation:"## How the language is designed",
    "external-reference":"https://smt-lib.org/papers/smt-lib-reference-v2.7-r2026-09-09.pdf"
   };
   cases.push({label,kind:"source-anchor",building:[{role:"anchor",source:value.path,revision:body.snapshot,sha256:value.sha256,git_blob:value.blob,line:value.line,anchor:anchors[label]}]});
  }else throw Error(`Unexpected deferred producer schema ${path}`);
 }
 return cases;
}

function verifyNested(ledgers, pin, getSource, hash, candidates) {
 const result={pinned_tree:pin,counts:{cases:0,file_paths:0,sha256_matches:0,git_blob_matches:0,anchor_matches:0,timing_sets:0,timing_rows:0},ledgers:[]};
 for(const path of Object.keys(ledgers).sort()){
  const {blob,body}=ledgers[path];
  const observations=[];
  for(const item of candidates(path,body,pin)){
   result.counts.cases++;
   const sourceRecords={};
   const checks=item.building.map(binding=>{
    const {git_blob,sha256,line,anchor,...identity}=binding;
    const record=getSource(binding.revision,binding.source,Boolean(sha256));
    if(!record)throw Error(`Missing source ${binding.revision}:${binding.source}`);
    if(git_blob&&git_blob!==record.blob)throw Error(`Git blob differs for ${binding.source}`);
    if(sha256&&sha256!==hash(record.text))throw Error(`SHA-256 differs for ${binding.source}`);
    if(anchor){
      const position=record.text.indexOf(anchor);
      if(position<0||record.text.indexOf(anchor,position+anchor.length)>=0)
       throw Error(`Expected one anchor in ${binding.source}`);
      const actualLine=record.text.slice(0,position).split("\n").length;
      if(actualLine!==line)throw Error(`Anchor line differs in ${binding.source}`);
    }
    sourceRecords[binding.role]=record.text;
    result.counts.file_paths++;
    if(git_blob)result.counts.git_blob_matches++;
    if(sha256)result.counts.sha256_matches++;
    if(anchor)result.counts.anchor_matches++;
    return {...identity,observed_blob:record.blob,...(git_blob?{git_blob}:{}),...(sha256?{sha256}:{}),...(anchor?{line,anchor}:{})};
   });
   const info={label:item.label,kind:item.kind,checks};
   if(item.kind==="timing-set"){
    // Require one CSV record per physical line, allowing quoted commas.
    const text=sourceRecords.samples;
    if(text.split("\n").some(line=>(line.match(/"/g)?.length??0)%2!==0))throw Error(`Unexpected multiline CSV for ${item.label}`);
    const sampleRows=text.trimEnd().split("\n").length-1;
    const source=body.sources[item.label];
    const config=JSON.parse(sourceRecords.config);
    const summary=JSON.parse(sourceRecords.summary);
    if(sampleRows!==item.rows||
       (summary.samples_sha256??summary.sample_sha256)!==source.samples_sha256||
       config.cpu_model!==source.cpu_model||config.kernel!==source.kernel||config.trials!==source.trials_per_profile)
      throw Error(`Timing metadata differs for ${item.label}`);
    result.counts.timing_sets++;
    result.counts.timing_rows+=sampleRows;
    info.rows=sampleRows;
   }
   observations.push(info);
  }
  result.ledgers.push({path,blob,observations});
 }
 return result;
}

function readGit(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 });
}

function getSource(revision, path, needsText) {
  const blob = readGit("rev-parse", "--verify", revision + ":" + path).toString("utf8").trim();
  if (readGit("cat-file", "-t", blob).toString("utf8").trim() !== "blob") {
    throw Error("Expected an exact tracked blob for " + path);
  }
  return { blob, text: needsText ? readGit("cat-file", "blob", blob).toString("utf8") : null };
}

const ledgers = {};
for (const path of subjects) {
  const { blob, text } = getSource(pinned, path, true);
  const body = JSON.parse(text);
  if (body.snapshot && body.tree) {
    const actual = readGit("rev-parse", body.snapshot + "^{tree}").toString("utf8").trim();
    if (body.tree !== actual) throw Error("Source inventory tree does not match its snapshot");
  }
  ledgers[path] = { blob, body };
}

const sha256 = text => createHash("sha256").update(text, "utf8").digest("hex");
const evidence = verifyNested(ledgers, pinned, getSource, sha256, nestedCandidates);
process.stdout.write(JSON.stringify(evidence, null, 2) + "\n");
