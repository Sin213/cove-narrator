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
    pitch, speed, depth, gender, median_f0 = analyze_reference(str(wav))
    assert isinstance(pitch, int)
    assert isinstance(speed, int)
    assert isinstance(depth, int)
    assert gender in ("F", "M")
    assert isinstance(median_f0, float)
    assert median_f0 > 0


def test_analyze_values_in_range(tmp_path):
    wav = _make_test_wav(tmp_path)
    pitch, speed, depth, gender, median_f0 = analyze_reference(str(wav))
    assert -100 <= pitch <= 100
    assert -100 <= speed <= 100
    assert -100 <= depth <= 100
