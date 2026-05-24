#!/bin/bash
# =============================================================================
# build_mac_app.sh
# =============================================================================
# Builds a self-contained macOS .app bundle for NEISS Research Studio.
#
# What this script does:
#   1. Downloads a standalone Python 3.11 for macOS (no system Python needed)
#   2. Installs all required packages into it
#   3. Packages your app files + Python into a .app bundle
#   4. Produces:  dist/NEISS Research Studio.app
#
# Requirements to run this script (on YOUR Mac, the developer machine):
#   - macOS 12 or later
#   - Internet connection (to download Python and packages once)
#   - curl (built into macOS)
#
# How to run:
#   cd ~/Desktop/Research\ Apps/Development/neiss_streamlit_duckdb
#   chmod +x build_mac_app.sh
#   ./build_mac_app.sh
#
# The finished app will be at:
#   dist/NEISS Research Studio.app
#
# To distribute to classmates:
#   Zip that .app and share it. They drag it to Applications and double-click.
#
# =============================================================================

set -e  # Exit immediately on any error

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these if needed
# ─────────────────────────────────────────────────────────────────────────────
APP_NAME="NEISS Research Studio"
APP_VERSION="2.0"

# python-build-standalone release: a self-contained Python 3.11 binary for macOS
# Check https://github.com/astral-sh/python-build-standalone/releases for latest
PYTHON_VERSION="3.11.9"
PYTHON_RELEASE="20240726"  # Release date tag from python-build-standalone

# Detect architecture (Intel vs Apple Silicon)
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    PYTHON_ARCH="aarch64"
    echo "Detected Apple Silicon (M1/M2/M3)"
else
    PYTHON_ARCH="x86_64"
    echo "Detected Intel Mac"
fi

PYTHON_TARBALL="cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${PYTHON_ARCH}-apple-darwin-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE}/${PYTHON_TARBALL}"

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build_tmp"
DIST_DIR="${SCRIPT_DIR}/dist"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
MACOS_DIR="${APP_BUNDLE}/Contents/MacOS"
RESOURCES_DIR="${APP_BUNDLE}/Contents/Resources"
PYTHON_DIR="${RESOURCES_DIR}/python"   # bundled Python lives here
APP_FILES_DIR="${RESOURCES_DIR}/app"   # your .py files live here

# ─────────────────────────────────────────────────────────────────────────────
# STEP 0: Clean previous build
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo " Step 0: Cleaning previous build"
echo "════════════════════════════════════════"
rm -rf "$BUILD_DIR" "$APP_BUNDLE"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Download standalone Python (skip if already downloaded)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo " Step 1: Getting standalone Python ${PYTHON_VERSION}"
echo "════════════════════════════════════════"

TARBALL_PATH="${BUILD_DIR}/${PYTHON_TARBALL}"

if [ -f "$TARBALL_PATH" ]; then
    echo "Python tarball already downloaded, skipping..."
else
    echo "Downloading from:"
    echo "  ${PYTHON_URL}"
    echo "(This is ~30 MB — takes about 30–60 seconds)"
    echo ""
    curl -L --progress-bar -o "$TARBALL_PATH" "$PYTHON_URL"
fi

echo "Extracting Python..."
tar -xzf "$TARBALL_PATH" -C "$BUILD_DIR"

# python-build-standalone extracts to a 'python' directory
EXTRACTED_PYTHON="${BUILD_DIR}/python"
BUNDLED_PYTHON="${EXTRACTED_PYTHON}/bin/python3"

if [ ! -f "$BUNDLED_PYTHON" ]; then
    echo "ERROR: Could not find Python binary after extraction."
    echo "Expected: ${BUNDLED_PYTHON}"
    echo "Contents of ${BUILD_DIR}:"
    ls "$BUILD_DIR"
    exit 1
fi

echo "Python ${PYTHON_VERSION} ready: ${BUNDLED_PYTHON}"
"$BUNDLED_PYTHON" --version

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Install all required packages into the bundled Python
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo " Step 2: Installing Python packages"
echo "════════════════════════════════════════"
echo "(This installs ~300 MB of packages — takes 3–8 minutes)"
echo ""

