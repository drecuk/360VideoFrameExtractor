#!/usr/bin/env bash

#   ##########################################################
#   By Eugene Ch'ng
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   BEGINNER MACOS LAUNCHER
#   ----------------------------------------------------------
#   Starts the Streamlit web app from the local Python
#   environment created by install_macos.command
#   ##########################################################

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

printf '\nStarting 360VideoFrameExtractor...\n'
printf 'A browser window should open at http://localhost:8501\n\n'

chmod +x run.sh
./run.sh
