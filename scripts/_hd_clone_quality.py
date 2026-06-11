r"""Reproduce the HD clone from source with a REAL speech reference (generated
by kokoro) and report objective speech-likeness stats on the output, to tell
whether the 'gibberish' is a code bug or a CPU/reference artefact.

Run: .\.hdtest\Scripts\python.exe scripts\_hd_clone_quality.py
"""
import os
import sys
import traceback

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def log(m):
    print(m, flush=True)


def speech_stats(y, sr, label):
    from src.engine import audio_features as af
    import numpy as np
    f0, voiced = af.estimate_f0(y, sr)
    vr = float(voiced.mean()) if len(voiced) else 0.0
    vf = f0[voiced & ~np.isnan(f0)] if len(f0) else np.array([])
    med = float(np.median(vf)) if len(vf) else 0.0
    rms = float(np.sqrt(np.mean(y.astype("float64") ** 2)))
    log(f"  [{label}] dur={len(y)/sr:.2f}s  voiced={vr*100:.0f}%  "
        f"medianF0={med:.0f}Hz  rms={rms:.3f}  peak={float(np.max(np.abs(y))):.3f}")
    return vr, med


def main():
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    # 1) Real speech reference via kokoro
    log("=== generating real speech reference (kokoro) ===")
    kok = Kokoro(os.path.join(_ROOT, "data/models/kokoro-v1.0.onnx"),
                 os.path.join(_ROOT, "data/models/voices-v1.0.bin"))
    ref_text = "Hello, my name is Jordan and this is a sample of my speaking voice."
    samples, sr = kok.create(ref_text, voice="am_michael", speed=1.0, lang="en-us")
    ref_path = os.path.join(_ROOT, ".hdtest_realref.wav")
    sf.write(ref_path, samples, sr)
    speech_stats(np.asarray(samples), sr, "reference")

    # 2) Clone it
    from src.engine.clone_tts import QwenCloneEngine
    eng = QwenCloneEngine()
    log("=== load() ===")
    eng.load(progress_cb=log)
    text = "The quick brown fox jumps over the lazy dog."
    log(f"=== synthesize: {text!r} (expect ~3-4s of intelligible speech) ===")
    audio, out_sr = eng.synthesize(text, ref_path)
    out_path = os.path.join(_ROOT, ".hdtest_realclone.wav")
    sf.write(out_path, audio, out_sr)
    log(f"saved clone -> {out_path}")
    speech_stats(audio, out_sr, "clone-output")
    log("\nIf clone dur >> a few seconds and voiced% is low/erratic, the "
        "vocoder/tokenizer path is producing garbage (code bug). If it looks "
        "like speech (~40-70% voiced, F0 80-200Hz, sane duration), the pipeline "
        "is correct and 'gibberish' is reference/quality-related.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
