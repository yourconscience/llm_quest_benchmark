"""QM file parsing and data structures for Space Rangers quests"""
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List
import base64

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
    parser_script = PROJECT_ROOT / "llm_quest_benchmark" / "scripts" / "consoleplayer.ts"

    # Run parser with --json flag and no stdin
    cmd = [
        "node",
        "-r",
        "ts-node/register",
        str(parser_script),
        str(qm_path),
        "--json"
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL
        )

        # Extract valid JSON substring from the output
        raw_output = proc.stdout
        start_idx = raw_output.find('{')
        end_idx = raw_output.rfind('}')
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No valid JSON found in parser output")
        json_text = raw_output[start_idx:end_idx+1]
        qm_data = json.loads(json_text)

        # Convert QM data to our format with base64 decoding
        locations = {}
        for loc in qm_data.get('locations', []):
            decoded_text = ""
            if loc.get('texts') and len(loc['texts']) > 0:
                try:
                    decoded_text = base64.b64decode(loc['texts'][0]).decode('utf8')
                except Exception:
                    decoded_text = loc['texts'][0]

            # Get jumps for this location
            choices = []
            for jump in qm_data.get('jumps', []):
                if jump.get('fromLocationId') == loc['id']:
                    decoded_text = ""
                    if jump.get('texts') and len(jump['texts']) > 0:
                        try:
                            decoded_text = base64.b64decode(jump['texts'][0]).decode('utf8')
                        except Exception:
                            decoded_text = jump['texts'][0]
                    choices.append(QMChoice(jumpId=jump.get('toLocationId', 0), text=decoded_text))

            locations[int(loc['id'])] = QMLocation(
                id=int(loc['id']),
                text=decoded_text,
                choices=choices
            )

        # Find start location
        start_id = qm_data.get('startLoc', 0)
        if not start_id:
            # Try to find starting location from locations
            for loc in qm_data.get('locations', []):
                if loc.get('isStarting'):
                    start_id = loc['id']
                    break

        return QMGame(start_id=start_id, locations=locations)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Node parser error:\n{e.stderr}")
    except json.JSONDecodeError as e:
        print(f"Raw output: {proc.stdout[:200]}...")
        raise ValueError(f"Failed to parse JSON from parser. Error: {e}")
    except KeyError as e:
        print(f"Raw output: {proc.stdout[:200]}...")
        raise ValueError(f"Missing required field in parser output: {e}")
    except IndexError as e:
        print(f"Raw output: {proc.stdout[:200]}...")
        raise ValueError(f"No choices found in parser output: {e}")
