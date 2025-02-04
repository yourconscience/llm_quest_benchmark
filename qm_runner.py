import subprocess
import json
from pathlib import Path

class QMReader:
    def __init__(self):
        self.script_path = Path("scripts/consoleplayer.ts").resolve()
        self.submodule_path = Path("space-rangers-quest").resolve()

        if not self.submodule_path.exists():
            raise FileNotFoundError("Run 'git submodule update --init' first")

    def parse_qm(self, qm_path: str) -> dict:
        """Get structured QM data"""
        cmd = [
            "npx", "ts-node",
            str(self.script_path),
            str(qm_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.submodule_path
        )

        if result.returncode != 0:
            raise RuntimeError(f"QM parsing failed: {result.stderr}")

        return json.loads(result.stdout)

# Usage
if __name__ == "__main__":
    reader = QMReader()
    data = reader.parse_qm("quests/boat.qm")
    print(json.dumps(data, indent=2, ensure_ascii=False))