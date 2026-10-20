"""Workspace path helpers for local and external-drive processing."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path


VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")


def is_hidden_or_system_path(path: Path) -> bool:
    """Identify dotfiles, AppleDouble sidecars, and Windows hidden/system files."""
    if path.name.startswith("."):
        return True

    try:
        file_attributes = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return True

    hidden_mask = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0)
    system_mask = getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0)
    return bool(file_attributes & (hidden_mask | system_mask))


def _run_directory_picker(command: list[str]) -> tuple[Path | None, str | None]:
    """Run a native picker command and distinguish cancellation from failure."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        return None, f"Could not open the directory picker: {error}"

    selected_path = result.stdout.strip().lstrip("\ufeff")
    error_text = result.stderr.strip()

    if result.returncode == 0:
        if not selected_path:
            return None, None
        try:
            return normalise_workspace_path(selected_path), None
        except (OSError, ValueError) as error:
            return None, f"The selected directory could not be read: {error}"

    cancellation_text = error_text.casefold()
    if result.returncode in {1, 130} and (
        not error_text
        or "cancel" in cancellation_text
        or "user canceled" in cancellation_text
    ):
        return None, None

    return None, error_text or "The native directory picker did not open."


def choose_workspace_directory() -> tuple[Path | None, str | None]:
    """Open the operating system's folder picker on the Streamlit host."""
    system_name = platform.system()

    if system_name == "Darwin":
        return _run_directory_picker(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "Select a video workspace")',
            ]
        )

    if system_name == "Windows":
        powershell = (
            shutil.which("powershell.exe")
            or shutil.which("powershell")
            or shutil.which("pwsh")
        )
        if powershell:
            picker_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$dialog.Description = 'Select a video workspace'; "
                "$dialog.ShowNewFolderButton = $false; "
                "$result = $dialog.ShowDialog(); "
                "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { "
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "Write-Output $dialog.SelectedPath }"
            )
            return _run_directory_picker(
                [powershell, "-NoProfile", "-STA", "-Command", picker_script]
            )

    if system_name == "Linux":
        zenity = shutil.which("zenity")
        if zenity:
            return _run_directory_picker(
                [
                    zenity,
                    "--file-selection",
                    "--directory",
                    "--title=Select a video workspace",
                ]
            )

        kdialog = shutil.which("kdialog")
        if kdialog:
            return _run_directory_picker(
                [kdialog, "--getexistingdirectory", ".", "--title", "Select a video workspace"]
            )

    # Run Tk in a separate process so its GUI loop is on that process's main
    # thread rather than Streamlit's script thread.
    tkinter_script = """
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
try:
    root.attributes("-topmost", True)
except tk.TclError:
    pass
selected = filedialog.askdirectory(title="Select a video workspace")
print(selected)
root.destroy()
"""
    return _run_directory_picker([sys.executable, "-c", tkinter_script])


def normalise_workspace_path(path_value: str | os.PathLike[str]) -> Path:
    """Return an absolute workspace path from pasted macOS or Windows text."""
    path_text = os.fspath(path_value).strip()
    if len(path_text) >= 2 and path_text[0] == path_text[-1] and path_text[0] in {'"', "'"}:
        path_text = path_text[1:-1].strip()

    if not path_text:
        raise ValueError("Enter a directory path.")

    expanded_path = os.path.expandvars(os.path.expanduser(path_text))
    return Path(expanded_path).resolve()


def validate_workspace_directory(directory: Path) -> list[str]:
    """Describe problems that prevent a directory from being used as a workspace."""
    problems = []
    if not directory.exists():
        return ["The directory does not exist."]
    if not directory.is_dir():
        return ["The path is not a directory."]
    if not os.access(directory, os.R_OK):
        problems.append("The directory is not readable.")
    if not os.access(directory, os.W_OK):
        problems.append("The directory is not writable.")
    return problems


def list_video_files(directory: Path) -> list[Path]:
    """List visible files with supported video-container extensions."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and not is_hidden_or_system_path(path)
            and path.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def list_ignored_video_sidecars(directory: Path) -> list[Path]:
    """List hidden/system files that resemble videos but must never be processed."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and is_hidden_or_system_path(path)
            and path.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def list_image_files(directory: Path) -> list[Path]:
    """List visible images while excluding metadata sidecars such as ._*.png."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and not is_hidden_or_system_path(path)
            and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def list_extracted_folders(directory: Path) -> list[Path]:
    """List cubemap output folders directly inside a workspace."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_dir()
            and not is_hidden_or_system_path(path)
            and path.name.startswith("cubemap-")
        ),
        key=lambda path: path.name.casefold(),
    )
