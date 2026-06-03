import numpy as np
import librosa


def slider_to_speed(slider: int) -> float:
    if slider < 0:
        return 1.0 + slider * 0.5 / 100.0  # -100 → 0.5, 0 → 1.0
    else:
        return 1.0 + slider * 1.0 / 100.0  # 0 → 1.0, 100 → 2.0


def slider_to_semitones(slider: int) -> float:
    return slider * 12.0 / 100.0


def apply_pitch_shift(audio: np.ndarray, slider: int, sr: int) -> np.ndarray:
    if slider == 0:
        return audio.copy()
    semitones = slider_to_semitones(slider)
    shifted = librosa.effects.pitch_shift(y=audio, sr=sr, n_steps=semitones)
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


def apply_all(audio: np.ndarray, sr: int, pitch: int = 0, depth: int = 0) -> np.ndarray:
    result = audio
    if pitch != 0:
        result = apply_pitch_shift(result, pitch, sr)
    if depth != 0:
        result = apply_depth(result, depth)
    return result
