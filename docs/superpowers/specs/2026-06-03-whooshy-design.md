# Whooshy — Offline TTS Desktop App Design Spec

## Overview

Whooshy is a simplified, fully offline text-to-speech desktop application. Users type text and hear it spoken with neural-quality voice synthesis, or build custom utterances from individual phoneme buttons. All processing runs locally — no network required after the initial model download.

**Stack:** Python 3 + PySide6 (Qt6) + Kokoro TTS (kokoro-onnx / ONNX Runtime)

## Goals

- Fully offline and portable after first-launch model download
- Two modes: simple text-to-speech (Tab 1) and phoneme-level voice building (Tab 2)
- Adjustable pitch, speed, and expressiveness ("depth") via sliders (-100 to +100, default 0)
- Export generated audio as WAV
- Voice presets: select from Kokoro built-ins + save custom slider configurations
- Reference audio matching: drop an audio file to auto-set sliders to approximate its characteristics

## Non-Goals (v1)

- Voice cloning (requires GPU + multi-GB models)
- Multilingual support (Kokoro is English-only; Piper multilingual is a v2 path)
- SSML editing, pronunciation dictionaries, batch processing
- EPUB/DOCX/OCR parsing
- Streaming synthesis (batch-then-play is sufficient at sentence scale)
- Mobile, browser, or plugin system

## Architecture

```
whooshy-project/
├── src/
│   ├── main.py              # Entry point, app init
│   ├── app.py               # QApplication + main window with tabs
│   ├── tabs/
│   │   ├── simple_tab.py    # Tab 1: text → speech
│   │   └── custom_tab.py    # Tab 2: phoneme builder
│   ├── engine/
│   │   ├── tts.py           # Kokoro wrapper (synthesize text or phonemes)
│   │   ├── audio_dsp.py     # Pitch shift, time stretch, expressiveness
│   │   └── analyzer.py      # Reference audio analysis (pitch/speed/depth detection)
│   ├── data/
│   │   ├── phonemes.py      # English phoneme inventory (~44) + Kokoro mapping
│   │   └── dictionary.py    # CMU Pronouncing Dictionary lookup + G2P fallback
│   ├── models/
│   │   └── manager.py       # First-launch model download + verification
│   └── utils/
│       ├── audio_player.py  # sounddevice playback wrapper
│       ├── export.py        # WAV export
│       └── presets.py       # Voice preset save/load (JSON)
├── data/
│   └── cmudict.txt          # ~130KB, bundled CMU dictionary
├── requirements.txt
└── pyproject.toml
```

## Data Flow

### Tab 1 (Simple)

```
text input → dictionary lookup (flag unknowns) → Kokoro synthesize_text()
  → DSP (pitch shift, time stretch, expressiveness reshape) → playback / export
```

### Tab 2 (Custom)

```
phoneme button clicks → phoneme sequence → Kokoro synthesize_phonemes()
  → DSP (pitch shift, time stretch, expressiveness reshape) → playback / export
```

### Reference Audio Analysis

```
audio file → librosa extract (median F0, tempo, spectral flux variance)
  → map to -100/+100 slider values relative to Kokoro default baseline → set sliders
```

## Components

### TTS Engine (`engine/tts.py`)

Wraps `kokoro-onnx` with two synthesis modes:

- `synthesize_text(text: str, voice: str, speed: float) -> np.ndarray` — full text-to-speech
- `synthesize_phonemes(phonemes: list[str], voice: str, speed: float) -> np.ndarray` — phoneme sequence to audio

Returns raw PCM audio as a numpy array at 24kHz sample rate. All post-processing (pitch, speed, depth) happens downstream in the DSP module.

Voice selection passes Kokoro's voice ID string (e.g., `"af_heart"`, `"am_adam"`).

### Audio DSP (`engine/audio_dsp.py`)

Three post-processing effects applied to the synthesized PCM:

**Pitch** — Phase vocoder pitch shift on 24kHz PCM.
- Slider range: -100 to +100
- Maps to: -12 to +12 semitones
- 0 = no shift

**Speed** — Time-stretch without pitch change (phase vocoder / WSOLA).
- Slider range: -100 to +100
- Maps to: 0.5x to 2.0x playback speed
- 0 = 1.0x (original speed)

**Depth (Expressiveness)** — Post-processing pitch-contour reshape. Kokoro has no native expressiveness parameter, so this is implemented as:
- Extract the pitch contour (F0 track) of the generated audio
- At -100 (monotone): flatten the contour toward the mean F0
- At +100 (theatrical): amplify deviations from the mean F0
- 0 = unmodified contour
- Implemented by interpolating between the flattened and amplified contours, then applying the new F0 via PSOLA or phase vocoder resynthesis.

### Reference Audio Analyzer (`engine/analyzer.py`)

Uses `librosa` to extract three characteristics from a dropped audio file:

- **Pitch**: Median fundamental frequency (F0) via `librosa.pyin()`. Mapped to the pitch slider relative to Kokoro's default output pitch as baseline.
- **Speed**: Tempo estimation via `librosa.beat.beat_track()` or speaking-rate proxy. Mapped to speed slider.
- **Depth**: Spectral flux variance as a proxy for expressiveness. High variance = more expressive. Mapped to depth slider.

All values mapped to -100/+100 range relative to a calibrated Kokoro default baseline.

### Dictionary (`data/dictionary.py`)

