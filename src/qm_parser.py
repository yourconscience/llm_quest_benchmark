"""
QM file parser integrated with core data structures
"""
from struct import unpack_from
from typing import Dict, List
from .data_structures import QMParameter, QMLocation, QMTransition, QMStructure

def parse_qm(buffer: bytes) -> QMStructure:
    """Parse QM file into structured data"""
    pos = 0

    # Header validation
    magic = unpack_from("<I", buffer, pos)[0]
    pos += 4
    if magic not in (0xD2353A42, 0xD3353A42):  # Common SR2 headers
        raise ValueError("Unsupported QM format")

    # Parse parameters
    params = {}
    for param_id in range(48):
        name_len = unpack_from("<I", buffer, pos)[0]
        pos += 4
        name = buffer[pos:pos+name_len*2].decode('utf-16le', errors='replace')
        pos += name_len*2

        min_val = unpack_from("<i", buffer, pos)[0]
        max_val = unpack_from("<i", buffer, pos+4)[0]
        is_money = bool(unpack_from("<B", buffer, pos+8)[0])
        pos += 12

        params[param_id] = QMParameter(
            id=param_id,
            name=name.strip(),
            min_value=min_val,
            max_value=max_val,
            is_money=is_money,
            initial_value=min_val  # Default to min value
        )

    # Parse locations
    loc_count = unpack_from("<I", buffer, pos)[0]
    pos +=4
    locations = {}
    for _ in range(loc_count):
        loc_id = unpack_from("<I", buffer, pos)[0]
        pos +=4
        text_len = unpack_from("<I", buffer, pos)[0]
        pos +=4
        text = buffer[pos:pos+text_len*2].decode('utf-16le', errors='replace')
        pos += text_len*2
        locations[loc_id] = QMLocation(
            id=loc_id,
            descriptions=[text],
            is_terminal=False,  # Will be updated later
            parameter_mods={}
        )

    # Parse transitions
    transitions = []
    jump_count = unpack_from("<I", buffer, pos)[0]
    pos +=4
    for _ in range(jump_count):
        source = unpack_from("<I", buffer, pos)[0]
        pos +=4
        target = unpack_from("<I", buffer, pos)[0]
        pos +=4
        pos += 4*8  # Skip complex fields

        # Parse conditions
        cond_count = unpack_from("<I", buffer, pos)[0]
        pos +=4
        conditions = {}
        for _ in range(cond_count):
            param_id = unpack_from("<I", buffer, pos)[0]
            pos +=4
            min_val = unpack_from("<i", buffer, pos)[0]
            max_val = unpack_from("<i", buffer, pos+4)[0]
            pos +=8
            conditions[param_id] = (min_val, max_val)

        transitions.append(QMTransition(
            source=source,
            target=target,
            description=locations.get(target, ""),
            conditions=conditions
        ))

    return QMStructure(
        parameters=params,
        locations=locations,
        transitions=transitions,
        start_location=0  # Will be updated later
    )