#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const previous = "087d2e5e952255778d76637ce5fd41b9df2d5396";
const pinned = "7d407636c4a06d1b601376bc66ea96d5a26e0b8f";

function fields(body, path) {
 const names=["archive_replay_sources_sha256","input_sources_sha256","runner_sha256","source_digests","source_sha256","sources","sources_sha256","file_sha256","fixture_sha256","input_sha256","prototype_sha256","replayed_ledger_sha256","replayed_axiom_output_sha256"];
 const selected=[];
 const valid=value=>typeof value==="string"&&/^(?:sha256:)?[a-f0-9]{64}$/.test(value);
 for(const key of names){
  const value=body[key];
  if(key==="runner_sha256"&&typeof value==="string")selected.push([key,null,valid(value)?value:null]);
  else if(value&&typeof value==="object"&&!Array.isArray(value)){
    for(const label of Object.keys(value).sort())selected.push([key,label,valid(value[label])?value[label]:null]);
  }
 }
 if(path.endsWith("/FFI-HOSTED-PROFILE-MATRIX-01/evidence.json")){
  if(!valid(body.fixture_sha256))throw Error("Missing FFI fixture hash");
  selected.push(["fixture_sha256","abi.c",body.fixture_sha256]);
 }
 return {fields:selected,baseline:typeof body.baseline==="string"&&/^[a-f0-9]{40}$/.test(body.baseline)?body.baseline:null};
}

function locate(ledger,key,label,baseline,current){
 const parts=ledger.split("/"); parts.pop();
 const folder=parts.join("/");
 const stage=parts.slice(0,-1).join("/");
 const category=parts.slice(0,-2).join("/");
 const fixture=parts[parts.length-1];
 const stagePaths=new Set(["JIT-SHARED-CONFORMANCE-01","LAYER-BOUNDARIES-01","INDEX-INTEGRITY-01","POSIX-CROSS-LIBC-01","PRIMITIVE-ERROR-DOMAINS-01","COMPOSED-MAPPING-IPC-01","RV64-HAL-QEMU-01","RV64-LIVE-FRAME-IPC-01","RV64-TIMER-PREEMPTION-01","CONTRACT-BODY-MERGES-01"]);
 const categoryPaths=new Set(["LIBRARY-CONTRACT-01","PORTABLE-MANIFEST-01","COMPONENT-ALLOCATOR-01"]);
 if(fixture==="NATIVE-MERGE-DRIVER-REPLAY-01"&&key==="fixture_sha256"&&baseline){
   return [`${stage}/NATIVE-MERGE-DRIVER-01/${label}`,baseline,"archived-original-fixture"];
 }
 if(label===null){
   return current[`${folder}/run.py`] ?
      [`${folder}/run.py`,null,"scalar-runner"] : [`${folder}/check.py`,null,"scalar-runner"];
 }
 if(label.startsWith("research/")||fixture==="EVIDENCE-PROTOCOL-BOUNDARY-01"&&label.startsWith("draft/"))
   return [label,null,"repository-relative"];
 if(["NAVIGATION-DELTA-01","PLAN-NAVIGATION-01"].includes(fixture) &&
   ["audit_research_index_coverage.py","audit_research_index_reachability.py"].includes(label))
   return [`.github/scripts/${label}`,null,"navigation-audit-source"];
 if(stagePaths.has(fixture)&&label.includes("/"))return [`${stage}/${label}`,null,"stage-relative"];
 if(categoryPaths.has(fixture)&&label.includes("/"))return [`${category}/${label}`,null,"category-relative"];
 if(["SEMANTIC-IMPACT-AND-EVIDENCE-01","COMMIT-TREE-SEMANTIC-ROOT-01"].includes(fixture)&&key==="prototype_sha256")
   return [`research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/${label}`,null,"shared-prototype"];
 if((fixture==="MERGE-RESOLUTION-BOUNDARY-01"&&key==="sources"||
     fixture==="REVIEW-PACKET-BOUNDARY-01"&&key==="input_sha256")&&/^[\w-]+-01$/.test(label))
   return [`${stage}/${label}/evidence.json`,null,"sibling-evidence"];
 const joint="research/language-design/RT-04/JOINT-CONTRACTS-01";
 const pkg="research/packages-and-ecosystem/PROTOTYPES";
 const aliases={
  "ANALOGUE-DISPATCH-01":{joint_contract_runner:`${joint}/run.py`,native_provider_probe:`${joint}/probe.c`},
  "CONTEXTUAL-SUBSTITUTION-01":{native_reference_runner:`${joint}/run.py`,native_probe:`${joint}/probe.c`},
  "CONTRACT-INFERENCE-01":{joint_native_runner:`${joint}/run.py`,joint_native_probe:`${joint}/probe.c`},
  "AUTHORIZED-INDEX-01":{"sparse.py":`${stage}/INDEX-INTEGRITY-01/sparse.py`,signing:"research/security/RT-16/BUILD-ATTESTATION-01/run.py"},
  "OFFLINE-SEMANTIC-CLONE-01":{closed_graph_reader:`${stage}/CLOSED-GRAPH-BACKUP-01/run.py`},
  "PACKAGE-CONTENT-01":{"package_archive.py":`${pkg}/PACKAGE-INDEX-01/package_archive.py`,"package_index.py":`${pkg}/PACKAGE-INDEX-01/package_index.py`,"package_identity.py":`${pkg}/PACKAGE-IDENTITY-01/package_identity.py`},
  "SCOPED-REGISTRY-01":{"content_store.py":`${pkg}/PACKAGE-INDEX-01/content_store.py`},
  "CHANNEL-COST-01":{fixture:`${stage}/SCOPED-RETRIEVAL-01/run.py`},
  "BOUNDED-TRAVERSAL-FALLBACK-01":{diamond_fixture:`${stage}/DIAMOND-TRAVERSAL-01/run.py`,runner:`${folder}/run.py`}
 };
 const alias=aliases[fixture]?.[label];
 if(alias)return [alias,null,"explicit-producer-alias"];
 // Resolve only relative labels under the fixture. Every accepted candidate is checked
 // by path before hashing. No fallback searches the tree by digest.
 const combined=[];
 for(const part of `${folder}/${label}`.split("/")){
   if(part==="..")combined.pop();
   else if(part&&part!==".")combined.push(part);
 }
 return [combined.join("/"),null,"fixture-relative"];
}

