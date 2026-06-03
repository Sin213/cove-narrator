import numpy as np
from src.engine.tts import TTSEngine

def test_synthesize_text_returns_audio():
    engine = TTSEngine()
    audio, sr = engine.synthesize_text("Hello", voice="af_heart")
    assert isinstance(audio, np.ndarray)
    assert sr == 24000
    assert len(audio) > 0
    assert audio.dtype == np.float32

def test_synthesize_phonemes_returns_audio():
    engine = TTSEngine()
    audio, sr = engine.synthesize_phonemes("həlˈoʊ", voice="af_heart")
    assert isinstance(audio, np.ndarray)
    assert sr == 24000
    assert len(audio) > 0

def test_get_voices_returns_list():
    engine = TTSEngine()
    voices = engine.get_voices()
    assert isinstance(voices, list)
    assert "af_heart" in voices
    assert len(voices) > 10

def test_speed_parameter_changes_duration():
    engine = TTSEngine()
    audio_normal, _ = engine.synthesize_text("Hello world", voice="af_heart", speed=1.0)
    audio_fast, _ = engine.synthesize_text("Hello world", voice="af_heart", speed=2.0)
    assert len(audio_fast) < len(audio_normal)
