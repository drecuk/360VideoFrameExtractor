import os
import subprocess
import re
import math
import json
import shlex
import shutil
import tempfile
import yaml
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

from utils_workspace import is_hidden_or_system_path


PROJECT_ROOT = Path(__file__).resolve().parent
FFMPEG_PATH_FILE = PROJECT_ROOT / ".ffmpeg_path"
HORIZONTAL_COVERAGE_MODES = {
    "full_360",
    "front_window",
    "back_window",
    "front_180",
    "back_180",
}
PREVIEW_VIEW_BATCH_SIZE = 24
MIN_PERSPECTIVE_RESOLUTION = 512
RECOMMENDED_PERSPECTIVE_RESOLUTION = 2048
MAX_PERSPECTIVE_RESOLUTION = 4096
FFMPEG_PROGRESS_KEYS = {
    "bitrate",
    "drop_frames",
    "dup_frames",
    "fps",
    "frame",
    "out_time",
    "out_time_ms",
    "out_time_us",
    "progress",
    "speed",
    "stream_0_0_q",
    "total_size",
}


def normalise_yaw_degrees(yaw):
    """Return a yaw angle in the FFmpeg-friendly -180..180 range."""
    numeric_yaw = float(yaw)
    normalised = ((numeric_yaw + 180.0) % 360.0) - 180.0
    if math.isclose(normalised, -180.0) and numeric_yaw > 0:
        return 180.0
    return normalised


def _angle_identifier(angle):
    """Create a filename-safe, human-readable identifier for an angle."""
    rounded = round(float(angle), 3)
    if math.isclose(rounded, 0.0):
        rounded = 0.0
    return f"{rounded:g}".replace("-", "m").replace(".", "p")


def calculate_horizontal_view_count(
    coverage_degrees,
    view_fov_degrees,
    overlap_percent=65,
    maximum_views=64,
):
    """Calculate contained view count for a target angular overlap."""
    coverage_degrees = float(coverage_degrees)
    view_fov_degrees = float(view_fov_degrees)
    overlap_fraction = float(overlap_percent) / 100.0

    if not 0 < coverage_degrees <= 360:
        raise ValueError("coverage_degrees must be between 0 and 360")
    if not 0 < view_fov_degrees < 180:
        raise ValueError("view_fov_degrees must be between 0 and 180")
    if view_fov_degrees > coverage_degrees:
        raise ValueError("view FOV cannot be wider than the selected coverage")
    if not 0 <= overlap_fraction < 1:
        raise ValueError("overlap_percent must be at least 0 and below 100")

    if math.isclose(view_fov_degrees, coverage_degrees):
        return 1

    maximum_step = view_fov_degrees * (1.0 - overlap_fraction)
    if maximum_step <= 0:
        return int(maximum_views)

    centre_span = coverage_degrees - view_fov_degrees
    required_views = math.ceil(centre_span / maximum_step) + 1
    return max(1, min(int(maximum_views), required_views))


