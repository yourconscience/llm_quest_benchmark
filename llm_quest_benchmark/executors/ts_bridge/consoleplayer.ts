/// <reference types="node" />

import * as readline from "readline";
import { parse } from "../../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import { QMPlayer } from "../../../space-rangers-quest/src/lib/qmplayer";

// Get the quest file path and language from command line arguments
if (process.argv.length < 3) {
    console.error("Usage: ts-node consoleplayer.ts <quest_file.qm> [--parse]");
    process.exit(1);
}

const questFilePath = process.argv[2];
const parseMode = process.argv.includes("--parse");
const validLanguages = ["rus", "eng"];
const language = process.env.QM_LANG || "rus";

if (!validLanguages.includes(language)) {
    console.error(`Invalid language: ${language}. Valid options are: ${validLanguages.join(", ")}`);
    process.exit(1);
}

// Read and parse the quest file
let data: Buffer;
try {
    data = fs.readFileSync(questFilePath);
} catch (error) {
    console.error(`Error reading quest file: ${error}`);
    process.exit(1);
}

const qm = parse(data);

// If parse mode, output raw QM structure and exit
if (parseMode) {
    console.log(JSON.stringify(qm));
    process.exit(0);
}

// Interactive mode - initialize player
const player = new QMPlayer(qm, language as "rus" | "eng");
player.start();

// Output initial raw state
console.log(JSON.stringify({
    state: player.getState(),
    saving: player.getSaving()
}));

// Read commands and return raw state
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
});

rl.on('line', (input) => {
    try {
        const command = input.trim();

        // Handle special commands
        if (command === "get_state") {
            console.log(JSON.stringify({
                state: player.getState(),
                saving: player.getSaving()
            }));
            return;
        }

        // Try to perform jump
        const jumpId = parseInt(command, 10);
        if (!isNaN(jumpId)) {
            player.performJump(jumpId);
            console.log(JSON.stringify({
                state: player.getState(),
                saving: player.getSaving()
            }));
        } else {
            console.error(JSON.stringify({ error: "Invalid jump ID" }));
        }
    } catch (error) {
        console.error(JSON.stringify({ error: String(error) }));
    }
});