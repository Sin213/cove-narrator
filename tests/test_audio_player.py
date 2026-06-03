import numpy as np
from src.utils.audio_player import AudioPlayer


def test_player_initial_state():
    player = AudioPlayer()
    assert not player.is_playing
    assert not player.is_paused


def test_player_load_audio():
    player = AudioPlayer()
    audio = np.random.randn(24000).astype(np.float32)
    player.load(audio, 24000)
    assert not player.is_playing


def test_player_stop_when_not_playing():
    player = AudioPlayer()
    player.stop()
    assert not player.is_playing
