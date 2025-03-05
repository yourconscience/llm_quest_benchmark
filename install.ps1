# Check prerequisites
$ErrorActionPreference = "Stop"

function Test-Command($command) {
    try { Get-Command $command -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

if (-not (Test-Command python)) {
    Write-Error "Python 3 is required but not installed. Aborting."
    exit 1
}
if (-not (Test-Command node)) {
    Write-Error "Node.js is required but not installed. Aborting."
    exit 1
}
if (-not (Test-Command npm)) {
    Write-Error "npm is required but not installed. Aborting."
    exit 1
}

# Print versions
Write-Host "Using:"
python --version
node --version
npm --version

# Setup Python environment
Write-Host "Setting up Python environment..."
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Setup TypeScript bridge
Write-Host "Setting up TypeScript bridge..."
Push-Location space-rangers-quest
npm install --legacy-peer-deps
npm run build
Pop-Location

# Create default config if not exists
if (-not (Test-Path .env)) {
    Write-Host "Creating default .env file..."
    Copy-Item .env.example .env
    Write-Host "Please edit .env with your API keys"
}

Write-Host "Installation complete! Please:"
Write-Host "1. Edit .env with your API keys"
Write-Host "2. Activate the virtual environment: .\venv\Scripts\Activate.ps1"
