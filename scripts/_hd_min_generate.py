r"""Minimal HD clone generation that loads Qwen3TTSModel directly (no clone_tts,
so no kokoro_onnx import) — lets us run under system Python (transformers 4.x)
to compare against the 5.10.2 build. Dumps token stats (HD_DEBUG) and saves audio.
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
    import torch
    import transformers
    import numpy as np
    import soundfile as sf
    from src.vendor.qwen_tts import Qwen3TTSModel

    log(f"transformers {transformers.__version__}  torch {torch.__version__}")
    model_dir = os.path.expanduser(
        "~/.config/cove-narrator/models/qwen3-tts-1.7b")
    log("loading model…")
    m = Qwen3TTSModel.from_pretrained(
        model_dir, device_map="cpu", dtype=torch.float32)
    ref = os.path.join(_ROOT, ".hdtest_realref.wav")
    log("generating (max_new_tokens=150)…")
    wavs, sr = m.generate_voice_clone(
        text="The quick brown fox jumps over the lazy dog.",
        language="English", ref_audio=ref, ref_text="unused",
        x_vector_only_mode=True, non_streaming_mode=True,
        max_new_tokens=500,
    )
    a = wavs[0]
    a = a if isinstance(a, np.ndarray) else a.cpu().numpy()
    a = a.astype(np.float32).squeeze()
    tag = transformers.__version__.split(".")[0] + "." + transformers.__version__.split(".")[1]
    out = os.path.join(_ROOT, f".hdtest_tf{tag}_clone.wav")
    sf.write(out, a, sr)
    log(f"saved -> {out}  dur={a.size/sr:.2f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("ERROR:")
        traceback.print_exc()
        sys.exit(1)
