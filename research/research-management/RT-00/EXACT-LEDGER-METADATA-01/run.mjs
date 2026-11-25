#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const selection = "research/research-management/RT-00/EXACT-LEDGER-REFRESH-01/evidence.json";
const pinned = "7d407636c4a06d1b601376bc66ea96d5a26e0b8f";

function metadata(body){
 const exactVersion=value=>typeof value==="string"&&/(?:^|[^0-9.])\d+\.\d+(?:\.\d+){0,2}(?=$|[^0-9.])/.test(value);
 const digest=value=>typeof value==="string"&&/^(?:sha256:)?[a-f0-9]{64}$/.test(value);
 const arch=value=>typeof value==="string"&&/^(x86_64|amd64|aarch64|arm64|riscv64|s390x|ppc64le)$/i.test(value);
 const fields={version:{},digest:{},host:{}};
 const versions=["python","python_version","git","git_version","sqlite","gcc","clang","compiler","rustc","lean","qemu","qemu_version","go","java","tlc","apalache","node","archive_tool","llvm_version","runtime"];
 for(const key of versions)if(exactVersion(body[key]))fields.version[key]=body[key];
 const digests=["clang_sha256","python_sha256","qemu_sha256","apalache_jar","libc_archive_sha256"];
 for(const key of digests)if(digest(body[key]))fields.digest[key]=body[key];
 for(const key of ["tool_versions","solver_versions"]){
  for(const [name,version] of Object.entries(body[key]??{}).sort())if(exactVersion(version))fields.version[`${key}.${name}`]=version;
 }
 for(const key of ["tool_hashes","libc_archive_sha256","libc_archives_sha256"]){
  const value=body[key];
  if(!value||typeof value!=="object"||Array.isArray(value))continue;
  for(const [name,hash] of Object.entries(value).sort())if(digest(hash))fields.digest[`${key}.${name}`]=hash;
 }
 for(const key of ["tool","fixture_compiler"]){
  const value=body[key];
  if(value&&exactVersion(value.version))fields.version[`${key}.version`]=value.version;
  for(const label of ["digest","artifact"])if(value&&digest(value[label]))fields.digest[`${key}.${label}`]=value[label];
 }
 if(exactVersion(body.kernel))fields.host.kernel=body.kernel;
 for(const key of ["host","machine","native_platform","platform"])if(arch(body[key]))fields.host[key]=body[key];
 for(const label of ["host","platform","toolchain_and_host"]){
  const value=body[label];
  if(!value||typeof value!=="object"||Array.isArray(value))continue;
  for(const key of ["arch","machine","kernel","linux","system","libc","cpu_name","filesystem"]){
   if(typeof value[key]==="string"&&value[key].trim())fields.host[`${label}.${key}`]=value[key];
  }
  for(const key of ["python","toolchain"]){
   if(exactVersion(value[key]))fields.version[`${label}.${key}`]=value[key];
  }
 }
 return fields;
}

function evidence(archive,pinned,selectionLedger) {
 const counts={ledgers:0,versions:0,tool_artifact_hashes:0,host_fields:0,tool_and_host:0,version_without_host:0,none_under_checked_fields:0};
 const rows=[];
 for(const path of Object.keys(archive).sort()){
  const {blob,filter}=archive[path];
  const version=Object.keys(filter.version).length>0;
  const digest=Object.keys(filter.digest).length>0;
  const host=Object.keys(filter.host).length>0;
  counts.ledgers++;
  counts.versions+=Number(version);
  counts.tool_artifact_hashes+=Number(digest);
  counts.host_fields+=Number(host);
  counts.tool_and_host+=Number((version||digest)&&host);
  counts.version_without_host+=Number(version&&!host);
  counts.none_under_checked_fields+=Number(!version&&!digest&&!host);
  rows.push({path,blob,...filter});
 }
 return {pinned_tree:pinned,selection_ledger:selectionLedger,counts,ledgers:rows};
}

function git(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 }).toString("utf8");
}

const previous = JSON.parse(readFileSync(selection, "utf8"));
if (previous.pinned_tree !== pinned) throw Error("Input provenance census refers to another tree");
const subjects = previous.added_ledgers.filter(row => !row.bindings.some(binding => binding.status === "match"));
if (subjects.length !== 207) throw Error("Unexpected evidence population");

const archive = {};
for (const { path, blob } of subjects) {
  if (git("rev-parse", "--verify", pinned + ":" + path).trim() !== blob) {
    throw Error("Selection path has a different Git blob: " + path);
  }
  const body = JSON.parse(git("cat-file", "blob", blob));
  archive[path] = { blob, filter: metadata(body) };
}
process.stdout.write(JSON.stringify(evidence(archive, pinned, selection), null, 2) + "\n");
