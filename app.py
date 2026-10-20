#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   360 VIDEO EXTRACTION TOOLKIT
#   ----------------------------------------------------------
#   A Streamlit application for extracting perspective frames
#   from equirectangular 360-degree videos
#
#   Provides interactive camera layout visualisation, batch
#   extraction and image quality filtering for sky and blur
#
#   FFmpeg and FFprobe are used for video processing
#   COLMAP is checked for the 3D reconstruction workflow
#   ##########################################################

import streamlit as st
import inspect
import os
import shutil
import tempfile
from pathlib import Path
from utils_viz import generate_360_splits
from utils_ffmpeg import (
    extract_360_frames,
    find_v360_ffmpeg,
    probe_video_file,
    resolve_ffprobe_executable,
)
from utils_os import open_folder
from util_detectsky import evaluate_sky_image, move_confirmed_skies
from utils_checksys import check_dependencies, get_os_instructions
from util_detectblurry import evaluate_blurry_image, move_confirmed_blurry
from util_read_yaml import read_frame_metadata
from utils_images import create_thumbnail_bytes
from utils_workspace import (
    VIDEO_EXTENSIONS,
    choose_workspace_directory,
    list_extracted_folders,
    list_ignored_video_sidecars,
    list_image_files,
    list_video_files,
    normalise_workspace_path,
    validate_workspace_directory,
)


st.set_page_config(page_title="360 Frame Extractor", layout="wide")

GALLERY_PAGE_SIZE = 64
GALLERY_COLUMNS = 8
GALLERY_THUMBNAIL_SIZE = 160
GALLERY_SCROLL_HEIGHT = 720
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_DIR = PROJECT_ROOT / "uploaded_videos"


def get_workspace_dir():
    """Return the active workspace, initialising the project default if needed."""
    DEFAULT_WORKSPACE_DIR.mkdir(exist_ok=True)
    if "workspace_dir" not in st.session_state:
        st.session_state["workspace_dir"] = str(DEFAULT_WORKSPACE_DIR)
    return Path(st.session_state["workspace_dir"])


def clear_workspace_dependent_state():
    """Discard selections and scan results that belong to another workspace."""
    state_keys = (
        "last_output_dir",
        "detected_skies",
        "scan_complete",
        "detected_blurry",
        "blur_scan_complete",
        "selected_gallery_image",
        "blur_folder",
        "browse_folder_tab5",
    )
    for key in state_keys:
        st.session_state.pop(key, None)

    for key in list(st.session_state):
        if key.startswith("gallery_page_"):
            st.session_state.pop(key, None)


def reset_workspace():
    """Reset the workspace selector before Streamlit recreates its widgets."""
    DEFAULT_WORKSPACE_DIR.mkdir(exist_ok=True)
    clear_workspace_dependent_state()
    st.session_state["workspace_dir"] = str(DEFAULT_WORKSPACE_DIR)
    st.session_state["workspace_path_input"] = str(DEFAULT_WORKSPACE_DIR)


