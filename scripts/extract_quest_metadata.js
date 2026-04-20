#!/usr/bin/env node
/**
 * Extract quest metadata (hardness, taskText, etc.) from all .qm files.
 * Outputs configs/quest_metadata.json with tier annotations.
 *
 * Usage: node scripts/extract_quest_metadata.js
 *   OR:  ./node_modules/.bin/ts-node scripts/extract_quest_metadata.js
 *
 * Requires ts-node for the TypeScript qmreader import.
 */

"use strict";

const fs = require("fs");
const path = require("path");

// We need ts-node to load the TypeScript qmreader.
// Register ts-node so require() can load .ts files.
require("ts-node").register({
  project: path.join(__dirname, "..", "tsconfig.json"),
  transpileOnly: true,
});

const { parse } = require("../space-rangers-quest/src/lib/qmreader");

const REPO_ROOT = path.join(__dirname, "..");
const QUESTS_DIR = path.join(REPO_ROOT, "quests");
const OUTPUT_PATH = path.join(REPO_ROOT, "configs", "quest_metadata.json");

// ---- helpers ---------------------------------------------------------------

function findQmFiles(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findQmFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".qm")) {
      results.push(full);
    }
  }
  return results;
}

function inferLang(dirName) {
  if (dirName.endsWith("_eng")) return "eng";
  if (dirName.endsWith("_ru")) return "ru";
  // top-level quests/ directory has Boat.qm which is Russian
  return "ru";
}

function relPath(absPath) {
  return path.relative(REPO_ROOT, absPath).replace(/\\/g, "/");
}

function percentile(sorted, p) {
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (idx - lo) * (sorted[hi] - sorted[lo]);
}

// ---- main ------------------------------------------------------------------

const qmFiles = findQmFiles(QUESTS_DIR);
console.log(`Found ${qmFiles.length} .qm files`);

const metadata = {};
const errors = [];

for (const absPath of qmFiles) {
  const rel = relPath(absPath);
  // Parent dir of the file
  const parentDir = path.basename(path.dirname(absPath));
  // Immediate subdir under quests/ (may equal "quests" if file is at top level)
  const questsRelDir = path.relative(QUESTS_DIR, path.dirname(absPath));
  const collection = questsRelDir === "" ? "top" : questsRelDir.replace(/\\/g, "/");
  const lang = inferLang(collection);

  try {
    const data = fs.readFileSync(absPath);
    const qm = parse(data);

    const description = qm.taskText ? qm.taskText.slice(0, 100) : "";

    metadata[rel] = {
      hardness: qm.hardness,
      description,
      lang,
      collection,
      playerRace: qm.playerRace,
      planetRace: qm.planetRace,
      playerCareer: qm.playerCareer,
      defaultJumpCountLimit: qm.defaultJumpCountLimit,
    };
  } catch (err) {
    errors.push({ file: rel, error: err.message });
    process.stderr.write(`ERROR parsing ${rel}: ${err.message}\n`);
  }
}

// ---- hardness distribution -------------------------------------------------

const hardnessValues = Object.values(metadata).map((m) => m.hardness);
const sorted = [...hardnessValues].sort((a, b) => a - b);

const min = sorted[0];
const max = sorted[sorted.length - 1];
const p25 = percentile(sorted, 25);
const p50 = percentile(sorted, 50);
const p75 = percentile(sorted, 75);

console.log("\n--- Hardness distribution ---");
console.log(`  count:  ${sorted.length}`);
console.log(`  min:    ${min}`);
console.log(`  p25:    ${p25}`);
console.log(`  median: ${p50}`);
console.log(`  p75:    ${p75}`);
console.log(`  max:    ${max}`);

// Histogram buckets
const buckets = {};
for (const v of sorted) {
  const bucket = Math.floor(v / 10) * 10;
  buckets[bucket] = (buckets[bucket] || 0) + 1;
}
console.log("\n  Histogram (bucket=10):");
for (const [bucket, count] of Object.entries(buckets).sort((a, b) => Number(a[0]) - Number(b[0]))) {
  const bar = "#".repeat(count);
  console.log(`    ${String(bucket).padStart(3)}-${String(Number(bucket) + 9).padStart(3)}: ${bar} (${count})`);
}

// ---- tier assignment -------------------------------------------------------
// Easy: hardness <= p33, Medium: p33 < hardness <= p66, Hard: above p66
const p33 = percentile(sorted, 33);
const p66 = percentile(sorted, 66);

console.log(`\n  Tier boundaries (p33=${p33.toFixed(1)}, p66=${p66.toFixed(1)}):`);
console.log(`    easy:   hardness <= ${Math.round(p33)}`);
console.log(`    medium: hardness in (${Math.round(p33)}, ${Math.round(p66)}]`);
console.log(`    hard:   hardness > ${Math.round(p66)}`);

// Assign tiers
for (const meta of Object.values(metadata)) {
  if (meta.hardness <= p33) {
    meta.tier = "easy";
  } else if (meta.hardness <= p66) {
    meta.tier = "medium";
  } else {
    meta.tier = "hard";
  }
}

const tierCounts = { easy: 0, medium: 0, hard: 0 };
for (const meta of Object.values(metadata)) tierCounts[meta.tier]++;
console.log(`\n  Tier counts: easy=${tierCounts.easy}, medium=${tierCounts.medium}, hard=${tierCounts.hard}`);

// ---- per-quest summary -----------------------------------------------------
console.log("\n--- Per-quest hardness + tier ---");
const rows = Object.entries(metadata).map(([rel, meta]) => ({
  rel,
  hardness: meta.hardness,
  tier: meta.tier,
  lang: meta.lang,
}));
rows.sort((a, b) => a.hardness - b.hardness);
for (const row of rows) {
  console.log(
    `  ${String(row.hardness).padStart(3)}  [${row.tier.padEnd(6)}]  [${row.lang}]  ${row.rel}`,
  );
}

// ---- write output ----------------------------------------------------------
fs.writeFileSync(OUTPUT_PATH, JSON.stringify(metadata, null, 2) + "\n");
console.log(`\nWrote ${Object.keys(metadata).length} entries to ${relPath(OUTPUT_PATH)}`);

if (errors.length) {
  console.log(`\nFailed to parse ${errors.length} files:`);
  for (const e of errors) console.log(`  ${e.file}: ${e.error}`);
}