- Loads CMU Pronouncing Dictionary (~134K English words) at startup into a Python dict.
- `lookup(word: str) -> tuple[list[str], bool]` — returns (ARPAbet phoneme list, is_known).
- Unknown words: rule-based grapheme-to-phoneme fallback (no ML, no network). Returns `is_known=False` so the UI can flag them.
- The CMU dict file (`data/cmudict.txt`, ~4 MB uncompressed) ships bundled with the app.

### Phoneme Inventory (`data/phonemes.py`)

45 buttons total:
- **Vowels (15)**: AA, AE, AH, AO, AW, AY, EH, ER, EY, IH, IY, OW, OY, UH, UW
- **Consonants (24)**: B, CH, D, DH, F, G, HH, JH, K, L, M, N, NG, P, R, S, SH, T, TH, V, W, Y, Z, ZH
- **Pause (1)**: silence/break token

Each entry maps ARPAbet symbol → Kokoro's expected IPA input symbol. Color-coded in UI: vowels (blue), consonants (purple), pause (gray).

### Voice Presets (`utils/presets.py`)

Stored as JSON files in `~/.config/whooshy/presets/`.

Preset schema:
```json
{
  "name": "My Deep Voice",
  "voice_id": "am_adam",
  "pitch": -20,
  "speed": -10,
  "depth": 30
}
```

- Built-in presets (from Kokoro's voice list) are read-only.
- User-created presets can be edited and deleted.
- Dropdown shows built-ins first, then a separator, then user presets.

### Model Manager (`models/manager.py`)

- Model directory: `~/.local/share/whooshy/models/`
- On app launch: check if the Kokoro ONNX model file exists and SHA256 matches.
- If missing: show a modal download dialog with progress bar. Download from HuggingFace, verify SHA256, save.
- If corrupted: re-download.
- No network access after successful model verification.

### Audio Player (`utils/audio_player.py`)

- Uses `sounddevice` for real-time PCM playback at 24kHz.
- Supports play, pause, stop.
- Runs playback in a background thread to keep the UI responsive.
- Emits signals for playback state changes (playing, paused, stopped, finished).

### WAV Export (`utils/export.py`)

- Writes the last-generated PCM audio to a WAV file via `soundfile`.
- Default directory: `~/Music/Whooshy/` (configurable).
- Filename: `whooshy-YYYYMMDD-HHMMSS.wav` (timestamp-based, no overwrites).
- Sample rate: 24kHz, 16-bit PCM.

## UI Design

### Window Layout

```
┌─────────────────────────────────────────────────┐
│  Voice: [af_heart ▾]                [💾 Save]   │  ← persistent header
├──────────────────┬──────────────────────────────┤
│  [Tab 1: Simple] │  [Tab 2: Custom]             │  ← tab bar
├──────────────────┴──────────────────────────────┤
│                                                 │
│  (tab content area)                             │
│                                                 │
└─────────────────────────────────────────────────┘
```

Voice dropdown and preset save button persist above the tab bar, shared across both tabs.

### Tab 1 — Simple

1. **Text area** — multi-line text input. Words checked against CMU dict in real-time (debounced 300ms). Unknown words shown with a subtle red-tinted background inline. Guessed words still spoken.
2. **Three sliders** — Pitch, Speed, Depth. Each labeled, range -100 to +100, default 0. Numeric value displayed beside each slider.
3. **Controls row** — Play/Pause button (toggles), Stop button, Export WAV button, save directory path (clickable to change).

### Tab 2 — Custom

1. **Phoneme button grid** — 45 buttons in a flow layout. Color-coded by type. Each click appends that phoneme to the sequence bar.
2. **Phoneme sequence bar** — horizontal scrolling bar showing the current phoneme sequence as tags. Click a tag to remove it.
3. **Reference audio drop zone** — dashed-border area. Accept drag-and-drop of audio files (WAV, MP3, FLAC, OGG). On drop: analyze with librosa, animate sliders to detected values.
4. **Three sliders** — same as Tab 1, but independent state. Auto-set when reference audio is dropped.
5. **Controls row** — same as Tab 1.

### Interactions

- Sliders are per-tab (Tab 1 and Tab 2 maintain independent slider states)
- Play during playback → pause. Play again → resume. Stop → reset to beginning.
- Export always writes the most recently generated audio (from whichever tab produced it last)
- Save directory persists in `~/.config/whooshy/config.json`

## Dependencies

```
kokoro-onnx          # TTS engine
onnxruntime          # ONNX inference runtime
PySide6              # GUI framework (already installed system-wide)
sounddevice          # Audio playback
soundfile            # WAV read/write
numpy                # Audio DSP, array operations
librosa              # Reference audio analysis (pitch, tempo, spectral)
```

## First-Launch Experience

1. App opens to a model download dialog: "Whooshy needs to download the Kokoro voice model (~300 MB). This is a one-time download."
2. Progress bar shows download progress.
3. SHA256 verification on completion.
4. On success: dialog closes, app opens to Tab 1 with the default voice selected.
5. On failure: retry button + error message. App cannot proceed without the model.

## Platform Support

- **Linux**: Primary target. PySide6 + sounddevice work out of the box.
- **Windows**: Secondary. PyInstaller packaging. sounddevice uses WASAPI.
- **macOS**: Deferred to v1.1 (notarization complexity).

## Configuration Files

- `~/.config/whooshy/config.json` — save directory, last-used voice, window geometry
- `~/.config/whooshy/presets/*.json` — user voice presets
- `~/.local/share/whooshy/models/` — downloaded Kokoro ONNX model
