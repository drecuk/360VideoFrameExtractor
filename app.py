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
import os
from utils_viz import generate_360_splits
from utils_ffmpeg import extract_360_frames
from utils_os import open_folder
from util_detectsky import evaluate_sky_image, move_confirmed_skies
from utils_checksys import check_dependencies, get_os_instructions
from util_detectblurry import evaluate_blurry_image, move_confirmed_blurry
from util_read_yaml import read_frame_metadata
from PIL import Image # display image thumbnails


st.set_page_config(page_title="360 Frame Extractor", layout="wide")

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
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "0. Welcome",
    "1. Upload",
    "2. Extraction",
    "3. Remove Sky Photos",
    "4. Remove Blurry Images",
    "5. Browse Metadata"
])

#   ##########################################################
#   TAB 0: WELCOME AND SYSTEM CHECK
#   ----------------------------------------------------------
#   Checks required system applications and displays the main
#   workflow instructions for the 360 extraction toolkit
#   ##########################################################

with tab0:
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
    st.write("1. Go to **Tab 1** and upload your 360 video.")
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
#   Accepts one or more 360-degree video files and stores them
#   within the local uploaded_videos folder for processing
#   ##########################################################

with tab1:
    st.header("Upload Video")
    st.write("Upload a folder with your 360 videos or drag and drop.")

    # --------------------------- SELECT VIDEO FILES
    # accept the supported MP4, MOV, AVI and MKV video formats
    uploaded_files = st.file_uploader("Drop 360 videos here", type=['mp4', 'mov', 'avi', 'mkv'], accept_multiple_files=True)

    if uploaded_files:
        # create the local video folder if it does not already exist
        os.makedirs("uploaded_videos", exist_ok=True)

        # initialise the number of newly written video files
        new_uploads = 0

        # --------------------------- SAVE VIDEO FILES
        # process every video selected through the upload interface
        for f in uploaded_files:
            file_path = os.path.join("uploaded_videos", f.name)

            # only write new files or files with a different stored size
            if not os.path.exists(file_path) or os.path.getsize(file_path) != f.size:
                with open(file_path, "wb") as out_file:
                    out_file.write(f.read())
                new_uploads += 1

        if new_uploads > 0:
            st.success(f"Successfully uploaded and saved {new_uploads} new video(s).")
        else:
            st.info(f"{len(uploaded_files)} video(s) ready for extraction in the local folder.")

#   ##########################################################
#   TAB 2: VIDEO FRAME EXTRACTION
#   ----------------------------------------------------------
#   Configures the 360-degree camera layout and extracts the
#   selected perspective views using FFmpeg
#
#   Supports individual and batch video extraction
#   ##########################################################

