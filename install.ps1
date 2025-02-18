# PowerShell installation script
$ErrorActionPreference = "Stop"

# Install UV if missing
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing UV package manager..."
    Invoke-WebRequest -Uri https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression
}

Write-Host "Setting up Python environment..."
# Let uv handle the venv creation and activation
$env:VIRTUAL_ENV = Join-Path $PWD.Path ".venv"
$env:PATH = Join-Path $env:VIRTUAL_ENV "Scripts" + [IO.Path]::PathSeparator + $env:PATH
uv venv --python python3 .venv
uv pip install -e .

# Verify critical dependencies
Write-Host "Verifying dependencies..."
python -c "import anthropic; import openai; import litellm; print('✓ Dependencies verified')"

# Install and build TypeScript components
Write-Host "Setting up TypeScript components..."
npm install
npm run build

Write-Host "✓ Setup complete!"
Write-Host "Run '.venv\Scripts\activate' to activate the environment"
Write-Host "Then use 'llm-quest' to start using the tool"