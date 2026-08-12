<#
.SYNOPSIS
Start HomeBandhu development servers.

.DESCRIPTION
The PowerShell twin of dev.sh. With no flags, starts both services:
  frontend  http://localhost:5173
  backend   http://127.0.0.1:8000

Either server exiting stops the other, and Ctrl-C stops both — the same
contract dev.sh gets from `trap cleanup EXIT`. Three things that are free on
Unix have to be done explicitly here:

1. `Get-Command npm` resolves to npm.ps1 on Windows, and Start-Process cannot
   run a .ps1 — it shell-executes it, which opens an editor rather than a dev
   server. The .cmd shim beside it is the launchable one.
2. dev.sh runs each server through `exec`, so the pid it tracks *is* the
   server. Windows has no equivalent: npm.cmd spawns node, and uv spawns
   python, both as grandchildren. Killing only the tracked process leaves the
   real server holding its port, and the next run fails with "address already
   in use". Every kill here is a tree kill.
3. Ctrl-C terminates a PowerShell script without running `finally`, so the
   cleanup cannot be left to it. The console is switched to deliver Ctrl-C as
   input instead, and the poll loop treats it as a stop request.

.EXAMPLE
  .\dev.ps1
  .\dev.ps1 -Backend
  .\dev.ps1 -Frontend
#>

param (
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Help
)

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

# If no specific flags are provided, run both by default.
if (-not $Backend -and -not $Frontend) {
    $Backend = $true
    $Frontend = $true
}

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

# Resolve npm to something Start-Process can actually launch. On Windows the
# command usually resolves to npm.ps1, which is a PowerShell script and not an
# executable; the npm.cmd shim sits beside it and is the one to run.
$NpmPath = $NpmCmd.Source
if ($NpmPath -like "*.ps1") {
    $Shim = Join-Path (Split-Path -Parent $NpmPath) "npm.cmd"
    if (Test-Path $Shim) {
        $NpmPath = $Shim
    } else {
        Write-Error "Found npm at $NpmPath but no npm.cmd beside it to launch."
        exit 1
    }
}

# $PSScriptRoot gives the absolute directory where this script is located.
$RootDir = $PSScriptRoot
$Script:Processes = @()

function Start-Backend {
    Write-Host "Starting backend at http://127.0.0.1:8000 ..."
    $proc = Start-Process -FilePath $UvCmd.Source `
        -ArgumentList "run", "uvicorn", "app.main:app", "--reload" `
        -WorkingDirectory (Join-Path $RootDir "backend") -NoNewWindow -PassThru
    $Script:Processes += $proc
}

function Start-Frontend {
    # From the repository root, not frontend/: the root package.json is a
    # workspace whose `dev` script is `npm run dev -w frontend`. Same as dev.sh.
    Write-Host "Starting frontend at http://localhost:5173 ..."
    $proc = Start-Process -FilePath $NpmPath -ArgumentList "run", "dev" `
        -WorkingDirectory $RootDir -NoNewWindow -PassThru
    $Script:Processes += $proc
}

function Stop-Tree {
    # /T takes the children with it, which is the whole point: the tracked
    # process is a launcher, and the server is its child.
    param([int]$ProcessId)
    & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null
}

$exitCode = 0
$ctrlCHandled = $false

try {
    # Take Ctrl-C as console input so this script, rather than the runtime,
    # decides what happens next. Without it the script is terminated outright
    # and the `finally` below never runs, leaving both servers behind.
    if (-not [Console]::IsInputRedirected) {
        [Console]::TreatControlCAsInput = $true
        $ctrlCHandled = $true
    }

    if ($Backend)  { Start-Backend }
    if ($Frontend) { Start-Frontend }

    Write-Host "Press Ctrl-C to stop the selected development server(s)."

    while ($true) {
        $exited = $Script:Processes | Where-Object { $_.HasExited } | Select-Object -First 1
        if ($exited) {
            $exitCode = $exited.ExitCode
            break
        }

        if ($ctrlCHandled -and [Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if (($key.Modifiers -band [ConsoleModifiers]::Control) -and $key.Key -eq 'C') {
                Write-Host ""
                Write-Host "Stopping ..."
                $exitCode = 130
                break
            }
        }

        Start-Sleep -Milliseconds 200
    }
}
finally {
    foreach ($p in $Script:Processes) {
        if (-not $p.HasExited) {
            Stop-Tree -ProcessId $p.Id
        }
    }
    if ($ctrlCHandled) {
        [Console]::TreatControlCAsInput = $false
    }
}

exit $exitCode
