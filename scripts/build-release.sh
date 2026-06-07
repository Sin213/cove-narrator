#!/usr/bin/env bash
# Build .AppImage and .deb for Cove Narrator.
# Output lands in release/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_NAME="cove-narrator"
DISPLAY_NAME="Cove Narrator"
VERSION="${VERSION:-1.1.0}"
ARCH="x86_64"
DEB_ARCH="amd64"
RELEASE_DIR="$ROOT/release"
DIST_DIR="$ROOT/dist"
APPDIR="$ROOT/build/AppDir"
DEB_BUILD="$ROOT/build/deb-pkg"
BUILD_ENV="$ROOT/.buildenv"
ICON_SRC="$ROOT/build/icon.png"

LOCAL_BIN="${HOME}/.local/bin"
APPIMAGETOOL="${LOCAL_BIN}/appimagetool"

mkdir -p "$RELEASE_DIR" "$LOCAL_BIN"
rm -rf "$DIST_DIR" "$ROOT/build/tmp" "$ROOT/build/AppDir" "$ROOT/build/deb-pkg"

# ----------------------------------------------------------------------
# 0. Build venv
# ----------------------------------------------------------------------
echo "==> Creating build venv"
rm -rf "$BUILD_ENV"
python3 -m venv "$BUILD_ENV"
"$BUILD_ENV/bin/pip" install --quiet --upgrade pip
"$BUILD_ENV/bin/pip" install --quiet -r requirements.txt pyinstaller

# ----------------------------------------------------------------------
# 1. Download model files if missing
# ----------------------------------------------------------------------
MODELS_DIR="$ROOT/data/models"
mkdir -p "$MODELS_DIR"
if [ ! -f "$MODELS_DIR/kokoro-v1.0.onnx" ]; then
    echo "==> Downloading kokoro-v1.0.onnx"
    curl -fL --retry 3 --silent --show-error \
        -o "$MODELS_DIR/kokoro-v1.0.onnx" \
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
fi
if [ ! -f "$MODELS_DIR/voices-v1.0.bin" ]; then
    echo "==> Downloading voices-v1.0.bin"
    curl -fL --retry 3 --silent --show-error \
        -o "$MODELS_DIR/voices-v1.0.bin" \
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
fi

# ----------------------------------------------------------------------
# 2. PyInstaller
# ----------------------------------------------------------------------
echo "==> Running PyInstaller"
"$BUILD_ENV/bin/pyinstaller" \
    --noconfirm --clean --log-level WARN \
    --windowed \
    --name "$APP_NAME" \
    --paths . \
    --collect-submodules src \
    --collect-data src.vendor.qwen_tts \
    --collect-data kokoro_onnx \
    --collect-data phonemizer \
    --collect-data language_tags \
    --collect-data espeakng_loader \
    --collect-binaries espeakng_loader \
    --add-data "data/models/kokoro-v1.0.onnx:data/models" \
    --add-data "data/models/voices-v1.0.bin:data/models" \
    --add-data "data/cmudict.txt:data" \
    --add-data "build/icon.png:build" \
    --hidden-import kokoro_onnx \
    --hidden-import onnxruntime \
    --hidden-import sounddevice \
    --hidden-import soundfile \
    --hidden-import librosa \
    --hidden-import numpy \
    --hidden-import PySide6 \
    --hidden-import pymupdf \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtWebEngineWidgets \
    --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick \
    --exclude-module PySide6.Qt3DCore \
    --exclude-module PySide6.QtCharts \
    --exclude-module PySide6.QtDataVisualization \
    --exclude-module tkinter \
    src/main.py

BUNDLE="$DIST_DIR/$APP_NAME"
[ -d "$BUNDLE" ] || { echo "PyInstaller bundle not found at $BUNDLE"; exit 1; }

# ----------------------------------------------------------------------
# 3. AppImage
# ----------------------------------------------------------------------
echo "==> Assembling AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/$APP_NAME" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$BUNDLE"/. "$APPDIR/usr/lib/$APP_NAME/"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
cp "$ICON_SRC" "$APPDIR/$APP_NAME.png"
cp "$ICON_SRC" "$APPDIR/.DirIcon" 2>/dev/null || true

cat > "$APPDIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$DISPLAY_NAME
GenericName=Text-to-Speech Narrator
Comment=Offline TTS with voice blending and phoneme control
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=Audio;Utility;
Keywords=tts;narrator;speech;voice;kokoro;
StartupNotify=true
EOF
cp "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export APPIMAGE_ORIG_PATH="${PATH:-}"
export APPIMAGE_ORIG_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export APPIMAGE_ORIG_PYTHONHOME="${PYTHONHOME:-}"
export APPIMAGE_ORIG_PYTHONPATH="${PYTHONPATH:-}"
export APPIMAGE_ORIG_QT_PLUGIN_PATH="${QT_PLUGIN_PATH:-}"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib/cove-narrator:${LD_LIBRARY_PATH:-}"
exec "$HERE/usr/lib/cove-narrator/cove-narrator" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/usr/bin/$APP_NAME" <<'WRAPPER'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")/../lib/cove-narrator"
exec "$HERE/cove-narrator" "$@"
WRAPPER
chmod +x "$APPDIR/usr/bin/$APP_NAME"

