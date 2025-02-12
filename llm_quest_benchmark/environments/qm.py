"""QM file parsing and data structures for Space Rangers quests"""
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel

from llm_quest_benchmark.constants import PROJECT_ROOT


class QMChoice(BaseModel):
    """A single choice/action in a location"""
    jumpId: int
    text: str


class QMLocation(BaseModel):
    """A location in the quest with its text and available choices"""
    id: int
    text: str
    choices: List[QMChoice]


class QMGame(BaseModel):
    """Complete quest state"""
    start_id: int
    locations: Dict[int, QMLocation]

    def get_location(self, loc_id: int) -> QMLocation:
        return self.locations[loc_id]


def parse_qm(qm_path: str) -> QMGame:
    """Parse QM file using space-rangers-quest TypeScript parser"""
    qm_path = Path(qm_path).resolve()
    if not qm_path.exists():
        raise FileNotFoundError(f"QM file not found: {qm_path}")

    # Use correct path to parser in our package
    parser_script = PROJECT_ROOT / "llm_quest_benchmark" / "executors" / "ts_bridge" / "consoleplayer.ts"

    cmd = ["node", "-r", "ts-node/register", str(parser_script), str(qm_path), "--parse"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_data = json.loads(proc.stdout)

        # Extract what we need from the raw data
        state = raw_data['state']
        qm = raw_data['qm']

        # Convert to our format
        locations = {}
        for loc_id, loc in qm['locations'].items():
            locations[int(loc_id)] = QMLocation(
                id=int(loc_id),
                text=loc['texts'][0] if loc['texts'] else "",
                choices=[
                    QMChoice(jumpId=j['toLocId'], text=j['texts'][0] if j['texts'] else "")
                    for j in loc.get('jumps', [])
                ]
            )

        return QMGame(start_id=state['locId'], locations=locations)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Node parser error:\n{e.stderr}")
    except json.JSONDecodeError as e:
        # Add debug info
        print(f"Raw output: {proc.stdout[:200]}...")  # Show first 200 chars
        raise ValueError(f"Failed to parse JSON from parser. Error: {e}")
    except KeyError as e:
        # Add debug info for missing keys
        print(f"Raw output: {proc.stdout[:200]}...")
        print(f"Available keys: {raw_data.keys()}")
        raise ValueError(f"Missing required key in parser output: {e}")