def build_camera_views(
    num_horizontal_views,
    include_up_down,
    include_45_pitch,
    horizontal_coverage="full_360",
    front_yaw_degrees=0,
    horizontal_coverage_degrees=180,
    view_fov_degrees=0,
):
    """Build perspective-view directions for full or subject-window extraction.

    ``front_yaw_degrees`` is a user-defined reference within the already stitched
    equirectangular video. FFmpeg cannot infer which physical Insta360 lens that
    direction came from after stitching. Back coverage is always 180 degrees
    opposite this reference. Legacy ``front_180`` and ``back_180`` mode names are
    accepted for older saved workflows.
    """
    if horizontal_coverage not in HORIZONTAL_COVERAGE_MODES:
        raise ValueError(
            "horizontal_coverage must be full_360, front_window, or back_window"
        )
    if int(num_horizontal_views) < 1:
        raise ValueError("num_horizontal_views must be at least 1")

    num_horizontal_views = int(num_horizontal_views)
    front_yaw_degrees = normalise_yaw_degrees(front_yaw_degrees)

    if horizontal_coverage == "full_360":
        angle_step = 360.0 / num_horizontal_views
        horizontal_yaws = []
        for index in range(num_horizontal_views):
            yaw = index * angle_step
            if yaw > 180:
                yaw -= 360
            horizontal_yaws.append(yaw)
    else:
        horizontal_coverage_degrees = float(horizontal_coverage_degrees)
        view_fov_degrees = float(view_fov_degrees)
        if not 0 < horizontal_coverage_degrees <= 180:
            raise ValueError(
                "subject-window coverage must be greater than 0 and at most 180 degrees"
            )
        minimum_fov = 0 if horizontal_coverage in {"front_180", "back_180"} else 1
        if not minimum_fov <= view_fov_degrees <= horizontal_coverage_degrees:
            raise ValueError(
                "view FOV must fit inside the selected subject-window coverage"
            )

        coverage_centre = front_yaw_degrees
        if horizontal_coverage in {"back_window", "back_180"}:
            coverage_centre += 180.0

        # Keep the outer image rays within the requested subject window. The
        # first and last centres are inset by half an image FOV.
        centre_span = horizontal_coverage_degrees - view_fov_degrees
        if num_horizontal_views == 1 or math.isclose(centre_span, 0.0):
            horizontal_yaws = [normalise_yaw_degrees(coverage_centre)]
        else:
            angle_step = centre_span / (num_horizontal_views - 1)
            first_yaw = coverage_centre - (centre_span / 2.0)
            horizontal_yaws = [
                normalise_yaw_degrees(first_yaw + index * angle_step)
                for index in range(num_horizontal_views)
            ]

    views = []
    for yaw in horizontal_yaws:
        safe_yaw = _angle_identifier(yaw)
        views.append({"id": f"Horiz_{safe_yaw}", "yaw": yaw, "pitch": 0})

        if include_45_pitch:
            views.append({"id": f"Up45_{safe_yaw}", "yaw": yaw, "pitch": 45})
            views.append({"id": f"Down45_{safe_yaw}", "yaw": yaw, "pitch": -45})

    if include_up_down:
        views.append({"id": "Zenith_90", "yaw": front_yaw_degrees, "pitch": 90})

    return views


def _normalise_executable(candidate):
    """Return an absolute executable path, or None when it cannot be resolved."""
    if not candidate:
        return None

    expanded = os.path.expandvars(os.path.expanduser(str(candidate).strip()))
    if not expanded:
        return None

    if os.path.isfile(expanded):
        return os.path.abspath(expanded)

    resolved = shutil.which(expanded)
    return os.path.abspath(resolved) if resolved else None


def _configured_ffmpeg_candidates():
    """Yield configured and PATH FFmpeg candidates in precedence order."""
    candidates = [os.environ.get("FFMPEG_BINARY")]

    try:
        configured_path = FFMPEG_PATH_FILE.read_text(encoding="utf-8").strip()
        candidates.append(configured_path.lstrip("\ufeff"))
    except (OSError, UnicodeError):
        pass

    candidates.append(shutil.which("ffmpeg"))

    seen = set()
    for candidate in candidates:
        executable = _normalise_executable(candidate)
        if executable and os.path.normcase(executable) not in seen:
            seen.add(os.path.normcase(executable))
            yield executable


def _ffmpeg_has_v360(ffmpeg_path):
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    return result.returncode == 0 and bool(
        re.search(r"(^|\s)v360(\s|$)", result.stdout or "", re.MULTILINE)
    )


def find_v360_ffmpeg():
    """Return a v360-capable FFmpeg executable and an optional error message."""
    candidates = list(_configured_ffmpeg_candidates())
    for candidate in candidates:
        if _ffmpeg_has_v360(candidate):
            return candidate, None

    if candidates:
        locations = ", ".join(candidates)
        return None, (
            "FFmpeg was found, but it does not provide the required v360 filter. "
            f"Checked: {locations}. Install a full FFmpeg build (Windows: rerun "
            "install_windows.bat and allow dependency installation), then restart the app."
        )

    return None, (
        "FFmpeg was not found. Install a full FFmpeg build that includes the v360 "
        "filter (Windows: rerun install_windows.bat and allow dependency installation), "
        "then restart the app."
    )


