param(
  [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\backend"
if (!(Test-Path .venv)) {
  python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt | Out-Host
Pop-Location

if ($BuildFrontend) {
  Push-Location "$PSScriptRoot\..\frontend"
  npm install | Out-Host
  npm run build | Out-Host
  Pop-Location
}

Push-Location "$PSScriptRoot\..\backend"
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
Pop-Location
