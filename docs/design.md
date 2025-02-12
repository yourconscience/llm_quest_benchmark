# LLM Quest Benchmark Design

## Core Principles
1. **QM First** - Focus on faithful Space Rangers quest experience
2. **Developer Experience** - Prioritize testing, logging, and debugging
3. **Minimal Dependencies** - Focus on essential tools and libraries

## Architecture

### Core Components
1. **QM Parser Bridge** (TypeScript)
   - Parses QM files into JSON state
   - Handles game state transitions
   - Provides stable interface for Python environment

2. **Quest Environment** (Python)
   - Manages game state
   - Handles action validation
   - Provides observation space

3. **LLM Agent Interface**
   - Model-agnostic design
   - Unified API through LiteLLM
   - Structured prompt system

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