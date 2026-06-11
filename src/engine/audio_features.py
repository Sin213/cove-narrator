"""Pure numpy/scipy audio feature extraction — replaces librosa for the
voice-match analysis. librosa drags in numba/llvmlite and does not bundle
cleanly under PyInstaller, so the portable build ships without it (same reason
the qwen_tts mel filterbanks were reimplemented in numpy).

Only the features the voice-match needs are implemented: mono load+resample,
median F0 (YIN), a rough tempo, and a spectral-flux 'depth' statistic. soundfile
and scipy are already bundled.
"""
import numpy as np


def load_audio(path: str, sr: int = 24000) -> tuple[np.ndarray, int]:
    """Load mono float32 audio resampled to `sr`. Replaces librosa.load."""
    import soundfile as sf
    y, file_sr = sf.read(path, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1).astype(np.float32)
    if file_sr != sr:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(file_sr), int(sr))
        y = resample_poly(y, sr // g, file_sr // g).astype(np.float32)
    return np.ascontiguousarray(y, dtype=np.float32), sr


def _difference_function(x: np.ndarray, tau_max: int) -> np.ndarray:
    """YIN squared-difference function via FFT autocorrelation (O(W log W))."""
    W = len(x)
    x = x.astype(np.float64)
    cumsq = np.concatenate(([0.0], np.cumsum(x * x)))
    nfft = 1
    while nfft < 2 * W:
        nfft <<= 1
    X = np.fft.rfft(x, nfft)
    acf = np.fft.irfft(X * np.conj(X), nfft)[:tau_max + 1]
    tau = np.arange(tau_max + 1)
    return cumsq[W - tau] + (cumsq[W] - cumsq[tau]) - 2 * acf


def estimate_f0(y, sr, fmin=50.0, fmax=600.0, frame_length=2048,
                hop_length=256):
    """Per-frame fundamental frequency via the YIN algorithm. Returns
    (f0, voiced_mask). Drop-in for the median-F0 use of librosa.pyin;
    validated within ~0.6 Hz of librosa across 90-250 Hz."""
    tau_min = int(sr / fmax)
    tau_max = min(int(sr / fmin), frame_length - 1)
    n = len(y)
    if n < frame_length:
        return np.array([]), np.array([], dtype=bool)
    f0, voiced = [], []
    for start in range(0, n - frame_length, hop_length):
        d = _difference_function(y[start:start + frame_length], tau_max)
        cmnd = np.ones(tau_max + 1)
        running = 0.0
        for tau in range(1, tau_max + 1):
            running += d[tau]
            cmnd[tau] = d[tau] * tau / running if running > 0 else 1.0
        thr = 0.15
        tau_est = -1
        t = tau_min
        while t <= tau_max:
            if cmnd[t] < thr:
                while t + 1 <= tau_max and cmnd[t + 1] < cmnd[t]:
                    t += 1
                tau_est = t
                break
            t += 1
        if tau_est == -1:
            tau_est = tau_min + int(np.argmin(cmnd[tau_min:tau_max + 1]))
            if cmnd[tau_est] > 0.5:
                f0.append(np.nan)
                voiced.append(False)
                continue
        if tau_min < tau_est < tau_max:
            a, b, c = cmnd[tau_est - 1], cmnd[tau_est], cmnd[tau_est + 1]
            denom = a - 2 * b + c
            if denom != 0:
                tau_est = tau_est + 0.5 * (a - c) / denom
        f0.append(sr / tau_est)
        voiced.append(True)
    return np.array(f0), np.array(voiced, dtype=bool)


def median_f0(y, sr, fmin=50.0, fmax=600.0):
    """Median F0 over voiced frames, or None if unvoiced. Replaces the common
    `librosa.pyin(...) -> median` idiom."""
    f0, voiced = estimate_f0(y, sr, fmin, fmax)
    vf = f0[voiced & ~np.isnan(f0)]
    return float(np.median(vf)) if len(vf) > 0 else None


def _stft_mag(y, n_fft=2048, hop=512):
    win = np.hanning(n_fft).astype(np.float32)
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    cols = 1 + (len(y) - n_fft) // hop
    mag = np.empty((n_fft // 2 + 1, cols), dtype=np.float32)
    for j in range(cols):
        seg = y[j * hop:j * hop + n_fft] * win
        mag[:, j] = np.abs(np.fft.rfft(seg))
    return mag


def spectral_flux_std(y) -> float:
    """Std of frame-to-frame spectral flux ('depth' heuristic). Replaces the
    librosa.stft-based computation."""
    spec = _stft_mag(y)
    if spec.shape[1] < 2:
        return 0.0
    flux = np.sqrt(np.mean(np.diff(spec, axis=1) ** 2, axis=0))
    return float(np.std(flux)) if len(flux) else 0.0


def estimate_tempo(y, sr, baseline=100.0) -> float:
    """Rough global tempo (BPM) via onset-envelope autocorrelation. Replaces
    librosa.beat.beat_track for the 'speed' heuristic (approximate)."""
    hop = 512
    spec = _stft_mag(y, n_fft=2048, hop=hop)
    flux = np.maximum(0.0, np.diff(spec, axis=1)).sum(axis=0)
    if len(flux) < 4:
        return baseline
    flux = flux - flux.mean()
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    fps = sr / hop
    lag_min = int(fps * 60.0 / 200.0)
    lag_max = min(int(fps * 60.0 / 60.0), len(ac) - 1)
    if lag_max <= lag_min:
        return baseline
    lag = lag_min + int(np.argmax(ac[lag_min:lag_max + 1]))
    return float(60.0 * fps / lag) if lag > 0 else baseline
