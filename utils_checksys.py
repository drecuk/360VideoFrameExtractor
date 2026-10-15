#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   SYSTEM DEPENDENCY CHECK
#   ----------------------------------------------------------
#   Checks whether FFmpeg, FFprobe and COLMAP are available
#   within the system PATH
#
#   Generates installation instructions for macOS, Linux
#   and Windows when required dependencies are missing
#
#   How to use:
#   missing_deps = check_dependencies()
#   instructions = get_os_instructions(missing_deps)
#   ##########################################################

import shutil
import sys

from utils_ffmpeg import find_v360_ffmpeg, resolve_ffprobe_executable


#   ##########################################################
#   CHECK SYSTEM DEPENDENCIES
#   ----------------------------------------------------------
#   Searches the system PATH for the required command-line
#   applications
#
#   Returns a list containing the names of missing dependencies
#   ##########################################################

def check_dependencies():

    # --------------------------- INITIALISE RESULTS
    # create an empty list for recording missing dependencies
    missing_deps = []

    # --------------------------- CHECK FFMPEG + V360
    # Perspective extraction requires a full build containing the v360 filter.
    ffmpeg_path, _ = find_v360_ffmpeg()
    if ffmpeg_path is None:
        if shutil.which("ffmpeg") is None:
            missing_deps.append("ffmpeg")
        else:
            missing_deps.append("ffmpeg-v360")

    # --------------------------- CHECK MATCHING FFPROBE
    # Prefer FFprobe shipped beside the selected compatible FFmpeg executable.
    if ffmpeg_path and resolve_ffprobe_executable(ffmpeg_path) is None:
        missing_deps.append("ffprobe")

    # --------------------------- CHECK COLMAP
    # COLMAP is required for image-based 3D reconstruction
    if shutil.which("colmap") is None:
        missing_deps.append("colmap")

    # --------------------------- RETURN RESULTS
    return missing_deps


#   ##########################################################
#   GENERATE INSTALLATION INSTRUCTIONS
#   ----------------------------------------------------------
#   Detects the current operating system and generates
#   installation instructions for missing dependencies
#
#   Returns the instructions as Markdown-formatted text
#   ##########################################################

def get_os_instructions(missing_deps):

    # --------------------------- DETECT OPERATING SYSTEM
    # get the platform identifier from the current Python environment
    platform = sys.platform

    # initialise installation instruction text
    instructions = ""

    # --------------------------- MACOS INSTRUCTIONS
    # use Homebrew to install missing dependencies
    if platform == "darwin":
        instructions += "**For macOS (using Terminal):**\n"

        # install FFmpeg which normally includes FFprobe
        if any(dep in missing_deps for dep in ("ffmpeg", "ffmpeg-v360", "ffprobe")):
            instructions += "- `brew install ffmpeg`\n"

        # install COLMAP using Homebrew
        if "colmap" in missing_deps:
            instructions += "- `brew install colmap`\n"

    # --------------------------- LINUX INSTRUCTIONS
    # use the APT package manager for Ubuntu and Linux systems
    elif platform.startswith("linux"):
        instructions += "**For Ubuntu/Linux (using Terminal):**\n"

        # update the available package list before installation
        instructions += "- `sudo apt-get update`\n"

        # install FFmpeg which normally includes FFprobe
        if any(dep in missing_deps for dep in ("ffmpeg", "ffmpeg-v360", "ffprobe")):
            instructions += "- `sudo apt-get install ffmpeg`\n"

        # install COLMAP using APT
        if "colmap" in missing_deps:
            instructions += "- `sudo apt-get install colmap`\n"

    # --------------------------- WINDOWS INSTRUCTIONS
    # use WinGet where an installation package is available
    elif platform == "win32":
        instructions += "**For Windows (using Command Prompt / PowerShell):**\n"

        # install FFmpeg which normally includes FFprobe
        if any(dep in missing_deps for dep in ("ffmpeg", "ffmpeg-v360", "ffprobe")):
            instructions += (
                "- Rerun `install_windows.bat`, choose automatic dependency "
                "installation, or run `winget install --id Gyan.FFmpeg --exact --force`.\n"
            )

        # COLMAP must be downloaded and added to the system PATH
        if "colmap" in missing_deps:
            instructions += "- Download the latest release from the [COLMAP GitHub page](https://github.com/colmap/colmap/releases) and add it to your system PATH.\n"

    # --------------------------- RETURN INSTRUCTIONS
    return instructions
