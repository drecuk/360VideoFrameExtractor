#   ##########################################################
#   By Eugene Ch'ng
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   EXTRACT360FRAMES INSTALLER FOR WINDOWS
#   ----------------------------------------------------------
#   Installs external tools when requested, creates a Python
#   virtual environment and installs the Streamlit requirements
#   ##########################################################

param(
    [switch]$AutoInstallDependencies
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
}

function Add-UserPathEntry {
    param(
        [string]$PathEntry,
        [switch]$Prepend
    )

    if ([string]::IsNullOrWhiteSpace($PathEntry)) {
        return
    }

    if (-not (Test-Path $PathEntry)) {
        return
    }

    $CleanEntry = $PathEntry.TrimEnd("\")
    $CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $UserParts = @()

    if (-not [string]::IsNullOrWhiteSpace($CurrentUserPath)) {
        $UserParts = $CurrentUserPath -split ";" | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        }
    }

    $UserPartsWithoutEntry = @($UserParts | Where-Object {
        -not $_.TrimEnd("\").Equals($CleanEntry, [StringComparison]::OrdinalIgnoreCase)
    })

    if ($Prepend) {
        $NewUserPath = (@($CleanEntry) + $UserPartsWithoutEntry) -join ";"
    }
    else {
        $NewUserPath = ($UserPartsWithoutEntry + $CleanEntry) -join ";"
    }

    if ($NewUserPath -ne $CurrentUserPath) {
        [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
        Write-Host "Updated user PATH: $CleanEntry"
    }

    $CurrentSessionParts = @($env:Path -split ";" | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    })
    $SessionPartsWithoutEntry = @($CurrentSessionParts | Where-Object {
        -not $_.TrimEnd("\").Equals($CleanEntry, [StringComparison]::OrdinalIgnoreCase)
    })

    if ($Prepend) {
        $env:Path = (@($CleanEntry) + $SessionPartsWithoutEntry) -join ";"
    }
    else {
        $env:Path = ($SessionPartsWithoutEntry + $CleanEntry) -join ";"
    }
}

function Install-WingetPackage {
    param(
        [string]$PackageId,
        [string]$FriendlyName,
        [switch]$Force
    )

    if (-not (Test-CommandAvailable "winget")) {
        throw "Windows Package Manager was not found. Install App Installer from the Microsoft Store, then run install_windows.bat again."
    }

    Write-Host "`nInstalling $FriendlyName..."
    $WingetArguments = @(
        "install", "--id", $PackageId, "--exact", "--source", "winget",
        "--accept-source-agreements", "--accept-package-agreements", "--silent"
    )
    if ($Force) {
        $WingetArguments += "--force"
    }
    & winget @WingetArguments

    if ($LASTEXITCODE -ne 0) {
        throw "$FriendlyName could not be installed automatically. Try installing it manually, then run install_windows.bat again."
    }

    Refresh-Path
}

function Add-KnownPythonPaths {
    $PythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"

    if (-not (Test-Path $PythonRoot)) {
        return
    }

    $PythonFolders = Get-ChildItem -Path $PythonRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending

    foreach ($Folder in $PythonFolders) {
        $PythonExe = Join-Path $Folder.FullName "python.exe"
        if (Test-Path $PythonExe) {
            Add-UserPathEntry $Folder.FullName
            Add-UserPathEntry (Join-Path $Folder.FullName "Scripts")
            return
        }
    }
}

function Test-FfmpegV360 {
    param([string]$FfmpegPath)

    if ([string]::IsNullOrWhiteSpace($FfmpegPath) -or -not (Test-Path $FfmpegPath)) {
        return $false
    }

    try {
        $FilterOutput = & $FfmpegPath -hide_banner -filters 2>&1 | Out-String
        return ($LASTEXITCODE -eq 0 -and $FilterOutput -match "(?m)(^|\s)v360(\s|$)")
    }
    catch {
        return $false
    }
}

function Find-V360Ffmpeg {
    $CandidatePaths = @()
    $ConfiguredPathFile = Join-Path $ProjectDir ".ffmpeg_path"

    if (Test-Path $ConfiguredPathFile) {
        $ConfiguredPath = (Get-Content $ConfiguredPathFile -Raw).Trim()
        if (-not [string]::IsNullOrWhiteSpace($ConfiguredPath)) {
            $CandidatePaths += $ConfiguredPath
        }
    }

    $PathCommand = Get-Command "ffmpeg" -CommandType Application -ErrorAction SilentlyContinue
    if ($PathCommand) {
        $CandidatePaths += $PathCommand.Source
    }

    $CandidateRoots = @(
        (Join-Path $env:ProgramFiles "ffmpeg"),
        (Join-Path $env:ProgramFiles "Gyan\FFmpeg"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages")
    )

    foreach ($Root in $CandidateRoots) {
        if (-not (Test-Path $Root)) {
            continue
        }

        $CandidatePaths += Get-ChildItem -Path $Root -Recurse -Filter "ffmpeg.exe" -File -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    }

    $Seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($FfmpegPath in $CandidatePaths) {
        if (-not ($Seen.Add($FfmpegPath))) {
            continue
        }

        if (-not (Test-FfmpegV360 $FfmpegPath)) {
            continue
        }

        $FfmpegExe = Get-Item $FfmpegPath
        $FfprobePath = Join-Path $FfmpegExe.DirectoryName "ffprobe.exe"
        if (-not (Test-Path $FfprobePath)) {
            continue
        }

        return [pscustomobject]@{
            Ffmpeg = $FfmpegExe.FullName
            Ffprobe = $FfprobePath
            Directory = $FfmpegExe.DirectoryName
        }
    }

    return $null
}

function Get-PythonInvocation {
    $Candidates = @(
        @{ Command = "py"; Arguments = @("-3") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() }
    )

    foreach ($Candidate in $Candidates) {
        if (-not (Test-CommandAvailable $Candidate.Command)) {
            continue
        }

        & $Candidate.Command @($Candidate.Arguments) -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Command = $Candidate.Command
                Arguments = @($Candidate.Arguments)
            }
        }
    }

    return $null
}

function Ensure-Python {
    $Python = Get-PythonInvocation
    if ($Python) {
        Write-Host "Python 3.10 or newer found."
        return $Python
    }

    if (-not $AutoInstallDependencies) {
        throw "Python 3.10 or newer was not found."
    }

    Install-WingetPackage -PackageId "Python.Python.3.12" -FriendlyName "Python 3.12"
    Add-KnownPythonPaths
    Refresh-Path

    $Python = Get-PythonInvocation
    if (-not $Python) {
        throw "Python was installed, but Windows still cannot find it. Close this window, reopen it and run install_windows.bat again."
    }

    return $Python
}

function Ensure-Ffmpeg {
    $Selection = Find-V360Ffmpeg
    if ($Selection) {
        Add-UserPathEntry $Selection.Directory -Prepend
        [System.IO.File]::WriteAllText(
            (Join-Path $ProjectDir ".ffmpeg_path"),
            $Selection.Ffmpeg,
            [System.Text.UTF8Encoding]::new($false)
        )
        Write-Host "Compatible FFmpeg found: $($Selection.Ffmpeg)"
        return
    }

    if (-not $AutoInstallDependencies) {
        Write-Warning "A complete FFmpeg build with FFprobe and the v360 filter was not found."
        return
    }

    if (Test-CommandAvailable "ffmpeg") {
        $ExistingFfmpeg = (Get-Command "ffmpeg" -CommandType Application).Source
        Write-Warning "The existing FFmpeg is incompatible because it lacks v360 or its matching FFprobe: $ExistingFfmpeg"
    }

    Install-WingetPackage -PackageId "Gyan.FFmpeg" -FriendlyName "the full FFmpeg build" -Force
    Refresh-Path

    $Selection = Find-V360Ffmpeg
    if (-not $Selection) {
        throw "FFmpeg was installed, but no build with FFprobe and the v360 filter could be verified. Close this window and run install_windows.bat again."
    }

    Add-UserPathEntry $Selection.Directory -Prepend
    [System.IO.File]::WriteAllText(
        (Join-Path $ProjectDir ".ffmpeg_path"),
        $Selection.Ffmpeg,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Compatible FFmpeg selected: $($Selection.Ffmpeg)"
}

function Install-ColmapFromGithub {
    Write-Host "`nInstalling COLMAP from the official GitHub release..."
    Write-Host "COLMAP will be installed under: $env:LOCALAPPDATA\Programs\COLMAP"

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $Release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/colmap/colmap/releases/latest" `
        -Headers @{ "User-Agent" = "360VideoFrameExtractorInstaller" }

    $Asset = $Release.assets |
        Where-Object { $_.name -match "windows-nocuda\.zip$" } |
        Select-Object -First 1

    if (-not $Asset) {
        $Asset = $Release.assets |
            Where-Object { $_.name -match "windows.*\.zip$" } |
            Select-Object -First 1
    }

    if (-not $Asset) {
        throw "No Windows COLMAP ZIP file was found in the latest COLMAP release."
    }

    $InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\COLMAP"
    $TargetDir = Join-Path $InstallRoot $Release.tag_name
    $ZipPath = Join-Path $env:TEMP $Asset.name

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    if (-not (Get-ChildItem -Path $TargetDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { @("colmap.exe", "colmap.bat") -contains $_.Name.ToLowerInvariant() } |
        Select-Object -First 1)) {

        Write-Host "Downloading $($Asset.name)..."
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ZipPath

        Write-Host "Extracting COLMAP..."
        Expand-Archive -Path $ZipPath -DestinationPath $TargetDir -Force
        Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
    }

    $ColmapCommand = Get-ChildItem -Path $TargetDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { @("colmap.exe", "colmap.bat") -contains $_.Name.ToLowerInvariant() } |
        Select-Object -First 1

    if (-not $ColmapCommand) {
        throw "COLMAP was downloaded, but colmap.exe could not be found."
    }

    Add-UserPathEntry $ColmapCommand.DirectoryName
    Refresh-Path
}

function Ensure-Colmap {
    Write-Host "`nChecking COLMAP..."

    if (Test-CommandAvailable "colmap") {
        Write-Host "COLMAP found."
        return
    }

    if (-not $AutoInstallDependencies) {
        Write-Warning "COLMAP was not found."
        return
    }

    try {
        Install-ColmapFromGithub
    }
    catch {
        Write-Warning "COLMAP could not be installed automatically: $($_.Exception.Message)"
        Write-Warning "The web app can still run, but the dependency checker will report COLMAP as missing."
        return
    }

    if (-not (Test-CommandAvailable "colmap")) {
        Write-Warning "COLMAP was installed, but Windows still cannot find it. Close this window, reopen it and run install_windows.bat again."
    }
    else {
        Write-Host "COLMAP installation verified."
    }
}

Write-Host "`nChecking Python..."
$Python = Ensure-Python
$PythonCommand = $Python.Command
$PythonArguments = @($Python.Arguments)

if ($AutoInstallDependencies) {
    Write-Host "`nAutomatic Windows dependency installation is enabled."
    Refresh-Path
    Write-Host "`nChecking FFmpeg and FFprobe..."
    Ensure-Ffmpeg
    Ensure-Colmap
}

$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment..."
    & $PythonCommand @PythonArguments -m venv .venv
}

Write-Host "Installing Streamlit, PyYAML and Python requirements..."
& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r requirements.txt

New-Item -ItemType Directory -Force -Path "uploaded_videos" | Out-Null

Write-Host "`nChecking external applications..."
& $VenvPython validate_install.py --allow-missing-system

Write-Host "`nInstallation complete."
Write-Host "Start the application with: .\run_windows.bat"

if (-not (Find-V360Ffmpeg)) {
    Write-Warning "A complete FFmpeg build with FFprobe and v360 is required for frame extraction. Rerun install_windows.bat and allow dependency installation."
}

if (-not (Get-Command colmap -ErrorAction SilentlyContinue)) {
    Write-Warning "COLMAP was not found. If it was just installed, close this window and run install_windows.bat again."
}
