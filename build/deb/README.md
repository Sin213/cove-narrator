# .deb Packaging

Build a .deb from the PyInstaller output using fpm:

```bash
# Install fpm
gem install fpm

# Build .deb from PyInstaller dist
fpm -s dir -t deb \
  -n cove-narrator \
  -v 1.0.0 \
  --description "Offline TTS desktop app" \
  --license "MIT" \
  --depends "libportaudio2" \
  --after-install build/deb/postinst.sh \
  dist/cove-narrator/=/opt/cove-narrator \
  build/deb/cove-narrator.desktop=/usr/share/applications/cove-narrator.desktop
```