"$BUNDLED_PYTHON" -m pip install --upgrade pip --quiet

# Install from the project's requirements.txt
"$BUNDLED_PYTHON" -m pip install \
    streamlit \
    duckdb \
    pandas \
    numpy \
    matplotlib \
    scipy \
    python-docx \
    openpyxl \
    pyarrow \
    --quiet

echo ""
echo "Verifying installations..."
"$BUNDLED_PYTHON" -c "import streamlit; print('  streamlit:', streamlit.__version__)"
"$BUNDLED_PYTHON" -c "import duckdb;    print('  duckdb:   ', duckdb.__version__)"
"$BUNDLED_PYTHON" -c "import pandas;    print('  pandas:   ', pandas.__version__)"
"$BUNDLED_PYTHON" -c "import matplotlib;print('  matplotlib:', matplotlib.__version__)"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Create the .app bundle structure
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo " Step 3: Creating .app bundle"
echo "════════════════════════════════════════"

mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"
mkdir -p "$APP_FILES_DIR"
mkdir -p "${APP_BUNDLE}/Contents/Resources/data"    # empty data folder for CSVs
mkdir -p "${APP_BUNDLE}/Contents/Resources/output"  # DuckDB output folder

# Copy the bundled Python into Resources/python/
echo "Copying bundled Python..."
cp -R "${EXTRACTED_PYTHON}" "${PYTHON_DIR}"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Copy app source files
# ─────────────────────────────────────────────────────────────────────────────
echo "Copying app source files..."

APP_PY_FILES=(
    "app.py"
    "analysis.py"
    "database.py"
    "code_mappings.py"
    "stats.py"
    "reports.py"
    "excel_export.py"
    "single_group.py"
    "trend_analysis.py"
    "proportions.py"
    "manuscript_text.py"
    "figures.py"
)

for f in "${APP_PY_FILES[@]}"; do
    if [ -f "${SCRIPT_DIR}/${f}" ]; then
        cp "${SCRIPT_DIR}/${f}" "${APP_FILES_DIR}/${f}"
        echo "  Copied: ${f}"
    else
        echo "  WARNING: ${f} not found in project root — skipping"
    fi
done

# Copy requirements.txt for reference
[ -f "${SCRIPT_DIR}/requirements.txt" ] && \
    cp "${SCRIPT_DIR}/requirements.txt" "${APP_FILES_DIR}/requirements.txt"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Write the Streamlit config to suppress the welcome dialog
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "${APP_FILES_DIR}/.streamlit"
cat > "${APP_FILES_DIR}/.streamlit/config.toml" << 'STREAMLIT_CONFIG'
[browser]
gatherUsageStats = false

