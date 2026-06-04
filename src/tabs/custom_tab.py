from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGridLayout,
    QSlider, QLabel, QScrollArea, QFileDialog, QFrame, QSpinBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QTextCursor

import numpy as np

from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all, slider_to_speed
from src.data.phonemes import PHONEMES, PAUSE_TOKEN
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav
from src.utils.presets import Preset


class HybridSynthWorker(QThread):
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
            audio, sr = self._engine.synthesize_hybrid(
                self._text, voice=self._voice, speed=self._speed
            )
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))


class AnalyzeWorker(QThread):
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, file_path, kokoro):
        super().__init__()
        self._file_path = file_path
        self._kokoro = kokoro

    def run(self):
        try:
            from src.engine.analyzer import analyze_reference
            from src.engine.voice_blend import find_best_blend
            _, speed, depth, gender, median_f0 = analyze_reference(self._file_path)
            self.progress.emit(f"Finding best voice blend for {median_f0:.0f} Hz {gender} voice…")
            weights, tensor = find_best_blend(
                self._kokoro, self._file_path,
                progress_cb=lambda stage, detail: self.progress.emit(detail),
            )
            self.finished.emit({
                "speed": speed, "depth": depth,
                "weights": weights, "tensor": tensor,
                "gender": gender, "median_f0": median_f0,
            })
        except Exception as e:
            self.error.emit(str(e))


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(50)
        self.setProperty("state", "idle")
        self._label = QLabel("Drop audio file to match voice characteristics", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: #6b6b80; border: none; background: transparent;")
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def _update_state(self, state):
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_state("drag")

    def dragLeaveEvent(self, event):
        self._update_state("idle")

    def dropEvent(self, event: QDropEvent):
        self._update_state("hasfile")
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._label.setText(f"{Path(path).name}")
            self.file_dropped.emit(path)


class CustomTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000
        self._save_dir = Path.home() / "Music" / "Cove Narrator"
        self._worker: HybridSynthWorker | None = None

        layout = QVBoxLayout(self)

        # Text area for hybrid input
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(
            'Type text here. Click phoneme buttons below to insert pronunciation.\n'
            'Example: my cat {F EH L IY AH S} is very frantic at the vet'
        )
        self._text_edit.setMaximumHeight(100)
        layout.addWidget(self._text_edit)

        # Phoneme buttons in a scroll area
        phoneme_header = QHBoxLayout()
        ph_label = QLabel("PHONEME KEYS · ARPABET")
        ph_label.setObjectName("sectionLabel")
        phoneme_header.addWidget(ph_label)
        phoneme_header.addStretch()
        hint = QLabel("Click to insert at cursor")
        hint.setObjectName("voiceDesc")
        phoneme_header.addWidget(hint)
        layout.addLayout(phoneme_header)

        phoneme_scroll = QScrollArea()
        phoneme_scroll.setWidgetResizable(True)
        phoneme_scroll.setMinimumHeight(100)
        phoneme_scroll.setMaximumHeight(170)
        phoneme_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        btn_widget = QWidget()
        self._build_phoneme_grid(btn_widget)
        phoneme_scroll.setWidget(btn_widget)
        layout.addWidget(phoneme_scroll)

        # Reference audio drop zone
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        layout.addWidget(self._drop_zone)

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
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇  Export WAV")
        self._export_btn.setObjectName("exportButton")
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self._status = QLabel("")
        self._status.setObjectName("statusLabel")
        layout.addWidget(self._status)

        self._player.state_changed.connect(self._on_playback_state)

    def _build_phoneme_grid(self, parent):
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        max_cols = 15
        groups = [
            ("Vowels", [p for p in PHONEMES if p["category"] == "vowel"]),
            ("Consonants", [p for p in PHONEMES if p["category"] == "consonant"]),
        ]

        for group_name, phonemes in groups:
            header = QLabel(group_name)
            header.setObjectName("vowelLabel" if group_name == "Vowels" else "consonantLabel")
            outer.addWidget(header)

            grid_widget = QWidget()
            grid = QGridLayout(grid_widget)
            grid.setSpacing(3)
            grid.setContentsMargins(0, 0, 0, 0)

            col = 0
            row = 0
            for phoneme in phonemes:
                cat = phoneme["category"]
                btn = QPushButton(phoneme["arpabet"])
                btn.setToolTip(f'{phoneme["arpabet"]} — "{phoneme["example"]}"')
                btn.setFixedSize(42, 28)
                btn.setProperty("phoneme", cat)
                arp = phoneme["arpabet"]
                btn.clicked.connect(lambda checked=False, a=arp: self._insert_phoneme(a))
                grid.addWidget(btn, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            outer.addWidget(grid_widget)
        outer.addStretch()

    def _insert_phoneme(self, arpabet: str):
        cursor = self._text_edit.textCursor()
        pos = cursor.position()
        text = self._text_edit.toPlainText()

        brace_open = text.rfind("{", 0, pos)
        brace_close = text.rfind("}", 0, pos)
        inside_block = brace_open > brace_close

        if inside_block:
            cursor.insertText(f" {arpabet}")
        elif pos > 0 and text[pos - 1:pos] == "}":
            cursor.setPosition(pos - 1)
            cursor.insertText(f" {arpabet}")
        else:
            cursor.insertText(f"{{{arpabet}}}")

        self._text_edit.setFocus()

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

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return
        text = self._text_edit.toPlainText().strip()
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
        self._worker = HybridSynthWorker(self._engine, text, voice, speed)
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

    def _on_file_dropped(self, file_path: str):
        if hasattr(self, '_analyze_worker') and self._analyze_worker is not None:
            if self._analyze_worker.isRunning():
                self._status.setText("Analysis already in progress…")
                return
        self._status.setText(f"Analyzing {Path(file_path).name}…")
        kokoro = self._engine._kokoro
        self._analyze_worker = AnalyzeWorker(file_path, kokoro)
        self._analyze_worker.finished.connect(self._on_analysis_done)
        self._analyze_worker.progress.connect(lambda msg: self._status.setText(msg))
        self._analyze_worker.error.connect(self._on_analysis_error)
        self._analyze_worker.start()

    def _on_analysis_done(self, result: object):
        self._pitch_slider.setValue(0)
        self._speed_slider.setValue(result["speed"])
        self._depth_slider.setValue(result["depth"])
        main = self.window()
        if main and hasattr(main, '_set_custom_voice'):
            main._set_custom_voice(result["tensor"], result["weights"])
        desc = " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                          for v, w in result["weights"].items())
        self._status.setText(f"Custom voice: {desc}")

    def _on_analysis_error(self, msg: str):
        self._status.setText(f"Analysis error: {msg}")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Press Play first.")
            return
        path = export_wav(self._last_audio, self._last_sr, self._save_dir)
        self._status.setText(f"Exported: {path.name}")

    def toggle_play_pause(self):
        if self._player.is_playing:
            self._player.pause()
        elif self._player.is_paused:
            self._player.play()
        else:
            self._on_play()
