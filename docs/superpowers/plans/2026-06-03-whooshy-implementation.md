# Whooshy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully offline TTS desktop app with two tabs (simple text-to-speech + custom phoneme builder), voice presets, pitch/speed/depth sliders, reference audio matching, and WAV export.

**Architecture:** PySide6 tabbed window with a Kokoro TTS engine wrapper. Text goes through CMU dictionary lookup then Kokoro synthesis. Phonemes go directly to Kokoro via `is_phonemes=True`. Post-processing DSP applies pitch shift and expressiveness. Audio plays via sounddevice.

**Tech Stack:** Python 3.14, PySide6 6.11, kokoro-onnx 0.4.7, onnxruntime, sounddevice, soundfile, librosa, numpy

**Spec:** `docs/superpowers/specs/2026-06-03-whooshy-design.md`

**Kokoro API Reference (verified):**
- `Kokoro(model_path, voices_path)` — constructor, takes two files
- `kokoro.create(text, voice, speed=1.0, lang="en-us", is_phonemes=False)` → `(np.ndarray float32, 24000)`
- `kokoro.get_voices()` → `list[str]` — e.g. `["af_heart", "am_adam", ...]`
- Phoneme format: IPA strings like `"həlˈoʊ wˈɜːld"` (espeak-ng output)
- `Tokenizer().phonemize(text)` → IPA string for direct phoneme input
- Model files: `kokoro-v1.0.onnx` (326 MB) + `voices-v1.0.bin` (28 MB) from GitHub releases

---

### Task 1: Project Scaffolding + Model Setup

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/main.py` (minimal entry point)
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "whooshy"
version = "0.1.0"
description = "Offline TTS desktop app with phoneme-level voice building"
requires-python = ">=3.10"
dependencies = [
    "kokoro-onnx>=0.4.7",
    "onnxruntime>=1.20.1",
    "PySide6>=6.7",
    "sounddevice>=0.5",
    "soundfile>=0.12",
    "numpy>=2.0",
    "librosa>=0.10",
]

[project.scripts]
whooshy = "src.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create requirements.txt**

```
kokoro-onnx>=0.4.7
onnxruntime>=1.20.1
sounddevice>=0.5
soundfile>=0.12
numpy>=2.0
librosa>=0.10
pytest>=8.0
```

Note: PySide6 is system-wide, not in requirements.txt (it's provided by the system package).

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
data/models/*.onnx
data/models/*.bin
.superpowers/
```

- [ ] **Step 4: Create directory structure and __init__.py files**

```bash
mkdir -p src/engine src/data src/models src/utils src/tabs tests data/models
touch src/__init__.py src/engine/__init__.py src/data/__init__.py src/models/__init__.py src/utils/__init__.py src/tabs/__init__.py tests/__init__.py
```

- [ ] **Step 5: Create minimal entry point**

Create `src/main.py`:
```python
import sys
from PySide6.QtWidgets import QApplication, QLabel


def main():
    app = QApplication(sys.argv)
    label = QLabel("Whooshy — loading...")
    label.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Download model files**

```bash
cd data/models
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

Verify: `ls -la data/models/` — should show ~326 MB onnx + ~28 MB bin.

- [ ] **Step 7: Verify Kokoro works end-to-end**

```bash
cd /home/sin/Projects/whooshy-project
.venv/bin/python3 -c "
from kokoro_onnx import Kokoro
k = Kokoro('data/models/kokoro-v1.0.onnx', 'data/models/voices-v1.0.bin')
samples, sr = k.create('Hello from Whooshy!', voice='af_heart', speed=1.0)
print(f'Generated {len(samples)} samples at {sr}Hz ({len(samples)/sr:.1f}s)')
import soundfile as sf
sf.write('/tmp/whooshy-test.wav', samples, sr)
print('Wrote /tmp/whooshy-test.wav')
"
```

Expected: prints sample count and writes a WAV file. Play it to verify audio quality.

- [ ] **Step 8: Run the GUI smoke test**

```bash
.venv/bin/python3 src/main.py
```

Expected: a window appears with "Whooshy — loading...". Close it.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml requirements.txt .gitignore src/ tests/ data/models/.gitkeep
git commit -m "feat: project scaffolding with Kokoro model verified"
```

Note: do NOT commit the .onnx/.bin model files (they're in .gitignore). Create `data/models/.gitkeep` to track the directory.

---

### Task 2: Model Loader

**Files:**
- Create: `src/models/loader.py`
- Create: `tests/test_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_loader.py`:
```python
from pathlib import Path
from src.models.loader import find_model_files


def test_find_model_files_returns_paths():
    model_path, voices_path = find_model_files()
    assert model_path.exists()
    assert voices_path.exists()
    assert model_path.name == "kokoro-v1.0.onnx"
    assert voices_path.name == "voices-v1.0.bin"


def test_find_model_files_raises_on_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.models.loader._data_dir", lambda: tmp_path / "nonexistent")
    try:
        find_model_files()
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.loader'`

- [ ] **Step 3: Implement the model loader**

Create `src/models/loader.py`:
```python
from pathlib import Path

MODEL_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "models"


def find_model_files() -> tuple[Path, Path]:
    base = _data_dir()
    model_path = base / MODEL_FILENAME
    voices_path = base / VOICES_FILENAME
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not voices_path.exists():
        raise FileNotFoundError(f"Voices not found: {voices_path}")
    return model_path, voices_path
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python3 -m pytest tests/test_loader.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/models/loader.py tests/test_loader.py
git commit -m "feat: model loader finds bundled Kokoro model files"
```

---

### Task 3: TTS Engine Wrapper

**Files:**
- Create: `src/engine/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tts.py`:
```python
import numpy as np
from src.engine.tts import TTSEngine


def test_synthesize_text_returns_audio():
    engine = TTSEngine()
    audio, sr = engine.synthesize_text("Hello", voice="af_heart")
    assert isinstance(audio, np.ndarray)
    assert sr == 24000
    assert len(audio) > 0
    assert audio.dtype == np.float32


def test_synthesize_phonemes_returns_audio():
    engine = TTSEngine()
    audio, sr = engine.synthesize_phonemes("həlˈoʊ", voice="af_heart")
    assert isinstance(audio, np.ndarray)
    assert sr == 24000
    assert len(audio) > 0


def test_get_voices_returns_list():
    engine = TTSEngine()
    voices = engine.get_voices()
    assert isinstance(voices, list)
    assert "af_heart" in voices
    assert len(voices) > 10


def test_speed_parameter_changes_duration():
    engine = TTSEngine()
    audio_normal, _ = engine.synthesize_text("Hello world", voice="af_heart", speed=1.0)
    audio_fast, _ = engine.synthesize_text("Hello world", voice="af_heart", speed=2.0)
    assert len(audio_fast) < len(audio_normal)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_tts.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the TTS engine**

Create `src/engine/tts.py`:
```python
import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.tokenizer import Tokenizer

from src.models.loader import find_model_files


