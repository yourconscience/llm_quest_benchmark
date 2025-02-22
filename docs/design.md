# LLM Quest Benchmark Design

## Core Principles
1. **QM First** - Focus on faithful Space Rangers quest experience
2. **Developer Experience** - Prioritize testing, logging, and debugging
3. **Minimal Dependencies** - Focus on essential tools and libraries

## Architecture

### Core Components
1. **QM Parser Bridge** (TypeScript)
   - Parses QM files into structured format
   - Handles text, choices, conditions
   - Provides consistent interface for both interactive and automated play
   - Handles game state transitions

2. **Quest Environment** (Python)
   - Manages game state and transitions
   - Provides standard environment interface (reset, step)
   - Handles reward calculation and episode termination
   - Works identically for both human and LLM players

3. **Player Interface**
   - Abstract interface for decision making
   - Two implementations:
     a. LLM Agent: Makes automated decisions using language models
     b. Human Player: Takes input through console interface
   - Both use same environment and state format
   - Unified API through LiteLLM
   - Structured prompt system

4. **Metrics Collection**
   - SQLite database with UTF-8 encoding
   - Tracks all steps, choices, and outcomes
   - Supports both human and LLM players
   - Debug mode for detailed logging
   - Analysis tools for post-run insights

## Workflow

1. **Quest Execution**
   - Parser loads and parses QM file
   - Environment initializes with parsed quest
   - Player (Human/LLM) receives observation and choices
   - Player selects action:
     - Human: Through console input
     - LLM: Through API call
   - Environment processes action and updates state
   - Metrics are logged for each step
   - Loop continues until episode ends

2. **Metrics Analysis**
   - Metrics stored in SQLite database
   - Each step includes:
     - State and choices
     - Player's action
     - Reward and outcome
     - Debug info (optional)
   - Analysis tools provide:
     - Quest summary
     - Step-by-step review
     - Decision patterns
     - Performance metrics

## Technology Stack

### Core
- TypeScript (QM Parser)
- Python 3.11+ (Core)
- Rich (Terminal UI)
- LiteLLM (Model API)
- pytest (Testing)
- uv (Package Management)

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

### Package Management
- Use uv for all Python package operations
- Lock files must be committed (uv.lock)
- Virtual environments managed by uv
- Dependencies specified in pyproject.toml

### Testing Strategy
- Unit tests for core logic
- Integration tests for full pipeline
- Timeout handling for LLM calls
- Debug logging in test mode

### Git Workflow
- Direct commits to master for:
  - Documentation updates
  - Small fixes
  - Test updates
- Feature branches for:
  - New features
  - Major refactoring
  - Breaking changes
- Branch naming: `feature/description` or `fix/description`