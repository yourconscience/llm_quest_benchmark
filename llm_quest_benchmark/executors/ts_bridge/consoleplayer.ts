/// <reference types="node" />

import * as readline from "readline";
import { parse } from "../../../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";
import * as process from "process";
import { QMPlayer } from "../../../space-rangers-quest/src/lib/qmplayer";
import { initGame, performJump } from "../../../space-rangers-quest/src/lib/qmplayer/funcs";

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

// Initialize from an explicit stable seed. The bridge records timestamps for
// every jump; a stable initial PRNG state makes independent runs comparable.
const player = new QMPlayer(qm, language as "rus" | "eng");
const seed = process.env.QM_SEED || "llm-quest-default";
player.loadSaving(initGame(qm, seed));

function emitState() {
    console.log(JSON.stringify({
        state: player.getState(),
        saving: player.getSaving()
    }));
}

function emitError(message: string) {
    // Protocol errors go to stdout so the Python bridge fails fast instead of
    // waiting for a state packet that will never arrive.
    console.log(JSON.stringify({ error: message }));
}

// If parse mode, output raw QM structure and exit
if (parseMode) {
    // Format data consistently with interactive mode
    const state = player.getState();
    const saving = player.getSaving();
    console.log(JSON.stringify({
        state: state,
        saving: saving,
        metadata: {
            startLocationId: qm.locations[0]?.id || 0,
            locations: qm.locations
        }
    }));
    process.exit(0);
}

// Output initial raw state
emitState();

// Structured command protocol: one JSON object per stdin line.
//   {"cmd":"state"}
//   {"cmd":"jump","jumpId":<int>,"performedAtMs":<int>}
//   {"cmd":"load","saving":{...}}
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
});

rl.on('line', (input) => {
    try {
        const raw = input.trim();
        if (!raw) {
            return;
        }

        let command: any;
        try {
            command = JSON.parse(raw);
        } catch (parseError) {
            emitError(`Malformed command JSON: ${raw}`);
            return;
        }
        if (!command || typeof command !== "object") {
            emitError("Command must be a JSON object");
            return;
        }

        switch (command.cmd) {
            case "state": {
                emitState();
                return;
            }
            case "jump": {
                const jumpId = Number(command.jumpId);
                const performedAtMs = Number(command.performedAtMs);
                if (!Number.isFinite(jumpId)) {
                    emitError("jump requires a numeric jumpId");
                    return;
                }
                if (!Number.isFinite(performedAtMs)) {
                    // Deterministic replay depends on the caller-supplied timestamp,
                    // so the bridge never invents one.
                    emitError("jump requires a numeric performedAtMs");
                    return;
                }
                // IMPORTANT: keep stdout protocol clean.
                // space-rangers-quest performJump defaults showDebug=true, which can emit console.info lines
                // (e.g. autojump logs) to stdout and break the Python bridge parser.
                const nextSaving = performJump(jumpId, qm, player.getSaving(), performedAtMs, false);
                player.loadSaving(nextSaving);
                emitState();
                return;
            }
            case "load": {
                if (!command.saving || typeof command.saving !== "object") {
                    emitError("load requires a saving object");
                    return;
                }
                player.loadSaving(command.saving);
                emitState();
                return;
            }
            default: {
                emitError(`Unknown command: ${String(command.cmd)}`);
                return;
            }
        }
    } catch (error) {
        emitError(String(error));
    }
});