class TTSEngine:
    def __init__(self):
        model_path, voices_path = find_model_files()
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._tokenizer = Tokenizer()

    def synthesize_text(
        self, text: str, voice: str, speed: float = 1.0
    ) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(
            text, voice=voice, speed=speed, lang="en-us"
        )
        return samples, sr

    def synthesize_phonemes(
        self, phonemes: str, voice: str, speed: float = 1.0
    ) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(
            phonemes, voice=voice, speed=speed, lang="en-us", is_phonemes=True
        )
        return samples, sr

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, lang="en-us")

    def get_voices(self) -> list[str]:
        return self._kokoro.get_voices()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python3 -m pytest tests/test_tts.py -v
```

Expected: 4 passed. Note: first run loads the 326 MB model so it takes a few seconds.

- [ ] **Step 5: Commit**

```bash
git add src/engine/tts.py tests/test_tts.py
git commit -m "feat: TTS engine wrapper with text and phoneme synthesis"
```

---

### Task 4: Audio DSP (Pitch + Depth)

**Files:**
- Create: `src/engine/audio_dsp.py`
- Create: `tests/test_audio_dsp.py`

Speed is handled by Kokoro's `speed` param directly (0.5–2.0). DSP only handles:
- **Pitch**: slider -100/+100 → -12/+12 semitones via librosa
- **Depth**: slider -100/+100 → amplitude envelope reshape (monotone ↔ theatrical)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_audio_dsp.py`:
```python
import numpy as np
from src.engine.audio_dsp import (
    apply_pitch_shift,
    apply_depth,
    slider_to_speed,
    apply_all,
)

SR = 24000


def _make_tone(freq=440.0, duration=0.5, sr=SR):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def test_slider_to_speed_center():
    assert slider_to_speed(0) == 1.0


def test_slider_to_speed_extremes():
    assert slider_to_speed(-100) == 0.5
    assert slider_to_speed(100) == 2.0


def test_pitch_shift_zero_is_identity():
    audio = _make_tone()
    result = apply_pitch_shift(audio, 0, SR)
    assert len(result) == len(audio)
    assert np.corrcoef(audio[:1000], result[:1000])[0, 1] > 0.95


def test_pitch_shift_changes_audio():
    audio = _make_tone()
    result = apply_pitch_shift(audio, 50, SR)
    assert len(result) == len(audio)
    assert not np.allclose(audio, result, atol=0.01)


def test_depth_zero_is_identity():
    audio = _make_tone()
    result = apply_depth(audio, 0)
    np.testing.assert_array_almost_equal(audio, result, decimal=5)


def test_depth_negative_reduces_dynamic_range():
    audio = _make_tone() * np.linspace(0.1, 1.0, len(_make_tone())).astype(np.float32)
    result = apply_depth(audio, -100)
    orig_std = np.std(np.abs(audio))
    result_std = np.std(np.abs(result))
    assert result_std < orig_std


def test_apply_all_returns_valid_audio():
    audio = _make_tone()
    result = apply_all(audio, SR, pitch=10, depth=20)
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert len(result) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_audio_dsp.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement audio DSP**

Create `src/engine/audio_dsp.py`:
```python
import numpy as np
import librosa


def slider_to_speed(slider: int) -> float:
    return 1.0 + slider * 0.5 / 100.0


def slider_to_semitones(slider: int) -> float:
    return slider * 12.0 / 100.0


def apply_pitch_shift(audio: np.ndarray, slider: int, sr: int) -> np.ndarray:
    if slider == 0:
        return audio.copy()
    semitones = slider_to_semitones(slider)
    shifted = librosa.effects.pitch_shift(
        y=audio, sr=sr, n_steps=semitones
    )
    return shifted.astype(np.float32)


def apply_depth(audio: np.ndarray, slider: int) -> np.ndarray:
    if slider == 0:
        return audio.copy()

    frame_len = 1024
    hop = 512
    n_frames = 1 + (len(audio) - frame_len) // hop
    if n_frames < 2:
        return audio.copy()

    envelope = np.array([
        np.sqrt(np.mean(audio[i * hop : i * hop + frame_len] ** 2))
        for i in range(n_frames)
    ])

    mean_env = np.mean(envelope)
    if mean_env < 1e-8:
        return audio.copy()

    scale = slider / 100.0
    if scale < 0:
        target_env = mean_env + (envelope - mean_env) * (1.0 + scale)
    else:
        target_env = mean_env + (envelope - mean_env) * (1.0 + scale)

    gain = np.where(envelope > 1e-8, target_env / envelope, 1.0)

    gain_samples = np.ones(len(audio), dtype=np.float32)
    for i in range(n_frames):
        start = i * hop
        end = min(start + frame_len, len(audio))
        gain_samples[start:end] = gain[i]

    result = audio * gain_samples
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result /= peak
    return result.astype(np.float32)


def apply_all(
    audio: np.ndarray, sr: int, pitch: int = 0, depth: int = 0
) -> np.ndarray:
    result = audio
    if pitch != 0:
        result = apply_pitch_shift(result, pitch, sr)
    if depth != 0:
        result = apply_depth(result, depth)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_audio_dsp.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/engine/audio_dsp.py tests/test_audio_dsp.py
git commit -m "feat: audio DSP with pitch shift and depth/expressiveness"
```

---

### Task 5: Audio Player + WAV Export

**Files:**
- Create: `src/utils/audio_player.py`
- Create: `src/utils/export.py`
- Create: `tests/test_audio_player.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Write the failing tests for export**

Create `tests/test_export.py`:
```python
import numpy as np
import soundfile as sf
from pathlib import Path
from src.utils.export import export_wav


def test_export_wav_creates_file(tmp_path):
    audio = np.random.randn(24000).astype(np.float32)
    path = export_wav(audio, 24000, tmp_path)
    assert path.exists()
    assert path.suffix == ".wav"
    data, sr = sf.read(str(path))
    assert sr == 24000
    assert len(data) == 24000


def test_export_wav_no_overwrite(tmp_path):
    audio = np.random.randn(24000).astype(np.float32)
    path1 = export_wav(audio, 24000, tmp_path)
    path2 = export_wav(audio, 24000, tmp_path)
    assert path1 != path2
    assert path1.exists()
    assert path2.exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_export.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement WAV export**

Create `src/utils/export.py`:
```python
from pathlib import Path
from datetime import datetime

import numpy as np
import soundfile as sf


