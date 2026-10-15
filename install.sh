#!/usr/bin/env bash

#   ##########################################################
#   By Eugene Ch'ng
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   EXTRACT360FRAMES INSTALLER FOR MACOS AND LINUX
#   ----------------------------------------------------------
#   Creates a Python virtual environment, installs the Python
#   requirements and checks the external video tools
#   ##########################################################

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'Error: Python 3 was not found. Install Python 3.10 or newer.\n' >&2
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    printf 'Error: Python 3.10 or newer is required.\n' >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    printf 'Creating Python virtual environment...\n'
    "$PYTHON_BIN" -m venv .venv
fi

if [ ! -x "$VENV_PYTHON" ]; then
    printf 'Error: The existing .venv is incomplete or uses a Python installation that is no longer available.\n' >&2
    printf 'Move or remove .venv, then run ./install.sh again.\n' >&2
    exit 1
fi

printf 'Installing Streamlit, PyYAML and Python requirements...\n'
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install -r requirements.txt

printf 'Verifying the OpenCV cv2 module in the project environment...\n'
"$VENV_PYTHON" -c 'import cv2; print(f"OpenCV cv2: {cv2.__version__}")'

mkdir -p uploaded_videos

printf '\nChecking external applications...\n'
"$VENV_PYTHON" validate_install.py --allow-missing-system

printf '\nInstallation complete.\n'
printf 'Start the application with: ./run.sh\n'
printf 'Direct command: .venv/bin/python -m streamlit run app.py\n'
printf 'Do not use "streamlit run app.py" outside the project environment.\n'

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    printf '\nFFmpeg installation is required for frame extraction.\n'
    case "$(uname -s)" in
        Darwin*) printf 'Install it with: brew install ffmpeg\n' ;;
        Linux*)  printf 'Install it with: sudo apt-get update && sudo apt-get install ffmpeg\n' ;;
    esac
fi

if ! command -v colmap >/dev/null 2>&1; then
    printf '\nCOLMAP was not found. The current interface reports it as a dependency.\n'
    case "$(uname -s)" in
        Darwin*) printf 'Install it with: brew install colmap\n' ;;
        Linux*)  printf 'Install it with: sudo apt-get install colmap\n' ;;
    esac
fi
