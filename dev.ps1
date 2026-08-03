<#
.SYNOPSIS
Start HomeBandhu development servers.

.DESCRIPTION
With no flags, starts both services:
  frontend  http://localhost:5173
  backend   http://127.0.0.1:8000
#>

param (
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Help
)

# Show help if requested
if ($Help) {
    Write-Host "Usage: .\dev.ps1 [-Backend] [-Frontend]"
    Write-Host ""
    Write-Host "Start HomeBandhu development servers."
    Write-Host ""
    Write-Host "With no flags, starts both services:"
    Write-Host "  frontend  http://localhost:5173"
    Write-Host "  backend   http://127.0.0.1:8000"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Backend    Start only the FastAPI backend."
    Write-Host "  -Frontend   Start only the Vite frontend."
    Write-Host "  -Help       Show this help message."
    exit 0
}

# If no specific flags are provided, run both by default
if (-not $Backend -and -not $Frontend) {
    $Backend = $true
    $Frontend = $true
}

# Resolve paths for dependencies (handles Windows .cmd/.exe vs Linux/macOS binaries)
$UvCmd  = Get-Command "uv" -ErrorAction SilentlyContinue
$NpmCmd = Get-Command "npm" -ErrorAction SilentlyContinue

if ($Backend -and -not $UvCmd) {
    Write-Error "Backend requires uv. Install it from https://docs.astral.sh/uv/"
    exit 1
}

if ($Frontend -and -not $NpmCmd) {
    Write-Error "Frontend requires npm (Node.js)."
    exit 1
}

# $PSScriptRoot gives the absolute directory where this script is located
$RootDir = $PSScriptRoot
$Script:Processes = @()

function Start-Backend {
    Write-Host "Starting backend at http://127.0.0.1:8000 ..."
    # Start-Process with -PassThru returns a process object we can track and kill later
    $proc = Start-Process -FilePath $UvCmd.Path -ArgumentList "run uvicorn app.main:app --reload" -WorkingDirectory "$RootDir\backend" -NoNewWindow -PassThru
    $Script:Processes += $proc
}

function Start-Frontend {
    Write-Host "Starting frontend at http://localhost:5173 ..."
    $proc = Start-Process -FilePath $NpmCmd.Path -ArgumentList "run dev" -WorkingDirectory "$RootDir" -NoNewWindow -PassThru
    $Script:Processes += $proc
}

# The try-finally block acts similarly to 'trap cleanup EXIT' in bash
try {
    if ($Backend) { Start-Backend }
    if ($Frontend) { Start-Frontend }

    Write-Host "Press Ctrl-C to stop the selected development server(s)."

    # Polling loop to check if either process exits prematurely
    $exitCode = 0
    while ($true) {
        $anyExited = $false
        foreach ($p in $Script:Processes) {
            if ($p.HasExited) {
                $anyExited = $true
                $exitCode = $p.ExitCode
                break
            }
        }

        if ($anyExited) {
            break
        }

        Start-Sleep -Milliseconds 200
    }
    
    if ($exitCode -ne 0) {
        exit $exitCode
    }
}
finally {
    # Cleanup: Kill any lingering child processes
    foreach ($p in $Script:Processes) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}