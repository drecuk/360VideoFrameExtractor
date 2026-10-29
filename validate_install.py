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
    "utils_images.py",
    "utils_os.py",
    "utils_workspace.py",
    "utils_checksys.py",
    "util_detectsky.py",
    "util_detectblurry.py",
    "util_read_yaml.py",
    ".streamlit/config.toml",
    "logo/logo.png",
)

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
    from utils_ffmpeg import find_v360_ffmpeg, resolve_ffprobe_executable

    missing = []

    ffmpeg_path, ffmpeg_error = find_v360_ffmpeg()
    if ffmpeg_path:
        print(f"[OK] ffmpeg with v360: {ffmpeg_path}")
        ffprobe_path = resolve_ffprobe_executable(ffmpeg_path)
        if ffprobe_path:
            print(f"[OK] ffprobe: {ffprobe_path}")
        else:
            print("[MISSING] ffprobe matching the selected FFmpeg")
            missing.append("ffprobe")
    else:
        print(f"[MISSING] ffmpeg-v360: {ffmpeg_error}")
        missing.append("ffmpeg-v360")

    colmap_path = shutil.which("colmap")
    if colmap_path:
        print(f"[OK] colmap: {colmap_path}")
    else:
        print("[MISSING] colmap")
        missing.append("colmap")

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


def check_camera_coverage() -> list[str]:
    try:
        from utils_ffmpeg import (
            build_camera_views,
            calculate_horizontal_view_count,
            normalise_yaw_degrees,
        )

        view_count = calculate_horizontal_view_count(
            coverage_degrees=90,
            view_fov_degrees=60,
            overlap_percent=65,
        )
        if view_count != 3:
            raise RuntimeError(
                f"90°/60°/65% should calculate 3 views, got {view_count}"
            )

        front_views = build_camera_views(
            view_count,
            include_up_down=False,
            include_45_pitch=False,
            horizontal_coverage="front_window",
            front_yaw_degrees=0,
            horizontal_coverage_degrees=90,
            view_fov_degrees=60,
        )
        back_views = build_camera_views(
            view_count,
            include_up_down=False,
            include_45_pitch=False,
            horizontal_coverage="back_window",
            front_yaw_degrees=0,
            horizontal_coverage_degrees=90,
            view_fov_degrees=60,
        )
        if len(front_views) != 3 or len(back_views) != 3:
            raise RuntimeError("subject-window view count mismatch")

        if abs((front_views[0]["yaw"] - 30) - (-45)) > 1e-6:
            raise RuntimeError("front window starts outside the requested -45° edge")
        if abs((front_views[-1]["yaw"] + 30) - 45) > 1e-6:
            raise RuntimeError("front window ends outside the requested +45° edge")

        for front_view, back_view in zip(front_views, back_views):
            expected_back = normalise_yaw_degrees(front_view["yaw"] + 180)
            if abs(normalise_yaw_degrees(back_view["yaw"] - expected_back)) > 1e-6:
                raise RuntimeError("back coverage is not opposite front coverage")

        print("[OK] Contained front/back subject-window camera coverage")
        return []
    except Exception as exc:
        print(f"[FAILED] Camera coverage: {exc}")
        return ["camera-coverage"]


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
                    "horizontal_coverage": "front_window",
                    "horizontal_coverage_degrees": 90,
                    "front_reference_yaw_degrees": 15,
                },
                fov=90,
                resolution=1024,
            )

            metadata = read_frame_metadata(yaml_path, print_summary=False)
            if metadata["camera_spatial"]["view_id"] != "Horiz_0":
                raise RuntimeError("YAML metadata view ID mismatch")
            if metadata["camera_spatial"]["horizontal_coverage"] != "front_window":
                raise RuntimeError("YAML metadata coverage mismatch")
            if metadata["camera_spatial"]["horizontal_coverage_degrees"] != 90:
                raise RuntimeError("YAML metadata coverage angle mismatch")
            if metadata["camera_spatial"]["front_reference_yaw_degrees"] != 15:
                raise RuntimeError("YAML metadata front-reference yaw mismatch")

        print("[OK] YAML sidecar metadata generation and reading")
        return []
    except Exception as exc:
        print(f"[FAILED] YAML sidecar metadata: {exc}")
        return ["yaml-sidecar-metadata"]