function sourceOverride(ledger,field,label){
 const dir=ledger.slice(0,ledger.lastIndexOf("/"));
 const stage=dir.slice(0,dir.lastIndexOf("/"));
 const name=dir.split("/").at(-1);
 if(name==="EVIDENCE-PROTOCOL-BOUNDARY-01"&&field==="input_sha256")return [label,"1ec32a8c356a1a44c3531a59e25d73a60120313b","protocol-baseline"];
 const pkg="research/runtime-and-systems/PROTOTYPES";
 const cargo=`${pkg}/ALLOCATOR-COMPAT-01/probe.rs`;
 const signing="research/security/RT-16/BUILD-ATTESTATION-01/run.py";
 const cleanup="research/language-design/RT-03/SOURCE-CLEANUP-CFG-01";
 const aliases={
  "ROUTE-RESOURCE-GATE-01":{"checker.py":`${stage}/DIFFERENCE-CERTIFICATE-01/checker.py`,"run.py":`${stage}/SOURCE-DIFFERENCE-ROUTES-01/run.py`},
  "SOURCE-OWNERSHIP-GRANT-01":{"flow.py":`${cleanup}/flow.py`,"reference.py":`${cleanup}/reference.py`,"run.py":`${cleanup}/run.py`},
  "ALLOCATOR-CONCURRENT-01":{compatibility_probe:cargo},
  "MODERN-TCMALLOC-01":{probe:cargo,graph:`${pkg}/ALLOCATOR-BENCH-01/graph.rs`},
  "DURABLE-MIGRATION-01":{"run.py":`${stage}/DIGEST-MIGRATION-01/run.py`,"migration.py":`${stage}/DIGEST-MIGRATION-01/migration.py`},
  "WIRE-SUITE-01":{"run.py":`${stage}/CANONICAL-WIRE-01/run.py`,"decode.mjs":`${stage}/CANONICAL-WIRE-01/decode.mjs`},
  "BOUNDARY-TESTS-01":{"policy.py":"research/security/PROTOTYPES/RT-16-AUTHORIZATION-01/policy.py","run.py":`${stage}/TOOLCHAIN-ROUNDTRIP-01/run.py`,"toolchain.py":"research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01/toolchain.py"},
  "AUDIT-CHAIN-01":{signing_fixture:signing}
 };
 return aliases[name]?.[label]&&["source_sha256","sources","sources_sha256"].includes(field)?[aliases[name][label],null,"explicit-producer-alias"]:null;
}

