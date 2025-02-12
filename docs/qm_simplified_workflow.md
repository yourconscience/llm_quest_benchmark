# QM Simplified Workflow

This document describes the simplified workflow for running Space Rangers quests.

## Components

1. QM Parser (TypeScript Bridge)
   - Parses QM files into structured format
   - Handles text, choices, conditions, etc.
   - Provides consistent interface for both interactive and automated play

2. Environment
   - Manages game state and transitions
   - Provides standard environment interface (reset, step, close)
   - Handles reward calculation and episode termination
   - Works identically for both human and LLM players

3. Player Interface
   - Abstract interface for decision making
   - Two implementations:
     a. LLM Agent: Makes automated decisions using language models
     b. Human Player: Takes input through console interface
   - Both use same environment and state format

4. Renderer
   - Formats game state for display
   - Handles text layout and styling
   - Manages history tracking
   - Adapts output based on player type (rich UI for humans, logging for LLMs)

## Workflow

1. Parser loads and parses QM file through TypeScript bridge
2. Environment initializes with parsed quest
3. Player (Human/LLM) receives observation and choices
4. Player selects action:
   - Human: Through console input
   - LLM: Through API call
5. Environment processes action and updates state
6. Renderer formats state for display
7. Loop continues until episode ends

## Key Features

- Unified workflow for both human and LLM players
- Simple, modular design
- Standard environment interface
- Clean separation of concerns
- Easy to extend and modify
- Minimal dependencies

## Implementation Notes

1. Both `llm-quest run` and `llm-quest play` use:
   - Same TypeScript bridge for QM parsing
   - Same environment for state management
   - Same state format and choice handling
   - Only differ in action selection mechanism

2. Common workflow ensures:
   - Consistent behavior
   - Shared testing infrastructure
   - Easy comparison between human and LLM performance
   - Simplified maintenance
