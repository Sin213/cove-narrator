import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


class AudioPlayer(QObject):
    playback_finished = Signal()
    state_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._audio: np.ndarray | None = None
        self._sr: int = 24000
        self._position: int = 0
        self._is_playing = False
        self._is_paused = False
        self._stream: sd.OutputStream | None = None

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def load(self, audio: np.ndarray, sr: int):
        self.stop()
        self._audio = audio
        self._sr = sr
        self._position = 0

    def play(self):
        if self._audio is None:
            return
        if self._is_paused:
            self._is_paused = False
            self._is_playing = True
            self.state_changed.emit("playing")
            return
        self.stop()
        self._is_playing = True
        self._position = 0
        self.state_changed.emit("playing")
        self._stream = sd.OutputStream(
            samplerate=self._sr, channels=1, dtype="float32",
            blocksize=4096,
            callback=self._callback, finished_callback=self._on_finished,
        )
        self._stream.start()

    def pause(self):
        if self._is_playing and not self._is_paused:
            self._is_paused = True
            self._is_playing = False
            self.state_changed.emit("paused")

    def stop(self):
        self._is_playing = False
        self._is_paused = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._position = 0
        self.state_changed.emit("stopped")

    def _callback(self, outdata, frames, time_info, status):
        if self._audio is None or not self._is_playing:
            outdata[:] = 0
            if self._is_paused:
                return
            raise sd.CallbackStop()
        end = self._position + frames
        if end >= len(self._audio):
            remaining = len(self._audio) - self._position
            outdata[:remaining, 0] = self._audio[self._position:]
            outdata[remaining:] = 0
            self._position = len(self._audio)
            raise sd.CallbackStop()
        else:
            outdata[:, 0] = self._audio[self._position:end]
            self._position = end

    def _on_finished(self):
        self._is_playing = False
        self._is_paused = False
        self._stream = None
        self.playback_finished.emit()
        self.state_changed.emit("stopped")
