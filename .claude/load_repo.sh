#!/bin/bash

# Script to auto-load repository structure into Claude CLI
# Place this in the .claude directory

REPO_ROOT=$(git rev-parse --show-toplevel)
CLAUDE_DIR="$REPO_ROOT/.claude"

# Check if Claude documentation exists
if [ ! -d "$CLAUDE_DIR" ]; then
  echo "Claude documentation directory not found at $CLAUDE_DIR"
  exit 1
fi

# Load main guide first
cat "$CLAUDE_DIR/CLAUDE.md"

echo -e "\n\n----------------------------------------\n"
echo "Loading repository structure guide..."
cat "$CLAUDE_DIR/guides/repo_structure.md"

echo -e "\n\n----------------------------------------\n"
echo "Loading CLI commands guide..."
cat "$CLAUDE_DIR/guides/cli_commands.md"

echo -e "\n\n----------------------------------------\n"
echo "Loading code patterns guide..."
cat "$CLAUDE_DIR/guides/code_patterns.md"

echo "Loaded repository structure and guide information."
