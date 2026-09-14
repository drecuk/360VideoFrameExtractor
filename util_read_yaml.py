import os
import yaml

def read_frame_metadata(yaml_path, print_summary=True):
    """
    Reads a frame's sidecar YAML file and returns its structured metadata dictionary.
    Optionally prints a formatted terminal summary including camera spatial orientation.
    """
    if not os.path.exists(yaml_path):
        print(f"[Error] Metadata file not found: {yaml_path}")
        return None

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[Error] Failed to parse YAML file: {e}")
        return None

    if print_summary and metadata:
        camera = metadata.get("camera_spatial", {})
        timestamps = metadata.get("timestamps", {})
        vision = metadata.get("vision_model", {})
        transients = metadata.get("transient_objects", {})
        sam2 = metadata.get("sam2_masks", {})

        res = camera.get("resolution_px", [None, None])
        res_str = f"{res[0]}x{res[1]}px" if isinstance(res, list) and len(res) == 2 else "N/A"

        print("=" * 50)
        print(f" METADATA SUMMARY: {os.path.basename(yaml_path)}")
        print("=" * 50)
        print(f"Camera View ID     : {camera.get('view_id', 'N/A')} (Index: {camera.get('view_index', 'N/A')})")
        print(f"Orientation        : Yaw {camera.get('yaw_degrees')}°, Pitch {camera.get('pitch_degrees')}°")
        print(f"FOV & Resolution   : FOV {camera.get('fov_degrees')}° | {res_str} ({camera.get('projection', 'N/A')})")
        print("-" * 50)
        print(f"Video Start Time   : {timestamps.get('video_start_time')}")
        print(f"Frame Current Time : {timestamps.get('frame_current_time')}")
        print(f"Elapsed Seconds    : {timestamps.get('elapsed_seconds')}s")
        print("-" * 50)
        print(f"Vision Model       : {vision.get('model_name') or 'N/A'}")
        print(f"Description        : {vision.get('description') or 'None'}")
        print("-" * 50)
        print(f"Transient Objects  : {', '.join(transients.get('keywords', [])) or 'None'}")
        print(f"SAM2 Mask Count    : {sam2.get('mask_count', 0)}")
        print("=" * 50)

    return metadata