def check_thumbnail_generation() -> list[str]:
    try:
        from io import BytesIO

        from PIL import Image
        from utils_images import create_thumbnail_bytes

        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "Windows thumbnail test ü.png"
            Image.new("RGBA", (320, 180), (30, 120, 210, 180)).save(source_path)

            thumbnail_bytes = create_thumbnail_bytes(source_path, max_dimension=96)
            with Image.open(BytesIO(thumbnail_bytes)) as thumbnail:
                if thumbnail.format != "JPEG":
                    raise RuntimeError("thumbnail is not JPEG encoded")
                if max(thumbnail.size) > 96:
                    raise RuntimeError("thumbnail dimensions exceed the requested size")

        print("[OK] Cross-platform thumbnail generation")
        return []
    except Exception as exc:
        print(f"[FAILED] Thumbnail generation: {exc}")
        return ["thumbnail-generation"]


def check_workspace_selection() -> list[str]:
    try:
        from utils_workspace import (
            _run_directory_picker,
            list_extracted_folders,
            list_ignored_video_sidecars,
            list_image_files,
            list_video_files,
            normalise_workspace_path,
            validate_workspace_directory,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "B.MP4").touch()
            (workspace / "a.mov").touch()
            (workspace / "ignore.txt").touch()
            (workspace / "._hidden.mp4").touch()
            (workspace / "frame.png").touch()
            (workspace / "._frame.png").touch()
            (workspace / "cubemap-a").mkdir()

            quoted_workspace = normalise_workspace_path(f'"{workspace}"')
            if quoted_workspace != workspace.resolve():
                raise RuntimeError("quoted directory path was not normalised")
            if validate_workspace_directory(quoted_workspace):
                raise RuntimeError("temporary workspace was rejected")
            if [path.name for path in list_video_files(workspace)] != [
                "a.mov",
                "B.MP4",
            ]:
                raise RuntimeError("supported video discovery failed")
            if [path.name for path in list_extracted_folders(workspace)] != [
                "cubemap-a"
            ]:
                raise RuntimeError("extracted folder discovery failed")
            if [path.name for path in list_ignored_video_sidecars(workspace)] != [
                "._hidden.mp4"
            ]:
                raise RuntimeError("hidden video sidecar filtering failed")
            if [path.name for path in list_image_files(workspace)] != ["frame.png"]:
                raise RuntimeError("hidden image sidecar filtering failed")

            picker_path, picker_error = _run_directory_picker(
                [sys.executable, "-c", f"print({str(workspace)!r})"]
            )
            if picker_error or picker_path != workspace.resolve():
                raise RuntimeError("native picker result handling failed")

        print("[OK] Local and external-drive workspace selection")
        return []
    except Exception as exc:
        print(f"[FAILED] Workspace selection: {exc}")
        return ["workspace-selection"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Extract360Frames installation.")
    parser.add_argument(
        "--allow-missing-system",
        action="store_true",
        help="Report missing external tools without returning an error.",
    )
    args = parser.parse_args()

    print(f"Python: {sys.version.split()[0]}")
    print(f"Interpreter: {sys.executable}")
    print("\nPython modules")
    python_missing = check_python_modules()

    print("\nProject files")
    file_missing = check_project_files()

    print("\nApplication smoke test")
    smoke_missing = check_visualisation()
    smoke_missing.extend(check_camera_coverage())
    smoke_missing.extend(check_yaml_metadata())
    smoke_missing.extend(check_thumbnail_generation())
    smoke_missing.extend(check_workspace_selection())

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
