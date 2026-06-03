from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTabWidget, QLabel, QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt
from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import PresetManager, Preset
from src.tabs.simple_tab import SimpleTab
from src.tabs.custom_tab import CustomTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whooshy")
        self.setMinimumSize(700, 500)
        self._engine = TTSEngine()
        self._player = AudioPlayer(self)
        self._presets = PresetManager()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)

        # Voice header
        header = QHBoxLayout()
        header.addWidget(QLabel("Voice:"))
        self._voice_combo = QComboBox()
        self._voice_combo.setMinimumWidth(200)
        self._populate_voices()
        header.addWidget(self._voice_combo)
        header.addStretch()
        save_btn = QPushButton("Save Preset")
        save_btn.clicked.connect(self._save_preset)
        header.addWidget(save_btn)
        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        self._simple_tab = SimpleTab(self._engine, self._player, self)
        self._custom_tab = CustomTab(self._engine, self._player, self)
        self._tabs.addTab(self._simple_tab, "Simple")
        self._tabs.addTab(self._custom_tab, "Custom")
        layout.addWidget(self._tabs)

        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)

    def _populate_voices(self):
        self._voice_combo.clear()
        for preset in self._presets.get_all_presets():
            label = f"{'⭐ ' if not preset.is_builtin else ''}{preset.name}"
            self._voice_combo.addItem(label if not preset.is_builtin else preset.name, preset)
        self._voice_combo.setCurrentIndex(0)

    def _on_voice_changed(self, index):
        if index < 0:
            return
        preset = self._voice_combo.itemData(index)
        if preset:
            self._simple_tab.apply_preset(preset)
            self._custom_tab.apply_preset(preset)

    def get_current_voice_id(self) -> str:
        preset = self._voice_combo.currentData()
        if preset:
            return preset.voice_id
        return "af_heart"

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        current_tab = self._tabs.currentWidget()
        sliders = current_tab.get_slider_values()
        preset = Preset(
            name=name.strip(),
            voice_id=self.get_current_voice_id(),
            pitch=sliders["pitch"],
            speed=sliders["speed"],
            depth=sliders["depth"],
        )
        self._presets.save_preset(preset)
        self._populate_voices()
