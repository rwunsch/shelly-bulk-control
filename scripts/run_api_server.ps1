# Run the Shelly Device Manager API Server (Windows PowerShell version)

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8000,
    [string]$Config = "",
    [ValidateSet("debug", "info", "warning", "error", "critical")]
    [string]$LogLevel = "info"
)

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

# Build the command arguments
$Arguments = @("--host", $Host, "--port", $Port, "--log-level", $LogLevel)

if ($Config -ne "") {
    $Arguments += @("--config", $Config)
}

Write-Host "Starting API server at http://$($Host):$($Port)"
Write-Host "Log level: $LogLevel"
if ($Config -ne "") {
    Write-Host "Using config file: $Config"
}

# Run the API server
& python -m src.shelly_manager.interfaces.api.server @Arguments 