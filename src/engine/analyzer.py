import numpy as np

from src.engine import audio_features as af

_F0_FEMALE = 200.0
_F0_MALE = 120.0
_GENDER_THRESHOLD = 165.0

_BASELINE_TEMPO = 100.0
_BASELINE_FLUX_STD = 0.5


def analyze_reference(file_path: str) -> tuple[int, int, int, str, float]:
    """Analyze a reference audio clip and return
    (pitch, speed, depth, gender, median_f0).

    Gender is "F" or "M" based on median F0 of the clip.
    Pitch slider is relative to the detected gender's baseline.
    median_f0 is returned so the caller can pick the closest voice.
    """
    y, sr = af.load_audio(file_path, sr=24000)

    med = af.median_f0(y, sr, fmin=50, fmax=600)

    if med is not None:
        median_f0 = med
        if median_f0 >= _GENDER_THRESHOLD:
            gender = "F"
            baseline_f0 = _F0_FEMALE
        else:
            gender = "M"
            baseline_f0 = _F0_MALE
        semitone_diff = 12.0 * np.log2(median_f0 / baseline_f0)
        pitch_slider = int(np.clip(semitone_diff * (100.0 / 12.0), -100, 100))
    else:
        pitch_slider = 0
        gender = "F"
        median_f0 = _F0_FEMALE

    tempo = max(af.estimate_tempo(y, sr, baseline=_BASELINE_TEMPO), 1.0)
    speed_ratio = tempo / _BASELINE_TEMPO
    speed_slider = int(np.clip((speed_ratio - 1.0) * 100.0, -100, 100))

    flux_std = af.spectral_flux_std(y) or _BASELINE_FLUX_STD
    depth_ratio = flux_std / _BASELINE_FLUX_STD
    depth_slider = int(np.clip((depth_ratio - 1.0) * 100.0, -100, 100))

    return pitch_slider, speed_slider, depth_slider, gender, median_f0
