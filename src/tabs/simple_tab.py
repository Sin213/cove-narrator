from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QSlider, QLabel, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
import numpy as np
from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all, slider_to_speed
from src.data.dictionary import Dictionary
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav
from src.utils.presets import Preset

class SynthWorker(QThread):
    finished = Signal(np.ndarray, int)
    error = Signal(str)

    def __init__(self, engine, text, voice, speed):
        super().__init__()
        self._engine = engine
        self._text = text
        self._voice = voice
        self._speed = speed

    def run(self):
        try:
            audio, sr = self._engine.synthesize_text(self._text, voice=self._voice, speed=self._speed)
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))

class SimpleTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._dict = Dictionary()
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000
        self._save_dir = Path.home() / "Music" / "Whooshy"
        self._worker: SynthWorker | None = None
        self._highlighting = False  # guard flag to prevent infinite loop

        layout = QVBoxLayout(self)

        # Text area
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Type or paste text here...")
        layout.addWidget(self._text_edit)

        self._highlight_timer = QTimer()
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(300)
        self._highlight_timer.timeout.connect(self._highlight_unknown_words)
        self._text_edit.textChanged.connect(self._on_text_changed)

        # Sliders
        slider_layout = QHBoxLayout()
        self._pitch_slider, pitch_group = self._make_slider("Pitch")
        self._speed_slider, speed_group = self._make_slider("Speed")
        self._depth_slider, depth_group = self._make_slider("Depth")
        slider_layout.addLayout(pitch_group)
        slider_layout.addLayout(speed_group)
        slider_layout.addLayout(depth_group)
        layout.addLayout(slider_layout)

        # Controls
        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇ Export WAV")
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        self._dir_label = QPushButton(f"📁 {self._save_dir}")
        self._dir_label.setFlat(True)
        self._dir_label.clicked.connect(self._choose_dir)
        controls.addWidget(self._dir_label)
        layout.addLayout(controls)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._player.state_changed.connect(self._on_playback_state)

    def _on_text_changed(self):
        """Only restart highlight timer if we are not currently highlighting."""
        if not self._highlighting:
            self._highlight_timer.start()

    def _make_slider(self, name: str) -> tuple[QSlider, QVBoxLayout]:
        group = QVBoxLayout()
        label = QLabel(f"{name}: 0")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.valueChanged.connect(lambda v, lbl=label, n=name: lbl.setText(f"{n}: {v}"))
        group.addWidget(label)
        group.addWidget(slider)
        return slider, group

    def get_slider_values(self) -> dict[str, int]:
        return {"pitch": self._pitch_slider.value(), "speed": self._speed_slider.value(), "depth": self._depth_slider.value()}

    def apply_preset(self, preset: Preset):
        self._pitch_slider.setValue(preset.pitch)
        self._speed_slider.setValue(preset.speed)
        self._depth_slider.setValue(preset.depth)

    def _highlight_unknown_words(self):
        text = self._text_edit.toPlainText()
        if not text.strip():
            return
        self._highlighting = True  # prevent textChanged re-trigger
        try:
            cursor = self._text_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            default_fmt = QTextCharFormat()
            cursor.setCharFormat(default_fmt)
            cursor.clearSelection()

            flagged_fmt = QTextCharFormat()
            flagged_fmt.setBackground(QColor(85, 51, 51))
            flagged_fmt.setForeground(QColor(255, 153, 153))

            pos = 0
            for word, _, is_known in self._dict.lookup_with_flags(text):
                idx = text.find(word, pos)
                if idx == -1:
                    continue
                if not is_known and any(c.isalpha() for c in word):
                    cursor.setPosition(idx)
                    cursor.setPosition(idx + len(word), QTextCursor.KeepAnchor)
                    cursor.setCharFormat(flagged_fmt)
                pos = idx + len(word)
            cursor.endEditBlock()
        finally:
            self._highlighting = False  # always re-enable

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._status.setText("No text to speak.")
            return
        self._status.setText("Synthesizing...")
        self._play_btn.setEnabled(False)
        speed = slider_to_speed(self._speed_slider.value())
        voice = self.window().get_current_voice_id()
        self._worker = SynthWorker(self._engine, text, voice, speed)
        self._worker.finished.connect(self._on_synth_done)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    def _on_synth_done(self, audio: np.ndarray, sr: int):
        pitch = self._pitch_slider.value()
        depth = self._depth_slider.value()
        audio = apply_all(audio, sr, pitch=pitch, depth=depth)
        self._last_audio = audio
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._play_btn.setEnabled(True)
        self._status.setText(f"Playing ({len(audio)/sr:.1f}s)")

    def _on_synth_error(self, msg: str):
        self._play_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")

    def _on_stop(self):
        self._player.stop()

    def _on_playback_state(self, state: str):
        if state == "playing":
            self._play_btn.setText("⏸ Pause")
        elif state == "paused":
            self._play_btn.setText("▶ Resume")
        else:
            self._play_btn.setText("▶ Play")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Press Play first.")
            return
        path = export_wav(self._last_audio, self._last_sr, self._save_dir)
        self._status.setText(f"Exported: {path.name}")

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save Directory", str(self._save_dir))
        if d:
            self._save_dir = Path(d)
            self._dir_label.setText(f"📁 {self._save_dir}")
