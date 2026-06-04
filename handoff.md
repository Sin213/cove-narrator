# Handoff: Cove Narrator v1.0.0 — Redesign + Voice Blending

## Summary
Rename from Whooshy to Cove Narrator v1.0.0 and apply the Cove design language
(dark theme, sidebar layout, custom titlebar). Add voice blend engine that mixes
kokoro voice tensors to approximate a reference audio clip.

## Changes

### Rename (Whooshy → Cove Narrator)
- `pyproject.toml`: name, version 1.0.0, script entry
- `src/utils/config.py`, `export.py`, `presets.py`: config dirs, export filenames
- `src/app.py`, all tabs: window title, default paths
- `build/build.sh`, `build/pyinstaller/cove-narrator.spec`: build paths
- `tests/test_presets.py`: temp dir name
- Renamed doc files from whooshy to cove-narrator

### Cove Design Language
- **New `src/utils/theme.py`**: ~300-line QSS dark theme (#0b0b10 canvas, #50e6cf accent)
- **New `src/utils/chrome.py`**: Frameless window with custom titlebar (icon + centered title + min/max/close), edge resizing
- **Rewritten `src/app.py`**: Sidebar layout (mode nav, voice card, presets, settings) + QStackedWidget replacing QTabWidget + voice gallery dialog
- Tab updates: removed inline styles, added objectNames for QSS, colored slider pips (Pitch=blue, Speed=teal, Depth=purple), themed phoneme buttons (vowel=blue, consonant=purple)
- `src/utils/settings_dialog.py`: removed inline style

### Voice Blend Engine
- **New `src/engine/voice_blend.py`**: `find_best_blend()` — analyzes reference clip F0, scores same-gender kokoro voices, tries pairwise blends of top 4, returns optimal tensor. `CustomVoiceManager` — saves/loads blended tensors as .npz + .json metadata.
- `src/engine/analyzer.py`: returns gender + median_f0; uses 15s clip for stable F0
- `src/tabs/custom_tab.py`: AnalyzeWorker runs blend optimizer, passes tensor to MainWindow
- `src/app.py`: `_set_custom_voice()` activates blended tensor, `get_current_voice_id()` returns tensor when custom voice active

### Audio Fixes
- `src/engine/audio_dsp.py`: `apply_pitch_shift` no longer truncates audio when pitching down
- `src/engine/tts.py`: all synthesis uses `trim=False` with gentle trailing silence trimmer (threshold 0.001); `_split_sentences` splits long text before kokoro calls; applied to `synthesize_text`, `synthesize_hybrid`, `synthesize_raw`

## Verification
- `python -m py_compile` on all changed files: pass
- `pytest tests/ -q`: 33 passed
- Offscreen launch: window title, stack count, voice, modes all correct
- Manual test: app renders dark theme, sidebar works, voice gallery opens, reference audio analysis produces blend, audio plays without cutoff
