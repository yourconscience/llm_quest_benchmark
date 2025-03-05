# Claude Code Documentation

This directory contains structured documentation to help Claude Code effectively work with the LLM Quest Benchmark repository.

## Files and Directories

- `CLAUDE.md`: Primary documentation file with project overview, principles, and commands
- `guides/`: Detailed documentation for specific aspects of the codebase
  - `repo_structure.md`: Repository structure and organization
  - `code_patterns.md`: Common code patterns and examples
  - `cli_commands.md`: Command-line interface reference

## Using with Claude Code

To start Claude Code with full repository context:

```bash
./.claude/load_repo.sh | claude code
```

## Maintaining Documentation

When making significant changes to the codebase:

1. Update the relevant guide files
2. Run your changes through `.claude/load_repo.sh` to ensure they load correctly
3. Commit your documentation updates alongside code changes

## Advantages Over Previous Approach

- Structured and maintainable documentation
- Easily searchable with `rg` (ripgrep)
- Separate guides for different aspects of the codebase
- Loadable via a simple shell script
