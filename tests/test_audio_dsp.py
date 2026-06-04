import numpy as np
from src.engine.audio_dsp import apply_pitch_shift, apply_depth, slider_to_speed, apply_all

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
    assert len(result) > 0
    assert not np.allclose(audio[:len(result)], result[:len(audio)], atol=0.01)


def test_depth_zero_is_identity():
    audio = _make_tone()
    result = apply_depth(audio, 0)
    np.testing.assert_array_almost_equal(audio, result, decimal=5)


def test_depth_changes_audio():
    audio = _make_tone()
    result = apply_depth(audio, 50)
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert len(result) == len(audio)


def test_apply_all_returns_valid_audio():
    audio = _make_tone()
    result = apply_all(audio, SR, pitch=10, depth=20)
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert len(result) > 0
