#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    printf 'Installation not found. Run ./install.sh first.\n' >&2
    exit 1
fi

if ! "$VENV_PYTHON" -c 'import streamlit, cv2' >/dev/null 2>&1; then
    printf 'The project Python environment is missing Streamlit or OpenCV (cv2).\n' >&2
    printf 'Repair it by running: ./install.sh\n' >&2
    printf 'Then start the app with: ./run.sh\n' >&2
    exit 1
fi

cd "$PROJECT_DIR"
exec "$VENV_PYTHON" -m streamlit run app.py "$@"
