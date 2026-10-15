$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Installation not found. Run .\install.ps1 first."
    exit 1
}

& $VenvPython -c "import sys, streamlit, cv2; from PIL import Image; print(f'Using {sys.executable}'); print(f'Streamlit {streamlit.__version__}, OpenCV {cv2.__version__}, Pillow {Image.__version__}')"
if ($LASTEXITCODE -ne 0) {
    Write-Error "The project environment is missing Streamlit, OpenCV, or Pillow. Run .\install.ps1 again."
    exit 1
}

Set-Location $ProjectDir
& $VenvPython -m streamlit run app.py @args
