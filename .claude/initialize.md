# Claude Code Initialization

This repository includes structured documentation in the `.claude` directory to help Claude Code work effectively with the codebase.

## Available Documentation

- **Main Guide**: General project information
- **Repository Structure**: Code organization and directory structure
- **Code Patterns**: Common patterns and implementations
- **CLI Commands**: Reference for CLI commands

## How to Use

When starting a new Claude Code session, you can load the repository context by running:

```bash
./.claude/load_repo.sh | claude code
```

This will provide Claude with comprehensive knowledge about the repository structure, code patterns, and commands.

## Updating Documentation

You can update the documentation files in the `.claude/guides/` directory:

- `repo_structure.md`: Update when directory structure changes
- `code_patterns.md`: Add new common code patterns
- `cli_commands.md`: Update when CLI commands change

The main `CLAUDE.md` file contains high-level project information and should be updated when major features or concepts change.
