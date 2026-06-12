r"""Local HD-clone smoke test (not shipped). Runs the real clone path from
source against the downloaded Qwen model + a reference wav, so transformers-5.x
errors surface without building the exe. Run with the pinned .hdtest venv:

    .\.hdtest\Scripts\python.exe scripts\_hd_clone_smoke.py
"""
import os
import sys
import traceback

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def log(m):
    print(m, flush=True)


def _ensure_ref(path):
    """CI has no committed reference wav (.hdtest_* is gitignored). Synthesize a
    short voiced-like mono clip so the clone path has something to extract a
    speaker embedding from. Voice quality is irrelevant — this only drives the
    pipeline so generation can be asserted non-degenerate."""
    if os.path.exists(path):
        return
    import numpy as np
    import soundfile as sf
    sr = 16000
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    f0 = 120.0
    sig = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in (1, 2, 3, 4))
    env = np.minimum(t / 0.05, (3.0 - t) / 0.05).clip(0, 1)
    sig = (0.3 * sig * env).astype("float32")
    sf.write(path, sig, sr)
    log(f"generated synthetic reference wav -> {path}")


def main():
    from src.engine.clone_tts import QwenCloneEngine

    eng = QwenCloneEngine()
    log(f"model_dir: {eng.model_dir()}")
    log(f"is_downloaded: {eng.is_downloaded()}")
    if not eng.is_downloaded():
        log("MODEL NOT DOWNLOADED YET — wait for snapshot_download to finish")
        return 2

    ref = os.path.join(_ROOT, ".hdtest_ref.wav")
    _ensure_ref(ref)
    log(f"ref_audio: {ref} exists={os.path.exists(ref)}")

    log("=== load() ===")
    eng.load(progress_cb=log)
    log("LOAD OK")

    log("=== synthesize() ===")
    audio, sr = eng.synthesize(
        "Hello, this is a test of voice cloning.", ref
    )
    import numpy as np
    import soundfile as sf
    out = os.path.join(_ROOT, ".hdtest_out.wav")
    sf.write(out, audio, sr)
    dur = len(audio) / sr
    peak = float(np.max(np.abs(audio)))
    log(f"SYNTH OK -> {out} samples={len(audio)} sr={sr} "
        f"dur={dur:.2f}s peak={peak:.3f}")

    # Assert non-degenerate output. The transformers-5.x port produced
    # non-stop generation that ran to the length cap; correct 4.57.3 output
    # for this short sentence terminates in a few seconds. A too-long clip or a
    # silent one is a regression. Thresholds are env-overridable for tuning.
    min_peak = float(os.environ.get("SMOKE_MIN_PEAK", "0.01"))
    min_dur = float(os.environ.get("SMOKE_MIN_DUR", "0.4"))
    max_dur = float(os.environ.get("SMOKE_MAX_DUR", "15.0"))
    problems = []
    if peak < min_peak:
        problems.append(f"peak {peak:.4f} < {min_peak} (silent / no speech)")
    if not (min_dur <= dur <= max_dur):
        problems.append(
            f"dur {dur:.2f}s outside [{min_dur}, {max_dur}]s "
            f"(degenerate / non-terminating generation?)")
    if problems:
        log("SMOKE FAIL: " + "; ".join(problems))
        return 3
    log("SMOKE PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
