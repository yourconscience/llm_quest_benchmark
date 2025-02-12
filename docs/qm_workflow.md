# QM Workflow

## Overview
This document describes the simplified interaction flow between components in the LLM Quest Benchmark system.

## Core Components

1. **TypeScript Bridge** (`consoleplayer.ts`)
   - Single source of truth for game state
   - Handles all QM engine interactions
   - Provides consistent JSON interface
   - Manages game progression and choices

2. **Python Environment** (`QMPlayerEnv`)
   - Thin wrapper around TypeScript bridge
   - Formats observations for agents
   - Maps numeric choices to actions
   - No internal state duplication

3. **Agent Interface**
   - Receives text observations
   - Returns numeric choices (1-based)
   - Agnostic to game internals

## Simplified Workflow

### Initialization
1. Environment setup:
   ```python
   env = QMPlayerEnv(quest_file)
   ```
   - Launches TypeScript bridge process
   - Gets initial state via bridge

2. Initial observation:
   ```json
   {
     "text": "Location description...",
     "choices": [
       {"id": "jump_id", "text": "Choice text"}
     ]
   }
   ```

### Game Loop
1. **Agent Step**
   - Receives formatted text observation
   - Selects choice number (1-based)

2. **Environment Step**
   - Maps choice number to jump ID
   - Sends jump ID to bridge
   - Returns bridge response directly

3. **Bridge Response**
   ```json
   {
     "text": "New location text",
     "choices": [...],  // Available choices
     "gameEnded": false,  // Game state
     "finalReward": 0  // Optional end reward
   }
   ```

### Game End
- Bridge indicates completion:
  ```json
  {
    "gameEnded": true,
    "finalReward": 1,  // 1 for success, 0 for failure
    "text": "Final text"
  }
  ```

## Key Simplifications

1. **Single Source of Truth**
   - Bridge owns all game state
   - No state duplication in Python
   - Direct pass-through of bridge responses

2. **Minimal Transformation**
   - Only transform choice numbers to IDs
   - Keep text formatting simple
   - Pass through all bridge data

3. **Clear Boundaries**
   - Bridge: Game logic and state
   - Environment: Choice mapping and formatting
   - Agent: Decision making only

4. **Simplified Error Handling**
   - Bridge handles game logic errors
   - Environment handles choice mapping errors
   - Clear error messages in responses

## Example Flow
```
Agent -> Env: Choice "1"
Env -> Bridge: Jump ID "xyz"
Bridge -> Env: New state
Env -> Agent: Formatted observation
```

## Implementation Guidelines

1. **Bridge Interface**
   - Keep JSON schema consistent
   - Validate all responses
   - Include debug information

2. **Environment Design**
   - Minimal state tracking
   - Simple choice mapping
   - Clear error reporting

3. **Testing Strategy**
   - Unit test choice mapping
   - Integration test full flow
   - End-to-end agent tests