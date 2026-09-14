#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    printf 'Installation not found. Run ./install.sh first.\n' >&2
    exit 1
fi

cd "$PROJECT_DIR"
exec "$VENV_PYTHON" -m streamlit run app.py "$@"