def export_wav(audio: np.ndarray, sr: int, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"whooshy-{timestamp}.wav"
    counter = 2
    while path.exists():
        path = directory / f"whooshy-{timestamp}-{counter}.wav"
        counter += 1
    sf.write(str(path), audio, sr, subtype="PCM_16")
    return path
```

- [ ] **Step 4: Run export tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_export.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Write the failing tests for audio player**

Create `tests/test_audio_player.py`:
```python
import numpy as np
from src.utils.audio_player import AudioPlayer


def test_player_initial_state():
    player = AudioPlayer()
    assert not player.is_playing
    assert not player.is_paused


def test_player_load_audio():
    player = AudioPlayer()
    audio = np.random.randn(24000).astype(np.float32)
    player.load(audio, 24000)
    assert not player.is_playing


def test_player_stop_when_not_playing():
    player = AudioPlayer()
    player.stop()
    assert not player.is_playing
```

- [ ] **Step 6: Implement audio player**

Create `src/utils/audio_player.py`:
```python
import threading

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


class AudioPlayer(QObject):
    playback_finished = Signal()
    state_changed = Signal(str)  # "playing", "paused", "stopped"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._audio: np.ndarray | None = None
        self._sr: int = 24000
        self._position: int = 0
        self._is_playing = False
        self._is_paused = False
        self._stream: sd.OutputStream | None = None
        self._lock = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def load(self, audio: np.ndarray, sr: int):
        self.stop()
        self._audio = audio
        self._sr = sr
        self._position = 0

    def play(self):
        if self._audio is None:
            return
        if self._is_paused:
            self._is_paused = False
            self._is_playing = True
            self.state_changed.emit("playing")
            return
        self.stop()
        self._is_playing = True
        self._position = 0
        self.state_changed.emit("playing")
        self._stream = sd.OutputStream(
            samplerate=self._sr,
            channels=1,
            dtype="float32",
            callback=self._callback,
            finished_callback=self._on_finished,
        )
        self._stream.start()

    def pause(self):
        if self._is_playing and not self._is_paused:
            self._is_paused = True
            self._is_playing = False
            self.state_changed.emit("paused")

    def stop(self):
        self._is_playing = False
        self._is_paused = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._position = 0
        self.state_changed.emit("stopped")

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if self._audio is None or not self._is_playing:
                outdata[:] = 0
                if self._is_paused:
                    return
                raise sd.CallbackStop()

            end = self._position + frames
            if end >= len(self._audio):
                remaining = len(self._audio) - self._position
                outdata[:remaining, 0] = self._audio[self._position:]
                outdata[remaining:] = 0
                self._position = len(self._audio)
                raise sd.CallbackStop()
            else:
                outdata[:, 0] = self._audio[self._position:end]
                self._position = end

    def _on_finished(self):
        self._is_playing = False
        self._is_paused = False
        self._stream = None
        self.playback_finished.emit()
        self.state_changed.emit("stopped")
```

- [ ] **Step 7: Run audio player tests**

```bash
.venv/bin/python3 -m pytest tests/test_audio_player.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add src/utils/audio_player.py src/utils/export.py tests/test_audio_player.py tests/test_export.py
git commit -m "feat: audio player with play/pause/stop and WAV export"
```

---

### Task 6: CMU Dictionary + Phoneme Inventory

**Files:**
- Create: `src/data/dictionary.py`
- Create: `src/data/phonemes.py`
- Create: `tests/test_dictionary.py`
- Create: `tests/test_phonemes.py`
- Download: `data/cmudict.txt`

- [ ] **Step 1: Download CMU dictionary**

```bash
cd /home/sin/Projects/whooshy-project
wget -O data/cmudict.txt https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
wc -l data/cmudict.txt
```

Expected: ~134,000 lines.

- [ ] **Step 2: Write the failing tests for dictionary**

Create `tests/test_dictionary.py`:
```python
from src.data.dictionary import Dictionary


def test_lookup_known_word():
    d = Dictionary()
    phonemes, is_known = d.lookup("hello")
    assert is_known
    assert len(phonemes) > 0
    assert isinstance(phonemes[0], str)


def test_lookup_unknown_word():
    d = Dictionary()
    phonemes, is_known = d.lookup("xyzzyplugh")
    assert not is_known
    assert len(phonemes) > 0


def test_lookup_case_insensitive():
    d = Dictionary()
    lower_ph, _ = d.lookup("hello")
    upper_ph, _ = d.lookup("HELLO")
    assert lower_ph == upper_ph


def test_to_ipa_returns_string():
    d = Dictionary()
    ipa = d.to_ipa("hello world")
    assert isinstance(ipa, str)
    assert len(ipa) > 0
```

- [ ] **Step 3: Write the failing tests for phonemes**

Create `tests/test_phonemes.py`:
```python
from src.data.phonemes import PHONEMES, arpabet_to_ipa, PAUSE_TOKEN


def test_phoneme_count():
    assert len(PHONEMES) == 45


def test_all_phonemes_have_ipa():
    for p in PHONEMES:
        if p["arpabet"] == PAUSE_TOKEN:
            continue
        assert p["ipa"] != "", f"{p['arpabet']} has no IPA mapping"


def test_categories_present():
    categories = {p["category"] for p in PHONEMES}
    assert "vowel" in categories
    assert "consonant" in categories
    assert "pause" in categories


def test_arpabet_to_ipa_maps_known():
    assert arpabet_to_ipa("AA") is not None
    assert arpabet_to_ipa("B") is not None


def test_arpabet_to_ipa_returns_none_for_unknown():
    assert arpabet_to_ipa("ZZZZ") is None
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_dictionary.py tests/test_phonemes.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: Implement phoneme inventory**

Create `src/data/phonemes.py`:
```python
PAUSE_TOKEN = "SIL"

PHONEMES = [
    # Vowels (15)
    {"arpabet": "AA", "ipa": "ɑ", "example": "father", "category": "vowel"},
    {"arpabet": "AE", "ipa": "æ", "example": "cat", "category": "vowel"},
    {"arpabet": "AH", "ipa": "ʌ", "example": "but", "category": "vowel"},
    {"arpabet": "AO", "ipa": "ɔ", "example": "law", "category": "vowel"},
    {"arpabet": "AW", "ipa": "aʊ", "example": "cow", "category": "vowel"},
    {"arpabet": "AY", "ipa": "aɪ", "example": "my", "category": "vowel"},
    {"arpabet": "EH", "ipa": "ɛ", "example": "bed", "category": "vowel"},
    {"arpabet": "ER", "ipa": "ɜː", "example": "her", "category": "vowel"},
    {"arpabet": "EY", "ipa": "eɪ", "example": "say", "category": "vowel"},
    {"arpabet": "IH", "ipa": "ɪ", "example": "sit", "category": "vowel"},
    {"arpabet": "IY", "ipa": "iː", "example": "see", "category": "vowel"},
    {"arpabet": "OW", "ipa": "oʊ", "example": "go", "category": "vowel"},
    {"arpabet": "OY", "ipa": "ɔɪ", "example": "boy", "category": "vowel"},
    {"arpabet": "UH", "ipa": "ʊ", "example": "book", "category": "vowel"},
    {"arpabet": "UW", "ipa": "uː", "example": "food", "category": "vowel"},
    # Consonants (24)
    {"arpabet": "B", "ipa": "b", "example": "boy", "category": "consonant"},
    {"arpabet": "CH", "ipa": "ʧ", "example": "chair", "category": "consonant"},
    {"arpabet": "D", "ipa": "d", "example": "dog", "category": "consonant"},
    {"arpabet": "DH", "ipa": "ð", "example": "the", "category": "consonant"},
    {"arpabet": "F", "ipa": "f", "example": "fish", "category": "consonant"},
    {"arpabet": "G", "ipa": "ɡ", "example": "go", "category": "consonant"},
    {"arpabet": "HH", "ipa": "h", "example": "hat", "category": "consonant"},
    {"arpabet": "JH", "ipa": "ʤ", "example": "joy", "category": "consonant"},
    {"arpabet": "K", "ipa": "k", "example": "cat", "category": "consonant"},
    {"arpabet": "L", "ipa": "l", "example": "lip", "category": "consonant"},
    {"arpabet": "M", "ipa": "m", "example": "man", "category": "consonant"},
    {"arpabet": "N", "ipa": "n", "example": "no", "category": "consonant"},
    {"arpabet": "NG", "ipa": "ŋ", "example": "sing", "category": "consonant"},
    {"arpabet": "P", "ipa": "p", "example": "pin", "category": "consonant"},
    {"arpabet": "R", "ipa": "ɹ", "example": "red", "category": "consonant"},
    {"arpabet": "S", "ipa": "s", "example": "sun", "category": "consonant"},
    {"arpabet": "SH", "ipa": "ʃ", "example": "she", "category": "consonant"},
    {"arpabet": "T", "ipa": "t", "example": "top", "category": "consonant"},
    {"arpabet": "TH", "ipa": "θ", "example": "thin", "category": "consonant"},
    {"arpabet": "V", "ipa": "v", "example": "van", "category": "consonant"},
    {"arpabet": "W", "ipa": "w", "example": "win", "category": "consonant"},
    {"arpabet": "Y", "ipa": "j", "example": "yes", "category": "consonant"},
    {"arpabet": "Z", "ipa": "z", "example": "zoo", "category": "consonant"},
    {"arpabet": "ZH", "ipa": "ʒ", "example": "vision", "category": "consonant"},
    # Pause (1)
    {"arpabet": PAUSE_TOKEN, "ipa": " ", "example": "(silence)", "category": "pause"},
]

_ARPABET_TO_IPA = {p["arpabet"]: p["ipa"] for p in PHONEMES}


def arpabet_to_ipa(arpabet: str) -> str | None:
    clean = arpabet.rstrip("012")
    return _ARPABET_TO_IPA.get(clean)


def arpabet_sequence_to_ipa(sequence: list[str]) -> str:
    parts = []
    for symbol in sequence:
        ipa = arpabet_to_ipa(symbol)
        if ipa is not None:
            parts.append(ipa)
    return "".join(parts)
```

- [ ] **Step 6: Implement dictionary**

Create `src/data/dictionary.py`:
```python
from pathlib import Path

from src.data.phonemes import arpabet_to_ipa

_DICT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cmudict.txt"

_G2P_RULES = {
    "a": "AH", "b": "B", "c": "K", "d": "D", "e": "EH",
    "f": "F", "g": "G", "h": "HH", "i": "IH", "j": "JH",
    "k": "K", "l": "L", "m": "M", "n": "N", "o": "AA",
    "p": "P", "q": "K", "r": "R", "s": "S", "t": "T",
    "u": "AH", "v": "V", "w": "W", "x": "K", "y": "Y", "z": "Z",
    "ch": "CH", "sh": "SH", "th": "TH", "ng": "NG", "zh": "ZH",
}


class Dictionary:
    def __init__(self, dict_path: Path | None = None):
        self._entries: dict[str, list[str]] = {}
        path = dict_path or _DICT_PATH
        if path.exists():
            self._load(path)

    def _load(self, path: Path):
        with open(path, encoding="latin-1") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";;;"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                word = parts[0].lower()
                if word.endswith(")"):
                    word = word.rsplit("(", 1)[0]
                if word not in self._entries:
                    self._entries[word] = parts[1:]

    def lookup(self, word: str) -> tuple[list[str], bool]:
        key = word.lower().strip()
        if key in self._entries:
            return self._entries[key], True
        return self._g2p_fallback(key), False

    def _g2p_fallback(self, word: str) -> list[str]:
        result = []
        i = 0
        while i < len(word):
            if i + 1 < len(word) and word[i:i+2] in _G2P_RULES:
                result.append(_G2P_RULES[word[i:i+2]])
                i += 2
            elif word[i] in _G2P_RULES:
                result.append(_G2P_RULES[word[i]])
                i += 1
            else:
                i += 1
        return result if result else ["AH"]

    def to_ipa(self, text: str) -> str:
        words = text.split()
        ipa_parts = []
        for word in words:
            clean = "".join(c for c in word if c.isalpha())
            if not clean:
                continue
            phonemes, _ = self.lookup(clean)
            ipa_word = []
            for p in phonemes:
                ipa = arpabet_to_ipa(p)
                if ipa:
                    ipa_word.append(ipa)
            ipa_parts.append("".join(ipa_word))
        return " ".join(ipa_parts)

    def lookup_with_flags(self, text: str) -> list[tuple[str, list[str], bool]]:
        words = text.split()
        result = []
        for word in words:
            clean = "".join(c for c in word if c.isalpha())
            if not clean:
                result.append((word, [], True))
                continue
            phonemes, is_known = self.lookup(clean)
            result.append((word, phonemes, is_known))
        return result
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_dictionary.py tests/test_phonemes.py -v
```

Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add src/data/dictionary.py src/data/phonemes.py tests/test_dictionary.py tests/test_phonemes.py data/cmudict.txt
git commit -m "feat: CMU dictionary with G2P fallback and phoneme inventory"
```

---

### Task 7: Voice Presets

**Files:**
- Create: `src/utils/presets.py`
- Create: `tests/test_presets.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_presets.py`:
```python
import json
from pathlib import Path
from src.utils.presets import PresetManager, Preset


def test_builtin_presets_exist():
    pm = PresetManager(config_dir=Path("/tmp/whooshy-test-presets"))
    builtins = pm.get_builtin_presets()
    assert len(builtins) > 0
    assert any(p.voice_id == "af_heart" for p in builtins)


def test_save_and_load_custom(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="My Voice", voice_id="am_adam", pitch=-20, speed=10, depth=30)
    pm.save_preset(preset)
    loaded = pm.get_custom_presets()
    assert len(loaded) == 1
    assert loaded[0].name == "My Voice"
    assert loaded[0].pitch == -20


def test_delete_custom(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="Temp", voice_id="af_heart", pitch=0, speed=0, depth=0)
    pm.save_preset(preset)
    assert len(pm.get_custom_presets()) == 1
    pm.delete_preset("Temp")
    assert len(pm.get_custom_presets()) == 0


def test_all_presets_builtins_first(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="Custom", voice_id="af_heart", pitch=5, speed=5, depth=5)
    pm.save_preset(preset)
    all_presets = pm.get_all_presets()
    builtin_count = len(pm.get_builtin_presets())
    assert all_presets[0].is_builtin
    assert not all_presets[builtin_count].is_builtin
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_presets.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement voice presets**

Create `src/utils/presets.py`:
```python
import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Preset:
    name: str
    voice_id: str
    pitch: int = 0
    speed: int = 0
    depth: int = 0
    is_builtin: bool = False


_BUILTIN_VOICES = [
    ("Heart (F)", "af_heart"),
    ("Bella (F)", "af_bella"),
    ("Nova (F)", "af_nova"),
    ("Sarah (F)", "af_sarah"),
    ("Nicole (F)", "af_nicole"),
    ("Sky (F)", "af_sky"),
    ("River (F)", "af_river"),
    ("Adam (M)", "am_adam"),
    ("Michael (M)", "am_michael"),
    ("Eric (M)", "am_eric"),
    ("Liam (M)", "am_liam"),
    ("Alice (BF)", "bf_alice"),
    ("Emma (BF)", "bf_emma"),
    ("Daniel (BM)", "bm_daniel"),
    ("George (BM)", "bm_george"),
]


class PresetManager:
    def __init__(self, config_dir: Path | None = None):
        self._dir = config_dir or Path.home() / ".config" / "whooshy" / "presets"
        self._dir.mkdir(parents=True, exist_ok=True)

    def get_builtin_presets(self) -> list[Preset]:
        return [
            Preset(name=name, voice_id=vid, is_builtin=True)
            for name, vid in _BUILTIN_VOICES
        ]

    def get_custom_presets(self) -> list[Preset]:
        presets = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                presets.append(Preset(
                    name=data["name"],
                    voice_id=data["voice_id"],
                    pitch=data.get("pitch", 0),
                    speed=data.get("speed", 0),
                    depth=data.get("depth", 0),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return presets

    def get_all_presets(self) -> list[Preset]:
        return self.get_builtin_presets() + self.get_custom_presets()

    def save_preset(self, preset: Preset):
        safe_name = "".join(c if c.isalnum() else "_" for c in preset.name)
        path = self._dir / f"{safe_name}.json"
        data = {"name": preset.name, "voice_id": preset.voice_id,
                "pitch": preset.pitch, "speed": preset.speed, "depth": preset.depth}
        path.write_text(json.dumps(data, indent=2))

    def delete_preset(self, name: str):
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        path = self._dir / f"{safe_name}.json"
        if path.exists():
            path.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_presets.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/utils/presets.py tests/test_presets.py
git commit -m "feat: voice presets with save/load/delete"
```

---

### Task 8: App Shell + Tab 1 (Simple)

**Files:**
- Modify: `src/main.py`
- Create: `src/app.py`
- Create: `src/tabs/simple_tab.py`

This is the main GUI task. No unit tests for GUI — verify manually by running the app.

- [ ] **Step 1: Implement the main window shell**

Create `src/app.py`:
```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTabWidget, QLabel, QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import PresetManager, Preset
from src.tabs.simple_tab import SimpleTab
from src.tabs.custom_tab import CustomTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whooshy")
        self.setMinimumSize(700, 500)

        self._engine = TTSEngine()
        self._player = AudioPlayer(self)
        self._presets = PresetManager()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)

        # Voice header
        header = QHBoxLayout()
        header.addWidget(QLabel("Voice:"))
        self._voice_combo = QComboBox()
        self._voice_combo.setMinimumWidth(200)
        self._populate_voices()
        header.addWidget(self._voice_combo)
        header.addStretch()
        save_btn = QPushButton("Save Preset")
        save_btn.clicked.connect(self._save_preset)
        header.addWidget(save_btn)
        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        self._simple_tab = SimpleTab(self._engine, self._player, self)
        self._custom_tab = CustomTab(self._engine, self._player, self)
        self._tabs.addTab(self._simple_tab, "Simple")
        self._tabs.addTab(self._custom_tab, "Custom")
        layout.addWidget(self._tabs)

        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)

    def _populate_voices(self):
        self._voice_combo.clear()
        for preset in self._presets.get_all_presets():
            label = f"{'⭐ ' if not preset.is_builtin else ''}{preset.name}"
            self._voice_combo.addItem(label if not preset.is_builtin else preset.name, preset)
        self._voice_combo.setCurrentIndex(0)

    def _on_voice_changed(self, index):
        if index < 0:
            return
        preset = self._voice_combo.itemData(index)
        if preset:
            self._simple_tab.apply_preset(preset)
            self._custom_tab.apply_preset(preset)

    def get_current_voice_id(self) -> str:
        preset = self._voice_combo.currentData()
        if preset:
            return preset.voice_id
        return "af_heart"

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        current_tab = self._tabs.currentWidget()
        sliders = current_tab.get_slider_values()
        preset = Preset(
            name=name.strip(),
            voice_id=self.get_current_voice_id(),
            pitch=sliders["pitch"],
            speed=sliders["speed"],
            depth=sliders["depth"],
        )
        self._presets.save_preset(preset)
        self._populate_voices()
```

- [ ] **Step 2: Implement Tab 1 (Simple)**

Create `src/tabs/simple_tab.py`:
```python
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QSlider, QLabel, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor

import numpy as np

from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all, slider_to_speed
from src.data.dictionary import Dictionary
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav
from src.utils.presets import Preset


class SynthWorker(QThread):
    finished = Signal(np.ndarray, int)
    error = Signal(str)

    def __init__(self, engine, text, voice, speed):
        super().__init__()
        self._engine = engine
        self._text = text
        self._voice = voice
        self._speed = speed

    def run(self):
        try:
            audio, sr = self._engine.synthesize_text(
                self._text, voice=self._voice, speed=self._speed
            )
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))


class SimpleTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._dict = Dictionary()
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000
        self._save_dir = Path.home() / "Music" / "Whooshy"
        self._worker: SynthWorker | None = None

        layout = QVBoxLayout(self)

        # Text area
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Type or paste text here...")
        layout.addWidget(self._text_edit)

        self._highlight_timer = QTimer()
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(300)
        self._highlight_timer.timeout.connect(self._highlight_unknown_words)
        self._text_edit.textChanged.connect(self._highlight_timer.start)

        # Sliders
        slider_layout = QHBoxLayout()
        self._pitch_slider, pitch_group = self._make_slider("Pitch")
        self._speed_slider, speed_group = self._make_slider("Speed")
        self._depth_slider, depth_group = self._make_slider("Depth")
        slider_layout.addLayout(pitch_group)
        slider_layout.addLayout(speed_group)
        slider_layout.addLayout(depth_group)
        layout.addLayout(slider_layout)

        # Controls
        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇ Export WAV")
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        self._dir_label = QPushButton(f"📁 {self._save_dir}")
        self._dir_label.setFlat(True)
        self._dir_label.clicked.connect(self._choose_dir)
        controls.addWidget(self._dir_label)
        layout.addLayout(controls)

        # Status
        self._status = QLabel("")
        layout.addWidget(self._status)

        self._player.state_changed.connect(self._on_playback_state)

    def _make_slider(self, name: str) -> tuple[QSlider, QVBoxLayout]:
        group = QVBoxLayout()
        label = QLabel(f"{name}: 0")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.valueChanged.connect(lambda v, lbl=label, n=name: lbl.setText(f"{n}: {v}"))
        group.addWidget(label)
        group.addWidget(slider)
        return slider, group

    def get_slider_values(self) -> dict[str, int]:
        return {
            "pitch": self._pitch_slider.value(),
            "speed": self._speed_slider.value(),
            "depth": self._depth_slider.value(),
        }

    def apply_preset(self, preset: Preset):
        self._pitch_slider.setValue(preset.pitch)
        self._speed_slider.setValue(preset.speed)
        self._depth_slider.setValue(preset.depth)

    def _highlight_unknown_words(self):
        text = self._text_edit.toPlainText()
        if not text.strip():
            return
        cursor = self._text_edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        default_fmt = QTextCharFormat()
        cursor.setCharFormat(default_fmt)
        cursor.clearSelection()

        flagged_fmt = QTextCharFormat()
        flagged_fmt.setBackground(QColor(85, 51, 51))
        flagged_fmt.setForeground(QColor(255, 153, 153))

        pos = 0
        for word, _, is_known in self._dict.lookup_with_flags(text):
            idx = text.find(word, pos)
            if idx == -1:
                continue
            if not is_known and any(c.isalpha() for c in word):
                cursor.setPosition(idx)
                cursor.setPosition(idx + len(word), QTextCursor.KeepAnchor)
                cursor.setCharFormat(flagged_fmt)
            pos = idx + len(word)
        cursor.endEditBlock()

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return

        text = self._text_edit.toPlainText().strip()
        if not text:
            self._status.setText("No text to speak.")
            return

        self._status.setText("Synthesizing...")
        self._play_btn.setEnabled(False)

        speed = slider_to_speed(self._speed_slider.value())
        voice = self.window().get_current_voice_id()

        self._worker = SynthWorker(self._engine, text, voice, speed)
        self._worker.finished.connect(self._on_synth_done)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    def _on_synth_done(self, audio: np.ndarray, sr: int):
        pitch = self._pitch_slider.value()
        depth = self._depth_slider.value()
        audio = apply_all(audio, sr, pitch=pitch, depth=depth)

        self._last_audio = audio
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._play_btn.setEnabled(True)
        self._status.setText(f"Playing ({len(audio)/sr:.1f}s)")

    def _on_synth_error(self, msg: str):
        self._play_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")

    def _on_stop(self):
        self._player.stop()

    def _on_playback_state(self, state: str):
        if state == "playing":
            self._play_btn.setText("⏸ Pause")
        elif state == "paused":
            self._play_btn.setText("▶ Resume")
        else:
            self._play_btn.setText("▶ Play")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Press Play first.")
            return
        path = export_wav(self._last_audio, self._last_sr, self._save_dir)
        self._status.setText(f"Exported: {path.name}")

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save Directory", str(self._save_dir))
        if d:
            self._save_dir = Path(d)
            self._dir_label.setText(f"📁 {self._save_dir}")
```

- [ ] **Step 3: Update main.py entry point**

Replace `src/main.py`:
```python
import sys

from PySide6.QtWidgets import QApplication

from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create a stub custom_tab.py so the app can launch**

Create `src/tabs/custom_tab.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import Preset


class CustomTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Custom tab — coming next task"))

    def apply_preset(self, preset: Preset):
        pass

    def get_slider_values(self) -> dict[str, int]:
        return {"pitch": 0, "speed": 0, "depth": 0}
```

- [ ] **Step 5: Run the app and manually test Tab 1**

```bash
cd /home/sin/Projects/whooshy-project && .venv/bin/python3 -m src.main
```

Test checklist:
1. Window opens with voice dropdown and two tabs
2. Type "Hello world" → unknown word highlighting works (or doesn't flag known words)
3. Click Play → audio synthesizes and plays
4. Move pitch slider → next Play sounds different
5. Click Export WAV → file created in ~/Music/Whooshy/
6. Click save directory → file dialog opens
7. Pause/Resume/Stop work during playback

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/app.py src/tabs/simple_tab.py src/tabs/custom_tab.py
git commit -m "feat: main window shell + Tab 1 (simple text-to-speech)"
```

---

### Task 9: Tab 2 (Custom Phoneme Builder)

**Files:**
- Modify: `src/tabs/custom_tab.py` (replace stub)

- [ ] **Step 1: Implement the full custom tab**

Replace `src/tabs/custom_tab.py`:
```python
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGridLayout,
    QSlider, QLabel, QScrollArea, QFileDialog, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent

import numpy as np

from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all, slider_to_speed
from src.data.phonemes import PHONEMES, arpabet_sequence_to_ipa, PAUSE_TOKEN
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav
from src.utils.presets import Preset


class PhonemeWorker(QThread):
    finished = Signal(np.ndarray, int)
    error = Signal(str)

    def __init__(self, engine, ipa_text, voice, speed):
        super().__init__()
        self._engine = engine
        self._ipa_text = ipa_text
        self._voice = voice
        self._speed = speed

    def run(self):
        try:
            audio, sr = self._engine.synthesize_phonemes(
                self._ipa_text, voice=self._voice, speed=self._speed
            )
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))


class AnalyzeWorker(QThread):
    finished = Signal(int, int, int)
    error = Signal(str)

    def __init__(self, file_path):
        super().__init__()
        self._file_path = file_path

    def run(self):
        try:
            from src.engine.analyzer import analyze_reference
            pitch, speed, depth = analyze_reference(self._file_path)
            self.finished.emit(pitch, speed, depth)
        except Exception as e:
            self.error.emit(str(e))


class PhonemeTag(QPushButton):
    def __init__(self, arpabet: str, index: int, parent=None):
        super().__init__(arpabet, parent)
        self.arpabet = arpabet
        self.index = index
        self.setFixedHeight(26)
        self.setStyleSheet(
            "background: #2a3a4a; color: #8cf; border: 1px solid #445; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px;"
        )


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(60)
        self.setStyleSheet(
            "background: #1a1a2a; border: 2px dashed #333; border-radius: 6px;"
        )
        self._label = QLabel("🎵 Drop audio file to match voice characteristics", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: #555; border: none;")
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "background: #1a2a1a; border: 2px dashed #5a5; border-radius: 6px;"
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "background: #1a1a2a; border: 2px dashed #333; border-radius: 6px;"
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "background: #1a1a2a; border: 2px dashed #333; border-radius: 6px;"
        )
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._label.setText(f"🎵 {Path(path).name}")
            self.file_dropped.emit(path)


class CustomTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._sequence: list[str] = []
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000
        self._save_dir = Path.home() / "Music" / "Whooshy"
        self._worker: PhonemeWorker | None = None

        layout = QVBoxLayout(self)

        # Phoneme buttons
        layout.addWidget(QLabel("PHONEME BUTTONS"))
        btn_widget = QWidget()
        btn_layout = self._build_phoneme_grid(btn_widget)
        btn_widget.setLayout(btn_layout)
        layout.addWidget(btn_widget)

        # Sequence bar
        layout.addWidget(QLabel("PHONEME SEQUENCE"))
        self._seq_scroll = QScrollArea()
        self._seq_scroll.setWidgetResizable(True)
        self._seq_scroll.setFixedHeight(50)
        self._seq_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._seq_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._seq_widget = QWidget()
        self._seq_layout = QHBoxLayout(self._seq_widget)
        self._seq_layout.setContentsMargins(4, 4, 4, 4)
        self._seq_layout.setSpacing(3)
        self._seq_layout.addStretch()
        self._seq_scroll.setWidget(self._seq_widget)
        layout.addWidget(self._seq_scroll)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_sequence)
        layout.addWidget(clear_btn)

        # Reference audio drop zone
        layout.addWidget(QLabel("REFERENCE AUDIO"))
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        layout.addWidget(self._drop_zone)

        # Sliders
        slider_layout = QHBoxLayout()
        self._pitch_slider, pitch_group = self._make_slider("Pitch")
        self._speed_slider, speed_group = self._make_slider("Speed")
        self._depth_slider, depth_group = self._make_slider("Depth")
        slider_layout.addLayout(pitch_group)
        slider_layout.addLayout(speed_group)
        slider_layout.addLayout(depth_group)
        layout.addLayout(slider_layout)

        # Controls
        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇ Export WAV")
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        self._dir_label = QPushButton(f"📁 {self._save_dir}")
        self._dir_label.setFlat(True)
        self._dir_label.clicked.connect(self._choose_dir)
        controls.addWidget(self._dir_label)
        layout.addLayout(controls)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._player.state_changed.connect(self._on_playback_state)

    def _build_phoneme_grid(self, parent) -> QHBoxLayout:
        container = QHBoxLayout()
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(3)

        col = 0
        row = 0
        max_cols = 12
        colors = {
            "vowel": ("background: #2a3a4a; color: #8cf;", "#445"),
            "consonant": ("background: #3a2a4a; color: #c8f;", "#545"),
            "pause": ("background: #333; color: #999;", "#555"),
        }

        for phoneme in PHONEMES:
            cat = phoneme["category"]
            style_base, border = colors.get(cat, ("background: #333; color: #ccc;", "#555"))
            btn = QPushButton(phoneme["arpabet"])
            btn.setToolTip(f"{phoneme['example']}")
            btn.setFixedSize(42, 28)
            btn.setStyleSheet(
                f"{style_base} border: 1px solid {border}; "
                f"border-radius: 3px; font-size: 10px; font-weight: bold;"
            )
            arp = phoneme["arpabet"]
            btn.clicked.connect(lambda checked=False, a=arp: self._add_phoneme(a))
            grid.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        container.addWidget(inner)
        return container

    def _add_phoneme(self, arpabet: str):
        self._sequence.append(arpabet)
        self._rebuild_sequence_bar()

    def _remove_phoneme(self, index: int):
        if 0 <= index < len(self._sequence):
            self._sequence.pop(index)
            self._rebuild_sequence_bar()

    def _clear_sequence(self):
        self._sequence.clear()
        self._rebuild_sequence_bar()

    def _rebuild_sequence_bar(self):
        while self._seq_layout.count() > 0:
            item = self._seq_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, arp in enumerate(self._sequence):
            tag = PhonemeTag(arp, i)
            tag.clicked.connect(lambda checked=False, idx=i: self._remove_phoneme(idx))
            self._seq_layout.addWidget(tag)
        self._seq_layout.addStretch()

    def _make_slider(self, name: str) -> tuple[QSlider, QVBoxLayout]:
        group = QVBoxLayout()
        label = QLabel(f"{name}: 0")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.valueChanged.connect(lambda v, lbl=label, n=name: lbl.setText(f"{n}: {v}"))
        group.addWidget(label)
        group.addWidget(slider)
        return slider, group

    def get_slider_values(self) -> dict[str, int]:
        return {
            "pitch": self._pitch_slider.value(),
            "speed": self._speed_slider.value(),
            "depth": self._depth_slider.value(),
        }

    def apply_preset(self, preset: Preset):
        self._pitch_slider.setValue(preset.pitch)
        self._speed_slider.setValue(preset.speed)
        self._depth_slider.setValue(preset.depth)

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return

        if not self._sequence:
            self._status.setText("No phonemes in sequence.")
            return

        ipa_text = arpabet_sequence_to_ipa(self._sequence)
        if not ipa_text.strip():
            self._status.setText("Could not convert phonemes to IPA.")
            return

        self._status.setText("Synthesizing...")
        self._play_btn.setEnabled(False)

        speed = slider_to_speed(self._speed_slider.value())
        voice = self.window().get_current_voice_id()

        self._worker = PhonemeWorker(self._engine, ipa_text, voice, speed)
        self._worker.finished.connect(self._on_synth_done)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    def _on_synth_done(self, audio: np.ndarray, sr: int):
        pitch = self._pitch_slider.value()
        depth = self._depth_slider.value()
        audio = apply_all(audio, sr, pitch=pitch, depth=depth)

        self._last_audio = audio
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._play_btn.setEnabled(True)
        self._status.setText(f"Playing ({len(audio)/sr:.1f}s)")

    def _on_synth_error(self, msg: str):
        self._play_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")

    def _on_stop(self):
        self._player.stop()

    def _on_playback_state(self, state: str):
        if state == "playing":
            self._play_btn.setText("⏸ Pause")
        elif state == "paused":
            self._play_btn.setText("▶ Resume")
        else:
            self._play_btn.setText("▶ Play")

    def _on_file_dropped(self, file_path: str):
        self._status.setText(f"Analyzing {Path(file_path).name}...")
        self._analyze_worker = AnalyzeWorker(file_path)
        self._analyze_worker.finished.connect(self._on_analysis_done)
        self._analyze_worker.error.connect(self._on_analysis_error)
        self._analyze_worker.start()

    def _on_analysis_done(self, pitch: int, speed: int, depth: int):
        self._pitch_slider.setValue(pitch)
        self._speed_slider.setValue(speed)
        self._depth_slider.setValue(depth)
        self._status.setText("Sliders adjusted to match reference audio.")

    def _on_analysis_error(self, msg: str):
        self._status.setText(f"Analysis error: {msg}")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Press Play first.")
            return
        path = export_wav(self._last_audio, self._last_sr, self._save_dir)
        self._status.setText(f"Exported: {path.name}")

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save Directory", str(self._save_dir))
        if d:
            self._save_dir = Path(d)
            self._dir_label.setText(f"📁 {self._save_dir}")
```

- [ ] **Step 2: Run the app and test Tab 2**

```bash
cd /home/sin/Projects/whooshy-project && .venv/bin/python3 -m src.main
```

Test checklist:
1. Tab 2 shows phoneme buttons color-coded by category
2. Clicking a button adds it to the sequence bar
3. Clicking a tag in the sequence bar removes it
4. Clear All empties the sequence
5. Play synthesizes the phoneme sequence and plays audio
6. Sliders affect the output
7. Export WAV works
8. Drop zone accepts audio files (test in next task)

- [ ] **Step 3: Commit**

```bash
git add src/tabs/custom_tab.py
git commit -m "feat: Tab 2 custom phoneme builder with sequence bar"
```

---

### Task 10: Reference Audio Analyzer

**Files:**
- Create: `src/engine/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_analyzer.py`:
```python
import numpy as np
import soundfile as sf
from pathlib import Path
from src.engine.analyzer import analyze_reference


def _make_test_wav(tmp_path: Path, freq=220.0, duration=2.0, sr=24000) -> Path:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    path = tmp_path / "test.wav"
    sf.write(str(path), audio, sr)
    return path


def test_analyze_returns_three_ints(tmp_path):
    wav = _make_test_wav(tmp_path)
    pitch, speed, depth = analyze_reference(str(wav))
    assert isinstance(pitch, int)
    assert isinstance(speed, int)
    assert isinstance(depth, int)


def test_analyze_values_in_range(tmp_path):
    wav = _make_test_wav(tmp_path)
    pitch, speed, depth = analyze_reference(str(wav))
    assert -100 <= pitch <= 100
    assert -100 <= speed <= 100
    assert -100 <= depth <= 100
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_analyzer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the analyzer**

Create `src/engine/analyzer.py`:
```python
import numpy as np
import librosa


_BASELINE_F0 = 200.0
_BASELINE_TEMPO = 130.0
_BASELINE_FLUX_STD = 0.5


def analyze_reference(file_path: str) -> tuple[int, int, int]:
    y, sr = librosa.load(file_path, sr=24000, mono=True)

    # Pitch: median F0
    f0, voiced, _ = librosa.pyin(y, fmin=50, fmax=600, sr=sr)
    voiced_f0 = f0[voiced & ~np.isnan(f0)]
    if len(voiced_f0) > 0:
        median_f0 = float(np.median(voiced_f0))
        semitone_diff = 12.0 * np.log2(median_f0 / _BASELINE_F0)
        pitch_slider = int(np.clip(semitone_diff * (100.0 / 12.0), -100, 100))
    else:
        pitch_slider = 0

    # Speed: tempo estimation
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0]) if len(tempo) > 0 else _BASELINE_TEMPO
    tempo = float(tempo)
    speed_ratio = tempo / _BASELINE_TEMPO
    speed_slider = int(np.clip((speed_ratio - 1.0) * 200.0, -100, 100))

    # Depth: spectral flux variance as expressiveness proxy
    spec = np.abs(librosa.stft(y))
    flux = np.sqrt(np.mean(np.diff(spec, axis=1) ** 2, axis=0))
    flux_std = float(np.std(flux)) if len(flux) > 0 else _BASELINE_FLUX_STD
    depth_ratio = flux_std / _BASELINE_FLUX_STD
    depth_slider = int(np.clip((depth_ratio - 1.0) * 100.0, -100, 100))

    return pitch_slider, speed_slider, depth_slider
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_analyzer.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/engine/analyzer.py tests/test_analyzer.py
git commit -m "feat: reference audio analyzer for voice matching"
```

---

### Task 11: Integration Polish + Config Persistence

**Files:**
- Create: `src/utils/config.py`
- Modify: `src/app.py` (add config save/load)

- [ ] **Step 1: Implement config persistence**

Create `src/utils/config.py`:
```python
import json
from pathlib import Path


