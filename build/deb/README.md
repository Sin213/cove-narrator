# .deb Packaging

Build a .deb from the PyInstaller output using fpm:

```bash
# Install fpm
gem install fpm

# Build .deb from PyInstaller dist
fpm -s dir -t deb \
  -n whooshy \
  -v 0.1.0 \
  --description "Offline TTS desktop app" \
  --license "MIT" \
  --depends "libportaudio2" \
  --after-install build/deb/postinst.sh \
  dist/whooshy/=/opt/whooshy \
  build/deb/whooshy.desktop=/usr/share/applications/whooshy.desktop
```
