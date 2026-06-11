r"""Isolate vocoder vs talker: encode the reference audio to codec tokens, then
decode them back. If the round-trip reconstructs clean speech, the encoder +
vocoder are fine and the talker generation is the bug. If it's noise, the
encoder/vocoder (tokenizer_12hz rope/mask or speech_vq mel) is the bug.
"""
import os
import sys
import traceback

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def log(m):
    print(m, flush=True)


def stats(y, sr, label):
    import numpy as np
    from src.engine import audio_features as af
    y = np.asarray(y, dtype="float64")
    f0, voiced = af.estimate_f0(y.astype("float32"), sr)
    vr = float(voiced.mean()) if len(voiced) else 0.0
    log(f"  [{label}] dur={len(y)/sr:.2f}s voiced={vr*100:.0f}% "
        f"rms={float(np.sqrt(np.mean(y**2))):.3f} peak={float(np.max(np.abs(y))):.3f}")


def main():
    import numpy as np
    import soundfile as sf
    from src.engine.clone_tts import QwenCloneEngine

    eng = QwenCloneEngine()
    eng.load(progress_cb=log)
    model = eng._model.model  # inner HF model holds speech_tokenizer

    ref = os.path.join(_ROOT, ".hdtest_realref.wav")
    wav, sr = sf.read(ref, dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    log(f"reference: {wav.shape} @ {sr}Hz")
    stats(wav, sr, "reference-in")

    log("=== encode reference -> codec tokens ===")
    enc = model.speech_tokenizer.encode([wav], sr=sr)
    codes = enc.audio_codes[0]
    import torch
    n = codes.shape[0] if hasattr(codes, "shape") else len(codes)
    log(f"ref codes shape: {tuple(codes.shape)}")

    log("=== decode tokens -> audio (round-trip) ===")
    wavs_all, fs = model.speech_tokenizer.decode([{"audio_codes": codes}])
    recon = wavs_all[0]
    recon = recon if isinstance(recon, np.ndarray) else recon.cpu().numpy()
    recon = recon.astype(np.float32).squeeze()
    out = os.path.join(_ROOT, ".hdtest_RECON.wav")
    sf.write(out, recon, int(fs))
    log(f"saved reconstruction -> {out}")
    stats(recon, int(fs), "reconstruction")
    log("\nIf reconstruction sounds like the reference speech -> vocoder OK, "
        "talker generation is the bug. If it's noise -> encoder/vocoder bug.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
