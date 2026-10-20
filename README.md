# 360VideoFrameExtractor

> **"Making Heritage Technologies Accessible"**

## About

360VideoFrameExtractor is a Streamlit web application for extracting perspective frames from equirectangular 360-degree videos and processing the resulting photographs. It has been tested with Insta360 series devices.

The application provides interactive camera-layout visualisation, single and batch extraction, sky-content filtering, and partial-blur detection. FFmpeg and FFprobe are used for video processing, while COLMAP is checked as part of the wider 3D reconstruction workflow.

The frame extractor is used for work presented in the following accepted paper:

> Ch'ng, E. (2026). Analysis of Multi-Modal Semantic Masking, Inpainting for 3D Reconstruction and Visualisation of Heritage Sites. In *Proceedings of the 23rd Eurographics Workshop on Graphics and Cultural Heritage (GCH 2026)*, Universitat Politècnica de Catalunya, Barcelona, Catalonia, 2–5 November 2026. Accepted paper.

## Author

**Authored by Professor Eugene Ch'ng**

| Profile | Link |
| --- | --- |
| LinkedIn | [linkedin.com/in/eugenecc](https://www.linkedin.com/in/eugenecc) |
| Google Scholar | [Eugene Ch'ng's publications](https://scholar.google.com/citations?user=AcYUcdEAAAAJ&hl=e) |
| GitHub | [github.com/drecuk](https://github.com/drecuk) |

## Features

- Process MP4, MOV, AVI, and MKV videos directly from a chosen folder.
- Select folders on internal storage or mounted external hard drives with the operating system's native folder picker, without uploading or copying the videos first.
- Optionally upload videos through the browser into the active workspace.
- Ignore hidden/system sidecars such as `._*.mp4` and admit only video files containing an FFprobe-readable video stream.
- Preview horizontal, 45-degree, and zenith camera views in 3D.
- Extract perspective PNG frames with the FFmpeg `v360` filter.
- Generate YAML sidecar metadata files for extracted perspective frames.
- Browse extracted images beside their associated YAML metadata.
- Process one video or all uploaded videos as a batch.
- Detect blue-sky images using OpenCV HSV masks.
- Detect partial blur using Variance of Laplacian grid analysis.
- Review detected images before moving them into filtered folders.

## Tutorial: Insta360 Studio Export Settings

### Preparing Footage for 3D Gaussian Splatting, NeRF, and Photogrammetry

Use the following Insta360 Studio export settings before processing footage with this application or a structure-from-motion workflow.

### Insta360 X5 and X6 Recommended Export Settings for Photogrammetry

Use this side-by-side comparison when exporting Insta360 X5 or X6 footage:

| Setting | Insta360 X5 | Insta360 X6 |
| --- | --- | --- |
| Resolution | Original maximum, preferably **8K** | **8K (7680 × 3840)** |
| Frame Rate | Match the original recording | **30 fps**, matching the original recording |
| Bitrate | Maximum available; **100 Mbps or higher** for H.264/H.265 | **200 Mbps** to minimise re-encoding artefacts |
| Codec | **ProRes 422/422 LT** preferred; otherwise high-bitrate H.264/H.265 | **H.265 (HEVC)** |
| Colour Space | **Standard SDR** | **Rec.709, 10-bit** when the source was recorded in 10-bit |
| Bottom Stitching Optimisation | Test if available; reject settings that introduce geometric distortion | **ON**, provided it introduces no geometric distortion |
| APMP | **OFF** | **OFF** |
| Export Format | **360° equirectangular video** | **MP4, 360° equirectangular** |
| FFmpeg Frame Extraction | **PNG** using a configurable sampling interval | **PNG at 3–5 fps** |
| Stabilisation | **OFF:** FlowState Stabilisation and Horizon Lock | Test **OFF** first for geometric consistency |

> **Priority:** Maximum resolution, consistent geometry, and minimal compression artefacts.

For X6 footage, select **Frames per second** in the application's **Extraction** tab and choose **3–5 fps**. For X5 footage or sparse sampling workflows, select **Seconds between frames**.

### Shared Export Guidance

### Media Type

**Select:** `Video`

This applies the stitching, horizon calibration, and lens-distortion profile required to transform raw dual-fisheye footage into a standard flat equirectangular projection. FFmpeg and structure-from-motion software can then interpret the exported video correctly.

Avoid `Video Original`. Gaussian Splatting and photogrammetry engines cannot align the raw, unstitched circles produced by the camera's two lenses.

### Stitch Type

**Select:** `Equirectangular (Standard 360)`

This produces the standard 2:1 panoramic projection expected by the extraction pipeline.

### Resolution

Follow the model-specific recommendation in the table above. Select `Custom`, then retain the original maximum resolution; use `8K (7680 × 3840)` for the recommended X6 workflow.

Higher source resolution preserves more visual detail for feature matching, camera alignment, NeRF training, and Gaussian Splatting reconstruction.

### Encoding and Format

For X5 footage, prefer `ProRes 422` or `ProRes 422 LT` when available. For the recommended X6 workflow, use `H.265 (HEVC)` at `200 Mbps`.

ProRes provides high-quality intermediate footage with minimal visible compression. A separate bitrate setting is generally unnecessary when exporting X5 footage to ProRes.

When ProRes is unavailable for X5 footage and MP4 with H.264 or H.265 must be used, select the maximum available bitrate, such as `100 Mbps` or higher.

### Colour

For X5 footage, select `Standard SDR`. For X6 footage recorded in 10-bit, select `Rec.709, 10-bit`.

Avoid `Vivid`, `Color Plus`, or other enhanced colour modes. These modes can alter lighting, contrast, and shadow information required for consistent matching across camera views.

### Stabilisation

For X5 footage, turn off:

- FlowState Stabilisation
- Horizon Lock

For X6 footage, test with stabilisation off first. Structure-from-motion and reconstruction pipelines need consistent camera motion and image geometry. Artificial horizon correction or frame-by-frame stabilisation can introduce warping, jitter, and geometric inconsistencies that make camera alignment less reliable.

### Dolby Vision

**Turn off:** `Dolby Vision`

Dolby Vision uses dynamic metadata to adjust brightness, tone mapping, and contrast throughout the video. Gaussian Splatting and photogrammetry rely on consistent pixel lighting across different viewing angles. Dynamic tone mapping can interfere with feature matching and may contribute to floaters, blur, or reconstruction artifacts.

Use standard SDR or another consistent, non-dynamic colour workflow instead.

### APMP

**Turn off:** `APMP (Apple Photography Metadata Profile)`

APMP packages footage for immersive playback on devices such as Apple Vision Pro. This changes how the video data is stored and can break standard 360-degree compatibility or prevent FFmpeg from extracting geometric perspective frames cleanly.

### Summary Checklist

- [x] **Export Type:** 360 Video
- [x] **Media Type:** Video
- [x] **Stitch Type:** Equirectangular (Standard 360)
- [x] **Resolution:** Follow the X5/X6 values in the comparison table
- [x] **Frame rate:** Match the original recording
- [x] **Codec and bitrate:** Use the model-specific recommendation
- [x] **Colour:** Standard SDR for X5; Rec.709 10-bit for 10-bit X6 footage
- [x] **Disabled:** Dolby Vision
- [x] **Disabled:** APMP
- [x] **Geometry check:** Reject stitching or stabilisation settings that introduce distortion

> **Pipeline note:** Nerfstudio, NSVF, Luma AI, Postshot, and similar pipelines may include their own frame-extraction and lens-calibration tools. Check the selected pipeline before performing a separate manual FFmpeg extraction.

## Requirements

- Python 3.10 or newer.
- PyYAML for reading and writing frame sidecar metadata.
- FFmpeg and FFprobe with the `v360` filter.
- COLMAP is checked by the current interface for the wider reconstruction workflow, although this version does not invoke COLMAP directly.
- Sufficient local storage for uploaded videos and extracted PNG frames.

## Windows Beginner Installation

These steps are for Windows users who are new to Python, GitHub, or command-line tools.

For Windows beginners, `install_windows.bat` is the main installer. It automatically installs Python, FFmpeg, FFprobe, COLMAP, Streamlit, PyYAML, and the other Python packages used by this application. It also sets the user `PATH` for the installed tools where needed.

### Step 1. Check Windows Package Manager

The beginner installer uses **Windows Package Manager**, also called `winget`, to install Python and FFmpeg automatically. It downloads COLMAP separately from the official COLMAP GitHub release because COLMAP is not always available as a standard `winget` package.

Most Windows 10 and Windows 11 computers already include it. If the installer says `winget` is missing, install **App Installer** from the Microsoft Store, then run `install_windows.bat` again.

### Step 2. Get the Project

The easiest method is to download the project as a ZIP file from the [GitHub repository](https://github.com/drecuk/360VideoFrameExtractor):

1. Go to the GitHub repository.
2. Click **Code**.
3. Click **Download ZIP**.
4. Extract the ZIP file.
5. Open the extracted folder.

If you already use Git, you can clone it instead:

```powershell
git clone https://github.com/drecuk/360VideoFrameExtractor.git
cd 360VideoFrameExtractor
```

### Step 3. Install Everything Automatically

Inside the project folder, double-click:

```text
install_windows.bat
```

If Python is already installed, `install_windows.bat` first creates the local `.venv` environment. It then runs `install.ps1`, which checks Python, installs FFmpeg, downloads COLMAP from the official COLMAP GitHub release, and installs the Python requirements.

The installer will try to install:

- Python 3.12
- FFmpeg and FFprobe
- COLMAP from the official COLMAP GitHub release
- Streamlit, PyYAML, and the other Python packages listed in `requirements.txt`

It also adds the installed tools to your **user PATH**, so Windows can find `python`, `ffmpeg`, `ffprobe`, and `colmap` from Terminal.

If Windows asks for permission to install software, approve the request.

### Step 4. Start the Web App

After installation, double-click:

```text
run_windows.bat
```

The application should open in your browser at:

```text
http://localhost:8501
```

Keep the black terminal window open while using the app. Closing it stops the web app.

### Beginner Troubleshooting

If `winget` is missing, install **App Installer** from the Microsoft Store, then run `install_windows.bat` again.

If Windows still cannot find Python, FFmpeg, or COLMAP after installation, close the black terminal window and double-click `install_windows.bat` again. Newly installed PATH settings sometimes need a fresh terminal session.

If Python installation fails through `winget`, install Python 3.12 manually from [python.org](https://www.python.org/downloads/windows/) and tick `Add python.exe to PATH`, then run `install_windows.bat` again.

If thumbnails do not appear in **Remove Sky Photos**, **Remove Blurry Images**, or **Browse Metadata**, close the app and run:

```powershell
.\install.ps1
.\run.ps1
```

The launcher verifies that Streamlit, OpenCV, and Pillow are installed in the project `.venv`. Use `run_windows.bat` or `.\run.ps1` rather than a global `streamlit run app.py` command. The project pins Streamlit 1.56.0 because its Tornado media server avoids the Windows `/media/` HTTP 500 errors observed with the newer Starlette server. Thumbnail rendering also uses Windows-safe sizing, and any unreadable image displays its filename and the underlying Windows error.

If the app does not open automatically, open a browser and go to [http://localhost:8501](http://localhost:8501).

## macOS Beginner Installation

These steps are for macOS users who are new to Python, GitHub, or Terminal.

For macOS beginners, `install_macos.command` is the main installer. It opens Terminal automatically, installs Homebrew if needed, installs Python, Git, FFmpeg, COLMAP, Streamlit, PyYAML, and the other Python packages used by this application.

### Step 1. Get the Project

Download the project as a ZIP file from the [GitHub repository](https://github.com/drecuk/360VideoFrameExtractor):

1. Go to the GitHub repository.
2. Click **Code**.
3. Click **Download ZIP**.
4. Extract the ZIP file.
5. Move the extracted folder somewhere simple, such as `Documents`.

If you already use Git, you can clone it instead:

```bash
git clone https://github.com/drecuk/360VideoFrameExtractor.git
cd 360VideoFrameExtractor
```

### Step 2. Install Everything Automatically

Inside the project folder, double-click:

```text
install_macos.command
```

The installer will try to install:

- Homebrew, if it is missing
- Python
- Git
- FFmpeg and FFprobe
- COLMAP
- Streamlit, PyYAML, and the other Python packages listed in `requirements.txt`

It also sets the Homebrew `PATH` for Apple Silicon and Intel Macs where needed.

If macOS says the file cannot be opened because it is from an unidentified developer, right-click `install_macos.command`, choose **Open**, then choose **Open** again.

### Step 3. Start the Web App

After installation, double-click:

```text
run_macos.command
```

The application should open in your browser at:

```text
http://localhost:8501
```

Keep the Terminal window open while using the app. Closing it stops the web app.

Always start the application with `run_macos.command`, `./run.sh`, or the explicit project-environment command:

```bash
.venv/bin/python -m streamlit run app.py
```

Do not run `streamlit run app.py` directly from an unrelated Terminal environment. That command can select a global Python installation where project packages such as OpenCV (`cv2`) are not installed.

### Optional Terminal Method

If double-clicking does not work, open **Terminal** from:

```text
Applications > Utilities > Terminal
```

Type `cd ` in Terminal, including the space after `cd`, then drag the project folder into the Terminal window and press **Return**.

Then run:

```bash
chmod +x install_macos.command run_macos.command install.sh run.sh
./install_macos.command
```

### macOS Beginner Troubleshooting

If `brew` is not found after installation, close Terminal, reopen it, and run `install_macos.command` again.

If `python3` is not found, run `install_macos.command` again. The installer uses Homebrew to install Python and set the Homebrew `PATH`.

If FFmpeg is not found, run `install_macos.command` again, or install it manually with:

```bash
brew install ffmpeg
```

If COLMAP cannot be installed automatically, the web app can still run, but the dependency checker will report COLMAP as missing.

If the app reports `ModuleNotFoundError: No module named 'cv2'`, repair and launch the project environment with:

```bash
./install.sh
./run.sh
```

You can verify OpenCV directly with:

```bash
.venv/bin/python -c 'import cv2; print(cv2.__version__)'
```

If the app does not open automatically, open a browser and go to [http://localhost:8501](http://localhost:8501).

## Ubuntu Beginner Installation

These steps are for Ubuntu or Debian-based Linux users who are new to Python, GitHub, or Terminal.

For Ubuntu beginners, `install_ubuntu.sh` is the main installer. It installs Python, Git, FFmpeg, COLMAP, Streamlit, PyYAML, and the other Python packages used by this application.

### Step 1. Get the Project

Download the project as a ZIP file from the [GitHub repository](https://github.com/drecuk/360VideoFrameExtractor):

1. Go to the GitHub repository.
2. Click **Code**.
3. Click **Download ZIP**.
4. Extract the ZIP file.
5. Move the extracted folder somewhere simple, such as `Documents`.

If you already use Git, you can clone it instead:

```bash
git clone https://github.com/drecuk/360VideoFrameExtractor.git
cd 360VideoFrameExtractor
```

### Step 2. Install Everything Automatically

Open **Terminal** from the application menu, or press:

```text
Ctrl + Alt + T
```

Type `cd ` in Terminal, including the space after `cd`, then drag the project folder into the Terminal window and press **Return**.

Then run:

```bash
chmod +x install_ubuntu.sh run_ubuntu.sh install.sh run.sh
./install_ubuntu.sh
```

Ubuntu may ask for your password so it can install system packages with `apt`.

The installer will try to install:

- Python 3
- Python virtual environment support
- Git
- FFmpeg and FFprobe
- COLMAP
- Streamlit, PyYAML, and the other Python packages listed in `requirements.txt`

### Step 3. Start the Web App

Run:

```bash
./run_ubuntu.sh
```

The application should open in your browser at:

```text
http://localhost:8501
```

Keep the Terminal window open while using the app. Closing it stops the web app.

### Ubuntu Beginner Troubleshooting

If `python3-venv` is missing, run `sudo apt install python3-venv`, then run `./install_ubuntu.sh` again.

If FFmpeg is not found, run `sudo apt install ffmpeg`, then close and reopen Terminal.

If COLMAP is not available from your Ubuntu package repository, the web app can still be installed, but the dependency checker will report COLMAP as missing.

If the app does not open automatically, open a browser and go to [http://localhost:8501](http://localhost:8501).

## Quick Installation

Clone the repository:

```bash
git clone https://github.com/drecuk/360VideoFrameExtractor.git
cd 360VideoFrameExtractor
```

### macOS or Linux

```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
.\run.ps1
```

Beginners can use the platform-specific launcher files instead:

- Windows: `install_windows.bat` and `run_windows.bat`
- macOS: `install_macos.command` and `run_macos.command`
- Ubuntu: `install_ubuntu.sh` and `run_ubuntu.sh`

The application normally opens at [http://localhost:8501](http://localhost:8501).

## External Applications

### macOS

The beginner macOS installer normally handles this automatically through `install_macos.command`.

For manual installation, install FFmpeg and COLMAP with:

```bash
brew install ffmpeg colmap
```

### Ubuntu or Debian Linux

The beginner Ubuntu installer normally handles this automatically through `install_ubuntu.sh`.

For manual installation, install FFmpeg and COLMAP with:

```bash
sudo apt-get update
sudo apt-get install ffmpeg colmap
```

### Windows

The beginner Windows installer normally handles this automatically through `install_windows.bat`.

For manual installation, install FFmpeg with:

```powershell
winget install Gyan.FFmpeg
```

Download COLMAP from the [official COLMAP releases page](https://github.com/colmap/colmap/releases) and add its executable folder to the system `PATH`, or let `install_windows.bat` download COLMAP and add it to your user `PATH`.

## Manual Python Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python validate_install.py
.venv/bin/python -m streamlit run app.py
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Validation

Run the installation checker without starting Streamlit:

```bash
.venv/bin/python validate_install.py
```

The validator checks Python modules, required project assets, camera visualisation generation, YAML sidecar metadata generation and reading, cross-platform thumbnail generation, FFmpeg, FFprobe, COLMAP, and the FFmpeg `v360` filter.

## Project Structure

```text
360VideoFrameExtractor/
|-- app.py                    Streamlit application
|-- util_detectblurry.py      Partial-blur detection
|-- util_detectsky.py         Sky-content detection
|-- util_read_yaml.py         YAML sidecar metadata reader
|-- utils_checksys.py         External dependency checks
|-- utils_ffmpeg.py           FFmpeg extraction and YAML metadata pipeline
|-- utils_images.py           Cross-platform thumbnail generation
|-- utils_os.py               Native folder opening
|-- utils_viz.py              Interactive 3D camera layout
|-- utils_workspace.py        Local and external-drive workspace handling
|-- logo/logo.png             Application logo
|-- .streamlit/config.toml    Streamlit upload configuration
|-- requirements.txt          Python dependencies
|-- install_windows.bat       Beginner Windows installer
|-- run_windows.bat           Beginner Windows launcher
|-- install_macos.command     Beginner macOS installer
|-- run_macos.command         Beginner macOS launcher
|-- install_ubuntu.sh         Beginner Ubuntu installer
|-- run_ubuntu.sh             Beginner Ubuntu launcher
|-- install.sh                macOS and Linux installer
|-- install.ps1               Windows installer
|-- run.sh                    macOS and Linux launcher
|-- run.ps1                   Windows launcher
`-- validate_install.py       Installation checker
```

## Runtime Data

The **Upload** tab starts with `uploaded_videos/` as its default workspace. Click **Choose Directory…** to use the native macOS, Windows, or Linux folder picker and select any existing readable and writable directory, including a folder on a mounted external hard drive. Manual path entry remains available as a fallback; examples are `/Volumes/ExternalDrive/Survey` on macOS and `D:\HeritageSurvey` on Windows.

When **Use videos already in this directory** is selected, the app reads supported videos directly from that directory; it does not copy them through the browser. Extracted `cubemap-*` folders are created alongside the source videos, and the sky, blur, and metadata tabs use the same active workspace. The selected path lasts for the current app session and returns to the project folder when the app is restarted.

Before a video appears in Upload or Extraction, the app excludes hidden and operating-system files—including macOS AppleDouble files such as `._VID_20261015_140314_00_131.mp4`—and asks FFprobe to confirm that the file contains a readable video stream. Files that merely have a video extension but cannot be read are listed under **Show ignored files** and are never included in individual or batch extraction. The image-processing tabs apply the same hidden/system-file filtering to extracted photographs.

The default `uploaded_videos/` contents are excluded from Git so large videos and generated images are not accidentally committed to GitHub. Files in a separately selected workspace are outside the repository and are therefore not part of Git either.

The native picker opens on the computer running Streamlit. If the app is opened remotely, use manual entry for a path that exists on the server rather than on the browser computer.

The Streamlit configuration currently permits uploads up to 10 GB. Large extractions can require substantially more storage because each video produces multiple PNG views per sampled frame.

## Troubleshooting

### FFmpeg cannot read the video duration

Confirm both commands are available:

```bash
ffmpeg -version
ffprobe -version
```

### FFmpeg reports that the v360 filter is missing

Install a full FFmpeg build and confirm the filter is present:

```bash
ffmpeg -hide_banner -filters | grep v360
```

### The application cannot find uploaded videos

Run Streamlit from the repository root with `./run.sh`, `.\run.ps1`, or `.venv/bin/python -m streamlit run app.py`.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
