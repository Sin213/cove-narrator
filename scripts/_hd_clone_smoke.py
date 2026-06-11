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


def main():
    from src.engine.clone_tts import QwenCloneEngine

    eng = QwenCloneEngine()
    log(f"model_dir: {eng.model_dir()}")
    log(f"is_downloaded: {eng.is_downloaded()}")
    if not eng.is_downloaded():
        log("MODEL NOT DOWNLOADED YET — wait for snapshot_download to finish")
        return 2

    ref = os.path.join(_ROOT, ".hdtest_ref.wav")
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
    log(f"SYNTH OK -> {out} samples={len(audio)} sr={sr} "
        f"dur={len(audio)/sr:.2f}s peak={float(np.max(np.abs(audio))):.3f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