[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = false

[client]
showSidebarNavigation = false
STREAMLIT_CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Write the Python launcher script
# ─────────────────────────────────────────────────────────────────────────────
echo "Writing launcher scripts..."

# This is the Python script that starts Streamlit and opens the browser.
# It runs inside the bundled Python environment.
cat > "${APP_FILES_DIR}/launch_app.py" << 'LAUNCH_PY'
"""
launch_app.py
-------------
Launches Streamlit and opens the browser automatically.
This script is run by the macOS .app shell launcher using the bundled Python.
"""

import os
import sys
import time
import signal
import socket
import subprocess
import threading
import webbrowser
from pathlib import Path

# ── Resolve paths ────────────────────────────────────────────────────────────
# When running inside the .app bundle, __file__ is inside Resources/app/.
# The data/ and output/ directories are siblings of this app/ directory.
THIS_DIR   = Path(__file__).resolve().parent          # Resources/app/
RESOURCES  = THIS_DIR.parent                          # Resources/
APP_PY     = THIS_DIR / "app.py"
DATA_DIR   = RESOURCES / "data"
OUTPUT_DIR = RESOURCES / "output"
STREAMLIT_CONFIG_DIR = THIS_DIR / ".streamlit"

# Create runtime directories if they don't exist yet
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Change working directory so relative paths in app.py resolve correctly
os.chdir(THIS_DIR)

# ── Override database paths to point at Resources/data and Resources/output ──
# This is needed because database.py uses Path("data") and Path("output/...")
# which resolve relative to cwd. We've set cwd to THIS_DIR (Resources/app/),
# so we create symlinks or override via environment variable.
# Simplest: set an env var that database.py can read (see database.py patch note)
os.environ["NEISS_DATA_DIR"]   = str(DATA_DIR)
os.environ["NEISS_OUTPUT_DIR"] = str(OUTPUT_DIR)

# ── Find bundled Python and Streamlit ────────────────────────────────────────
PYTHON_BIN = Path(sys.executable)   # the bundled python3 running this script
STREAMLIT_BIN = PYTHON_BIN.parent / "streamlit"

if not STREAMLIT_BIN.exists():
    print(f"ERROR: streamlit not found at {STREAMLIT_BIN}")
    print("The app bundle may be corrupted. Please re-install.")
    sys.exit(1)

PORT = 8501
URL  = f"http://localhost:{PORT}"


def port_is_in_use(port):
    """Check whether a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def wait_then_open_browser(url, max_wait=30):
    """Wait until Streamlit is listening, then open the browser."""
    for _ in range(max_wait * 2):   # check every 0.5 s
        if port_is_in_use(PORT):
            time.sleep(0.5)  # brief extra delay for Streamlit to finish booting
            webbrowser.open(url)
            return
        time.sleep(0.5)
    print(f"WARNING: Streamlit did not start within {max_wait} seconds.")
    print(f"Try opening {url} manually in your browser.")


def show_startup_message():
    """Print a user-friendly startup message."""
    print("")
    print("══════════════════════════════════════════")
    print("  NEISS Research Studio")
    print("══════════════════════════════════════════")
    print("")
    print(f"  Starting app at {URL}")
    print(f"  App files:  {THIS_DIR}")
    print(f"  Data files: {DATA_DIR}")
    print("")
    print("  Place your NEISS CSV files in the Data folder,")
    print("  then click 'Build / Refresh Database' in the sidebar.")
    print("")
    print("  Press Ctrl-C or close this window to stop.")
    print("")


if __name__ == "__main__":
    show_startup_message()

    # Check if another instance is already running on this port
    if port_is_in_use(PORT):
        print(f"Port {PORT} already in use — opening existing session...")
        webbrowser.open(URL)
        sys.exit(0)

    # Start the browser opener in a background thread
    browser_thread = threading.Thread(
        target=wait_then_open_browser,
        args=(URL,),
        daemon=True,
    )
    browser_thread.start()

    # Launch Streamlit (this blocks until Streamlit exits)
    cmd = [
        str(PYTHON_BIN), "-m", "streamlit", "run",
        str(APP_PY),
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.enableCORS", "false",
        "--global.developmentMode", "false",
    ]

    try:
        proc = subprocess.run(cmd, cwd=str(THIS_DIR))
    except KeyboardInterrupt:
        print("\nApp stopped by user.")
LAUNCH_PY

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7: Write the macOS shell launcher (Contents/MacOS/NEISS Research Studio)
# This is the Unix executable that macOS runs when you double-click the .app.
# ─────────────────────────────────────────────────────────────────────────────
LAUNCHER_SHELL="${MACOS_DIR}/${APP_NAME}"

cat > "$LAUNCHER_SHELL" << 'SHELL_LAUNCHER'
#!/bin/bash
# macOS .app launcher for NEISS Research Studio
#
# macOS runs this script when you double-click the .app bundle.
# It resolves the bundle's own paths and starts the Python launcher.

# Find the bundle root regardless of where the .app was moved
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"          # Contents/MacOS/
BUNDLE_ROOT="$(dirname "$SCRIPT_PATH")"               # Contents/
RESOURCES="${BUNDLE_ROOT}/Resources"
PYTHON_BIN="${RESOURCES}/python/bin/python3"
LAUNCH_SCRIPT="${RESOURCES}/app/launch_app.py"

# Sanity checks with user-friendly errors via macOS dialog
if [ ! -f "$PYTHON_BIN" ]; then
    osascript -e 'display dialog "NEISS Research Studio could not start.\n\nBundled Python not found.\n\nPlease re-download the app." buttons {"OK"} default button "OK" with icon stop with title "NEISS Research Studio"'
    exit 1
fi

if [ ! -f "$LAUNCH_SCRIPT" ]; then
    osascript -e 'display dialog "NEISS Research Studio could not start.\n\nLauncher script not found.\n\nPlease re-download the app." buttons {"OK"} default button "OK" with icon stop with title "NEISS Research Studio"'
    exit 1
fi

# Run the Python launcher
# We open a new Terminal window so the user can see status/error messages
# and so they can close the app by closing the window.
osascript << APPLESCRIPT
tell application "Terminal"
    activate
    do script "\"${PYTHON_BIN}\" \"${LAUNCH_SCRIPT}\""
end tell
APPLESCRIPT
SHELL_LAUNCHER

chmod +x "$LAUNCHER_SHELL"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8: Write Info.plist
# ─────────────────────────────────────────────────────────────────────────────
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>edu.research.neiss-studio</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Research use only. NEISS data © CPSC.</string>
</dict>
</plist>
PLIST_EOF

# ─────────────────────────────────────────────────────────────────────────────
# STEP 9: Write a "Data" alias / README inside the bundle so users can find it
# ─────────────────────────────────────────────────────────────────────────────
cat > "${APP_BUNDLE}/Contents/Resources/data/PUT_NEISS_CSV_FILES_HERE.txt" << 'DATA_README'
Place your NEISS CSV files in this folder.
File names should include the year, for example:
    neiss2019.csv
    NEISS2022.csv

After adding files, click "Build / Refresh Database" in the app sidebar.
DATA_README

# ─────────────────────────────────────────────────────────────────────────────
# STEP 10: Remove quarantine attribute (prevents macOS "can't be opened" error)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo " Step 10: Removing quarantine attribute"
echo "════════════════════════════════════════"
xattr -cr "$APP_BUNDLE" 2>/dev/null || true
echo "Done."

# ─────────────────────────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────────────────────────
APP_SIZE=$(du -sh "$APP_BUNDLE" 2>/dev/null | cut -f1)

echo ""
echo "════════════════════════════════════════"
echo " BUILD COMPLETE"
echo "════════════════════════════════════════"
echo ""
echo "  App: ${APP_BUNDLE}"
echo "  Size: ${APP_SIZE}"
echo ""
echo "  To test it now:"
echo "    open \"${APP_BUNDLE}\""
echo ""
echo "  To distribute:"
echo "    Zip the .app and share it."
echo "    Your classmates drag it to Applications and double-click."
echo ""
echo "  ⚠️  IMPORTANT: The data/ folder is inside the bundle."
echo "  Your classmates will need to add NEISS CSV files to:"
echo "    ${APP_BUNDLE}/Contents/Resources/data/"
echo ""
echo "  See DATA_FOLDER_SETUP.md in the dist/ folder for instructions."
echo ""

# Write a helper for end users explaining the data folder
cat > "${DIST_DIR}/DATA_FOLDER_SETUP.md" << 'END_DATA_README'
# Adding NEISS Data Files to the App

The NEISS Research Studio needs your NEISS CSV data files.

## Where to put the files

1. Right-click (or Control-click) the app in Finder
2. Choose **Show Package Contents**
3. Navigate to: `Contents → Resources → data`
4. Copy your NEISS CSV files there (e.g. `neiss2019.csv`, `NEISS2022.csv`)

## After adding files

Open the app and click **Build / Refresh Database** in the left sidebar.

## File naming

File names should include a 4-digit year:
- ✅ `neiss2019.csv`
- ✅ `NEISS_2022.csv`
- ❌ `data.csv` (no year — will be skipped)

## Need to update the app files?

The `.py` source files are at:
`Contents → Resources → app → *.py`

You can update them without rebuilding the full bundle.
END_DATA_README
