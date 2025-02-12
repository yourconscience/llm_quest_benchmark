#!/bin/zsh
# Unified environment setup for agents
set -e

UV_PYTHON=${UV_PYTHON:-python3.11}  # Default to 3.11 as it's more widely available
ENV_DIR=${ENV_DIR:-.venv}
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)  # Get absolute path to project root

# Install UV if missing
if ! command -v uv > /dev/null; then
    echo "Installing uv..."
    curl -LsS https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create venv if missing
if [ ! -d "$ENV_DIR" ]; then
    echo "Creating virtual environment in $ENV_DIR"
    uv venv --python $UV_PYTHON $ENV_DIR >/dev/null
fi

# Activate with explicit paths
export PATH="$PROJECT_ROOT/$ENV_DIR/bin:$PATH"
export VIRTUAL_ENV="$PROJECT_ROOT/$ENV_DIR"

# Install dependencies
echo "Installing dependencies..."
cd "$PROJECT_ROOT"  # Ensure we're in the project root
uv pip install -e ".[dev]" --strict

echo "Environment ready! Python: $(which python)"