function prepare(ledgerFields, current, locate, sourceOverride) {
 const lookup={},queries={};
 for(const path of Object.keys(ledgerFields).sort()){
  const {fields,baseline}=ledgerFields[path];
  lookup[path]=fields.map(([field,label,advertised_sha256])=>{
   if(!advertised_sha256)return {field,label,status:"inline-or-other-schema"};
   const [source,revision,path_basis]=sourceOverride(path,field,label)??locate(path,field,label,baseline,current);
   const available=current[source];
   const query=revision?`${revision}:${source}`:available&&source!==path?available[0]:null;
   if(query)queries[query]=[source,revision,available,path_basis];
   return {field,label,path:source,revision,path_basis,advertised_sha256,query};
  });
 }
 return {lookup,queries};
}

function recognizesRunner(text) {
 return /runner_sha256[^\n]*__file__/.test(text) ||
        /runner_sha256[^\n]*HERE\.joinpath\("run\.py"\)/.test(text);
}

function summarize(index, lookup, observations, pin, oldPin, beforeSize, afterSize) {
 const totals={};
 const ledgers=[];
 for(const path of Object.keys(lookup).sort()){
   const bindings=lookup[path].map(binding=>{
      const {query,revision,...entry}=binding;
      let row;
      if(binding.status)row=entry;
      else{
       const data=query?observations[query]:undefined;
       const verifiedRunner=binding.path_basis!=="scalar-runner"||data?.[2];
       if(!data||!verifiedRunner){
         row={...entry,revision:revision??pin,status:!data?"unresolved-path":"unresolved-runner-binding"};
       }else{
         const [blob,actual_sha256]=data;
         row={...entry,revision:revision??pin,blob,actual_sha256,status:actual_sha256===binding.advertised_sha256.replace(/^sha256:/, "")?"match":"mismatch"};
       }
      }
      totals[row.status]=(totals[row.status]??0)+1;
      return row;
   });
   ledgers.push({path,blob:index[path][0],bindings});
 }
 return {previous:oldPin,pinned_tree:pin,previous_ledgers:beforeSize,current_ledgers:afterSize,added:ledgers.length,field_results:totals,added_ledgers:ledgers};
}

function format(report){
 const {added_ledgers,...header}=report;
 return JSON.stringify(header,null,2).slice(0,-2)+',\n  "added_ledgers": [\n'+added_ledgers.map(x=>"    "+JSON.stringify(x)).join(",\n")+"\n  ]\n}\n";
}

function git(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 });
}

function treeAt(revision) {
  const records = git("ls-tree", "-rlz", revision).toString("utf8").split("\0").filter(Boolean);
  return Object.fromEntries(records.map(record => {
    const tab = record.indexOf("\t");
    const [, type, sha, size] = record.slice(0, tab).trim().split(/\s+/);
    return [record.slice(tab + 1), { type, sha, size: Number(size) }];
  }).filter(([, entry]) => entry.type === "blob").map(([path, entry]) => [path, [entry.sha, entry.size]]));
}

const isLedger = path => path.startsWith("research/") && path.endsWith("/evidence.json");
const oldTree = treeAt(previous);
const newTree = treeAt(pinned);
const before = Object.keys(oldTree).filter(isLedger).sort();
const after = Object.keys(newTree).filter(isLedger).sort();
const changed = before.filter(path => newTree[path]?.[0] !== oldTree[path][0]);
if (changed.length) throw Error("Previous ledger entries changed or disappeared: " + changed.join(", "));

const ledgerFields = {};
for (const path of after.filter(path => !oldTree[path])) {
  const content = git("cat-file", "blob", newTree[path][0]).toString("utf8");
  ledgerFields[path] = fields(JSON.parse(content), path);
}

const { lookup, queries } = prepare(ledgerFields, newTree, locate, sourceOverride);
const historicalTrees = new Map();
const observations = {};
for (const [query, [path, revision, current]] of Object.entries(queries)) {
  if (revision && !historicalTrees.has(revision)) historicalTrees.set(revision, treeAt(revision));
  const source = revision ? historicalTrees.get(revision)[path] : current;
  if (!source) continue;
  const [blob, size] = source;
  const bytes = git("cat-file", "blob", blob);
  if (bytes.length !== size) throw Error("Tracked blob size changed: " + path);
  observations[query] = [blob, createHash("sha256").update(bytes).digest("hex"), recognizesRunner(bytes.toString("utf8"))];
}

const report = summarize(newTree, lookup, observations, pinned, previous, before.length, after.length);
process.stdout.write(format(report));
