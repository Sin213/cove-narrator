from pathlib import Path

import numpy as np

from src.engine.analyzer import analyze_reference
from src.engine.voice_blend import find_best_blend
from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all


class VoiceMatchResult:
    def __init__(self, weights: dict, tensor: np.ndarray,
                 pitch: int, speed: int, depth: int, gender: str, median_f0: float):
        self.weights = weights
        self.tensor = tensor
        self.pitch = pitch
        self.speed = speed
        self.depth = depth
        self.gender = gender
        self.median_f0 = median_f0

    @property
    def description(self) -> str:
        return " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                          for v, w in self.weights.items())


class VoiceMatchEngine:
    def __init__(self, tts_engine: TTSEngine):
        self._engine = tts_engine

    def analyze(self, ref_audio_path: str, progress_cb=None) -> VoiceMatchResult:
        pitch, speed, depth, gender, median_f0 = analyze_reference(ref_audio_path)
        blend_cb = (lambda stage, detail: progress_cb(detail)) if progress_cb else None
        weights, tensor = find_best_blend(
            self._engine._kokoro, ref_audio_path,
            progress_cb=blend_cb,
        )
        return VoiceMatchResult(
            weights=weights, tensor=tensor,
            pitch=pitch, speed=speed, depth=depth,
            gender=gender, median_f0=median_f0,
        )

    def synthesize(self, text: str, tensor: np.ndarray,
                   speed: float = 1.0, pitch: int = 0,
                   depth: int = 0) -> tuple[np.ndarray, int]:
        audio, sr = self._engine.synthesize_text(text, voice=tensor, speed=speed)
        audio = apply_all(audio, sr, pitch=pitch, depth=depth)
        return audio, sr


class QwenCloneEngine:
    _MODEL_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

    def __init__(self):
        self._model = None

    @staticmethod
    def model_dir() -> Path:
        d = Path.home() / ".config" / "cove-narrator" / "models" / "qwen3-tts-1.7b"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def is_downloaded(self) -> bool:
        return (self.model_dir() / "model.safetensors").exists()

    def is_loaded(self) -> bool:
        return self._model is not None

    def download(self, progress_cb=None):
        import os
        import threading
        import time as _time

        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        os.environ["HF_HUB_DISABLE_XET"] = "1"
        from huggingface_hub import snapshot_download

        ESTIMATED_BYTES = 4_300_000_000
        model_dir = self.model_dir()
        stop = threading.Event()

        def _monitor():
            start = _time.monotonic()
            while not stop.wait(3):
                try:
                    total = sum(
                        f.stat().st_size
                        for f in model_dir.rglob("*") if f.is_file()
                    )
                except OSError:
                    continue
                mb = total / 1_000_000
                pct = min(99, int(total / ESTIMATED_BYTES * 100))
                elapsed = _time.monotonic() - start
                if pct > 1 and elapsed > 5:
                    eta_sec = elapsed / pct * (100 - pct)
                    eta_min = max(1, int(eta_sec / 60))
                    progress_cb(
                        f"Downloading… {pct}%  —  "
                        f"ETA ~{eta_min} min  "
                        f"({mb:.0f} / ~4300 MB)"
                    )
                else:
                    progress_cb(f"Downloading… ({mb:.0f} MB)")

        if progress_cb:
            progress_cb("Starting Qwen3-TTS download…")
            threading.Thread(target=_monitor, daemon=True).start()

        try:
            snapshot_download(self._MODEL_REPO, local_dir=str(model_dir))
        finally:
            stop.set()

        if progress_cb:
            progress_cb("Download complete.")

    def load(self, progress_cb=None):
        if self._model is not None:
            return
        import torch
        from qwen_tts import Qwen3TTSModel
        if progress_cb:
            progress_cb("Loading Qwen3-TTS 1.7B…")
        kwargs = {}
        if torch.cuda.is_available():
            kwargs["device_map"] = "auto"
            kwargs["dtype"] = torch.bfloat16
        else:
            kwargs["device_map"] = "cpu"
            kwargs["dtype"] = torch.float32
        self._model = Qwen3TTSModel.from_pretrained(str(self.model_dir()), **kwargs)
        if progress_cb:
            progress_cb("Qwen3-TTS ready.")

    def synthesize(self, text: str, ref_audio_path: str) -> tuple[np.ndarray, int]:
        if self._model is None:
            raise RuntimeError("Qwen3-TTS not loaded")
        wavs, sr = self._model.generate_voice_clone(
            text=text, language="English",
            ref_audio=ref_audio_path, ref_text="unused",
            x_vector_only_mode=True,
            non_streaming_mode=True,
            temperature=0.3, top_p=0.85, top_k=20,
            repetition_penalty=1.0,
            max_new_tokens=2048,
        )
        audio = wavs[0]
        if not isinstance(audio, np.ndarray):
            audio = audio.cpu().numpy()
        return audio.astype(np.float32).squeeze(), int(sr)
