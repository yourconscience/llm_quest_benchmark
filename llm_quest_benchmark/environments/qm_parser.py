"""QM file parsing utilities"""
import subprocess
from pathlib import Path
from typing import Dict

from json_repair import repair_json

from llm_quest_benchmark.constants import PROJECT_ROOT
from llm_quest_benchmark.environments.qm import QMGame, QMLocation, QMChoice


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
        # Use json_repair to handle any malformed JSON from the TypeScript bridge
        raw_data = repair_json(proc.stdout, return_objects=True)

        # Extract what we need from the raw data
        state = raw_data['state']
        qm = raw_data['qm']

        # Convert to our format
        locations: Dict[str, QMLocation] = {}
        for loc in qm['locations']:
            if not loc:  # Skip empty locations
                continue
            loc_id = str(loc['id'])  # Convert to string for consistency
            locations[loc_id] = QMLocation(
                id=loc_id,
                text=loc['texts'][0] if loc['texts'] else "",
                choices=[
                    QMChoice(id=str(jump['toLocationId']), text=jump['text'])
                    for jump in loc.get('jumps', []) if jump
                ]
            )

        return QMGame(
            start_location_id=str(state['locId']),  # Convert to string
            locations=locations
        )

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Node parser error:\n{e.stderr}")
    except Exception as e:
        # Add debug info for any parsing errors
        print(f"Raw output: {proc.stdout[:200]}...")  # Show first 200 chars
        raise ValueError(f"Failed to parse QM data: {str(e)}")