r"""Short generation to inspect the talker codec tokens — degenerate/repetitive
tokens mean broken generation (positions/rope/cache), diverse tokens that still
decode to noise would mean a vocoder problem. Run with HD_DEBUG=1.
"""
import os
import sys
import traceback

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ["HD_DEBUG"] = "1"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def log(m):
    print(m, flush=True)


def main():
    from src.engine.clone_tts import QwenCloneEngine
    eng = QwenCloneEngine()
    eng.load(progress_cb=log)
    ref = os.path.join(_ROOT, ".hdtest_realref.wav")
    log("=== short generate (max_new_tokens=150) ===")
    wavs, sr = eng._model.generate_voice_clone(
        text="The quick brown fox jumps over the lazy dog.",
        language="English", ref_audio=ref, ref_text="unused",
        x_vector_only_mode=True, non_streaming_mode=True,
        max_new_tokens=150,
    )
    import numpy as np
    a = wavs[0]
    a = a if isinstance(a, np.ndarray) else a.cpu().numpy()
    log(f"output audio: {a.shape} dur={a.size/sr:.2f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
