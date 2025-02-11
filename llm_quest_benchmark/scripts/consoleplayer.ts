/// <reference types="node" />

import * as readline from "readline";
import { parse } from "../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import { QMPlayer } from "../../space-rangers-quest/src/lib/qmplayer";

// Helper function to clean text from QM tags
function cleanText(text: string): string {
    return text
        .replace(/<clr>/g, '')
        .replace(/<clrEnd>/g, '')
        .replace(/\r\n/g, '\n');
}

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
    const state = player.getState();
    console.log(JSON.stringify({
        state: {
            text: cleanText(state.text),
            choices: state.choices.map(choice => ({
                jumpId: choice.jumpId,
                text: cleanText(choice.text)
            }))
        }
    }));
    process.exit(0);
}

// Interactive mode
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
            rl.close();
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
        rl.close();
        process.exit(1);
    }
});