// Turns on SOTN Editor Extra Hacks in a disc's files, with the editor's own code (design/M20).
//
//   node editor_hacks.js <sotn-editor checkout> <files dir> <out dir> <hack id>[,<hack id>...]
//
// <files dir> holds the disc's files at their ISO paths (DRA.BIN, ST/NO3/NO3.BIN, ...), as
// harness/mods.py extracts them. Each changed file is written to <out dir> at the same path, and
// a JSON line lists them. Exit code 1 if the editor won't build that selection on this image.
"use strict";
const fs = require("fs");
const path = require("path");

const [editor, filesDir, outDir, ids] = process.argv.slice(2);
global.window = global;
require(path.join(editor, "extra-hacks-catalog.js"));
const ui = require(path.join(editor, "extra-hacks-ui.js"));

const catalog = ui.prepareCatalog(global.SotnExtraHacks);
const files = new Map();
for (const file of ui.filesUsed ? ui.filesUsed(catalog) : Object.keys(catalog.files)) {
  const p = path.join(filesDir, file);
  if (fs.existsSync(p)) files.set(file, new Uint8Array(fs.readFileSync(p)));
}
const analysis = ui.analyze(catalog, files);
if (!analysis.profile) {
  console.log(JSON.stringify({error: analysis.reason || "not a vanilla or ASS image"}));
  process.exit(1);
}
const avail = ui.availability(catalog, analysis);
let selected = new Map([...avail.values()].map(entry => [entry.feature.id, entry.source]));
const notes = [];
for (const id of ids.split(",")) {
  if (!avail.get(id)?.canToggle) {
    console.log(JSON.stringify({error: `${id}: ${avail.get(id)?.reason || "not available on this image"}`}));
    process.exit(1);
  }
  const result = ui.cascade(catalog, avail, selected, id, true, analysis.profile);
  selected = result.selected;
  notes.push(...result.notes);
}
const byFile = new Map();
for (const edit of ui.plan(catalog, analysis, selected)) {
  if (!byFile.has(edit.file)) byFile.set(edit.file, []);
  byFile.get(edit.file).push(edit);
}
const changed = [];
for (const [file, edits] of byFile) {
  const before = files.get(file);
  const buf = {before, after: before.slice()};
  ui.applyEdits(buf, edits, file);
  const out = path.join(outDir, file);
  fs.mkdirSync(path.dirname(out), {recursive: true});
  fs.writeFileSync(out, buf.after);
  changed.push(file);
}
console.log(JSON.stringify({profile: analysis.profile, changed, notes}));
