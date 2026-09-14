$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Installation not found. Run .\install.ps1 first."
    exit 1
}

Set-Location $ProjectDir
& $VenvPython -m streamlit run app.py @args