def resolve_ffprobe_executable(ffmpeg_path=None):
    """Prefer FFprobe shipped beside the selected FFmpeg binary."""
    candidates = [os.environ.get("FFPROBE_BINARY")]
    if ffmpeg_path:
        ffmpeg = Path(ffmpeg_path)
        suffix = ".exe" if ffmpeg.suffix.lower() == ".exe" else ""
        candidates.append(str(ffmpeg.with_name(f"ffprobe{suffix}")))
    candidates.append(shutil.which("ffprobe"))

    for candidate in candidates:
        executable = _normalise_executable(candidate)
        if executable:
            return executable
    return None


def probe_video_file(video_path, ffprobe_path, timeout=30):
    """Confirm FFprobe can read a real video stream from a candidate file."""
    if not ffprobe_path:
        return False, "FFprobe is not available."

    command = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,codec_type,width,height:stream_disposition=attached_pic",
        "-of",
        "json",
        os.fspath(video_path),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "FFprobe timed out while reading the file."
    except OSError as error:
        return False, f"FFprobe could not be started: {error}"

    if result.returncode != 0:
        error_text = (result.stderr or "").strip().splitlines()
        reason = error_text[-1] if error_text else "FFprobe could not read the file."
        return False, reason[:300]

    try:
        probe_data = json.loads(result.stdout or "{}")
    except (json.JSONDecodeError, TypeError):
        return False, "FFprobe returned invalid metadata."

    for stream in probe_data.get("streams", []):
        disposition = stream.get("disposition", {})
        if (
            stream.get("codec_type") == "video"
            and stream.get("codec_name")
            and int(stream.get("width") or 0) > 0
            and int(stream.get("height") or 0) > 0
            and not disposition.get("attached_pic")
        ):
            return True, None

    return False, "No decodable video stream was found."


def get_video_creation_time(video_path, ffprobe_path="ffprobe"):
    """
    Queries video metadata via ffprobe to extract the exact recording start time.
    Falls back to OS file creation time if embedded tags are missing.
    """
    if not os.path.exists(video_path):
        return None

    creation_time_str = None

    # Option A: Query embedded container metadata using JSON format
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
        video_path
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        data = json.loads(result.stdout)

        # Check container format tags first, then stream tags
        format_tags = data.get("format", {}).get("tags", {})
        if "creation_time" in format_tags:
            creation_time_str = format_tags["creation_time"]
        else:
            for stream in data.get("streams", []):
                if "tags" in stream and "creation_time" in stream["tags"]:
                    creation_time_str = stream["tags"]["creation_time"]
                    break
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError, FileNotFoundError):
        pass

    # Option B: Fallback to local file creation / modification time if metadata is missing
    if not creation_time_str:
        stat = os.stat(video_path)
        # Windows supports st_ctime as creation time, Linux uses st_mtime as reliable fallback
        timestamp = getattr(stat, "st_birthtime", stat.st_mtime)
        creation_time_str = datetime.fromtimestamp(timestamp).isoformat()

    return creation_time_str


def calculate_frame_time(start_time_iso, elapsed_seconds):
    """
    Calculates the absolute datetime of a frame given the video start time
    and elapsed video seconds.
    """
    try:
        clean_time_str = start_time_iso.replace("Z", "+00:00") if isinstance(start_time_iso, str) else start_time_iso
        start_dt = datetime.fromisoformat(clean_time_str)
    except Exception:
        start_dt = datetime.now()

    current_dt = start_dt + timedelta(seconds=elapsed_seconds)
    return start_dt.isoformat(), current_dt.isoformat()


def generate_frame_metadata_yaml(
    yaml_path,
    start_time_str,
    current_time_str,
    elapsed_seconds,
    view_info,
    fov,
    resolution,
):
    """Creates a structured YAML metadata file including spatial, camera orientation, and time data."""
    metadata = {
        "camera_spatial": {
            "view_id": view_info["id"],
            "view_index": view_info["index"],
            "yaw_degrees": view_info["yaw"],
            "pitch_degrees": view_info["pitch"],
            "fov_degrees": fov,
            "resolution_px": [resolution, resolution],
            "projection": "rectilinear_pinhole",
            "horizontal_coverage": view_info.get(
                "horizontal_coverage", "full_360"
            ),
            "horizontal_coverage_degrees": view_info.get(
                "horizontal_coverage_degrees", 360
            ),
            "front_reference_yaw_degrees": view_info.get(
                "front_reference_yaw_degrees", 0
            ),
        },
        "timestamps": {
            "video_start_time": start_time_str,
            "frame_current_time": current_time_str,
            "elapsed_seconds": round(float(elapsed_seconds), 3),
        },
        "vision_model": {
            "model_name": None,
            "description": None,
        },
        "transient_objects": {
            "keywords": [],
        },
        "sam2_masks": {
            "mask_count": 0,
            "annotations": [],
        },
    }

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)


