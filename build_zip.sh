#!/usr/bin/env bash
# Build a QGIS-installable ZIP for the Generic Feature Partitioner plugin.
# Usage: ./build_zip.sh
#
# Produces: generic_feature_partitioner.zip
# Install in QGIS via: Plugins > Install from ZIP

set -euo pipefail

PLUGIN_DIR="generic_feature_partitioner"
OUTPUT_ZIP="generic_feature_partitioner.zip"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "Error: plugin directory '$PLUGIN_DIR' not found." >&2
    exit 1
fi

# Remove stale bytecode
find "$PLUGIN_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PLUGIN_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Remove old zip if present
rm -f "$OUTPUT_ZIP"

# Build zip — QGIS expects the plugin folder at the root of the archive
zip -r "$OUTPUT_ZIP" "$PLUGIN_DIR" \
    -x "${PLUGIN_DIR}/.*" \
    -x "${PLUGIN_DIR}/__pycache__/*"

echo ""
echo "Created: $OUTPUT_ZIP ($(du -h "$OUTPUT_ZIP" | cut -f1))"
echo "Install in QGIS: Plugins > Manage and Install Plugins > Install from ZIP"
