#!/usr/bin/env python3

#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   INSTALLATION VALIDATION
#   ----------------------------------------------------------
#   Checks Python modules, project assets and external tools
#   without starting the Streamlit web application
#   ##########################################################

from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

PYTHON_MODULES = {
    "streamlit": "Streamlit",
    "numpy": "NumPy",
    "plotly": "Plotly",
    "cv2": "OpenCV",
    "PIL": "Pillow",
    "yaml": "PyYAML",
}

PROJECT_FILES = (
    "app.py",
    "utils_viz.py",
    "utils_ffmpeg.py",
    "utils_os.py",
    "utils_checksys.py",
    "util_detectsky.py",
    "util_detectblurry.py",
    "util_read_yaml.py",
    ".streamlit/config.toml",
    "logo/logo.png",
)

SYSTEM_TOOLS = ("ffmpeg", "ffprobe", "colmap")


def check_python_modules() -> list[str]:
    missing = []
    for module_name, display_name in PYTHON_MODULES.items():
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "installed")
            print(f"[OK] {display_name}: {version}")
        except ImportError:
            print(f"[MISSING] {display_name}")
            missing.append(display_name)
    return missing


def check_project_files() -> list[str]:
    missing = []
    for relative_path in PROJECT_FILES:
        if (PROJECT_ROOT / relative_path).exists():
            print(f"[OK] {relative_path}")
        else:
            print(f"[MISSING] {relative_path}")
            missing.append(relative_path)
    return missing


def check_system_tools() -> list[str]:
    missing = []
    for tool in SYSTEM_TOOLS:
        tool_path = shutil.which(tool)
        if tool_path:
            print(f"[OK] {tool}: {tool_path}")
        else:
            print(f"[MISSING] {tool}")
            missing.append(tool)

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "v360" in result.stdout:
            print("[OK] FFmpeg v360 filter")
        else:
            print("[MISSING] FFmpeg v360 filter")
            missing.append("ffmpeg-v360")
    return missing


def check_visualisation() -> list[str]:
    try:
        from utils_viz import generate_360_splits

        figure = generate_360_splits(HORIZONTAL_SPLITS=4)
        if not figure.data:
            raise RuntimeError("visualisation contains no traces")
        print(f"[OK] Camera visualisation: {len(figure.data)} traces")
        return []
    except Exception as exc:
        print(f"[FAILED] Camera visualisation: {exc}")
        return ["camera-visualisation"]


def check_yaml_metadata() -> list[str]:
    try:
        from util_read_yaml import read_frame_metadata
        from utils_ffmpeg import generate_frame_metadata_yaml

        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "metadata_smoke_test.yaml"
            generate_frame_metadata_yaml(
                yaml_path=yaml_path,
                start_time_str="2026-01-01T00:00:00",
                current_time_str="2026-01-01T00:00:02",
                elapsed_seconds=2,
                view_info={
                    "id": "Horiz_0",
                    "index": 0,
                    "yaw": 0,
                    "pitch": 0,
                },
                fov=90,
                resolution=1024,
            )

            metadata = read_frame_metadata(yaml_path, print_summary=False)
            if metadata["camera_spatial"]["view_id"] != "Horiz_0":
                raise RuntimeError("YAML metadata view ID mismatch")

        print("[OK] YAML sidecar metadata generation and reading")
        return []
    except Exception as exc:
        print(f"[FAILED] YAML sidecar metadata: {exc}")
        return ["yaml-sidecar-metadata"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Extract360Frames installation.")
    parser.add_argument(
        "--allow-missing-system",
        action="store_true",
        help="Report missing external tools without returning an error.",
    )
    args = parser.parse_args()

    print(f"Python: {sys.version.split()[0]}")
    print("\nPython modules")
    python_missing = check_python_modules()

    print("\nProject files")
    file_missing = check_project_files()

    print("\nApplication smoke test")
    smoke_missing = check_visualisation()
    smoke_missing.extend(check_yaml_metadata())

    print("\nExternal tools")
    system_missing = check_system_tools()

    required_missing = python_missing + file_missing + smoke_missing
    if system_missing and not args.allow_missing_system:
        required_missing.extend(system_missing)

    if required_missing:
        print("\nInstallation validation failed.")
        return 1

    if system_missing:
        print("\nPython installation is valid. Install the missing external tools before extraction.")
    else:
        print("\nInstallation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
