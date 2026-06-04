from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QKeySequenceEdit,
    QComboBox, QSpinBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from src.utils.config import load_config, save_config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._config = load_config()

        layout = QVBoxLayout(self)

        # Output section
        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)

        self._dir_label = QLabel(self._config.get("save_dir", ""))
        self._dir_label.setObjectName("voiceDesc")
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_label, 1)
        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._choose_dir)
        dir_row.addWidget(dir_btn)
        output_form.addRow("Save directory:", dir_row)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["WAV (PCM 16-bit)", "WAV (PCM 32-bit)"])
        cur_fmt = self._config.get("export_format", "PCM_16")
        self._format_combo.setCurrentIndex(0 if cur_fmt == "PCM_16" else 1)
        output_form.addRow("Export format:", self._format_combo)

        layout.addWidget(output_group)

        # Hotkeys section
        hotkey_group = QGroupBox("Hotkeys")
        hotkey_form = QFormLayout(hotkey_group)

        self._play_key = QKeySequenceEdit(
            QKeySequence(self._config.get("hotkey_play_pause", "Space"))
        )
        hotkey_form.addRow("Play / Pause:", self._play_key)

        self._stop_key = QKeySequenceEdit(
            QKeySequence(self._config.get("hotkey_stop", "Escape"))
        )
        hotkey_form.addRow("Stop:", self._stop_key)

        self._export_key = QKeySequenceEdit(
            QKeySequence(self._config.get("hotkey_export", "Ctrl+E"))
        )
        hotkey_form.addRow("Export WAV:", self._export_key)

        layout.addWidget(hotkey_group)

        # Synthesis section
        synth_group = QGroupBox("Synthesis")
        synth_form = QFormLayout(synth_group)

        self._pause_spin = QSpinBox()
        self._pause_spin.setRange(100, 5000)
        self._pause_spin.setSuffix(" ms")
        self._pause_spin.setSingleStep(100)
        self._pause_spin.setValue(int(self._config.get("pause_duration_ms", 500)))
        synth_form.addRow("Default [Pause] duration:", self._pause_spin)

        layout.addWidget(synth_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        save_btn.setDefault(True)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Export Directory", self._dir_label.text()
        )
        if d:
            self._dir_label.setText(d)

    def _save(self):
        self._config["save_dir"] = self._dir_label.text()
        fmt_idx = self._format_combo.currentIndex()
        self._config["export_format"] = "PCM_16" if fmt_idx == 0 else "PCM_32"
        self._config["hotkey_play_pause"] = self._play_key.keySequence().toString()
        self._config["hotkey_stop"] = self._stop_key.keySequence().toString()
        self._config["hotkey_export"] = self._export_key.keySequence().toString()
        self._config["pause_duration_ms"] = self._pause_spin.value()
        save_config(self._config)
        self.accept()

    def get_config(self) -> dict:
        return self._config
