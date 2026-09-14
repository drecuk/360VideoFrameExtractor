#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   OPEN FOLDER IN FILE EXPLORER
#   ----------------------------------------------------------
#   Opens a folder using the native file explorer available
#   within Windows, macOS or Linux
#
#   Returns True when the open command is executed
#   Returns False when the folder does not exist
#
#   How to use:
#   open_folder("path/to/folder")
#   ##########################################################

import os
import sys
import subprocess


#   ##########################################################
#   OPEN FOLDER
#   ----------------------------------------------------------
#   Detects the current operating system and opens the supplied
#   folder path using the appropriate system command
#   ##########################################################

def open_folder(path):

    # --------------------------- CHECK FOLDER PATH
    # stop if the supplied folder path does not exist
    if not os.path.exists(path):
        return False

    # --------------------------- WINDOWS
    # open the folder using the Windows file explorer
    if sys.platform == "win32":
        os.startfile(path)

    # --------------------------- MACOS
    # open the folder using the macOS open command
    elif sys.platform == "darwin":
        subprocess.call(["open", path])

    # --------------------------- LINUX
    # open the folder using the default Linux desktop application
    else:
        subprocess.call(["xdg-open", path])

    # --------------------------- RETURN RESULT
    return True
