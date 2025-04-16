# Start the Shelly Manager API service in development mode (Windows PowerShell version)

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Activate virtual environment if it exists
if (Test-Path "$ProjectRoot\.venv") {
    & "$ProjectRoot\.venv\Scripts\Activate.ps1"
}
elseif (Test-Path "$ProjectRoot\venv") {
    & "$ProjectRoot\venv\Scripts\Activate.ps1"
}
elseif (Test-Path "$ProjectRoot\venv-win") {
    & "$ProjectRoot\venv-win\Scripts\Activate.ps1"
}

# Set environment variables
$env:PYTHONPATH = "$ProjectRoot;" + $env:PYTHONPATH

# Change to project root directory
Set-Location $ProjectRoot

# Run uvicorn directly for hot reload during development
Write-Host "Starting API development server at http://0.0.0.0:8000"
Write-Host "Press Ctrl+C to stop the server"
uvicorn src.shelly_manager.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000 