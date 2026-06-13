"""Voice blend engine — finds the optimal mix of kokoro voices to
approximate a reference audio clip's pitch."""

import json
import os
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

from portable import is_portable, portable_data_dir
from src.engine import audio_features as af


_BLEND_PHRASE = "I have an important message for you today."


def _measure_f0(audio: np.ndarray, sr: int) -> float:
    med = af.median_f0(audio, sr, fmin=50, fmax=600)
    return med if med is not None else 150.0


def _f0_score(gen_f0: float, ref_f0: float) -> float:
    """Distance in semitones — 0 is perfect match."""
    if ref_f0 <= 0 or gen_f0 <= 0:
        return 99.0
    return abs(12.0 * np.log2(gen_f0 / ref_f0))


def find_best_blend(
    kokoro: Kokoro,
    ref_path: str,
    progress_cb=None,
) -> tuple[dict[str, float], np.ndarray]:
    """Find the voice blend that best matches a reference clip's F0.

    Returns (weights_dict, blended_voice_tensor).
    """
    def _progress(stage, detail=""):
        if progress_cb:
            progress_cb(stage, detail)

    _progress("loading", "Analyzing reference audio…")
    y_ref, sr_ref = af.load_audio(ref_path, sr=24000)
    # Use up to 15s for stable F0 estimate
    clip_len = min(len(y_ref), sr_ref * 15)
    ref_f0 = _measure_f0(y_ref[:clip_len], sr_ref)
    is_male = ref_f0 < 165

    _progress("scoring", f"Reference: {ref_f0:.0f} Hz {'male' if is_male else 'female'}")

    # Use American voices — they cover the full range and avoid
    # accent artifacts from British voices in blends
    if is_male:
        candidates = [v for v in kokoro.voices.keys()
                      if v.startswith("am_")]
    else:
        candidates = [v for v in kokoro.voices.keys()
                      if v.startswith("af_")]

    # Phase 1: measure F0 of each candidate
    voice_f0s = {}
    for vid in candidates:
        samples, sr = kokoro.create(
            _BLEND_PHRASE, voice=kokoro.voices[vid],
            speed=1.0, lang="en-us", trim=False)
        voice_f0s[vid] = _measure_f0(samples, sr)

    ranked = sorted(voice_f0s.items(), key=lambda x: _f0_score(x[1], ref_f0))
    top4 = [v for v, _ in ranked[:4]]
    _progress("blending", f"Top: {', '.join(v.split('_')[1].title() for v in top4)}")

    best_score = _f0_score(voice_f0s[top4[0]], ref_f0)
    best_weights = {top4[0]: 1.0}
    best_tensor = kokoro.voices[top4[0]].copy()

    # Phase 2: pairwise blends — these are instant (just tensor math),
    # only the F0 measurement needs synthesis
    for i in range(min(4, len(top4))):
        for j in range(i + 1, min(4, len(top4))):
            f0_i, f0_j = voice_f0s[top4[i]], voice_f0s[top4[j]]
            # Estimate the weight that would land on ref_f0
            # (linear interpolation of log-F0)
            if abs(f0_i - f0_j) < 1.0:
                continue
            w_est = (ref_f0 - f0_j) / (f0_i - f0_j)
            for w in set([0.3, 0.5, 0.7, round(max(0.1, min(0.9, w_est)), 2)]):
                blend = w * kokoro.voices[top4[i]] + (1 - w) * kokoro.voices[top4[j]]
                samples, sr = kokoro.create(
                    _BLEND_PHRASE, voice=blend, speed=1.0,
                    lang="en-us", trim=False)
                gen_f0 = _measure_f0(samples, sr)
                s = _f0_score(gen_f0, ref_f0)
                if s < best_score:
                    best_score = s
                    best_weights = {top4[i]: round(w, 2),
                                    top4[j]: round(1 - w, 2)}
                    best_tensor = blend

    desc = " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                      for v, w in best_weights.items())
    _progress("done", f"{desc} ({best_score:.1f} semitones off)")

    return best_weights, best_tensor


class CustomVoiceManager:
    """Saves and loads blended voice tensors as .npz files."""

    def __init__(self, config_dir: Path | None = None):
        if config_dir:
            self._dir = config_dir
        elif is_portable():
            self._dir = Path(os.path.join(portable_data_dir("cove-narrator"), "config", "voices"))
        else:
            self._dir = Path.home() / ".config" / "cove-narrator" / "voices"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, tensor: np.ndarray, weights: dict[str, float]) -> Path:
        base = "".join(c if c.isalnum() else "_" for c in name)
        safe = base
        counter = 2
        while (self._dir / f"{safe}.npz").exists():
            safe = f"{base}_{counter}"
            counter += 1
        path = self._dir / f"{safe}.npz"
        np.savez_compressed(str(path), tensor=tensor)
        meta_path = self._dir / f"{safe}.json"
        meta_path.write_text(json.dumps({"name": name, "key": safe, "weights": weights}))
        return path

    def load(self, key: str) -> tuple[np.ndarray, dict]:
        path = self._dir / f"{key}.npz"
        meta_path = self._dir / f"{key}.json"
        tensor = np.load(str(path))["tensor"]
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"name": key, "weights": {}}
        return tensor, meta

    def list_voices(self) -> list[dict]:
        voices = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                meta = json.loads(f.read_text())
                npz = f.with_suffix(".npz")
                if npz.exists():
                    if "key" not in meta:
                        meta["key"] = f.stem
                    voices.append(meta)
            except (json.JSONDecodeError, KeyError):
                continue
        return voices

    def delete(self, name: str):
        safe = "".join(c if c.isalnum() else "_" for c in name)
        for ext in (".npz", ".json"):
            p = self._dir / f"{safe}{ext}"
            if p.exists():
                p.unlink()
