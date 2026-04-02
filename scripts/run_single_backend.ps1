$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoDir "raccoon/backend"
$HostValue = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$PortValue = if ($env:PORT) { $env:PORT } else { "7891" }
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { Join-Path $RepoDir ".venv-backend/Scripts/python.exe" }

if (-not (Test-Path $PythonBin)) {
  $PythonBin = "python"
}

Set-Location $BackendDir
& $PythonBin -m uvicorn app.main:app --host $HostValue --port $PortValue