_CONFIG_DIR = Path.home() / ".config" / "whooshy"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

_DEFAULTS = {
    "save_dir": str(Path.home() / "Music" / "Whooshy"),
    "last_voice": "af_heart",
    "window_width": 700,
    "window_height": 500,
}


def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            return {**_DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def save_config(config: dict):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(config, indent=2))
```

- [ ] **Step 2: Wire config into MainWindow**

Add to `src/app.py` — import config at the top:
```python
from src.utils.config import load_config, save_config
```

In `MainWindow.__init__`, after setting up tabs, add:
```python
        self._config = load_config()
        self.resize(self._config["window_width"], self._config["window_height"])
```

Add a `closeEvent` override to save state:
```python
    def closeEvent(self, event):
        self._config["window_width"] = self.width()
        self._config["window_height"] = self.height()
        preset = self._voice_combo.currentData()
        if preset:
            self._config["last_voice"] = preset.voice_id
        save_config(self._config)
        self._player.stop()
        event.accept()
```

- [ ] **Step 3: Run the full app end-to-end**

```bash
cd /home/sin/Projects/whooshy-project && .venv/bin/python3 -m src.main
```

Full test checklist:
1. **Tab 1**: Type text → Play → hear speech → Pause → Resume → Stop
2. **Tab 1**: Move pitch slider → Play → pitch is shifted
3. **Tab 1**: Move depth slider → Play → expressiveness changes
4. **Tab 1**: Unknown word shows red highlight
5. **Tab 1**: Export WAV → file appears in directory
6. **Tab 2**: Click phonemes → sequence builds up
7. **Tab 2**: Click tag → removes from sequence
8. **Tab 2**: Play phoneme sequence → hear synthesized audio
9. **Tab 2**: Drop audio file → sliders auto-adjust
10. **Voice**: Change voice dropdown → different voice
11. **Preset**: Save preset → appears in dropdown
12. **Config**: Close → reopen → window size preserved

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python3 -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/utils/config.py src/app.py
git commit -m "feat: config persistence and integration polish"
```