def get_video_duration(video_path, ffprobe_path="ffprobe"):
    """
    Queries the video file using ffprobe to get its exact total duration in seconds.
    """
    cmd = [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def create_extraction_preview_bytes(
    video_path,
    horizontal_coverage="full_360",
    front_yaw_degrees=0,
    fov=90,
    timestamp_seconds=3.0,
    resolution=320,
    num_horizontal_views=4,
    include_up_down=False,
    include_45_pitch=False,
    horizontal_coverage_degrees=180,
):
    """Render every configured perspective view at one preview timestamp."""
    if horizontal_coverage == "full_360":
        horizontal_coverage_degrees = 360

    ffmpeg_path, ffmpeg_error = find_v360_ffmpeg()
    if not ffmpeg_path:
        return None, ffmpeg_error

    ffprobe_path = resolve_ffprobe_executable(ffmpeg_path)
    duration = get_video_duration(video_path, ffprobe_path) if ffprobe_path else None
    if duration:
        timestamp_seconds = min(max(float(timestamp_seconds), 0.0), duration / 2.0)
    else:
        timestamp_seconds = max(float(timestamp_seconds), 0.0)

    try:
        views = build_camera_views(
            num_horizontal_views,
            include_up_down=include_up_down,
            include_45_pitch=include_45_pitch,
            horizontal_coverage=horizontal_coverage,
            front_yaw_degrees=front_yaw_degrees,
            horizontal_coverage_degrees=horizontal_coverage_degrees,
            view_fov_degrees=fov,
        )
    except ValueError as exc:
        return None, f"Invalid preview coverage settings: {exc}"

    with tempfile.TemporaryDirectory(prefix="extract360-heading-preview-") as tmp_dir:
        output_paths = [
            Path(tmp_dir) / f"preview_{index:03d}.png"
            for index in range(len(views))
        ]

        # Multiple smaller FFmpeg runs avoid Windows command-line limits and
        # excessive filter graphs when all 193 possible views are enabled.
        for batch_start in range(0, len(views), PREVIEW_VIEW_BATCH_SIZE):
            batch_views = views[
                batch_start : batch_start + PREVIEW_VIEW_BATCH_SIZE
            ]
            batch_outputs = output_paths[
                batch_start : batch_start + PREVIEW_VIEW_BATCH_SIZE
            ]
            split_labels = "".join(
                f"[s{index}]" for index in range(len(batch_views))
            )
            filter_parts = [f"[0:v]split={len(batch_views)}{split_labels}"]
            for index, view in enumerate(batch_views):
                filter_parts.append(
                    f"[s{index}]v360=input=equirect:output=flat:"
                    f"h_fov={float(fov):g}:v_fov={float(fov):g}:"
                    f"yaw={view['yaw']:g}:pitch={view['pitch']:g}:"
                    f"w={int(resolution)}:h={int(resolution)}[v{index}]"
                )

            command = [
                ffmpeg_path,
                "-y",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp_seconds:.3f}",
                "-i",
                os.fspath(video_path),
                "-filter_complex",
                ";".join(filter_parts),
            ]
            for index, output_path in enumerate(batch_outputs):
                command.extend(
                    [
                        "-map",
                        f"[v{index}]",
                        "-frames:v",
                        "1",
                        os.fspath(output_path),
                    ]
                )

            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=90,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return None, f"Could not create the extraction preview: {exc}"

            missing_outputs = [
                path for path in batch_outputs if not path.is_file()
            ]
            if result.returncode != 0 or missing_outputs:
                error_text = result.stderr.decode("utf-8", errors="replace").strip()
                return None, (
                    "FFmpeg could not create the extraction preview. "
                    f"{error_text[-600:]}"
                ).strip()

        preview_frames = [
            {
                "bytes": output_path.read_bytes(),
                "view_id": view["id"],
                "yaw_degrees": view["yaw"],
                "pitch_degrees": view["pitch"],
            }
            for output_path, view in zip(output_paths, views)
        ]

    return {
        "frames": preview_frames,
        "timestamp_seconds": timestamp_seconds,
        "horizontal_coverage": horizontal_coverage,
        "horizontal_coverage_degrees": horizontal_coverage_degrees,
        "front_yaw_degrees": normalise_yaw_degrees(front_yaw_degrees),
    }, None


