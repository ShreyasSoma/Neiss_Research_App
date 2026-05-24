#!/bin/bash
# =============================================================================
# update_app_files.sh
# =============================================================================
# Quick-update script: copies the latest .py source files into an already-built
# .app bundle WITHOUT doing a full rebuild.
#
# Use this when you've changed app.py, stats.py, reports.py, etc. but don't
# need to change Python packages.
#
# How to run:
#   cd ~/Desktop/Research\ Apps/Development/neiss_streamlit_duckdb
#   chmod +x update_app_files.sh
#   ./update_app_files.sh
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="${SCRIPT_DIR}/dist/NEISS Research Studio.app"
APP_FILES_DIR="${APP_BUNDLE}/Contents/Resources/app"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: App bundle not found at:"
    echo "  ${APP_BUNDLE}"
    echo ""
    echo "Run build_mac_app.sh first to create the bundle."
    exit 1
fi

echo ""
echo "Updating app source files in bundle..."
echo ""

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
        echo "  Updated: ${f}"
    else
        echo "  Skipped: ${f} (not found in project root)"
    fi
done

echo ""
echo "Done. Restart the app to use the updated files."
