# LLM Quest Benchmark - Implementation Plan

### 1. Extend qm_parser.py to support parsing QM files into structured data
```python
# qm_parser.py
class QMReader:
    def __init__(self, buffer: bytes):
        self.pos = 0
        self.buffer = buffer


    def parse(self) -> QMStructure:
        # TODO: Check correctness of parsing !
        # Header handling from TS parseBase()
        header = unpack_from("<I", self.buffer, self.pos)[0]
        self.pos +=4

        # Version detection from TS parseBase()
        if header in (0xD2353A42, 0xD3353A42):  # SR2 headers
            return self.parse_sr2()
        elif header == 0x3457D5E3:  # QMM7
            return self.parse_qmm()
        else:
            raise QMVersionError(f"Unsupported header: 0x{header:08X}")

    def parse_sr2(self) -> QMStructure:
        # Replicate TS parseBase() SR2 logic
        params = []
        for _ in range(48):
            # Match TS parseParam() logic
            name = self.read_utf16()
            min_val = self.read_i32()
            max_val = self.read_i32()
            is_money = self.read_u8()
            params.append(QMParameter(...))
            # TODO: finish SR2 parsing
```

### 2. Support quest State Management
```python
# quest_state.py
class QuestState:
    def __init__(self, qm: QMStructure):
        self.params = {p.id: p.starting for p in qm.params}
        # TODO: Track current location
        # TODO: Validate transitions
```

### 3. Implement LLM Agent for decision-making: figure out best interface
```python
# llm_adapter.py
class QuestAgent:
    def choose_action(self, state: QuestState) -> int:
        # TODO: Generate prompt from location/transitions
        # TODO: Parse LLM response
        pass
```

### 4. Validation & Testing
```python
# test_parser.py
def test_smugglers_quest():
    qm = parse_qm("quests/smugglers.qm")
    assert len(qm.transitions) > 20
    assert "мародеры" in qm.locations[1]  # Russian text check
```

## Key Compromises
1. Only support 48-param QM versions
2. Simplified condition checks (min/max only)
3. UTF-16LE text decoding only
4. No formula/percentage change support
5. Basic error handling
