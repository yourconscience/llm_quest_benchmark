import { QMPlayer } from "../space-rangers-quest/src/lib/qmplayer";
import { parse } from "../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as readline from "readline";

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

export function runInteractiveQuest(qmPath: string): void {
    const data = fs.readFileSync(qmPath);
    const qm = parse(data);
    const player = new QMPlayer(qm, "rus");
    player.start();

    function showAndAsk() {
        const state = player.getState();
        console.info(state);  // Use same output as original
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
        console.error("Please provide a path to .qm file");
        process.exit(1);
    }
    runInteractiveQuest(qmPath);
}