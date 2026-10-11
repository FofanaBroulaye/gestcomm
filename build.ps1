$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    py -3.13 -m venv (Join-Path $projectRoot ".venv")
}

& $python -m pip install --upgrade pip
& $python -m pip install pyinstaller
& $python -m PyInstaller --noconfirm --clean --windowed --name GestCom (Join-Path $projectRoot "main.py")

Write-Host "Executable disponible dans dist\GestCom\GestCom.exe" -ForegroundColor Green