with tab2:
    st.header("Extraction Settings")

    # create separate columns for settings and 3D visualisation
    col_settings, col_viz = st.columns([1, 2])

    with col_settings:
        # --------------------------- EXTRACTION SETTINGS
        # configure sampling interval, camera views, field of view and resolution
        interval = st.slider("EXTRACT_EVERY_N_SECONDS", 1, 30, 2)
        h_splits = st.slider("HORIZONTAL_SPLITS", 4, 64, 8)
        inc_nadir = st.checkbox("INCLUDE_NADIR_ZENITH", value=True)
        inc_45 = st.checkbox("INCLUDE_45_PITCH", value=True)
        fov = st.number_input("FIELD_OF_VIEW", value=90)
        res = st.slider("IMAGE_RESOLUTION", 512, 4096, 1024, step=256)

        # --------------------------- FIND AVAILABLE VIDEOS
        # load supported videos from the local uploaded_videos folder
        available_videos = []
        if os.path.exists("uploaded_videos"):
            # include all supported extraction formats
            valid_exts = ('.mp4', '.mov', '.avi', '.mkv')
            available_videos = [f for f in os.listdir("uploaded_videos") if f.lower().endswith(valid_exts)]

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
        fig = generate_360_splits(interval, h_splits, inc_nadir, inc_45, fov, res)
        st.plotly_chart(fig, use_container_width=True)

    # --------------------------- SINGLE EXTRACTION
    # extract perspective frames from the selected video
    if extract_btn:
        if not selected_vid:
            st.error("Please upload a video in Tab 1 first.")
        else:
            vid_path = os.path.join("uploaded_videos", selected_vid)
            vid_clean_name = os.path.splitext(selected_vid)[0]
            out_dir = os.path.join("uploaded_videos", f"cubemap-{vid_clean_name}")

            st.markdown("---")
            st.write(f"**Extracting:** {selected_vid}")

            progress_bar = st.progress(0.0)
            status_text = st.empty()

            # run FFmpeg extraction using the selected camera settings
            extract_360_frames(vid_path, out_dir, vid_clean_name, interval, h_splits, inc_nadir, inc_45, fov, res, progress_bar, status_text)

            # remember the latest output folder for the folder viewer
            st.session_state['last_output_dir'] = os.path.abspath(out_dir)

    # --------------------------- BATCH EXTRACTION
    # process every supported video found within uploaded_videos
    if batch_extract_btn:
        if not available_videos:
            st.error("No videos available in the folder to process. Please upload them in Tab 1.")
        else:
            st.markdown("---")
            st.write(f"### 🚀 Batch Processing {len(available_videos)} Videos")

            overall_progress = st.progress(0.0)

            for idx, vid_filename in enumerate(available_videos):
                st.write(f"**File {idx + 1} of {len(available_videos)}:** `{vid_filename}`")

                vid_path = os.path.join("uploaded_videos", vid_filename)
                vid_clean_name = os.path.splitext(vid_filename)[0]
                out_dir = os.path.join("uploaded_videos", f"cubemap-{vid_clean_name}")

                # create dedicated progress controls for the current video
                file_progress_bar = st.progress(0.0)
                file_status_text = st.empty()

                # extract perspective frames from the current video
                extract_360_frames(vid_path, out_dir, vid_clean_name, interval, h_splits, inc_nadir, inc_45, fov, res, file_progress_bar, file_status_text)

                # update progress across the complete video batch
                overall_progress.progress((idx + 1) / len(available_videos))

            st.success("🎉 Batch extraction complete for all videos!")
            st.session_state['last_output_dir'] = os.path.abspath("uploaded_videos")

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

