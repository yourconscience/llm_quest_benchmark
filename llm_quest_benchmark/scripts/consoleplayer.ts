import { QMPlayer } from "../../space-rangers-quest/src/lib/qmplayer";
import { parse } from "../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import * as readline from "readline";

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

function printQuestAsJson(qmPath: string): void {
    const data = fs.readFileSync(qmPath);
    const qm = parse(data);
    const player = new QMPlayer(qm, "rus");
    player.start();

    // Just get the raw state and output as JSON
    const state = player.getState();
    console.log(JSON.stringify({
        state,
        qm
    }));
}

function runInteractiveQuest(qmPath: string): void {
    const data = fs.readFileSync(qmPath);
    const qm = parse(data);
    const player = new QMPlayer(qm, "rus");
    player.start();

    function showAndAsk() {
        const state = player.getState();
        console.info(state);
        rl.question("> ", (answer) => {
            const id = parseInt(answer);
            if (!isNaN(id) && state.choices.find(x => x.jumpId === id)) {
                player.performJump(id);
            } else {
                console.info(`Wrong input!`);
            }
            showAndAsk();
        });
    }

    showAndAsk();
}

if (require.main === module) {
    const qmPath = process.argv[2];
    if (!qmPath) {
        console.error("Usage: consoleplayer.ts [--json] <path-to-qm>");
        process.exit(1);
    }

    if (process.argv.includes("--json")) {
        try {
            printQuestAsJson(qmPath);
        } catch (err) {
            console.error("Failed to parse and print JSON:", err);
            process.exit(1);
        }
        process.exit(0);
    }

    runInteractiveQuest(qmPath);
}