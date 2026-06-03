import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.tokenizer import Tokenizer
from src.models.loader import find_model_files


class TTSEngine:
    def __init__(self):
        model_path, voices_path = find_model_files()
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._tokenizer = Tokenizer()

    def synthesize_text(self, text: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(text, voice=voice, speed=speed, lang="en-us")
        return samples, sr

    def synthesize_phonemes(self, phonemes: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        samples, sr = self._kokoro.create(phonemes, voice=voice, speed=speed, lang="en-us", is_phonemes=True)
        return samples, sr

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, lang="en-us")

    def get_voices(self) -> list[str]:
        return self._kokoro.get_voices()
