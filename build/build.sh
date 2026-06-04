#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Installing build deps ==="
.venv/bin/pip install pyinstaller

echo "=== Building with PyInstaller ==="
.venv/bin/pyinstaller build/pyinstaller/cove-narrator.spec --distpath dist/ --workpath build/tmp --clean

echo "=== Build complete ==="
ls -lah dist/cove-narrator/
echo ""
echo "Run with: ./dist/cove-narrator/cove-narrator"
