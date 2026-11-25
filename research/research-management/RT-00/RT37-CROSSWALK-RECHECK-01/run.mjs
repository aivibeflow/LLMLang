#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const spec = {
  "pinned": "7d407636c4a06d1b601376bc66ea96d5a26e0b8f",
  "archived": "research/runtime-and-systems/RT-37/TARGET-CLOSURE-CROSSWALK-01/evidence.json",
  "inputs": {
    "allocator": "research/runtime-and-systems/RT-37/cortex-m3-allocator/results.json",
    "closure": "research/runtime-and-systems/RT-37/cortex-m3-closure/results.json",
    "esp": "research/runtime-and-systems/RT-37/ESP32-SCHEDULING-PROFILES-01/evidence.json",
    "manifests": "research/runtime-and-systems/RT-37/MCU-TARGET-MANIFESTS-01/manifests.json",
    "renode": "research/runtime-and-systems/RT-37/MCU-GPIO-TIMER-UART-01/arm-emulator-evidence.json",
    "startup": "research/runtime-and-systems/RT-37/cortex-m3-startup-retention/evidence.json",
    "stm32": "research/runtime-and-systems/RT-37/MCU-GPIO-TIMER-UART-01/stm32-evidence.json"
  }
};

function canonical(value){
 if(Array.isArray(value))return value.map(canonical);
 if(value&&typeof value==="object")return Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])]));
 return value;
}

function summarize(inventory,sha256){
 const data={};
 const evidence={};
 const prefix="research/runtime-and-systems/RT-37/";
 for(const key of Object.keys(inventory).sort()){
  const {path,text}=inventory[key];
  data[key]=JSON.parse(text);
  evidence[key]={path:path.slice(prefix.length),sha256:sha256(text)};
 }
 const {allocator,closure,esp,manifests,renode,startup,stm32}=data;
 const images=Object.entries(closure.images);
 const identical=(left,right)=>JSON.stringify(canonical(left))===JSON.stringify(canonical(right));
 if(images.length!==5||closure.steps_per_image!==14||new Set(images.map(([,image])=>JSON.stringify(image.uart))).size!==1)
   throw Error("Cortex-M3 closure boot profiles disagree");
 const flash={};
 for(const [key,image] of images){
  const fileLoads=image.loads.filter(segment=>segment.file_bytes>0);
  const extent=Math.max(...fileLoads.map(segment=>segment.physical+segment.file_bytes));
  if(extent!==image.flash_extent_bytes)throw Error("Cortex-M3 flash extent disagrees for "+key);
  flash[key]=extent;
 }
 const exact=startup.profiles.exact_sections;
 const layoutControls=Object.entries(startup.profiles).filter(([key])=>key!=="exact_sections");
 if(layoutControls.length!==3||!layoutControls.every(([,row])=>identical(row.sections,exact.sections)&&row.uart!==exact.uart))
   throw Error("Expected same-layout, different-output startup controls");
 const pages=Object.values(allocator.images);
 const arenas=pages.map(x=>Number(x.arena.arena_end)-Number(x.arena.arena));
 if(pages.length!==4||arenas.some(bytes=>bytes!==64)||allocator.case_count!==644||
    allocator.requests_per_image!==676||identical(allocator.control.expected,allocator.control.observed))
   throw Error("Allocation arena, case inventory or negative control disagrees");
 const arm={};
 for(const [key,image] of Object.entries(stm32)){
  const manifest=manifests.profiles[key];
  const observed=renode.profiles[key];
  if(image.vector!==manifest.memory.flash[0]||!image.foreign_object_refused||
     !image.missing_archive_member_refused||!identical(observed.trace,renode.native_reference))
    throw Error("STM32 closure or emulator reference mismatch for "+key);
  arm[key]={profile:manifest.abi,flash_origin:image.vector,
            uart_observations:observed.trace.length,closure:"vendor-LL-CMSIS"};
 }
 const targetNames=Object.keys(esp.freestanding).sort();
 if(!identical(targetNames,["rv32","xtensa"])||Object.values(esp.freestanding).some(r=>r.runtime_dependencies)||
    esp.profiles["esp32-dual"].trace!=="S:2:0:1:1:2"||esp.profiles["esp32-unicore"].machine===esp.profiles["esp32c3-unicore"].machine||
    esp.radio.radio_disabled_vendor_archives!==0||esp.radio.observation!=="static_link_map")
   throw Error("ESP profile or static radio archive scope disagrees");
 return canonical({
  pinned_evidence:evidence,
  cortex_m3:{boot_images:images.length,exact_startup_images:1,same_layout_startup_controls:layoutControls.length,
    link_or_boot_controls:closure.controls,allocation_cases:allocator.case_count,
    allocation_observations:pages.length*allocator.requests_per_image,maximum_arena_bytes:Math.max(...arenas),
    allocation_profiles:[...new Set(pages.map(p=>p.linked_reservation_routine))].sort(),flash_extents_bytes:flash},
  stm32:arm,
  esp:{standalone_linked_architectures:targetNames,sdk_boot_profiles:Object.keys(esp.profiles).sort(),
    optional_radio_vendor_archives:Object.keys(esp.radio.radio_enabled_vendor_archives).length}
 });
}

const controls = [
  ["wrong-flash-extent", "closure", "flash extent", d=>{Object.values(d.images)[0].flash_extent_bytes++;}],
  ["startup-control-loses-distinction", "startup", "different-output", d=>{const p=Object.keys(d.profiles).find(k=>k!=="exact_sections");d.profiles[p].uart=d.profiles.exact_sections.uart;}],
  ["changed-emulator-trace", "renode", "emulator reference", d=>{d.profiles.f1.trace[0]+="x";}],
  ["radio-scope-upgrade", "esp", "radio archive scope", d=>{d.radio.observation="hardware";}]
];

function git(...args) {
  return execFileSync("git", args, { maxBuffer: 16 * 1024 * 1024 }).toString("utf8");
}

const sha256 = text => createHash("sha256").update(text, "utf8").digest("hex");
function read(path) {
  const blob = git("rev-parse", "--verify", spec.pinned + ":" + path).trim();
  return { path, blob, text: git("cat-file", "blob", blob) };
}

const inventory = Object.fromEntries(Object.entries(spec.inputs).map(([key, path]) => [key, read(path)]));
const archived = read(spec.archived);
const regenerated = JSON.stringify(summarize(inventory, sha256), null, 2) + "\n";
if (regenerated !== archived.text) throw Error("Crosswalk ledger bytes differ");
const outcomes = {};
for (const [name, key, expected, edit] of controls) {
  const revised = JSON.parse(inventory[key].text);
  edit(revised);
  try {
    summarize({ ...inventory, [key]: { ...inventory[key], text: JSON.stringify(revised) } }, sha256);
  } catch (error) {
    if (!String(error).includes(expected)) throw error;
    outcomes[name] = "refused";
  }
  if (!outcomes[name]) throw Error("Mutation was accepted: " + name);
}

const receipt = {
  pinned: spec.pinned,
  archived: { path: archived.path, blob: archived.blob, expected: sha256(archived.text),
              bytes: Buffer.byteLength(archived.text) },
  inputs: Object.fromEntries(Object.entries(inventory).map(([key, value]) => [
    key, { path: value.path, blob: value.blob, sha256: sha256(value.text) },
  ])),
  controls: outcomes,
};
process.stdout.write(JSON.stringify(receipt, null, 2) + "\n");
