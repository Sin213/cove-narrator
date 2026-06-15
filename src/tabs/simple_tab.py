from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QSlider, QLabel, QSpinBox,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor

import numpy as np

from src.engine.tts import TTSEngine, TAGS_HELP
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
            audio, sr = self._engine.synthesize_text(
                self._text, voice=self._voice, speed=self._speed
            )
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
        self._save_dir = Path.home() / "Music" / "Cove Narrator"
        self._worker: SynthWorker | None = None
        self._highlighting = False

        layout = QVBoxLayout(self)

        # Tag insertion toolbar
        tag_row = QHBoxLayout()
        tag_row.addWidget(QLabel("Insert:"))
        tag_buttons = [
            ("[Pause]", "[Pause] ", "Insert a 0.5s silence. Use [Pause 1.5] for custom duration."),
            ("[Speed]", "[Speed 1.5] ", "Change speed for next segment. 0.5=slow, 2.0=fast. [Speed] resets."),
            ("[Pitch]", "[Pitch 30] ", "Shift pitch for next segment. -100 to 100. [Pitch] resets."),
            ("[Soft]", "[Soft] ", "Quieter next segment (~40% volume)."),
            ("[Slow]", "[Slow] ", "Slow down next segment (0.7x speed, more deliberate)."),
        ]
        for label, insert_text, tooltip in tag_buttons:
            btn = QPushButton(label)
            btn.setObjectName("tagButton")
            btn.setToolTip(tooltip)
            btn.setFixedHeight(24)
            btn.clicked.connect(
                lambda checked=False, t=insert_text: self._insert_tag(t)
            )
            tag_row.addWidget(btn)
        tag_row.addStretch()
        layout.addLayout(tag_row)

        # Text area
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(
            'Type or paste text here...\nUse the buttons above to insert tags like [Pause], [Whisper], etc.'
        )
        layout.addWidget(self._text_edit)

        self._dict_hint = QLabel("")
        self._dict_hint.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        layout.addWidget(self._dict_hint)

        self._highlight_timer = QTimer()
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(300)
        self._highlight_timer.timeout.connect(self._highlight_unknown_words)
        self._text_edit.textChanged.connect(self._on_text_changed)

        # Sliders with spinboxes
        slider_layout = QHBoxLayout()
        self._pitch_slider, self._pitch_spin, pitch_group = self._make_slider("Pitch", "#7fd0ff")
        self._speed_slider, self._speed_spin, speed_group = self._make_slider("Speed", "#50e6cf")
        self._depth_slider, self._depth_spin, depth_group = self._make_slider("Depth", "#c89bff")
        slider_layout.addLayout(pitch_group)
        slider_layout.addLayout(speed_group)
        slider_layout.addLayout(depth_group)
        layout.addLayout(slider_layout)

        # Controls
        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setObjectName("playButton")
        self._play_btn.setFocusPolicy(Qt.NoFocus)
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setFocusPolicy(Qt.NoFocus)
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇  Export WAV")
        self._export_btn.setObjectName("exportButton")
        self._export_btn.setFocusPolicy(Qt.NoFocus)
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self._status = QLabel("")
        self._status.setObjectName("statusLabel")
        layout.addWidget(self._status)

        self._player.state_changed.connect(self._on_playback_state)

    def _on_text_changed(self):
        if not self._highlighting:
            self._highlight_timer.start()

    def _make_slider(self, name: str, color: str = "#50e6cf") -> tuple[QSlider, QSpinBox, QVBoxLayout]:
        group = QVBoxLayout()
        top_row = QHBoxLayout()
        pip = QLabel("●")
        pip.setStyleSheet(f"color: {color}; font-size: 6px;")
        pip.setFixedWidth(10)
        top_row.addWidget(pip)
        label = QLabel(f"{name}:")
        label.setObjectName("sliderName")
        spin = QSpinBox()
        spin.setRange(-100, 100)
        spin.setValue(0)
        spin.setFixedWidth(55)
        top_row.addWidget(label)
        top_row.addWidget(spin)
        group.addLayout(top_row)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        group.addWidget(slider)
        return slider, spin, group

    def get_slider_values(self) -> dict[str, int]:
        return {
            "pitch": self._pitch_slider.value(),
            "speed": self._speed_slider.value(),
            "depth": self._depth_slider.value(),
        }

    def set_save_dir(self, path: Path):
        self._save_dir = path

    def apply_preset(self, preset: Preset):
        self._pitch_slider.setValue(preset.pitch)
        self._speed_slider.setValue(preset.speed)
        self._depth_slider.setValue(preset.depth)

    def _highlight_unknown_words(self):
        text = self._text_edit.toPlainText()
        if not text.strip():
            return
        self._highlighting = True
        try:
            cursor = self._text_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            default_fmt = QTextCharFormat()
            cursor.setCharFormat(default_fmt)
            cursor.clearSelection()

            flagged_fmt = QTextCharFormat()
            flagged_fmt.setBackground(QColor(255, 107, 107, 41))
            flagged_fmt.setForeground(QColor(255, 107, 107))

            unknown_count = 0
            pos = 0
            for word, _, is_known in self._dict.lookup_with_flags(text):
                idx = text.find(word, pos)
                if idx == -1:
                    continue
                if not is_known and any(c.isalpha() for c in word):
                    cursor.setPosition(idx)
                    cursor.setPosition(idx + len(word), QTextCursor.KeepAnchor)
                    cursor.setCharFormat(flagged_fmt)
                    unknown_count += 1
                pos = idx + len(word)
            cursor.endEditBlock()

            if unknown_count > 0:
                self._dict_hint.setText(
                    f"{unknown_count} word(s) not in dictionary (highlighted). "
                    "Use Custom mode for phonetic spelling."
                )
            else:
                self._dict_hint.clear()
        finally:
            self._highlighting = False

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return
        cursor = self._text_edit.textCursor()
        full_text = self._text_edit.toPlainText()
        text = full_text[cursor.selectionStart():].strip() if cursor.hasSelection() else full_text.strip()
        if not text:
            self._status.setText("No text to speak.")
            return
        self._player.stop()
        self._status.setText("Synthesizing...")
        self._play_btn.setEnabled(False)
        speed = slider_to_speed(self._speed_slider.value())
        voice = self.window().get_current_voice_id()
        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
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
        self._play_btn.setEnabled(True)
        self._status.setText("")

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

    def _insert_tag(self, tag_text: str):
        cursor = self._text_edit.textCursor()
        cursor.insertText(tag_text)
        self._text_edit.setFocus()

    def toggle_play_pause(self):
        if self._player.is_playing:
            self._player.pause()
        elif self._player.is_paused:
            self._player.play()
        else:
            self._on_play()
