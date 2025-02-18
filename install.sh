#!/bin/bash
set -e  # Exit on error

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed. Aborting." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed. Aborting." >&2; exit 1; }

# Print versions
echo "Using:"
python3 --version
node --version
npm --version

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Setup Python environment using uv
echo "Setting up Python environment..."
uv venv
source .venv/bin/activate

# Install dependencies with uv
echo "Installing Python dependencies..."
uv pip install -e .

# Setup TypeScript bridge
echo "Setting up TypeScript bridge..."
cd space-rangers-quest
# Set NODE_OPTIONS to handle OpenSSL issues with newer Node versions
export NODE_OPTIONS=--openssl-legacy-provider
npm install --legacy-peer-deps
npm run build
cd ..

# Create default config if not exists
if [ ! -f .env ]; then
    echo "Creating default .env file..."
    cp .env.example .env
    echo "Please edit .env with your API keys"
fi

echo "Installation complete! Please:"
echo "1. Edit .env with your API keys"
echo "2. Activate the virtual environment: source .venv/bin/activate"
echo "3. Note: When running TypeScript-related tasks, you may need to set: export NODE_OPTIONS=--openssl-legacy-provider"