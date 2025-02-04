import { QMPlayer } from "../space-rangers-quest/src/lib/qmplayer";
import { parse } from "../space-rangers-quest/src/lib/qmreader";
import * as fs from "fs";

// Modified version of original consoleplayer.ts that outputs JSON
export function runQuest(qmPath: string): string {
  const data = fs.readFileSync(qmPath);
  const qm = parse(data);
  const player = new QMPlayer(qm, "rus");
  player.start();

  // Modified output logic
  return JSON.stringify({
    locations: qm.locations,
    params: qm.params,
    currentState: player.getState()
  });
}

// CLI handler
if (require.main === module) {
  const qmPath = process.argv[2];
  console.log(runQuest(qmPath));
}