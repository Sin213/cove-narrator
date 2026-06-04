from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTabWidget, QLabel, QInputDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from src.utils.config import load_config, save_config
from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import PresetManager, Preset
from src.utils.settings_dialog import SettingsDialog
from src.tabs.simple_tab import SimpleTab
from src.tabs.custom_tab import CustomTab
from src.tabs.reader_tab import ReaderTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whooshy")
        self.setMinimumSize(700, 500)
        self._engine = TTSEngine()
        self._player = AudioPlayer(self)
        self._presets = PresetManager()
        self._config = load_config()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)

        # Voice header
        header = QHBoxLayout()
        header.addWidget(QLabel("Voice:"))
        self._voice_combo = QComboBox()
        self._voice_combo.setMinimumWidth(300)
        self._populate_voices()
        header.addWidget(self._voice_combo)
        header.addStretch()

        save_btn = QPushButton("Save Preset")
        save_btn.clicked.connect(self._save_preset)
        header.addWidget(save_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        header.addWidget(settings_btn)

        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        self._simple_tab = SimpleTab(self._engine, self._player, self)
        self._custom_tab = CustomTab(self._engine, self._player, self)
        self._reader_tab = ReaderTab(self._engine, self._player, self)
        self._tabs.addTab(self._simple_tab, "Simple")
        self._tabs.addTab(self._custom_tab, "Custom")
        self._tabs.addTab(self._reader_tab, "Reader")
        layout.addWidget(self._tabs)

        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)

        # Apply config
        self.resize(self._config["window_width"], self._config["window_height"])
        self._apply_config()

        # Keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        play_key = self._config.get("hotkey_play_pause", "Space")
        self._play_shortcut = QShortcut(QKeySequence(play_key), self)
        self._play_shortcut.activated.connect(self._toggle_play_pause)

        stop_key = self._config.get("hotkey_stop", "Escape")
        self._stop_shortcut = QShortcut(QKeySequence(stop_key), self)
        self._stop_shortcut.activated.connect(self._stop_all)

        export_key = self._config.get("hotkey_export", "Ctrl+E")
        self._export_shortcut = QShortcut(QKeySequence(export_key), self)
        self._export_shortcut.activated.connect(self._export_current)

    def _toggle_play_pause(self):
        tab = self._tabs.currentWidget()
        tab.toggle_play_pause()

    def _stop_all(self):
        self._player.stop()
        self._simple_tab._play_btn.setEnabled(True)
        self._custom_tab._play_btn.setEnabled(True)
        self._reader_tab._on_stop()

    def _export_current(self):
        tab = self._tabs.currentWidget()
        tab._on_export()

    def _apply_config(self):
        save_dir = Path(self._config.get("save_dir", str(Path.home() / "Music" / "Whooshy")))
        self._simple_tab.set_save_dir(save_dir)
        self._custom_tab.set_save_dir(save_dir)
        self._reader_tab.set_save_dir(save_dir)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._config = dlg.get_config()
            self._apply_config()
            # Re-bind shortcuts
            self._play_shortcut.setKey(QKeySequence(self._config.get("hotkey_play_pause", "Space")))
            self._stop_shortcut.setKey(QKeySequence(self._config.get("hotkey_stop", "Escape")))
            self._export_shortcut.setKey(QKeySequence(self._config.get("hotkey_export", "Ctrl+E")))

    def closeEvent(self, event):
        self._config["window_width"] = self.width()
        self._config["window_height"] = self.height()
        preset = self._voice_combo.currentData()
        if preset:
            self._config["last_voice"] = preset.voice_id
        save_config(self._config)
        self._player.stop()
        event.accept()

    def _populate_voices(self):
        self._voice_combo.clear()
        for preset in self._presets.get_all_presets():
            label = f"{'⭐ ' if not preset.is_builtin else ''}{preset.name}"
            self._voice_combo.addItem(
                label if not preset.is_builtin else preset.name, preset
            )
        self._voice_combo.setCurrentIndex(0)

    def _on_voice_changed(self, index):
        if index < 0:
            return
        preset = self._voice_combo.itemData(index)
        if preset:
            self._simple_tab.apply_preset(preset)
            self._custom_tab.apply_preset(preset)
            self._reader_tab.apply_preset(preset)

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
