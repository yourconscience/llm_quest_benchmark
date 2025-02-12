# LLM Quest Benchmark Roadmap

## Core Principles
1. **QM First** - Focus on faithful Space Rangers quest experience
2. **Developer Experience** - Prioritize testing, logging, and debugging
3. **Minimal Dependencies** - Focus on essential tools and libraries

## Implementation Status

### ✅ Phase 1: Core Infrastructure
1. **QM Parser Bridge**
   - [x] TypeScript integration
   - [x] JSON state conversion
   - [ ] Error handling improvements
   - [ ] Stable parsing for all quests

2. **Quest Environment**
   - [x] State management
   - [x] Action handling
   - [x] Debug logging
   - [ ] Better error messages

3. **LLM Agent**
   - [x] Basic integration
   - [x] Model selection
   - [ ] Improved prompts
   - [ ] Memory system

### 🔄 Phase 2: Testing & Metrics
1. **Testing Infrastructure**
   - [x] Integration tests
   - [x] Timeout handling
   - [x] Debug logging
   - [ ] More test coverage

2. **Metrics System**
   - [x] Basic collection
   - [x] JSON output
   - [ ] Analysis tools
   - [ ] Benchmarking

### 📋 Phase 3: Improvements
1. **Parser Stability**
   - [ ] Better error handling
   - [ ] Quest validation
   - [ ] Format documentation

2. **Agent Enhancements**
   - [ ] Context management
   - [ ] Strategy injection
   - [ ] Performance tuning

3. **Benchmarking**
   - [ ] Quest selection
   - [ ] Model comparison
   - [ ] Results analysis

## Current Sprint
1. [x] Integration tests with timeouts
2. [x] Debug logging improvements
3. [ ] QM parser error handling
4. [ ] Agent prompt improvements
5. [ ] Metrics analysis tools

## Technology Stack

### Core
- Rich (terminal UI)
- LiteLLM (model API)
- TypeScript (QM parser)

### Testing
- pytest
- yapf + isort
- pre-commit hooks

### Future
- vLLM (local models)
- Guidance (prompts)

## Development Standards

### Testing
- Integration tests for CLI commands
- Unit tests for core components
- Debug logging in all modes
- Timeout handling everywhere

### Code Style
- Formatted with yapf
- Sorted with isort
- Type hints required
- Clear error messages

### Documentation
- Updated README
- Clear roadmap
- Inline comments
- Debug logs

## Technology Choices

### Keep
- TextArena (core infrastructure)
- Rich (terminal rendering)
- QM format (authentic Space Rangers feel)

### Add
- vLLM (local model serving)
- LiteLLM (unified API layer)
- Guidance (for structured output from LLMs)

### Remove
- Custom state management (using TextArena's)
- Low-level game engine code

## Learning Opportunities
- TextArena's wrapper system
- vLLM model serving
- LiteLLM routing
- Guidance templating
- Rich terminal UI

This keeps the architecture focused while letting you explore modern LLM ops tools!

## Workflow
1. Development:
   - Write tests first
   - Use type hints
   - Document with docstrings

2. Testing:
   - Unit tests for core components
   - Integration tests for full pipeline
   - Benchmark runs for models

3. Deployment:
   - Local development setup
   - Containerized evaluation
   - Results tracking

# Development Standards

## Code Style
- All Python code formatted with yapf (.style.yapf) and isort (.isort.cfg)
- Pre-commit hooks enforce:
  - Import sorting (isort)
  - Code formatting (yapf)
  - Type checking (mypy)
  - Linting (flake8)
- Run `pre-commit install` after cloning