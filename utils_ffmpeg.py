import os
import subprocess
import re
import math
import json
import yaml
from datetime import datetime, timedelta

def get_video_creation_time(video_path):
    """
    Queries video metadata via ffprobe to extract the exact recording start time.
    Falls back to OS file creation time if embedded tags are missing.
    """
    if not os.path.exists(video_path):
        return None

    creation_time_str = None

    # Option A: Query embedded container metadata using JSON format
    cmd = [
        "ffprobe",
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


def get_video_duration(video_path):
    """
    Queries the video file using ffprobe to get its exact total duration in seconds.
    """
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None

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
    st_text
):
    """
    Generates multi-view perspective extractions and writes structured
    sidecar metadata (.yaml) files for every extracted frame view.
    Updates the Streamlit UI with progress instead of the terminal.
    """
    if not os.path.exists(video_path):
        st_text.error(f"Input video not found: {video_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 1. Setup Camera Rig Angle Views
    views = []
    angle_step = 360 / num_horizontal_views

    for i in range(num_horizontal_views):
        yaw = i * angle_step
        if yaw > 180:
            yaw -= 360

        safe_yaw = str(int(yaw)).replace("-", "m")
        views.append({"id": f"Horiz_{safe_yaw}", "yaw": int(yaw), "pitch": 0})

        if include_45_pitch:
            views.append({"id": f"Up45_{safe_yaw}", "yaw": int(yaw), "pitch": 45})
            views.append({"id": f"Down45_{safe_yaw}", "yaw": int(yaw), "pitch": -45})

    if include_up_down:
        views.append({"id": "Zenith_90", "yaw": 0, "pitch": 90})

    total_views = len(views)

    # 2. Fetch Video Metadata
    total_duration = get_video_duration(video_path)
    video_start_time = get_video_creation_time(video_path)

    if not total_duration:
        st_text.error("Could not read video duration. Ensure FFmpeg is installed.")
        return

    estimated_frames_per_view = (
        math.ceil(total_duration / interval_seconds) if total_duration else 0
    )
    total_expected_images = estimated_frames_per_view * total_views

    # 3. Print Pre-Extraction Summary Statistics (Terminal)
    print("=" * 50)
    print("        PRE-EXTRACTION CONFIGURATION SUMMARY     ")
    print("=" * 50)
    print(f"Target Video    : {os.path.basename(video_path)}")
    print(f"Start Time      : {video_start_time}")
    print(
        f"Video Duration  : {f'{total_duration:.2f} seconds' if total_duration else 'Unknown'}"
    )
    print(f"Sample Rate     : Every {interval_seconds} seconds")
    print(f"Total Angles    : {total_views} viewpoints per timestamp")
    print(f"Est. Images Out : ~{total_expected_images} total .png files")
    print("=" * 50)

    # 4. Generate Sidecar YAML Metadata Files
    st_text.text("Generating metadata YAML files for all extraction frames...")
    if total_duration and estimated_frames_per_view > 0:
        for frame_idx in range(1, estimated_frames_per_view + 1):
            elapsed_sec = (frame_idx - 1) * interval_seconds

            # Compute start and current frame time
            start_iso, current_iso = calculate_frame_time(
                video_start_time, elapsed_sec
            )

            for view_idx, view in enumerate(views):
                base_name = f"{prefix}_{frame_idx:04d}_view_{view_idx:02d}_{view['id']}"
                yaml_path = os.path.join(output_dir, f"{base_name}.yaml")

                view_info = {
                    "id": view["id"],
                    "index": view_idx,
                    "yaw": view["yaw"],
                    "pitch": view["pitch"],
                }

                # Write initial structured YAML file with spatial & camera orientation
                generate_frame_metadata_yaml(
                    yaml_path=yaml_path,
                    start_time_str=start_iso,
                    current_time_str=current_iso,
                    elapsed_seconds=elapsed_sec,
                    view_info=view_info,
                    fov=fov,
                    resolution=resolution,
                )

    # 5. Build the -filter_complex graph
    filter_graph = f"fps=1/{interval_seconds}[split];"
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
            output_dir, f"{prefix}_%04d_view_{i:02d}_{view['id']}.png"
        )
        maps.extend(["-map", f"[v{i}]", out_filename])

    # 6. Build Command with Progress Tracking Flags
    command = (
        [
            "ffmpeg",
            "-y",
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
        + ["-vsync", "vfr"]
    )

    # Save the raw FFmpeg command to a text file in your output directory for reference
    command_file_path = os.path.join(output_dir, "run_ffmpeg_manually.sh")
    with open(command_file_path, "w") as text_file:
        text_file.write(" ".join(command))

    # 7. Execute FFmpeg with Streamlit UI Tracking
    st_text.text("Initializing FFmpeg extraction pipeline...")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    time_regex = re.compile(r"out_time_ms=(\d+)")
    last_seconds_cleared = 0

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        # Look for the internal microsecond progress string outputted by FFmpeg
        match = time_regex.search(line)
        if match:
            current_ms = int(match.group(1))
            current_seconds = int(current_ms / 1000000)

            if current_seconds > last_seconds_cleared:
                # Safely calculate progress fraction for Streamlit bar (max 1.0)
                progress_fraction = min(current_seconds / total_duration, 1.0)
                st_progress.progress(progress_fraction)
                st_text.text(f"Extracting... Processed {current_seconds}s of {int(total_duration)}s")
                last_seconds_cleared = current_seconds

    # Complete the UI elements
    st_progress.progress(1.0)
    st_text.success(f"Extraction complete! Images saved to: {output_dir}")