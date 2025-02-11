/// <reference types="node" />

import * as readline from "readline";
import { parse } from "../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import { QMPlayer } from "../../space-rangers-quest/src/lib/qmplayer";

// Get the quest file path and language from command line arguments or environment
if (process.argv.length < 3) {
    console.error("Usage: ts-node consoleplayer.ts <quest_file.qm>");
    process.exit(1);
}

const questFilePath = process.argv[2];
const validLanguages = ["rus", "eng"];
const language = process.env.QM_LANG || "rus";
const jsonMode = process.argv.includes("--json");

if (!validLanguages.includes(language)) {
    console.error(`Invalid language: ${language}. Valid options are: ${validLanguages.join(", ")}`);
    process.exit(1);
}

// Read the quest file
let data: Buffer;
try {
    data = fs.readFileSync(questFilePath);
} catch (error) {
    console.error(`Error reading quest file: ${error}`);
    process.exit(1);
}

const qm = parse(data);
const player = new QMPlayer(qm, language as "rus" | "eng");
player.start();

// If in JSON mode, output parsed data and exit
if (jsonMode) {
    console.log(JSON.stringify(qm));
    process.exit(0);
}

// Interactive mode
// Output initial state
console.log(JSON.stringify(player.getState()));

// Read input line by line (from Python)
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

rl.on('line', (input) => {
    try {
        const answer = input.trim();
        const state = player.getState();

        const id = parseInt(answer, 10);
        if (!isNaN(id) && state.choices.find((x) => x.jumpId === id)) {
            player.performJump(id);
            console.log(JSON.stringify(player.getState()));
        } else {
            console.info(`Wrong input!`);
        }
    } catch (error) {
        console.error(`Error processing input: ${error}`);
        rl.close();
        process.exit(1);
    }
});