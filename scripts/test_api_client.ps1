# Test client for the Shelly Device Manager API (Windows PowerShell version)

param(
    [string]$Command,
    [string]$Url = "http://localhost:8000",
    [string]$DeviceId,
    [string]$GroupName,
    [string]$Operation,
    [string]$Params,
    [string]$DeviceIds,
    [string]$Description,
    [switch]$Scan,
    [switch]$Reboot
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

# Helper function to print JSON in a pretty format
function Format-Json {
    param([Parameter(Mandatory, ValueFromPipeline)][String]$json)
    
    $indent = 0
    $result = ($json -replace ":\\s*\{", ": {" -replace ":\\s*\[", ": [") -split "\n" |
    ForEach-Object {
        if ($_ -match "^\s*[\}\]]") {
            $indent--
        }
        $line = " " * ($indent * 2) + $_.TrimStart()
        if ($_ -match "[\{\[]$") {
            $indent++
        }
        $line
    }
    $result | Out-String
}

# Function to make HTTP requests
function Invoke-ApiRequest {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body = $null
    )

    $fullUrl = "$Url$Endpoint"
    $headers = @{
        "Content-Type" = "application/json"
        "Accept" = "application/json"
    }

    try {
        if ($Method -eq "GET") {
            $response = Invoke-RestMethod -Uri $fullUrl -Method $Method -Headers $headers
        }
        else {
            $jsonBody = $null
            if ($Body) {
                $jsonBody = $Body | ConvertTo-Json -Depth 10
            }
            $response = Invoke-RestMethod -Uri $fullUrl -Method $Method -Headers $headers -Body $jsonBody
        }
        return $response
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Red
        if ($_.Exception.Response) {
            $statusCode = $_.Exception.Response.StatusCode.value__
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $errorContent = $reader.ReadToEnd()
                Write-Host "Status Code: $statusCode - $errorContent" -ForegroundColor Red
            }
            catch {
                Write-Host "Status Code: $statusCode - Unable to read response" -ForegroundColor Red
            }
        }
        return $null
    }
}

# Main functionality based on command
switch ($Command) {
    "devices" {
        $scanParam = ""
        if ($Scan) {
            $scanParam = "?scan=true"
        }
        $response = Invoke-ApiRequest -Method "GET" -Endpoint "/devices$scanParam"
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "device" {
        if (-not $DeviceId) {
            Write-Host "Error: Device ID is required" -ForegroundColor Red
            exit 1
        }
        $response = Invoke-ApiRequest -Method "GET" -Endpoint "/devices/$DeviceId"
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "groups" {
        $response = Invoke-ApiRequest -Method "GET" -Endpoint "/groups"
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "create-group" {
        if (-not $GroupName) {
            Write-Host "Error: Group name is required" -ForegroundColor Red
            exit 1
        }
        if (-not $DeviceIds) {
            Write-Host "Error: Device IDs are required" -ForegroundColor Red
            exit 1
        }
        
        $deviceIdArray = $DeviceIds -split ","
        $body = @{
            name = $GroupName
            device_ids = $deviceIdArray
        }
        
        if ($Description) {
            $body.description = $Description
        }
        
        $response = Invoke-ApiRequest -Method "POST" -Endpoint "/groups" -Body $body
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "operate" {
        if (-not ($DeviceId -or $GroupName)) {
            Write-Host "Error: Either DeviceId or GroupName must be specified" -ForegroundColor Red
            exit 1
        }
        if (-not $Operation) {
            Write-Host "Error: Operation is required" -ForegroundColor Red
            exit 1
        }
        
        $body = @{
            operation = $Operation
            parameters = @{}
        }
        
        if ($Params) {
            try {
                $paramsObject = $Params | ConvertFrom-Json
                $body.parameters = $paramsObject
            }
            catch {
                Write-Host "Error: Invalid JSON in Params" -ForegroundColor Red
                exit 1
            }
        }
        
        if ($DeviceId) {
            $response = Invoke-ApiRequest -Method "POST" -Endpoint "/devices/$DeviceId/operation" -Body $body
        }
        else {
            $response = Invoke-ApiRequest -Method "POST" -Endpoint "/groups/$GroupName/operation" -Body $body
        }
        
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "set-params" {
        if (-not ($DeviceId -or $GroupName)) {
            Write-Host "Error: Either DeviceId or GroupName must be specified" -ForegroundColor Red
            exit 1
        }
        if (-not $Params) {
            Write-Host "Error: Parameters are required" -ForegroundColor Red
            exit 1
        }
        
        try {
            $paramsObject = $Params | ConvertFrom-Json
            $body = @{
                parameters = $paramsObject
                reboot_if_needed = $Reboot.IsPresent
            }
            
            if ($DeviceId) {
                $response = Invoke-ApiRequest -Method "POST" -Endpoint "/devices/$DeviceId/parameters" -Body $body
            }
            else {
                $response = Invoke-ApiRequest -Method "POST" -Endpoint "/groups/$GroupName/parameters" -Body $body
            }
            
            if ($response) {
                $response | ConvertTo-Json -Depth 10 | Format-Json
            }
        }
        catch {
            Write-Host "Error: Invalid JSON in Params" -ForegroundColor Red
            exit 1
        }
    }
    
    "status" {
        $response = Invoke-ApiRequest -Method "GET" -Endpoint "/system/status"
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    "scan" {
        $response = Invoke-ApiRequest -Method "POST" -Endpoint "/discovery/scan"
        if ($response) {
            $response | ConvertTo-Json -Depth 10 | Format-Json
        }
    }
    
    default {
        Write-Host "Shelly Device Manager API Client" -ForegroundColor Green
        Write-Host ""
        Write-Host "Usage: .\test_api_client.ps1 -Command <command> [options]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Yellow
        Write-Host "  devices           Get all devices"
        Write-Host "  device            Get a specific device"
        Write-Host "  groups            Get all groups"
        Write-Host "  create-group      Create a new group"
        Write-Host "  operate           Perform an operation on a device or group"
        Write-Host "  set-params        Set parameters on a device or group"
        Write-Host "  status            Get system status"
        Write-Host "  scan              Trigger a network scan"
        Write-Host ""
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "  -Url <url>        API base URL (default: http://localhost:8000)"
        Write-Host "  -DeviceId <id>    Device ID"
        Write-Host "  -GroupName <name> Group name"
        Write-Host "  -Operation <op>   Operation to perform"
        Write-Host "  -Params <json>    Parameters as JSON string"
        Write-Host "  -DeviceIds <ids>  Comma-separated list of device IDs"
        Write-Host "  -Description <d>  Group description"
        Write-Host "  -Scan             Trigger a scan when getting devices"
        Write-Host "  -Reboot           Reboot devices if needed when setting parameters"
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Yellow
        Write-Host "  .\test_api_client.ps1 -Command devices"
        Write-Host "  .\test_api_client.ps1 -Command devices -Scan"
        Write-Host "  .\test_api_client.ps1 -Command device -DeviceId 'shellyplug-s-12345'"
        Write-Host "  .\test_api_client.ps1 -Command create-group -GroupName 'LivingRoom' -DeviceIds 'device1,device2' -Description 'Living Room Devices'"
        Write-Host "  .\test_api_client.ps1 -Command operate -DeviceId 'device1' -Operation 'toggle'"
        Write-Host "  .\test_api_client.ps1 -Command operate -GroupName 'LivingRoom' -Operation 'on'"
        Write-Host "  .\test_api_client.ps1 -Command set-params -DeviceId 'device1' -Params '{""eco_mode"":true}' -Reboot"
        Write-Host "  .\test_api_client.ps1 -Command status"
    }
} 