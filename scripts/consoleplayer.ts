import { QMPlayer } from "../space-rangers-quest/src/lib/qmplayer";
import { parse } from "../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
interface GameState {
    text: string;
    choices: Array<{id: number; text: string}>;
    daysPassed: number;
    params: Array<{name: string; value: number}>;
}

export function runInteractiveQuest(qmPath: string): void {
    const data = fs.readFileSync(qmPath);
    const qm = parse(data);
    const player = new QMPlayer(qm, "rus");
    player.start();

    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (input) => {
        const choiceId = parseInt(input.toString().trim());
        if (!isNaN(choiceId)) {
            player.performJump(choiceId);
            sendState(player.getState());
        } else {
            process.stderr.write("Invalid input\n");
        }
    });

    sendState(player.getState());
}

function sendState(state: any) {
    const gameState: GameState = {
        text: state.text,
        choices: state.choices.map((c: any) => ({
            id: c.jumpId,
            text: c.text
        })),
        daysPassed: state.daysPassed,
        params: Object.values(state.params).map((p: any) => ({
            name: p.name,
            value: p.value
        }))
    };

    process.stdout.write(JSON.stringify(gameState) + "\n");
}

// CLI handler
if (require.main === module) {
    const qmPath = process.argv[2];
    runInteractiveQuest(qmPath);
}