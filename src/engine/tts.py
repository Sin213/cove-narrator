import re

import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.tokenizer import Tokenizer
from src.models.loader import find_model_files
from src.engine.audio_dsp import apply_pitch_shift

PAUSE_SECONDS = 0.5

_PAUSE_RE = re.compile(r"\[Pause(?:\s+(\d+(?:\.\d+)?))?\]", re.IGNORECASE)
_PARAM_RE = re.compile(r"\[(Speed|Pitch|Soft|Slow)(?:\s+([^\]]*))?\]", re.IGNORECASE)

TAGS_HELP = [
    ("[Pause]", "0.5s silence", "[Pause 1.5] for custom duration"),
    ("[Speed 1.5]", "Speed up entire segment", "0.5 = slow, 2.0 = fast"),
    ("[Pitch 30]", "Raise pitch for entire segment", "-100 to 100"),
    ("[Soft]", "Quieter segment", "Reduces volume to ~40%"),
    ("[Slow]", "Slow down segment", "Speaks at 0.7x speed"),
]


def _fade_out(samples: np.ndarray, sr: int, duration: float = 0.05) -> np.ndarray:
    fade_len = int(sr * duration)
    if fade_len >= len(samples):
        return samples
    fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
    samples = samples.copy()
    samples[-fade_len:] *= fade
    return samples


def _finish_audio(samples: np.ndarray, sr: int) -> np.ndarray:
    samples = _fade_out(samples, sr)
    pad = np.zeros(int(sr * 0.1), dtype=np.float32)
    return np.concatenate([samples, pad])


def _trim_trailing_silence(samples: np.ndarray, sr: int, tail: float = 0.1, threshold: float = 0.005) -> np.ndarray:
    frame = 512
    i = len(samples) - frame
    while i > 0:
        rms = np.sqrt(np.mean(samples[i:i + frame] ** 2))
        if rms > threshold:
            end = min(i + frame + int(sr * tail), len(samples))
            return samples[:end]
        i -= frame
    return samples


def _make_silence(sr: int, duration: float = PAUSE_SECONDS) -> np.ndarray:
    return np.zeros(int(sr * duration), dtype=np.float32)


def _parse_segment_params(text: str, base_speed: float) -> tuple[str, float, int, bool]:
    speed = base_speed
    pitch = 0
    soft = False

    for m in _PARAM_RE.finditer(text):
        tag = m.group(1).lower()
        arg = m.group(2)
        if tag == "speed":
            if arg and arg.strip():
                try:
                    speed = max(0.5, min(2.0, float(arg.strip())))
                except ValueError:
                    pass
        elif tag == "pitch":
            if arg and arg.strip():
                try:
                    pitch = max(-100, min(100, int(float(arg.strip()))))
                except ValueError:
                    pass
        elif tag == "slow":
            speed = base_speed * 0.7
        elif tag == "soft":
            soft = True

    clean_text = _PARAM_RE.sub("", text).strip()
    return clean_text, speed, pitch, soft


class TTSEngine:
    def __init__(self):
        model_path, voices_path = find_model_files()
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._tokenizer = Tokenizer()

    def synthesize_text(self, text: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        pause_segments = _PAUSE_RE.split(text)
        parts: list[np.ndarray] = []
        sr = 24000

        for i, segment in enumerate(pause_segments):
            if i % 2 == 1:
                dur = float(segment) if segment else PAUSE_SECONDS
                parts.append(_make_silence(sr, dur))
            else:
                clean, seg_speed, seg_pitch, seg_soft = _parse_segment_params(
                    segment, speed
                )
                if not clean:
                    continue

                samples, sr = self._kokoro.create(
                    clean, voice=voice, speed=seg_speed, lang="en-us", trim=True
                )

                if seg_pitch != 0:
                    samples = apply_pitch_shift(samples, seg_pitch, sr)

                if seg_soft:
                    samples = samples * 0.4

                parts.append(samples)

        if not parts:
            return _make_silence(sr, 0.1), sr
        result = np.concatenate(parts)
        result = _finish_audio(result, sr)
        return result, sr

    def synthesize_raw(self, text: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(
            text, voice=voice, speed=speed, lang="en-us", trim=True
        )
        pad = np.zeros(int(sr * 0.25), dtype=np.float32)
        samples = np.concatenate([samples, pad])
        return samples, sr

    def synthesize_phonemes(self, phonemes: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(
            phonemes, voice=voice, speed=speed, lang="en-us", is_phonemes=True, trim=True
        )
        samples = _finish_audio(samples, sr)
        return samples, sr

    def synthesize_hybrid(self, text: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        from src.data.phonemes import arpabet_sequence_to_ipa
        chunks = re.split(r"(\{[^}]+\})", text)
        parts: list[np.ndarray] = []
        sr = 24000

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            if chunk.startswith("{") and chunk.endswith("}"):
                phoneme_str = chunk[1:-1].strip()
                arpabet_list = phoneme_str.split()
                ipa = arpabet_sequence_to_ipa(arpabet_list)
                if ipa.strip():
                    samples, sr = self._kokoro.create(
                        ipa, voice=voice, speed=speed,
                        lang="en-us", is_phonemes=True, trim=True
                    )
                    parts.append(samples)
            else:
                samples, sr = self._kokoro.create(
                    chunk, voice=voice, speed=speed, lang="en-us", trim=True
                )
                parts.append(samples)

        if not parts:
            return _make_silence(sr, 0.1), sr
        result = np.concatenate(parts)
        result = _finish_audio(result, sr)
        return result, sr

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, lang="en-us")

    def get_voices(self) -> list[str]:
        return self._kokoro.get_voices()
