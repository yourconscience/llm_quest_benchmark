#!/bin/sh
set -e

# Install UV if missing (faster than pip)
if ! command -v uv > /dev/null; then
    echo "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "Setting up Python environment..."
# Let uv handle the venv creation and activation
export VIRTUAL_ENV="$(pwd)/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
uv venv --python python3 .venv
uv pip install -e .

# Verify critical dependencies
echo "Verifying dependencies..."
python3 -c "import anthropic; import openai; import litellm; print('✓ Dependencies verified')"

# Install and build TypeScript components
echo "Setting up TypeScript components..."
npm install
npm run build

echo "✓ Setup complete!"
echo "Run 'source .venv/bin/activate' to activate the environment"
echo "Then use 'llm-quest' to start using the tool"