def _serialise_command(command):
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _is_progress_line(line):
    key, separator, _ = line.partition("=")
    return bool(separator) and key.strip() in FFMPEG_PROGRESS_KEYS


def _is_complete_png(image_path):
    """Check the PNG trailer so interrupted files are never treated as complete."""
    try:
        with open(image_path, "rb") as image_file:
            image_file.seek(-12, os.SEEK_END)
            return image_file.read(12) == b"\x00\x00\x00\x00IEND\xaeB`\x82"
    except (OSError, ValueError):
        return False


def _list_staged_pngs(staging_dir):
    """List real staged PNGs without macOS AppleDouble/system sidecars."""
    return sorted(
        path
        for path in Path(staging_dir).glob("*.png")
        if path.is_file() and not is_hidden_or_system_path(path)
    )


def _has_complete_view_groups(image_paths, prefix, total_views):
    filename_pattern = re.compile(
        rf"^{re.escape(prefix)}_(\d+)_view_(\d+)_"
    )
    expected_views = set(range(total_views))
    frame_views = {}

    for image_path in image_paths:
        match = filename_pattern.match(image_path.name)
        if not match:
            return False
        frame_idx = int(match.group(1))
        view_idx = int(match.group(2))
        frame_views.setdefault(frame_idx, set()).add(view_idx)

    return bool(frame_views) and all(
        view_indexes == expected_views for view_indexes in frame_views.values()
    )


def _remove_orphan_metadata(output_dir, prefix):
    removed = 0
    filename_prefix = f"{prefix}_"
    for yaml_path in Path(output_dir).glob("*.yaml"):
        if not yaml_path.name.startswith(filename_prefix):
            continue
        if not yaml_path.with_suffix(".png").is_file():
            try:
                yaml_path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def _generate_metadata_for_images(
    image_paths,
    output_dir,
    prefix,
    views,
    video_start_time,
    interval_seconds,
    fov,
    resolution,
    horizontal_coverage="full_360",
    front_yaw_degrees=0,
    horizontal_coverage_degrees=360,
):
    filename_pattern = re.compile(
        rf"^{re.escape(prefix)}_(\d+)_view_(\d+)_"
    )
    generated = 0

    for image_path in sorted(image_paths, key=lambda path: path.name):
        match = filename_pattern.match(image_path.name)
        if not match:
            continue

        frame_idx = int(match.group(1))
        view_idx = int(match.group(2))
        if not 0 <= view_idx < len(views):
            continue

        elapsed_sec = (frame_idx - 1) * interval_seconds
        start_iso, current_iso = calculate_frame_time(
            video_start_time, elapsed_sec
        )
        view = views[view_idx]
        view_info = {
            "id": view["id"],
            "index": view_idx,
            "yaw": view["yaw"],
            "pitch": view["pitch"],
            "horizontal_coverage": horizontal_coverage,
            "horizontal_coverage_degrees": horizontal_coverage_degrees,
            "front_reference_yaw_degrees": front_yaw_degrees,
        }
        yaml_path = Path(output_dir) / f"{image_path.stem}.yaml"
        generate_frame_metadata_yaml(
            yaml_path=yaml_path,
            start_time_str=start_iso,
            current_time_str=current_iso,
            elapsed_seconds=elapsed_sec,
            view_info=view_info,
            fov=fov,
            resolution=resolution,
        )
        generated += 1

    return generated


def _format_error_tail(error_lines, limit=24):
    lines = [line.rstrip() for line in error_lines if line.strip()]
    return "\n".join(lines[-limit:])


