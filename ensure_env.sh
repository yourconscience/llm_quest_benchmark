#!/bin/zsh
# Unified environment setup for agents
set -e

UV_PYTHON=${UV_PYTHON:-python3.12}
ENV_DIR=${ENV_DIR:-.venv}
LOCK_FILE=requirements.lock

# Install UV if missing
if ! command -v uv > /dev/null; then
    curl -LsS https://astral.sh/uv/install.sh | sh
fi

# Create venv if missing
if [ ! -d "$ENV_DIR" ]; then
    uv venv --python $UV_PYTHON $ENV_DIR
fi

# Activate with explicit paths
export PATH="$PWD/$ENV_DIR/bin:$PATH"
export VIRTUAL_ENV="$PWD/$ENV_DIR"

# Install dependencies
uv pip install -e . --strict