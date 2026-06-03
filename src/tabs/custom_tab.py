from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import Preset

class CustomTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Custom tab — coming next task"))

    def apply_preset(self, preset: Preset):
        pass

    def get_slider_values(self) -> dict[str, int]:
        return {"pitch": 0, "speed": 0, "depth": 0}
