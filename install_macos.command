#!/usr/bin/env bash

#   ##########################################################
#   By Eugene Ch'ng
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   BEGINNER MACOS INSTALLER
#   ----------------------------------------------------------
#   Installs Homebrew if needed, installs Python, FFmpeg,
#   COLMAP, PyYAML and the Streamlit Python requirements
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

add_homebrew_to_path() {
    if [ -x "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        if ! grep -qs '/opt/homebrew/bin/brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
            printf '\neval "$(/opt/homebrew/bin/brew shellenv)"\n' >> "$HOME/.zprofile"
        fi
    elif [ -x "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
        if ! grep -qs '/usr/local/bin/brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
            printf '\neval "$(/usr/local/bin/brew shellenv)"\n' >> "$HOME/.zprofile"
        fi
    fi
}

printf '\n360VideoFrameExtractor - macOS Beginner Installer\n'
printf '%s\n' '------------------------------------------------'
printf 'This installer will install the tools needed by the web app.\n\n'

if ! command -v brew >/dev/null 2>&1; then
    printf 'Homebrew was not found. Installing Homebrew...\n'
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    add_homebrew_to_path
else
    add_homebrew_to_path
fi

if ! command -v brew >/dev/null 2>&1; then
    printf 'Error: Homebrew was installed, but macOS still cannot find it.\n' >&2
    printf 'Close this window, open Terminal and run install_macos.command again.\n' >&2
    exit 1
fi

printf '\nInstalling Python, Git and FFmpeg...\n'
brew install python git ffmpeg

printf '\nInstalling COLMAP...\n'
if ! brew install colmap; then
    printf '\nWarning: COLMAP could not be installed automatically.\n' >&2
    printf 'The web app can still run, but the dependency checker will report COLMAP as missing.\n' >&2
fi

printf '\nInstalling Streamlit, PyYAML and Python requirements...\n'
chmod +x install.sh run.sh
./install.sh

printf '\nInstallation complete.\n'
printf 'To open the web app, double-click run_macos.command\n'