with tab3:
    st.header("Remove Sky Photos")
    st.write("Detect and filter out frames that are predominantly sky/empty space.")

    # --------------------------- FIND EXTRACTED FOLDERS
    # locate all cubemap folders created during video extraction
    extracted_folders = []
    if os.path.exists("uploaded_videos"):
        extracted_folders = [f for f in os.listdir("uploaded_videos")
                             if os.path.isdir(os.path.join("uploaded_videos", f)) and f.startswith("cubemap-")]

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
            full_target_path = os.path.join("uploaded_videos", target_folder)
            valid_exts = ('.png', '.jpg', '.jpeg')

            # reset previously detected images before starting a new scan
            st.session_state['detected_skies'] = []

            # --------------------------- SCAN FOR SKY IMAGES
            # evaluate every supported image using the selected sky threshold
            with st.spinner("Analyzing frames for sky content..."):
                for filename in os.listdir(full_target_path):
                    if filename.lower().endswith(valid_exts):
                        img_path = os.path.join(full_target_path, filename)
                        is_sky, pct = evaluate_sky_image(img_path, threshold)

                        if is_sky:
                            # store the image path, sky percentage and filename for review
                            st.session_state['detected_skies'].append({
                                'path': img_path,
                                'pct': pct,
                                'filename': filename
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
                dest_folder = os.path.join("uploaded_videos", target_folder, "skies_only")
                paths_to_move = [item['path'] for item in st.session_state['detected_skies']]

                moved = move_confirmed_skies(paths_to_move, dest_folder)
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
                    st.image(img_data['path'], use_container_width=True)
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

with tab4:
    st.header("Remove Blurry Images")
    st.write("Detect and filter out frames that contain blurry sectors (e.g., motion blur).")

    # --------------------------- FIND EXTRACTED FOLDERS
    # locate all cubemap folders created during video extraction
    extracted_folders = []
    if os.path.exists("uploaded_videos"):
        extracted_folders = [f for f in os.listdir("uploaded_videos")
                             if os.path.isdir(os.path.join("uploaded_videos", f)) and f.startswith("cubemap-")]

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
            full_target_path = os.path.join("uploaded_videos", target_folder_blur)
            valid_exts = ('.png', '.jpg', '.jpeg')

            # reset previously detected images before starting a new scan
            st.session_state['detected_blurry'] = []

            # --------------------------- SCAN FOR BLURRY IMAGES
            # evaluate every image in the folder using the selected blur settings
            with st.spinner("Analyzing frames for partial blur..."):
                for filename in os.listdir(full_target_path):
                    if filename.lower().endswith(valid_exts):
                        img_path = os.path.join(full_target_path, filename)

                        #  min_sectors passed in
                        is_blurry, bad_chunks, total_chunks = evaluate_blurry_image(img_path, grid_size, threshold, min_sectors)

                        if is_blurry:
                            # store image details and failed sector counts for review
                            st.session_state['detected_blurry'].append({
                                'path': img_path,
                                'bad_chunks': bad_chunks,
                                'total_chunks': total_chunks,
                                'filename': filename
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
                dest_folder = os.path.join("uploaded_videos", target_folder_blur, "blurry_only")
                paths_to_move = [item['path'] for item in st.session_state['detected_blurry']]

                moved = move_confirmed_blurry(paths_to_move, dest_folder)
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
                    st.image(img_data['path'], use_container_width=True)
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

with tab5:
    st.header("Browse Metadata")
    st.write("Select an extracted folder to browse the images and view their generated YAML metadata side-by-side.")

    # 1. Find Extracted Folders
    extracted_folders = []
    if os.path.exists("uploaded_videos"):
        extracted_folders = [f for f in os.listdir("uploaded_videos")
                             if os.path.isdir(os.path.join("uploaded_videos", f)) and f.startswith("cubemap-")]

    if not extracted_folders:
        st.info("No extracted folders found. Go to Tab 2 to extract a video first.")
    else:
        # 2. Select Folder
        target_browse_folder = st.selectbox("Select Extracted Folder to Browse:", extracted_folders, key="browse_folder_tab5")

        # FIX: We must use target_browse_folder, not target_folder_blur!
        full_browse_path = os.path.join("uploaded_videos", target_browse_folder)

        # 3. Get all images in the folder
        valid_exts = ('.png', '.jpg', '.jpeg')
        image_files = sorted([f for f in os.listdir(full_browse_path) if f.lower().endswith(valid_exts)])

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

                # Create a 4-column scrolling gallery
                gallery_cols = st.columns(4)

                for idx, img_file in enumerate(image_files):
                    g_col = gallery_cols[idx % 4]
                    with g_col:
                        img_path = os.path.join(full_browse_path, img_file)
                        st.image(img_path, use_container_width=True)

                        # Use a primary button if it is currently selected, else secondary
                        is_selected = st.session_state['selected_gallery_image'] == img_file
                        btn_type = "primary" if is_selected else "secondary"
                        btn_label = "Selected" if is_selected else "Select"

                        if st.button(btn_label, key=f"select_{img_file}", type=btn_type, use_container_width=True):
                            st.session_state['selected_gallery_image'] = img_file
                            st.rerun()

            with col_meta:
                st.write("**Selected Image & YAML Metadata**")

                selected_image = st.session_state['selected_gallery_image']
                image_path = os.path.join(full_browse_path, selected_image)

                # Show the actively selected image at the top of the metadata column
                st.image(image_path, use_container_width=True)

                # Replace image extension with .yaml
                yaml_filename = os.path.splitext(selected_image)[0] + ".yaml"
                yaml_path = os.path.join(full_browse_path, yaml_filename)

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