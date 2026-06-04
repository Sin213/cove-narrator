# Cove Narrator

Offline text-to-speech desktop app with voice blending, phoneme-level control, and document reading. Built on [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) — all processing runs locally, no network required.

## Features

- **Simple mode** — Type text, drop in inline tags (`[Pause]`, `[Soft]`, `[Slow]`, `[Speed]`, `[Pitch]`), and hit Play. Unknown words get flagged so you can spell them out in Custom mode.
- **Custom mode** — Spell tricky words phonetically with ARPABET buttons. Drop a reference audio clip to auto-match the closest voice blend by pitch analysis.
- **Reader mode** — Open `.txt` or `.pdf` files and read them sentence by sentence with live highlighting. Click any sentence to jump there. Next-sentence prefetch for seamless playback.
- **27 built-in voices** — American and British, male and female, with personality descriptions. Search and filter in the voice gallery.
- **Voice blending** — Drop a reference clip and Cove finds the optimal mix of kokoro voices to match its pitch. Save custom blends by name and reuse them.
- **Audio DSP** — Pitch, speed, and depth sliders with per-slider color coding. WAV export.
- **Presets** — Save and load slider + voice combinations.

## Requirements

- Python 3.10+
- PySide6, kokoro-onnx, onnxruntime, sounddevice, soundfile, numpy, librosa, pymupdf

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Kokoro model files go in `data/models/`:
- `kokoro-v1.0.onnx`
- `voices-v1.0.bin`

## Run

```bash
python -m src.main
```

## Build

```bash
bash build/build.sh
```

Produces `dist/cove-narrator/` with a standalone executable.

## Config

- Settings: `~/.config/cove-narrator/config.json`
- Presets: `~/.config/cove-narrator/presets/`
- Custom voices: `~/.config/cove-narrator/voices/`
- Exports: `~/Music/Cove Narrator/`

## Keyboard Shortcuts

| Action | Default |
|--------|---------|
| Play / Pause | Space |
| Stop | Escape |
| Export WAV | Ctrl+E |

Shortcuts are configurable in Settings.

## License

MIT
