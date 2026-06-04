import numpy as np
from scipy.signal import resample


def slider_to_speed(slider: int) -> float:
    if slider < 0:
        return 1.0 + slider * 0.5 / 100.0
    else:
        return 1.0 + slider * 1.0 / 100.0


def slider_to_semitones(slider: int) -> float:
    return slider * 4.0 / 100.0


def apply_pitch_shift(audio: np.ndarray, slider: int, sr: int) -> np.ndarray:
    if slider == 0:
        return audio.copy()
    semitones = slider_to_semitones(slider)
    ratio = 2.0 ** (semitones / 12.0)
    resampled_len = int(len(audio) / ratio)
    if resampled_len < 1:
        return audio.copy()
    shifted = resample(audio, resampled_len).astype(np.float32)
    if len(shifted) < len(audio):
        padded = np.zeros(len(audio), dtype=np.float32)
        padded[:len(shifted)] = shifted
        return padded
    return shifted


def apply_depth(audio: np.ndarray, slider: int) -> np.ndarray:
    if slider == 0:
        return audio.copy()
    scale = slider / 100.0
    if scale > 0:
        power = 1.0 - scale * 0.5
    else:
        power = 1.0 - scale * 0.5
    sign = np.sign(audio)
    magnitude = np.abs(audio)
    peak = np.max(magnitude)
    if peak < 1e-8:
        return audio.copy()
    normalized = magnitude / peak
    shaped = np.power(normalized + 1e-10, power)
    result = sign * shaped * peak
    out_peak = np.max(np.abs(result))
    if out_peak > 0:
        result *= peak / out_peak
    return result.astype(np.float32)


def apply_all(audio: np.ndarray, sr: int, pitch: int = 0, depth: int = 0) -> np.ndarray:
    result = audio
    if pitch != 0:
        result = apply_pitch_shift(result, pitch, sr)
    if depth != 0:
        result = apply_depth(result, depth)
    return result