if [ ! -x "$APPIMAGETOOL" ]; then
    if command -v appimagetool >/dev/null 2>&1; then
        APPIMAGETOOL="$(command -v appimagetool)"
    else
        echo "==> Downloading appimagetool to $APPIMAGETOOL"
        curl -fL --retry 3 --silent --show-error -o "$APPIMAGETOOL" \
            "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        chmod +x "$APPIMAGETOOL"
    fi
fi

echo "==> Building AppImage"
APPIMAGE_OUT="$RELEASE_DIR/${DISPLAY_NAME// /-}-${VERSION}-${ARCH}.AppImage"
ARCH=$ARCH "$APPIMAGETOOL" --no-appstream "$APPDIR" "$APPIMAGE_OUT"
chmod +x "$APPIMAGE_OUT"
( cd "$RELEASE_DIR" && sha256sum "$(basename "$APPIMAGE_OUT")" > "$(basename "$APPIMAGE_OUT").sha256" )
echo "    -> $APPIMAGE_OUT"
echo "    -> $APPIMAGE_OUT.sha256"

# ----------------------------------------------------------------------
# 4. .deb (manual: ar + tar.xz, no dpkg-deb dependency)
# ----------------------------------------------------------------------
if [ "${SKIP_DEB:-0}" = "1" ]; then
    echo "==> Skipping .deb (SKIP_DEB=1)"
    echo ""
    echo "Release artifacts in $RELEASE_DIR:"
    ls -lh "$RELEASE_DIR"
    exit 0
fi
echo "==> Assembling .deb tree"
PKG_ROOT="$DEB_BUILD/${APP_NAME}_${VERSION}_${DEB_ARCH}"
rm -rf "$DEB_BUILD"
mkdir -p "$PKG_ROOT/DEBIAN" \
         "$PKG_ROOT/usr/bin" \
         "$PKG_ROOT/usr/lib/$APP_NAME" \
         "$PKG_ROOT/usr/share/applications" \
         "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps" \
         "$PKG_ROOT/usr/share/doc/$APP_NAME"

cp -r "$BUNDLE"/. "$PKG_ROOT/usr/lib/$APP_NAME/"
cp "$ICON_SRC" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

cat > "$PKG_ROOT/usr/bin/$APP_NAME" <<'WRAPPER'
#!/usr/bin/env bash
exec /usr/lib/cove-narrator/cove-narrator "$@"
WRAPPER
chmod +x "$PKG_ROOT/usr/bin/$APP_NAME"

cat > "$PKG_ROOT/usr/share/applications/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$DISPLAY_NAME
GenericName=Text-to-Speech Narrator
Comment=Offline TTS with voice blending and phoneme control
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=Audio;Utility;
Keywords=tts;narrator;speech;voice;kokoro;
StartupNotify=true
EOF

[ -f "$ROOT/LICENSE" ] && cp "$ROOT/LICENSE" "$PKG_ROOT/usr/share/doc/$APP_NAME/copyright"

INSTALLED_SIZE=$(du -sk "$PKG_ROOT/usr" | awk '{print $1}')

cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: $APP_NAME
Version: $VERSION
Architecture: $DEB_ARCH
Maintainer: Cove <noreply@cove.local>
Installed-Size: $INSTALLED_SIZE
Depends: libportaudio2
Section: sound
Priority: optional
Homepage: https://github.com/Sin213/cove-narrator
Description: Offline TTS desktop app with voice blending
 Cove Narrator is a fully offline text-to-speech application with 27 built-in
 voices, voice blending from reference audio, ARPABET phoneme control, and
 document reading. Powered by Kokoro ONNX.
EOF

echo "==> Building .deb archive"
DEB_OUT="$RELEASE_DIR/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb"
WORK="$DEB_BUILD/work"
rm -rf "$WORK"
mkdir -p "$WORK"

(cd "$PKG_ROOT" && tar --xz --owner=0 --group=0 -cf "$WORK/control.tar.xz" -C DEBIAN .)
(cd "$PKG_ROOT" && tar --xz --owner=0 --group=0 -cf "$WORK/data.tar.xz" \
    --transform 's,^\./,,' \
    --exclude=./DEBIAN \
    .)
echo -n "2.0" > "$WORK/debian-binary"
echo "" >> "$WORK/debian-binary"

(cd "$WORK" && ar -rc "$DEB_OUT" debian-binary control.tar.xz data.tar.xz)
( cd "$RELEASE_DIR" && sha256sum "$(basename "$DEB_OUT")" > "$(basename "$DEB_OUT").sha256" )

echo "    -> $DEB_OUT"
echo "    -> $DEB_OUT.sha256"

echo ""
echo "Release artifacts in $RELEASE_DIR:"
ls -lh "$RELEASE_DIR"