def format_storage_size(byte_count):
    """Format a storage size for the workspace status panel."""
    size = float(byte_count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024


def workspace_is_available(workspace_dir):
    """Show a consistent recovery message when a workspace cannot be used."""
    workspace_problems = validate_workspace_directory(workspace_dir)
    if not workspace_problems:
        return True

    st.error(
        "The active workspace is unavailable. Reconnect the drive or choose "
        "another directory in Tab 1."
    )
    return False


@st.cache_resource(show_spinner=False)
def get_workspace_ffprobe_path():
    """Resolve FFprobe once for fast validation during repeated app reruns."""
    ffmpeg_path, _ = find_v360_ffmpeg()
    return resolve_ffprobe_executable(ffmpeg_path)


@st.cache_data(show_spinner=False, max_entries=2048)
def inspect_video_file(video_path, file_mtime_ns, file_size, ffprobe_path):
    """Cache FFprobe validation until a candidate file changes."""
    _ = file_mtime_ns, file_size
    return probe_video_file(video_path, ffprobe_path)


def get_workspace_video_files(workspace_dir):
    """Return FFprobe-readable videos and rejected visible candidates."""
    candidate_paths = list_video_files(workspace_dir)
    ffprobe_path = get_workspace_ffprobe_path()
    if not ffprobe_path:
        return [], [
            (path, "FFprobe is not available.") for path in candidate_paths
        ]

    video_paths = []
    rejected_paths = []
    for candidate_path in candidate_paths:
        try:
            file_stat = candidate_path.stat()
        except OSError as error:
            rejected_paths.append((candidate_path, str(error)))
            continue

        is_compatible, reason = inspect_video_file(
            str(candidate_path),
            file_stat.st_mtime_ns,
            file_stat.st_size,
            ffprobe_path,
        )
        if is_compatible:
            video_paths.append(candidate_path)
        else:
            rejected_paths.append(
                (candidate_path, reason or "FFprobe could not read this video.")
            )

    return video_paths, rejected_paths


def show_ignored_video_files(workspace_dir, rejected_paths):
    """Summarise system sidecars and invalid video-like files excluded from use."""
    ignored_items = [
        (path, "Hidden/system sidecar")
        for path in list_ignored_video_sidecars(workspace_dir)
    ]
    ignored_items.extend(rejected_paths)
    if not ignored_items:
        return

    st.info(
        f"Ignored {len(ignored_items)} hidden, system, or FFmpeg-incompatible "
        "file(s)."
    )
    with st.expander("Show ignored files"):
        for ignored_path, reason in ignored_items:
            st.write(f"`{ignored_path.name}` — {reason}")


@st.cache_data(show_spinner=False, max_entries=1024)
def create_image_thumbnail(
    image_path,
    file_mtime_ns,
    file_size,
    max_dimension=640,
):
    """Create a cached JPEG thumbnail, invalidated when the source file changes."""
    # File metadata is intentionally part of the cache key.
    _ = file_mtime_ns, file_size
    return create_thumbnail_bytes(image_path, max_dimension)


def display_thumbnail_safely(
    image_path,
    max_dimension=640,
    **image_options,
):
    """Display a cached thumbnail without allowing a damaged file to stop a run."""
    image_path = os.path.abspath(os.path.normpath(os.fspath(image_path)))

    try:
        file_stat = os.stat(image_path)
    except OSError as error:
        st.warning(
            f"Image is unavailable: `{os.path.basename(image_path)}` ({error})"
        )
        return False

    try:
        thumbnail = create_image_thumbnail(
            image_path,
            file_stat.st_mtime_ns,
            file_stat.st_size,
            max_dimension,
        )
    except (OSError, SyntaxError, ValueError) as error:
        st.warning(
            f"Could not create thumbnail for `{os.path.basename(image_path)}`: "
            f"{error}"
        )
        return False

    # On Windows, use Streamlit's long-supported default image sizing. Some
    # installations accept width="stretch" but fail to paint the image in the
    # browser. The source thumbnail dimensions still keep the grids compact.
    if os.name == "nt" and image_options.get("width") == "stretch":
        image_options.pop("width")

    st.image(thumbnail, output_format="JPEG", **image_options)
    return True


def select_gallery_image(image_filename):
    """Update the selected gallery image before Streamlit performs its rerun."""
    st.session_state['selected_gallery_image'] = image_filename

#   ##########################################################
#   CUSTOM APPLICATION THEME
#   ----------------------------------------------------------
#   Creates the selected light or dark Streamlit theme using
#   custom CSS applied to the main application interface
#   ##########################################################

def apply_theme(theme_choice):
    if theme_choice == "Dark":
        bg_color = "#0E1117"
        text_color = "#FFFFFF"
        bg_image = "none"
    elif theme_choice == "Light":
        bg_color = "#FFFFFF"
        text_color = "#000000"
        bg_image = "none"

    css = f"""
    <style>
    /* Set the main background */
    .stApp {{
        background-color: {bg_color} !important;
        background-image: {bg_image} !important;
    }}

    /* Force text colors across all standard Streamlit text elements */
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp label, .stApp span, .stMarkdown p, div[data-baseweb="checkbox"] label {{
        color: {text_color} !important;
    }}

    /* Ensure slider values and tick marks remain visible */
    div[data-baseweb="slider"] div, .stSlider div[data-testid="stThumbValue"] {{
        color: {text_color} !important;
    }}

    /* Force tab labels to be visible without needing to hover */
    button[data-baseweb="tab"],
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {{
        color: {text_color} !important;
    }}

    /* Preserve the classic red active underline on native Streamlit tabs. */
    div[data-baseweb="tab-highlight"] {{
        background-color: #ff4b4b !important;
    }}

    /* On older Streamlit versions, make the lazy navigation look like tabs
       instead of a segmented pill control. */
    div[data-testid="stButtonGroup"] > div[data-baseweb="button-group"] {{
        border-bottom: 1px solid rgba(128, 128, 128, 0.35) !important;
        column-gap: 0 !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
    }}

    div[data-testid="stButtonGroup"] button {{
        background: transparent !important;
        border: 0 !important;
        border-bottom: 3px solid transparent !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        flex: 0 0 auto !important;
        max-width: none !important;
        min-height: 3rem !important;
        padding: 0.65rem 1rem !important;
        white-space: nowrap !important;
        width: auto !important;
    }}

    div[data-testid="stButtonGroup"] button:hover {{
        border-bottom-color: rgba(255, 75, 75, 0.45) !important;
    }}

    div[data-testid="stButtonGroup"] button[kind$="Active"],
    div[data-testid="stButtonGroup"] button[data-testid$="Active"] {{
        border-bottom-color: #ff4b4b !important;
    }}

    /* The metadata summary is intentionally compact beside the preview. */
    div[data-testid="stCode"] pre,
    div[data-testid="stCode"] code {{
        font-size: 0.72rem !important;
        line-height: 1.35 !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --------------------------- SIDEBAR CONTROLS
# display the application theme selector and system status
with st.sidebar:
    st.header("🎨 Appearance")
    theme = st.selectbox("Select Theme", ["Dark", "Light"])
    apply_theme(theme)
    st.divider()
    st.write("🔧 System Ready")

# --------------------------- APPLICATION HEADER
# create the toolkit logo, title and author information
col1, col2 = st.columns([1, 4])
with col1:
    # display the application logo
    st.image("logo/logo.png", width=150)
with col2:
    st.title("360 Video Extraction Toolkit")
    st.markdown(
        '<p style="font-family: cursive; font-style: italic; font-size: 24px;">'
        'Making heritage technologies accessible'
        '</p>',
        unsafe_allow_html=True)
    st.markdown("""
    **Author:** Professor Eugene Ch'ng\n
    **LinkedIn:** [https://www.linkedin.com/in/eugenecc/](https://www.linkedin.com/in/eugenecc/) |
    **GitHub:** [https://github.com/drecuk/](https://github.com/drecuk/)
    """)

st.divider()

# --------------------------- MAIN APPLICATION TABS
# divide the workflow into welcome, upload, extraction and filtering stages
TAB_LABELS = [
    "0. Welcome",
    "1. Upload",
    "2. Extraction",
    "3. Remove Sky Photos",
    "4. Remove Blurry Images",
    "5. Browse Metadata"
]


def format_fallback_tab_label(label):
    """Escape the numbered prefix so Markdown keeps it visible."""
    return label.replace(".", r"\.", 1)

SUPPORTS_LAZY_TABS = "on_change" in inspect.signature(st.tabs).parameters

if SUPPORTS_LAZY_TABS:
    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs(
        TAB_LABELS,
        key="main_tabs",
        on_change="rerun",
    )
    fallback_active_tab = None
else:
    # Streamlit before 1.55 cannot track the active st.tabs tab. Use a
    # segmented navigation control so hidden sections remain genuinely lazy.
    fallback_active_tab = st.segmented_control(
        "Application section",
        TAB_LABELS,
        default=TAB_LABELS[0],
        format_func=format_fallback_tab_label,
        key="main_tabs_legacy",
        label_visibility="collapsed",
        width="stretch",
    )
    tab0, tab1, tab2, tab3, tab4, tab5 = (
        st.container() for _ in TAB_LABELS
    )

#   ##########################################################
#   TAB 0: WELCOME AND SYSTEM CHECK
#   ----------------------------------------------------------
#   Checks required system applications and displays the main
#   workflow instructions for the 360 extraction toolkit
#   ##########################################################

def render_welcome_tab():
    st.header("Welcome")

    # --- SYSTEM DEPENDENCY CHECK ---
    missing_deps = check_dependencies()

    if missing_deps:
        # Generate the specific instructions based on their OS
        os_instructions = get_os_instructions(missing_deps)
        missing_str = ", ".join(missing_deps).upper()

        # Custom Orange Warning Panel via HTML/CSS
        orange_panel = f"""
        <div style="background-color: #F57C00; padding: 20px; border-radius: 10px; color: white; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color: white; margin-top: 0; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.3);">⚠️ Missing System Dependencies</h3>
            <p style="font-size: 16px;">This application requires external software to function properly. The following tools are currently missing from your system PATH:</p>
            <ul style="font-size: 16px; font-weight: bold;">
                <li>{missing_str}</li>
            </ul>
        </div>
        """
        st.markdown(orange_panel, unsafe_allow_html=True)

        # Display the terminal instructions below the panel using Streamlit's native markdown
        st.markdown("### How to Fix This:")
        st.markdown(os_instructions)
        st.markdown("*(Note: If you just installed these, you may need to restart your terminal and Streamlit for the changes to take effect.)*")
        st.divider()

    # --- NORMAL WELCOME TEXT ---
    st.write("This web application allows you to extract precise perspective frames from 360-degree video footage.")
    st.write("### Instructions:")
    st.write("1. Go to **Tab 1** and choose a video workspace or upload your 360 video.")
    st.write("2. Go to **Tab 2** to adjust extraction settings. The 3D viewer will update in real-time.")
    st.write("3. Click **Extract Frames** to begin FFmpeg processing.")
    st.write("4. Go to **Tab 3** to automatically detect and filter out empty sky photos.")
    st.write("5. Go to **Tab 4** to automatically detect and filter out blurry images.")
    st.write("6. Go to **Tab 5** to browse extracted images and their generated sidecar YAML metadata.")

    # --- INSTA360 EXPORT SETTINGS ---
    st.divider()

    st.markdown("""
    ### 📷 Insta360 Studio Export Settings
    *For 3D Splatting, NeRF, and Photogrammetry*

    #### Insta360 X6 Recommended Preset

    Use this model-specific preset when exporting Insta360 X6 footage:

    | Setting | Recommendation |
    | --- | --- |
    | Resolution | **8K (7680 × 3840)** |
    | Frame Rate | **30 fps** (match the original recording) |
    | Bitrate | **200 Mbps** to minimise re-encoding artefacts |
    | Codec | **H.265 (HEVC)** |
    | Colour Space | **Rec.709, 10-bit** when the source was recorded in 10-bit |
    | Bottom Stitching Optimisation | **ON**, provided it introduces no geometric distortion |
    | APMP | **OFF** |
    | Export Format | **MP4, 360° equirectangular** |
    | FFmpeg Frame Extraction | **PNG at 3–5 fps** |
    | Stabilisation | Test **OFF** first for geometric consistency |

    > **Priority:** Maximum resolution, consistent geometry, and minimal compression artefacts.

    In **Tab 2: Extraction**, select **Frames per second** and choose **3–5 fps** to apply the recommended PNG sampling rate.

    #### General Insta360 Guidance

    * **Export Type:** 360° Video
    * **Media Type:** Video (Avoid Video Original)
        * *Why:* This applies the vital stitching, horizon calibration, and lens distortion profile needed to transform raw, dual-fisheye data into a flat equirectangular projection that FFmpeg and structure-from-motion (SfM) software can interpret. Avoid "Video Original," as splatting engines cannot align raw, unstitched dual-lens circles.
    * **Stitch Type:** Equirectangular (standard 360)
    * **Resolution:** Select "Custom", then keep the original max resolution (e.g., 8K)
    * **Encoding/Format:** ProRes 422 or ProRes 422 LT
    * **Bitrate:** Unnecessary for ProRes (it is visually lossless), but if you must choose MP4/H.265, set bitrate to max (e.g., 100 Mbps or higher).
    * **Color:** Standard *(Avoid vivid/color plus, as they alter lighting/shadows needed by the splatting engine)*
    * **Stabilization:** **TURN OFF** (No FlowState, No Horizon Lock)
        * *Why:* Splatting engines (like COLMAP) need to extract the raw movement of the camera through space and will fail if the software artificially stabilizes the horizon or jitters frames.
    * **Dolby Vision:** **TURN OFF**
        * *Why:* Dolby Vision forces the export to H.265 (heavy compression) and uses dynamic metadata to continuously shift brightness, tone mapping, and contrast frame-by-frame. Gaussian Splatting relies strictly on consistent pixel lighting across different camera angles. Dynamic tone mapping will confuse the engine, leading to "floaters" and blurry artifacts. Stick to standard SDR or standard linear color spaces.
    * **APMP (Apple Photography Metadata Profile):** **TURN OFF**
        * *Why:* APMP formats the file specifically to be played back as a 3D immersive video inside devices like the Apple Vision Pro. Enabling this drastically changes how the video data is packaged, breaking standard 360 compatibility and preventing FFmpeg from cleanly extracting geometric frames.

    #### ✅ Summary Checklist
    - **Export Type:** 360 Video
    - **Media Type:** Video
    - **Codec:** ProRes 422 (Mac) or High-Bitrate H.264/H.265 (Windows)
    - **Disabled Settings:** Dolby Vision, APMP, FlowState, Horizon Lock

    > 💡 **Pipeline Note:** If you are training your splat using Nerfstudio (NSVF), Luma AI, or Postshot, some of these pipelines have built-in scripts that handle the extraction and lens calibration automatically without needing manual FFmpeg parsing.
    """)

#   ##########################################################
#   TAB 1: UPLOAD 360 VIDEOS
#   ----------------------------------------------------------
#   Uses videos from a chosen local or external-drive directory
#   and optionally saves browser uploads into that workspace
#   ##########################################################

def render_upload_tab():
    st.header("Video Workspace")
    st.write(
        "Process videos directly from an existing directory, including a mounted "
        "external hard drive, or upload videos into that directory."
    )

    workspace_dir = get_workspace_dir()
    if "workspace_path_input" not in st.session_state:
        st.session_state["workspace_path_input"] = str(workspace_dir)

    picker_col, reset_col = st.columns([2, 1])
    with picker_col:
        choose_directory = st.button(
            "📁 Choose Directory…",
            type="primary",
            width="stretch",
            help="Open the folder picker on the computer running this app.",
        )
    with reset_col:
        st.button(
            "Reset to Project Folder",
            width="stretch",
            on_click=reset_workspace,
        )

    # The native picker must run before the text widget is created so the
    # selected path can safely update that widget's session value.
    if choose_directory:
        selected_directory, picker_error = choose_workspace_directory()
        if picker_error:
            st.error(picker_error)
            st.info("You can enter the directory path manually below.")
        elif selected_directory is not None:
            workspace_problems = validate_workspace_directory(selected_directory)
            if workspace_problems:
                for problem in workspace_problems:
                    st.error(problem)
            else:
                if selected_directory != workspace_dir:
                    clear_workspace_dependent_state()
                st.session_state["workspace_dir"] = str(selected_directory)
                st.session_state["workspace_path_input"] = str(selected_directory)
                workspace_dir = selected_directory
                st.success("Workspace directory selected.")

    st.text_input(
        "Or enter a workspace directory manually",
        key="workspace_path_input",
        help=(
            "Paste an existing folder path, for example "
            "/Volumes/ExternalDrive/Survey on macOS or "
            r"D:\HeritageSurvey on Windows."
        ),
    )

    use_directory = st.button("Use Typed Path")

    if use_directory:
        try:
            selected_directory = normalise_workspace_path(
                st.session_state["workspace_path_input"]
            )
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            workspace_problems = validate_workspace_directory(selected_directory)
            if workspace_problems:
                for problem in workspace_problems:
                    st.error(problem)
            else:
                if selected_directory != workspace_dir:
                    clear_workspace_dependent_state()
                st.session_state["workspace_dir"] = str(selected_directory)
                workspace_dir = selected_directory
                st.success("Workspace directory selected.")

    # Check the active path on every rerun so a disconnected external drive is
    # reported before any extraction or filtering operation begins.
    workspace_problems = validate_workspace_directory(workspace_dir)
    if workspace_problems:
        st.error(
            f"The active workspace is unavailable: `{workspace_dir}` "
            f"{' '.join(workspace_problems)}"
        )
        st.info("Reconnect the drive or select another existing directory above.")
        return

    video_paths, rejected_video_paths = get_workspace_video_files(workspace_dir)
    free_space = shutil.disk_usage(workspace_dir).free
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.metric("Videos found", len(video_paths))
    with status_col2:
        st.metric("Free space", format_storage_size(free_space))

    show_ignored_video_files(workspace_dir, rejected_video_paths)
    st.caption(f"Active workspace: `{workspace_dir}`")
    if st.button("📂 Open Workspace Folder"):
        if not open_folder(str(workspace_dir)):
            st.error("Could not open the workspace folder.")

    source_mode = st.radio(
        "Choose how to add videos",
        (
            "Use videos already in this directory",
            "Upload videos into this directory",
        ),
        horizontal=True,
    )

    if source_mode == "Use videos already in this directory":
        if video_paths:
            st.success(f"{len(video_paths)} supported video(s) are ready for extraction.")
            with st.expander("Show detected videos"):
                for video_path in video_paths:
                    st.write(video_path.name)
        else:
            st.info(
                "No FFmpeg-readable MP4, MOV, AVI, or MKV videos were found "
                "in this directory."
            )
        return

    # --------------------------- SELECT VIDEO FILES
    # Browser uploads remain available for smaller files and existing workflows.
    uploaded_files = st.file_uploader(
        "Drop 360 videos here",
        type=["mp4", "mov", "avi", "mkv"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        new_uploads = 0
        existing_uploads = 0
        rejected_uploads = []
        ffprobe_path = get_workspace_ffprobe_path()
        known_valid_paths = {path.resolve() for path in video_paths}

        if not ffprobe_path:
            st.error(
                "FFprobe is required to validate uploaded videos. Install FFmpeg "
                "and FFprobe, then restart the app."
            )
            return

        # --------------------------- SAVE VIDEO FILES
        # Validate in a temporary file before accepting an upload into the workspace.
        for uploaded_file in uploaded_files:
            safe_filename = Path(uploaded_file.name).name
            if safe_filename.startswith("."):
                rejected_uploads.append(
                    (safe_filename, "Hidden and system sidecar files are not allowed.")
                )
                continue
            if Path(safe_filename).suffix.lower() not in VIDEO_EXTENSIONS:
                rejected_uploads.append(
                    (safe_filename, "The file does not use a supported video extension.")
                )
                continue

            file_path = workspace_dir / safe_filename
            resolved_file_path = file_path.resolve()

            if (
                file_path.exists()
                and file_path.stat().st_size == uploaded_file.size
                and resolved_file_path in known_valid_paths
            ):
                existing_uploads += 1
                continue

            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=workspace_dir,
                    prefix=".360-upload-",
                    suffix=file_path.suffix,
                    delete=False,
                ) as output_file:
                    temporary_path = Path(output_file.name)
                    output_file.write(uploaded_file.getbuffer())

                is_compatible, reason = probe_video_file(
                    temporary_path,
                    ffprobe_path,
                )
                if not is_compatible:
                    rejected_uploads.append(
                        (
                            safe_filename,
                            reason or "FFprobe could not read this video.",
                        )
                    )
                    continue

                os.replace(temporary_path, file_path)
                temporary_path = None
                known_valid_paths.add(resolved_file_path)
                new_uploads += 1
            except OSError as error:
                rejected_uploads.append((safe_filename, str(error)))
            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError:
                        pass

        if new_uploads > 0:
            st.success(
                f"Successfully validated and saved {new_uploads} new video(s) "
                "to the workspace."
            )
        if existing_uploads > 0:
            st.info(f"{existing_uploads} validated video(s) were already present.")
        if rejected_uploads:
            st.warning(
                f"Rejected {len(rejected_uploads)} upload(s) that FFmpeg cannot use."
            )
            with st.expander("Show rejected uploads"):
                for filename, reason in rejected_uploads:
                    st.write(f"`{filename}` — {reason}")

#   ##########################################################
#   TAB 2: VIDEO FRAME EXTRACTION
#   ----------------------------------------------------------
#   Configures the 360-degree camera layout and extracts the
#   selected perspective views using FFmpeg
#
#   Supports individual and batch video extraction
#   ##########################################################

def render_extraction_tab():
    st.header("Extraction Settings")
    workspace_dir = get_workspace_dir()
    st.caption(f"Workspace: `{workspace_dir}`")

    if not workspace_is_available(workspace_dir):
        return

    # create separate columns for settings and 3D visualisation
    col_settings, col_viz = st.columns([1, 2])

    with col_settings:
        # --------------------------- EXTRACTION SETTINGS
        # configure sampling rate, camera views, field of view and resolution
        sampling_mode = st.selectbox(
            "FRAME_SAMPLING_MODE",
            ["Frames per second", "Seconds between frames"],
            help="Use 3–5 fps for the recommended Insta360 X6 photogrammetry workflow.",
        )

        if sampling_mode == "Frames per second":
            sample_fps = st.slider(
                "FRAME_EXTRACTION_FPS",
                min_value=3,
                max_value=5,
                value=3,
                help="Insta360 X6 recommendation: extract PNG frames at 3–5 fps.",
            )
            interval_seconds = 1.0 / sample_fps
            st.caption(f"PNG sampling interval: every {interval_seconds:.3f} seconds")
        else:
            interval_seconds = st.slider(
                "EXTRACT_EVERY_N_SECONDS",
                min_value=1,
                max_value=30,
                value=2,
            )

        h_splits = st.slider("HORIZONTAL_SPLITS", 4, 64, 8)
        inc_nadir = st.checkbox("INCLUDE_NADIR_ZENITH", value=True)
        inc_45 = st.checkbox("INCLUDE_45_PITCH", value=True)
        fov = st.number_input("FIELD_OF_VIEW", value=90)
        res = st.slider("IMAGE_RESOLUTION", 512, 8192, 1024, step=256)

        # --------------------------- FIND AVAILABLE VIDEOS
        # load supported videos from the active workspace
        video_paths, rejected_video_paths = get_workspace_video_files(workspace_dir)
        available_videos = [path.name for path in video_paths]
        show_ignored_video_files(workspace_dir, rejected_video_paths)

        # allow the user to select one video for individual extraction
        selected_vid = st.selectbox("Target Video to Extract:", available_videos) if available_videos else None

        # --------------------------- EXTRACTION COMMANDS
        # display individual and batch extraction buttons side by side
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            extract_btn = st.button("Extract Selected", type="primary", width="stretch")
        with btn_col2:
            batch_extract_btn = st.button("Batch Extract All", type="secondary", width="stretch")

    with col_viz:
        # --------------------------- CAMERA RIG VISUALISATION
        # update the interactive 3D camera layout when settings change
        fig = generate_360_splits(interval_seconds, h_splits, inc_nadir, inc_45, fov, res)
        st.plotly_chart(fig, width="stretch")

    # --------------------------- SINGLE EXTRACTION
    # extract perspective frames from the selected video
    if extract_btn:
        if not selected_vid:
            st.error("Choose a workspace containing a supported video in Tab 1 first.")
        else:
            vid_path = workspace_dir / selected_vid
            vid_clean_name = os.path.splitext(selected_vid)[0]
            out_dir = workspace_dir / f"cubemap-{vid_clean_name}"

            st.markdown("---")
            st.write(f"**Extracting:** {selected_vid}")

            progress_bar = st.progress(0.0)
            status_text = st.empty()

            # run FFmpeg extraction using the selected camera settings
            extract_360_frames(str(vid_path), str(out_dir), vid_clean_name, interval_seconds, h_splits, inc_nadir, inc_45, fov, res, progress_bar, status_text)

            # remember the latest output folder for the folder viewer
            st.session_state['last_output_dir'] = str(out_dir.resolve())

    # --------------------------- BATCH EXTRACTION
    # process every supported video found within the active workspace
    if batch_extract_btn:
        if not available_videos:
            st.error("No supported videos are available. Choose a workspace in Tab 1.")
        else:
            st.markdown("---")
            st.write(f"### 🚀 Batch Processing {len(available_videos)} Videos")

            overall_progress = st.progress(0.0)

            for idx, vid_filename in enumerate(available_videos):
                st.write(f"**File {idx + 1} of {len(available_videos)}:** `{vid_filename}`")

                vid_path = workspace_dir / vid_filename
                vid_clean_name = os.path.splitext(vid_filename)[0]
                out_dir = workspace_dir / f"cubemap-{vid_clean_name}"

                # create dedicated progress controls for the current video
                file_progress_bar = st.progress(0.0)
                file_status_text = st.empty()

                # extract perspective frames from the current video
                extract_360_frames(str(vid_path), str(out_dir), vid_clean_name, interval_seconds, h_splits, inc_nadir, inc_45, fov, res, file_progress_bar, file_status_text)

                # update progress across the complete video batch
                overall_progress.progress((idx + 1) / len(available_videos))

            st.success("🎉 Batch extraction complete for all videos!")
            st.session_state['last_output_dir'] = str(workspace_dir.resolve())

    # --------------------------- OPEN OUTPUT FOLDER
    # display the folder command after an extraction has completed
    if 'last_output_dir' in st.session_state:
        if st.button("📂 View Output Folder"):
            success = open_folder(st.session_state['last_output_dir'])
            if not success:
                st.error("Could not locate directory. It may not exist yet.")

#   ##########################################################
#   TAB 3: DETECT AND REMOVE SKY PHOTOS
#   ----------------------------------------------------------
#   Scans extracted images for blue sky content and presents
#   detected images for visual confirmation before moving them
#
#   Images selected for removal are moved into skies_only
#   ##########################################################

def render_sky_tab():
    st.header("Remove Sky Photos")
    st.write("Detect and filter out frames that are predominantly sky/empty space.")
    workspace_dir = get_workspace_dir()
    st.caption(f"Workspace: `{workspace_dir}`")
    if not workspace_is_available(workspace_dir):
        return

    # --------------------------- FIND EXTRACTED FOLDERS
    # locate all cubemap folders created during video extraction
    extracted_folders = [
        path.name for path in list_extracted_folders(workspace_dir)
    ]

    col_ctrl1, col_ctrl2 = st.columns([2, 1])

    with col_ctrl1:
        target_folder = st.selectbox("Select Extracted Folder to Analyze:", extracted_folders)
    with col_ctrl2:
        threshold = st.slider("Sky Threshold (%)", min_value=50.0, max_value=100.0, value=85.0, step=1.0)

    # --------------------------- INITIALISE SKY STATE
    # retain detected images and scan status between Streamlit reruns
    if 'detected_skies' not in st.session_state:
        st.session_state['detected_skies'] = []
    if 'scan_complete' not in st.session_state:
        st.session_state['scan_complete'] = False

    if st.button("Detect Skies", type="primary"):
        if not target_folder:
            st.error("No extracted folders found. Please extract frames in Tab 2 first.")
        else:
            full_target_path = workspace_dir / target_folder

            # reset previously detected images before starting a new scan
            st.session_state['detected_skies'] = []

            # --------------------------- SCAN FOR SKY IMAGES
            # evaluate every supported image using the selected sky threshold
            with st.spinner("Analyzing frames for sky content..."):
                for img_path in list_image_files(full_target_path):
                    is_sky, pct = evaluate_sky_image(str(img_path), threshold)

                    if is_sky:
                        # store the image path, sky percentage and filename for review
                        st.session_state['detected_skies'].append({
                            'path': str(img_path),
                            'pct': pct,
                            'filename': img_path.name
                        })

            st.session_state['scan_complete'] = True
            st.rerun()

    # --------------------------- REVIEW SKY IMAGES
    # display detected images after the sky scan has completed
    if st.session_state['scan_complete']:
        st.divider()
        if len(st.session_state['detected_skies']) == 0:
            st.success("No sky images detected at this threshold!")
        else:
            st.write(f"### Review: {len(st.session_state['detected_skies'])} Sky Photos Detected")
            st.write("Click '❌' to keep an image. Click 'Confirm' to move the remaining images.")

            # --------------------------- CONFIRM SKY REMOVAL
            # move every image remaining within the review list
            if st.button("✅ Confirm & Move Skies", type="primary"):
                dest_folder = workspace_dir / target_folder / "skies_only"
                paths_to_move = [item['path'] for item in st.session_state['detected_skies']]

                moved = move_confirmed_skies(paths_to_move, str(dest_folder))
                st.success(f"Successfully moved {moved} images to {dest_folder}")

                # clear the sky review state after moving confirmed images
                st.session_state['detected_skies'] = []
                st.session_state['scan_complete'] = False
                st.rerun()

            st.write("") # add spacing before the image grid

            # --------------------------- DISPLAY IMAGE GRID
            # create a four-column grid for reviewing detected sky images
            cols = st.columns(4)

            # iterate over a copy so images can be removed safely during review
            for idx, img_data in enumerate(list(st.session_state['detected_skies'])):
                col = cols[idx % 4]
                with col:
                    # display the image thumbnail and detected sky percentage
                    if display_thumbnail_safely(img_data['path'], width="stretch"):
                        st.caption(f"{img_data['pct']:.1f}% Sky")

                    # keep the image by removing it from the pending move list
                    if st.button("❌ Keep", key=f"keep_{img_data['path']}"):
                        st.session_state['detected_skies'] = [i for i in st.session_state['detected_skies'] if i['path'] != img_data['path']]
                        st.rerun()

#   ##########################################################
#   TAB 4: DETECT AND REMOVE BLURRY IMAGES
#   ----------------------------------------------------------
#   Divides extracted images into grid sectors and detects
#   partial blur using Variance of Laplacian focus measurement
#
#   Images selected for removal are moved into blurry_only
#   ##########################################################

def render_blurry_tab():
    st.header("Remove Blurry Images")
    st.write("Detect and filter out frames that contain blurry sectors (e.g., motion blur).")
    workspace_dir = get_workspace_dir()
    st.caption(f"Workspace: `{workspace_dir}`")
    if not workspace_is_available(workspace_dir):
        return

    # --------------------------- FIND EXTRACTED FOLDERS
    # locate all cubemap folders created during video extraction
    extracted_folders = [
        path.name for path in list_extracted_folders(workspace_dir)
    ]

    # Create 4 columns to accommodate the minimum sectors slider
    col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([2, 1, 1, 1])

    with col_ctrl1:
        target_folder_blur = st.selectbox("Select Extracted Folder:", extracted_folders, key="blur_folder")
    with col_ctrl2:
        grid_size = st.slider("Grid Size (NxN)", min_value=1, max_value=10, value=3, step=1)
    with col_ctrl3:
        threshold = st.slider("Blur Threshold", min_value=0.0, max_value=500.0, value=100.0, step=1.0)
    with col_ctrl4:
        # Dynamically calculate the maximum number of sectors based on the grid size (N x N)
        max_sectors = grid_size * grid_size
        min_sectors = st.slider("Min Blurry Sectors", min_value=1, max_value=max_sectors, value=1, step=1)

    # --------------------------- INITIALISE BLUR STATE
    # retain detected images and scan status between Streamlit reruns
    if 'detected_blurry' not in st.session_state:
        st.session_state['detected_blurry'] = []
    if 'blur_scan_complete' not in st.session_state:
        st.session_state['blur_scan_complete'] = False

    if st.button("Detect Blurry Images", type="primary"):
        if not target_folder_blur:
            st.error("No extracted folders found. Please extract frames in Tab 2 first.")
        else:
            full_target_path = workspace_dir / target_folder_blur

            # reset previously detected images before starting a new scan
            st.session_state['detected_blurry'] = []

            # --------------------------- SCAN FOR BLURRY IMAGES
            # evaluate every image in the folder using the selected blur settings
            with st.spinner("Analyzing frames for partial blur..."):
                for img_path in list_image_files(full_target_path):
                    #  min_sectors passed in
                    is_blurry, bad_chunks, total_chunks = evaluate_blurry_image(str(img_path), grid_size, threshold, min_sectors)

                    if is_blurry:
                        # store image details and failed sector counts for review
                        st.session_state['detected_blurry'].append({
                            'path': str(img_path),
                            'bad_chunks': bad_chunks,
                            'total_chunks': total_chunks,
                            'filename': img_path.name
                        })

            st.session_state['blur_scan_complete'] = True
            st.rerun()

    # --------------------------- REVIEW BLURRY IMAGES
    # display detected images after the blur scan has completed
    if st.session_state['blur_scan_complete']:
        st.divider()
        if len(st.session_state['detected_blurry']) == 0:
            st.success("No blurry images detected with these settings!")
        else:
            st.write(f"### Review: {len(st.session_state['detected_blurry'])} Blurry Photos Detected")
            st.write("Click '❌' to keep an image. Click 'Confirm' to move the remaining images.")

            # --------------------------- CONFIRM BLUR REMOVAL
            # move every image remaining within the review list
            if st.button("✅ Confirm & Move Blurry", type="primary"):
                dest_folder = workspace_dir / target_folder_blur / "blurry_only"
                paths_to_move = [item['path'] for item in st.session_state['detected_blurry']]

                moved = move_confirmed_blurry(paths_to_move, str(dest_folder))
                st.success(f"Successfully moved {moved} images to {dest_folder}")

                # clear the blur review state after moving confirmed images
                st.session_state['detected_blurry'] = []
                st.session_state['blur_scan_complete'] = False
                st.rerun()

            st.write("") # add space before the image grid

            # --------------------------- DISPLAY IMAGE GRID
            # create a four-column grid for reviewing detected blurry images
            cols = st.columns(4)

            # iterate over a copy so images can be removed safely during review
            for idx, img_data in enumerate(list(st.session_state['detected_blurry'])):
                col = cols[idx % 4]
                with col:
                    # display the image thumbnail and failed sector count
                    if display_thumbnail_safely(img_data['path'], width="stretch"):
                        st.caption(f"Failed: {img_data['bad_chunks']}/{img_data['total_chunks']} sectors")

                    # keep the image by removing it from the pending move list
                    if st.button("❌ Keep", key=f"keep_blur_{img_data['path']}"):
                        st.session_state['detected_blurry'] = [i for i in st.session_state['detected_blurry'] if i['path'] != img_data['path']]
                        st.rerun()

#   ##########################################################
#   TAB 5: BROWSE METADATA
#   ----------------------------------------------------------
#   Allows the user to select an extracted folder, browse its images,
#   and view the associated YAML sidecar metadata.
#   ##########################################################

def render_metadata_tab():
    st.header("Browse Metadata")
    st.write("Select an extracted folder to browse the images and view their generated YAML metadata side-by-side.")
    workspace_dir = get_workspace_dir()
    st.caption(f"Workspace: `{workspace_dir}`")
    if not workspace_is_available(workspace_dir):
        return

    # 1. Find Extracted Folders
    extracted_folders = [
        path.name for path in list_extracted_folders(workspace_dir)
    ]

    if not extracted_folders:
        st.info("No extracted folders found. Go to Tab 2 to extract a video first.")
    else:
        # 2. Select Folder
        target_browse_folder = st.selectbox("Select Extracted Folder to Browse:", extracted_folders, key="browse_folder_tab5")

        full_browse_path = workspace_dir / target_browse_folder

        # 3. Get all images in the folder
        image_files = [path.name for path in list_image_files(full_browse_path)]

        if not image_files:
            st.warning("No images found in the selected folder.")
        else:
            st.divider()

            # Create the split layout for gallery and metadata
            col_gallery, col_meta = st.columns([2, 1])

            # Use session state to remember which image was clicked in the gallery
            if 'selected_gallery_image' not in st.session_state:
                st.session_state['selected_gallery_image'] = image_files[0]

            # If the folder changes, reset the selected image to the first one in the new folder
            if st.session_state['selected_gallery_image'] not in image_files:
                 st.session_state['selected_gallery_image'] = image_files[0]

            with col_gallery:
                st.write("**Image Gallery (Click 'Select' to view metadata)**")

                total_pages = (
                    len(image_files) + GALLERY_PAGE_SIZE - 1
                ) // GALLERY_PAGE_SIZE
                page_number = st.number_input(
                    "Gallery page",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key=f"gallery_page_{target_browse_folder}",
                )
                page_start = (page_number - 1) * GALLERY_PAGE_SIZE
                page_end = min(page_start + GALLERY_PAGE_SIZE, len(image_files))
                page_image_files = image_files[page_start:page_end]
                st.caption(
                    f"Showing images {page_start + 1}–{page_end} of "
                    f"{len(image_files)}"
                )

                st.caption("Scroll inside the thumbnail gallery to browse this page.")

                # Keep the selected-image panel stationary by giving the thumbnail
                # grid its own vertical scroll area.
                with st.container(height=GALLERY_SCROLL_HEIGHT, border=True):
                    gallery_cols = st.columns(GALLERY_COLUMNS)

                    for idx, img_file in enumerate(page_image_files):
                        g_col = gallery_cols[idx % GALLERY_COLUMNS]
                        with g_col:
                            img_path = full_browse_path / img_file
                            display_thumbnail_safely(
                                img_path,
                                max_dimension=GALLERY_THUMBNAIL_SIZE,
                                width="stretch",
                            )

                            # Use a primary button if it is currently selected, else secondary
                            is_selected = st.session_state['selected_gallery_image'] == img_file
                            btn_type = "primary" if is_selected else "secondary"
                            btn_label = "Selected" if is_selected else "Select"

                            st.button(
                                btn_label,
                                key=f"select_{target_browse_folder}_{img_file}",
                                type=btn_type,
                                use_container_width=True,
                                on_click=select_gallery_image,
                                args=(img_file,),
                            )

            with col_meta:
                st.write("**Selected Image & YAML Metadata**")

                selected_image = st.session_state['selected_gallery_image']
                image_path = full_browse_path / selected_image

                # Show a larger cached preview of the actively selected image.
                display_thumbnail_safely(
                    image_path,
                    max_dimension=1280,
                    width="stretch",
                )

                # Replace image extension with .yaml
                yaml_filename = os.path.splitext(selected_image)[0] + ".yaml"
                yaml_path = full_browse_path / yaml_filename

                # Check if YAML exists and read it
                metadata = read_frame_metadata(yaml_path, print_summary=False)

                if metadata:
                    # Reconstruct the terminal-style summary for the UI using Markdown
                    camera = metadata.get("camera_spatial", {})
                    timestamps = metadata.get("timestamps", {})
                    vision = metadata.get("vision_model", {})
                    transients = metadata.get("transient_objects", {})
                    sam2 = metadata.get("sam2_masks", {})

                    res = camera.get("resolution_px", [None, None])
                    res_str = f"{res[0]}x{res[1]}px" if isinstance(res, list) and len(res) == 2 else "N/A"

                    st.code(f"""
==================================================
 METADATA SUMMARY: {yaml_filename}
==================================================
Camera View ID     : {camera.get('view_id', 'N/A')} (Index: {camera.get('view_index', 'N/A')})
Orientation        : Yaw {camera.get('yaw_degrees')}°, Pitch {camera.get('pitch_degrees')}°
FOV & Resolution   : FOV {camera.get('fov_degrees')}° | {res_str} ({camera.get('projection', 'N/A')})
--------------------------------------------------
Video Start Time   : {timestamps.get('video_start_time')}
Frame Current Time : {timestamps.get('frame_current_time')}
Elapsed Seconds    : {timestamps.get('elapsed_seconds')}s
--------------------------------------------------
Vision Model       : {vision.get('model_name') or 'N/A'}
Description        : {vision.get('description') or 'None'}
--------------------------------------------------
Transient Objects  : {', '.join(transients.get('keywords', [])) or 'None'}
SAM2 Mask Count    : {sam2.get('mask_count', 0)}
==================================================
                    """, language='yaml')

                    # Optionally, provide an expander to see the raw JSON/Dict
                    with st.expander("View Raw Dictionary"):
                        st.json(metadata)

                else:
                    st.error(f"Metadata file not found: `{yaml_filename}`")
                    st.info("Ensure the extraction pipeline successfully generated the .yaml files alongside the images.")


TAB_RENDERERS = [
    render_welcome_tab,
    render_upload_tab,
    render_extraction_tab,
    render_sky_tab,
    render_blurry_tab,
    render_metadata_tab,
]

tab_containers = (tab0, tab1, tab2, tab3, tab4, tab5)

if SUPPORTS_LAZY_TABS:
    for tab, render_tab in zip(tab_containers, TAB_RENDERERS):
        if tab.open:
            with tab:
                render_tab()
            break
else:
    active_tab_index = TAB_LABELS.index(
        fallback_active_tab or TAB_LABELS[0]
    )
    with tab_containers[active_tab_index]:
        TAB_RENDERERS[active_tab_index]()
