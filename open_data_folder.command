#!/bin/bash
# =============================================================================
# open_data_folder.command
# =============================================================================
# Double-click this script to open the NEISS data folder in Finder.
# Place your NEISS CSV files there, then click "Build / Refresh Database"
# in the app sidebar.
# =============================================================================

# The data folder lives inside the .app bundle
# This script should be placed alongside the .app in the dist/ folder.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="${SCRIPT_DIR}/NEISS Research Studio.app"
DATA_DIR="${APP_BUNDLE}/Contents/Resources/data"

if [ ! -d "$APP_BUNDLE" ]; then
    osascript -e 'display dialog "Could not find NEISS Research Studio.app.\n\nMake sure this script is in the same folder as the app." buttons {"OK"} with title "NEISS Research Studio" with icon stop'
    exit 1
fi

mkdir -p "$DATA_DIR"

echo "Opening data folder..."
echo "Place your NEISS CSV files there, then use the app."
echo ""
echo "Data folder: $DATA_DIR"

open "$DATA_DIR"
