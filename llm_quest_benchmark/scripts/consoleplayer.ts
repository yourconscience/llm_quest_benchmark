import * as readline from "readline";
import { parse } from "../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import * as assert from "assert";
import { QMPlayer } from "../../space-rangers-quest/src/lib/qmplayer";

// Helper function to clean text from QM tags
function cleanText(text: string): string {
    return text
        .replace(/<clr>/g, '')
        .replace(/<clrEnd>/g, '')
        .replace(/\r\n/g, '\n');
}

// Get the quest file path from the command line arguments
if (process.argv.length < 3) {
    console.error("Usage: ts-node consoleplayer.ts <quest_file.qm>");
    process.exit(1);
}
const questFilePath = process.argv[2];

// Read the quest file
let data: Buffer;
try {
    data = fs.readFileSync(questFilePath);
} catch (error) {
    console.error(`Error reading quest file: ${error}`);
    process.exit(1);
}

const qm = parse(data);
const player = new QMPlayer(qm, "rus");
player.start();

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

function showAndAsk() {
    const state = player.getState();
    // Output only text, paramsState, and choices, with cleaned text
    console.log(JSON.stringify({
        text: cleanText(state.text),
        paramsState: state.paramsState,
        choices: state.choices.map(choice => ({
            ...choice,
            text: cleanText(choice.text)
        }))
    }, null, 2));

    rl.question("> ", (answer) => {
        const id = parseInt(answer);
        if (!isNaN(id) && state.choices.find((x) => x.jumpId === id)) {
            player.performJump(id);
        } else {
            console.info(`Wrong input!`);
        }
        showAndAsk();
    });
}

showAndAsk();