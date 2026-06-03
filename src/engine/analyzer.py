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