---

### Task 12: Packaging (AppImage + .deb + Windows .exe)

**Files:**
- Create: `build/appimage/AppImageBuilder.yml`
- Create: `build/pyinstaller/whooshy.spec`
- Create: `build/build.sh`

- [ ] **Step 1: Create PyInstaller spec for Linux + Windows**

Create `build/pyinstaller/whooshy.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

block_cipher = None
project_root = Path(os.path.abspath(SPECPATH)).parent.parent

a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'data' / 'models' / 'kokoro-v1.0.onnx'), 'data/models'),
        (str(project_root / 'data' / 'models' / 'voices-v1.0.bin'), 'data/models'),
        (str(project_root / 'data' / 'cmudict.txt'), 'data'),
    ],
    hiddenimports=[
        'kokoro_onnx',
        'onnxruntime',
        'sounddevice',
        'soundfile',
        'librosa',
        'numpy',
        'PySide6',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='whooshy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='whooshy',
)
```

- [ ] **Step 2: Create build script**

Create `build/build.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Installing build deps ==="
.venv/bin/pip install pyinstaller

echo "=== Building with PyInstaller ==="
.venv/bin/pyinstaller build/pyinstaller/whooshy.spec --distpath dist/ --workpath build/tmp --clean

echo "=== Build complete ==="
ls -lah dist/whooshy/
echo ""
echo "Run with: ./dist/whooshy/whooshy"
```

```bash
chmod +x build/build.sh
```

- [ ] **Step 3: Test the build**

```bash
cd /home/sin/Projects/whooshy-project && bash build/build.sh
```

Expected: `dist/whooshy/` directory with the executable and all bundled files.

```bash
./dist/whooshy/whooshy
```

Verify the app launches and works identically to the dev version.

- [ ] **Step 4: Commit**

```bash
git add build/
git commit -m "feat: PyInstaller packaging for Linux and Windows builds"
```

- [ ] **Step 5: Create .deb packaging notes**

Create `build/deb/README.md`:
```markdown
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
```

- [ ] **Step 6: Commit**

```bash
git add build/deb/
git commit -m "docs: .deb packaging instructions"
```
