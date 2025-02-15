# LLM Quest Benchmark Design

## Core Principles
1. **QM First** - Focus on faithful Space Rangers quest experience
2. **Developer Experience** - Prioritize testing, logging, and debugging
3. **Minimal Dependencies** - Focus on essential tools and libraries

## Architecture

### Core Components
1. **QM Parser Bridge** (TypeScript)
   - Parses QM files into structured format
   - Handles text, choices, conditions, etc.
   - Provides consistent interface for both interactive and automated play
   - Handles game state transitions
   - Provides stable interface for Python environment

2. **Quest Environment** (Python)
   - Manages game state and transitions
   - Provides standard environment interface (reset, step, close)
   - Handles reward calculation and episode termination
   - Works identically for both human and LLM players
   - Handles action validation
   - Provides observation space

3. **Player Interface**
   - Abstract interface for decision making
   - Two implementations:
     a. LLM Agent: Makes automated decisions using language models
     b. Human Player: Takes input through console interface
   - Both use same environment and state format
   - Model-agnostic design
   - Unified API through LiteLLM
   - Structured prompt system

4. **Renderer**
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

### Key Features
- Unified workflow for both human and LLM players
- Simple, modular design
- Standard environment interface
- Clean separation of concerns
- Easy to extend and modify
- Minimal dependencies

## Technology Stack

### Current
- TypeScript (QM Parser)
- Python 3.11+ (Core)
- Rich (Terminal UI)
- LiteLLM (Model API)
- pytest (Testing)

### Development Tools
- yapf + isort (Formatting)
- mypy (Type checking)
- pre-commit hooks
- pytest (Testing framework)

## Development Standards

### Code Quality
- Type hints required
- Tests required for new features
- Debug logging in core components
- Clear error messages

### Testing Strategy
- Unit tests for core logic
- Integration tests for full pipeline
- Timeout handling for LLM calls
- Debug logging in test mode

### Documentation
- Docstrings for public APIs
- Inline comments for complex logic
- Debug logs for runtime behavior
- Clear error messages

### Git Workflow
- Direct commits to master for:
  - Documentation updates
  - Small fixes
  - Minor improvements
  - Test updates
- Feature branches for:
  - New features
  - Major refactoring
  - Breaking changes
  - Complex improvements
- Branch naming: `feature/description` or `fix/description`
- Test changes before merging
- Keep commits focused and well-described