def _classify_ffmpeg_failure(error_text, resolution, total_views, return_code):
    lower_error = (error_text or "").lower()
    raw_gib = resolution * resolution * 3 * total_views / (1024 ** 3)

    if "no such filter" in lower_error and "v360" in lower_error:
        return (
            "The selected FFmpeg build does not contain the required v360 filter. "
            "Install a full FFmpeg build and restart the app."
        )

    memory_markers = (
        "cannot allocate memory",
        "not enough memory",
        "out of memory",
        "memory allocation failed",
        "bad_alloc",
        "insufficient system resources",
    )
    memory_return_codes = {
        -1073741801,  # Windows STATUS_NO_MEMORY as a signed value
        -1073741670,  # Windows STATUS_INSUFFICIENT_RESOURCES as a signed value
        -9,
        137,
        3221225495,   # Windows STATUS_NO_MEMORY as an unsigned value
        3221225626,   # Windows STATUS_INSUFFICIENT_RESOURCES as an unsigned value
    }
    if (
        any(marker in lower_error for marker in memory_markers)
        or return_code in memory_return_codes
    ):
        return (
            "FFmpeg ran out of memory or was terminated by the operating system. "
            f"The {total_views}-view {resolution}x{resolution} pipeline needs at least "
            f"about {raw_gib:.1f} GiB for one uncompressed RGB frame set, plus FFmpeg "
            "buffers. Retry with a lower image resolution, fewer horizontal splits, "
            "or the 45-degree/zenith views disabled."
        )

    if any(marker in lower_error for marker in ("no space left", "disk full", "not enough space")):
        return (
            "FFmpeg could not finish because the output drive ran out of free space. "
            "Free space or choose another output directory, then retry."
        )

    if any(
        marker in lower_error
        for marker in ("permission denied", "access is denied", "could not open file")
    ):
        return (
            "FFmpeg could not write to the output directory. Check its permissions, "
            "close programs locking the files, or choose another directory."
        )

    return f"FFmpeg exited with code {return_code} before extraction completed."


