/// <reference types="node" />

import * as readline from "readline";
import { parse } from "../../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import { QMPlayer } from "../../../space-rangers-quest/src/lib/qmplayer";

// Helper function to clean text from QM tags
function cleanText(text: string): string {
    return text
        .replace(/<clr>/g, '')
        .replace(/<clrEnd>/g, '')
        .replace(/\r\n/g, '\n');
}

// Get the quest file path and language from command line arguments or environment
if (process.argv.length < 3) {
    console.error("Usage: ts-node consoleplayer.ts <quest_file.qm> [--json|--parse]");
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

// Read the quest file
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
    const player = new QMPlayer(qm, language as "rus" | "eng");
    player.start();
    const gameState = player.getSaving();  // Get actual game state
    console.log(JSON.stringify({
        state: {
            locId: gameState.locationId,
            params: gameState.paramValues
        },
        qm: qm
    }));
    process.exit(0);
}

// Interactive mode
const player = new QMPlayer(qm, language as "rus" | "eng");
player.start();

// Output initial state
console.log(JSON.stringify({
    text: cleanText(player.getState().text),
    paramsState: player.getState().paramsState,
    choices: player.getState().choices.map(choice => ({
        ...choice,
        text: cleanText(choice.text)
    }))
}));

// Read input line by line (from Python)
const rl = readline.createInterface({
  input: process.stdin, // Read from stdin (provided by Python)
  output: process.stdout, // Write to stdout (captured by Python)
});

rl.on('line', (input) => {
    try {
        const answer = input.trim();
        const state = player.getState();

        const id = parseInt(answer, 10);
        if (!isNaN(id) && state.choices.find((x) => x.jumpId === id)) {
            player.performJump(id);
        } else {
            console.info(`Wrong input!`);
        }

        const newState = player.getState();
        // Check for game end condition
        const gameEnded = newState.choices.length === 0;
        if (gameEnded) {
            // Get final game state from QMPlayer logic
            const finalReward = newState.gameState === "win" ? 1 : 0;

            const finalState = {
                gameEnded: true,
                finalReward,
                text: cleanText(newState.text),
                paramsState: newState.paramsState,
                choices: [],
            };

            // Emit the final state as JSON
            console.log(JSON.stringify(finalState));
        } else {
            console.log(JSON.stringify({
                text: cleanText(newState.text),
                paramsState: newState.paramsState,
                choices: newState.choices.map(choice => ({
                    ...choice,
                    text: cleanText(choice.text)
                }))
            }));
        }
    } catch (error) {
        console.error(`Error processing input: ${error}`);
        process.exit(1);
    }
});