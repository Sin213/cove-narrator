import numpy as np

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
    import librosa  # lazy: optional runtime dep, not bundled in frozen build

    y, sr = librosa.load(file_path, sr=24000, mono=True)

    f0, voiced, _ = librosa.pyin(y, fmin=50, fmax=600, sr=sr)
    voiced_f0 = f0[voiced & ~np.isnan(f0)]

    if len(voiced_f0) > 0:
        median_f0 = float(np.median(voiced_f0))
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

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0]) if len(tempo) > 0 else _BASELINE_TEMPO
    tempo = max(float(tempo), 1.0)
    speed_ratio = tempo / _BASELINE_TEMPO
    speed_slider = int(np.clip((speed_ratio - 1.0) * 100.0, -100, 100))

    spec = np.abs(librosa.stft(y))
    flux = np.sqrt(np.mean(np.diff(spec, axis=1) ** 2, axis=0))
    flux_std = float(np.std(flux)) if len(flux) > 0 else _BASELINE_FLUX_STD
    depth_ratio = flux_std / _BASELINE_FLUX_STD
    depth_slider = int(np.clip((depth_ratio - 1.0) * 100.0, -100, 100))

    return pitch_slider, speed_slider, depth_slider, gender, median_f0
