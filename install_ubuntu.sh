#!/usr/bin/env bash

#   ##########################################################
#   By Eugene Ch'ng
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   BEGINNER UBUNTU INSTALLER
#   ----------------------------------------------------------
#   Installs Python, FFmpeg, COLMAP, PyYAML and the
#   Streamlit Python requirements using apt and the local installer
#   ##########################################################

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

finish() {
    if [ -t 0 ]; then
        printf '\nPress RETURN to close this window...'
        read -r _
    fi
}
trap finish EXIT

printf '\n360VideoFrameExtractor - Ubuntu Beginner Installer\n'
printf '%s\n' '-------------------------------------------------'
printf 'This installer will install the tools needed by the web app.\n'
printf 'Ubuntu may ask for your password so apt can install system packages.\n\n'

if ! command -v apt-get >/dev/null 2>&1; then
    printf 'Error: apt-get was not found. This installer is for Ubuntu or Debian-based Linux.\n' >&2
    exit 1
fi

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git ffmpeg

printf '\nInstalling COLMAP...\n'
if ! sudo apt-get install -y colmap; then
    printf '\nWarning: COLMAP could not be installed automatically.\n' >&2
    printf 'The web app can still run, but the dependency checker will report COLMAP as missing.\n' >&2
fi

printf '\nInstalling Streamlit, PyYAML and Python requirements...\n'
chmod +x install.sh run.sh
./install.sh

printf '\nInstallation complete.\n'
printf 'To open the web app, run ./run_ubuntu.sh\n'
printf 'or\n'
printf '.venv/bin/python -m streamlit run app.py\n'