def extract_360_frames(
    video_path,
    output_dir,
    prefix,
    interval_seconds,
    num_horizontal_views,
    include_up_down,
    include_45_pitch,
    fov,
    resolution,
    st_progress,
    st_text,
    horizontal_coverage="full_360",
    front_yaw_degrees=0,
    write_yaml_metadata=True,
    horizontal_coverage_degrees=180,
):
    """
    Generates multi-view perspective extractions and optionally writes structured
    sidecar metadata (.yaml) files for every extracted frame view.
    Updates the Streamlit UI with progress instead of the terminal.
    """
    if not os.path.exists(video_path):
        st_text.error(f"Input video not found: {video_path}")
        return False

    try:
        resolution = int(resolution)
    except (TypeError, ValueError):
        st_text.error("Image resolution must be a whole number of pixels.")
        return False

    if not MIN_PERSPECTIVE_RESOLUTION <= resolution <= MAX_PERSPECTIVE_RESOLUTION:
        st_text.error(
            "Perspective image resolution must be between "
            f"{MIN_PERSPECTIVE_RESOLUTION} and {MAX_PERSPECTIVE_RESOLUTION} pixels. "
            f"Use {RECOMMENDED_PERSPECTIVE_RESOLUTION} for normal photogrammetry; "
            "the limit applies to each extracted square view, not to the source "
            "equirectangular video's resolution."
        )
        return False

    if horizontal_coverage == "full_360":
        horizontal_coverage_degrees = 360

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        st_text.error(f"Could not create the output directory: {exc}")
        return False

    removed_orphans = _remove_orphan_metadata(output_dir, prefix)

    ffmpeg_path, ffmpeg_error = find_v360_ffmpeg()
    if not ffmpeg_path:
        orphan_note = (
            f" Removed {removed_orphans} orphan metadata file(s)."
            if removed_orphans else ""
        )
        st_text.error(f"{ffmpeg_error}{orphan_note}")
        return False

    ffprobe_path = resolve_ffprobe_executable(ffmpeg_path)
    if not ffprobe_path:
        st_text.error(
            "FFprobe was not found beside the selected FFmpeg executable or on PATH. "
            "Install the complete FFmpeg package and restart the app."
        )
        return False

    # 1. Setup Camera Rig Angle Views
    try:
        views = build_camera_views(
            num_horizontal_views,
            include_up_down,
            include_45_pitch,
            horizontal_coverage,
            front_yaw_degrees,
            horizontal_coverage_degrees,
            fov,
        )
    except ValueError as exc:
        st_text.error(f"Invalid camera coverage settings: {exc}")
        return False

    total_views = len(views)

    # 2. Fetch Video Metadata
    total_duration = get_video_duration(video_path, ffprobe_path)
    video_start_time = (
        get_video_creation_time(video_path, ffprobe_path)
        if write_yaml_metadata
        else None
    )

    if not total_duration:
        st_text.error(
            "Could not read the video duration with FFprobe. The video may be "
            "unsupported or damaged."
        )
        return False

    sampling_fps = 1.0 / interval_seconds
    estimated_frames_per_view = (
        math.ceil(total_duration * sampling_fps) if total_duration else 0
    )
    total_expected_images = estimated_frames_per_view * total_views

    # 3. Print Pre-Extraction Summary Statistics (Terminal)
    print("=" * 50)
    print("        PRE-EXTRACTION CONFIGURATION SUMMARY     ")
    print("=" * 50)
    print(f"Target Video    : {os.path.basename(video_path)}")
    print(
        "Start Time      : "
        f"{video_start_time if write_yaml_metadata else 'not requested (YAML disabled)'}"
    )
    print(
        f"Video Duration  : {f'{total_duration:.2f} seconds' if total_duration else 'Unknown'}"
    )
    print(
        f"Sample Rate     : {sampling_fps:.3g} fps "
        f"(every {interval_seconds:.3g} seconds)"
    )
    print(f"Coverage        : {horizontal_coverage}")
    print(f"Coverage Width  : {horizontal_coverage_degrees:g} degrees")
    print(
        "Front Reference : yaw "
        f"{normalise_yaw_degrees(front_yaw_degrees):g} degrees"
    )
    print(f"Total Angles    : {total_views} viewpoints per timestamp")
    print(f"Est. Images Out : ~{total_expected_images} total .png files")
    print("=" * 50)

    # Images are first written to a private staging folder. This prevents failed
    # runs from leaving incomplete PNGs or metadata-only output in the gallery.
    try:
        staging_dir = Path(tempfile.mkdtemp(prefix=".extracting-", dir=output_dir))
    except OSError as exc:
        st_text.error(f"Could not create a temporary extraction directory: {exc}")
        return False

    # 5. Build the -filter_complex graph
    filter_graph = f"fps={sampling_fps:.6g}[split];"
    split_labels = "".join([f"[s{i}]" for i in range(total_views)])
    filter_graph += f"[split]split={total_views}{split_labels};"

    maps = []
    for i, view in enumerate(views):
        v360_str = (
            f"[s{i}]v360=e:flat:h_fov={fov}:v_fov={fov}:"
            f"w={resolution}:h={resolution}:yaw={view['yaw']}:pitch={view['pitch']}[v{i}]"
        )
        filter_graph += f"{v360_str};" if i < total_views - 1 else f"{v360_str}"

        out_filename = os.path.join(
            staging_dir, f"{prefix}_%04d_view_{i:02d}_{view['id']}.png"
        )
        maps.extend(["-map", f"[v{i}]", out_filename])

    # 6. Build Command with Progress Tracking Flags
    command = (
        [
            ffmpeg_path,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            video_path,
            "-filter_complex",
            filter_graph,
        ]
        + maps
    )

    # Save a safely quoted, reproducible command that targets the chosen output
    # directory rather than the internal staging directory.
    command_file_path = os.path.join(
        output_dir, f"{prefix}_run_ffmpeg_manually.txt"
    )
    manual_command = [
        arg.replace(str(staging_dir), os.fspath(output_dir)) for arg in command
    ]
    try:
        with open(command_file_path, "w", encoding="utf-8") as text_file:
            text_file.write(_serialise_command(manual_command))
            text_file.write("\n")
    except OSError:
        pass

    # 7. Execute FFmpeg with Streamlit UI Tracking
    st_text.text("Initializing FFmpeg extraction pipeline...")
    diagnostic_log_path = Path(output_dir) / f"{prefix}_ffmpeg_diagnostic.log"
    error_lines = deque(maxlen=200)

    try:
        diagnostic_log = diagnostic_log_path.open("w", encoding="utf-8")
        diagnostic_log.write(f"Command: {_serialise_command(command)}\n\n")
        diagnostic_log.flush()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        try:
            diagnostic_log.close()
        except (NameError, OSError):
            pass
        st_text.error(f"Could not start FFmpeg: {exc}")
        return False

    time_regex = re.compile(r"out_time_(?:ms|us)=(\d+)")
    last_seconds_cleared = 0

    try:
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if not line:
                continue

            diagnostic_log.write(line)
            diagnostic_log.flush()
            if not _is_progress_line(line):
                error_lines.append(line)

            # FFmpeg reports these progress values in microseconds.
            match = time_regex.search(line)
            if match:
                current_us = int(match.group(1))
                current_seconds = int(current_us / 1000000)

                if current_seconds > last_seconds_cleared:
                    progress_fraction = min(current_seconds / total_duration, 1.0)
                    st_progress.progress(progress_fraction)
                    st_text.text(
                        f"Extracting... Processed {current_seconds}s of "
                        f"{int(total_duration)}s"
                    )
                    last_seconds_cleared = current_seconds
    finally:
        diagnostic_log.close()

    return_code = process.wait()
    # External drives on macOS may create one `._*.png` AppleDouble sidecar for
    # every real image. Those files contain filesystem metadata rather than PNG
    # data and must not participate in image-integrity or view-group checks.
    staged_images = _list_staged_pngs(staging_dir)
    incomplete_images = [
        image_path for image_path in staged_images if not _is_complete_png(image_path)
    ]
    incomplete_view_groups = bool(staged_images) and not _has_complete_view_groups(
        staged_images, prefix, total_views
    )

    if return_code != 0 or not staged_images or incomplete_images or incomplete_view_groups:
        error_tail = _format_error_tail(error_lines)
        if return_code == 0 and not staged_images:
            failure_message = "FFmpeg completed without producing any PNG images."
        elif return_code == 0 and incomplete_images:
            failure_message = (
                f"FFmpeg produced {len(incomplete_images)} incomplete PNG file(s)."
            )
        elif return_code == 0 and incomplete_view_groups:
            failure_message = (
                "FFmpeg produced an incomplete set of camera views for one or more frames."
            )
        else:
            failure_message = _classify_ffmpeg_failure(
                error_tail, resolution, total_views, return_code
            )

        shutil.rmtree(staging_dir, ignore_errors=True)
        removed = _remove_orphan_metadata(output_dir, prefix)
        details = f"\n\nFFmpeg details:\n{error_tail}" if error_tail else ""
        orphan_note = (
            f" Removed {removed} orphan metadata file(s)." if removed else ""
        )
        st_text.error(
            f"{failure_message}{orphan_note}{details}\n\nFull diagnostic log: "
            f"{diagnostic_log_path}"
        )
        return False

    committed_images = []
    try:
        for staged_image in staged_images:
            final_image = Path(output_dir) / staged_image.name
            os.replace(staged_image, final_image)
            committed_images.append(final_image)
        shutil.rmtree(staging_dir)
    except OSError as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        st_text.error(
            "FFmpeg completed, but the images could not be moved into the output "
            f"directory. Check free disk space and permissions. Details: {exc}. "
            f"Diagnostic log: {diagnostic_log_path}"
        )
        return False

    metadata_count = 0
    if write_yaml_metadata:
        st_text.text("Generating metadata for verified images...")
        try:
            metadata_count = _generate_metadata_for_images(
                committed_images,
                output_dir,
                prefix,
                views,
                video_start_time,
                interval_seconds,
                fov,
                resolution,
                horizontal_coverage,
                normalise_yaw_degrees(front_yaw_degrees),
                horizontal_coverage_degrees,
            )
        except (OSError, yaml.YAMLError) as exc:
            st_text.error(
                f"Images were extracted, but metadata generation failed: {exc}. "
                "No metadata file is created without a matching image."
            )
            return False
    else:
        st_text.text("YAML sidecar output is disabled; keeping PNG images only...")

    _remove_orphan_metadata(output_dir, prefix)
    try:
        diagnostic_log_path.unlink()
    except OSError:
        pass

    # Complete the UI elements
    st_progress.progress(1.0)
    if write_yaml_metadata:
        result_summary = (
            f"{len(committed_images)} images and {metadata_count} metadata files"
        )
    else:
        result_summary = f"{len(committed_images)} images (YAML output disabled)"
    st_text.success(f"Extraction complete: {result_summary} saved to {output_dir}")
    return True
