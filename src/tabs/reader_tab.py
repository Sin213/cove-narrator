import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QSpinBox, QFileDialog, QTextEdit,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor

import numpy as np

from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all, slider_to_speed
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav
from src.utils.presets import Preset

_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+|\n\n+')


def _split_sentences(text: str) -> list[str]:
    raw = _SENTENCE_RE.split(text)
    sentences = []
    for s in raw:
        s = s.strip()
        if s:
            sentences.append(s)
    return sentences


class ChunkWorker(QThread):
    finished = Signal(np.ndarray, int)
    error = Signal(str)

    def __init__(self, engine, text, voice, speed, pitch, depth):
        super().__init__()
        self._engine = engine
        self._text = text
        self._voice = voice
        self._speed = speed
        self._pitch = pitch
        self._depth = depth

    def run(self):
        try:
            audio, sr = self._engine.synthesize_raw(
                self._text, voice=self._voice, speed=self._speed
            )
            if self._pitch != 0 or self._depth != 0:
                audio = apply_all(audio, sr, pitch=self._pitch, depth=self._depth)
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))


class ReaderTab(QWidget):
    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._save_dir = Path.home() / "Music" / "Cove Narrator"
        self._worker: ChunkWorker | None = None

        self._sentences: list[str] = []
        self._sentence_positions: list[tuple[int, int]] = []
        self._current_idx: int = 0
        self._is_reading = False
        self._full_audio_parts: list[np.ndarray] = []
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000

        layout = QVBoxLayout(self)

        # File controls
        file_row = QHBoxLayout()
        self._open_btn = QPushButton("📂  Open File")
        self._open_btn.setObjectName("openFileButton")
        self._open_btn.clicked.connect(self._open_file)
        file_row.addWidget(self._open_btn)
        self._file_label = QLabel("No file loaded")
        self._file_label.setObjectName("voiceDesc")
        file_row.addWidget(self._file_label, 1)
        layout.addLayout(file_row)

        # Text display (read-only with highlighting)
        self._text_display = QTextEdit()
        self._text_display.setReadOnly(True)
        self._text_display.setPlaceholderText(
            "Open a .txt or .pdf file, or paste text here to start reading.\n"
            "Click anywhere in the text to start reading from that point."
        )
        self._text_display.setReadOnly(False)
        self._text_display.cursorPositionChanged.connect(self._on_cursor_moved)
        layout.addWidget(self._text_display, 1)

        # Progress
        progress_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(16)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%v / %m sentences")
        progress_row.addWidget(self._progress)
        self._time_label = QLabel("")
        self._time_label.setObjectName("statusLabel")
        progress_row.addWidget(self._time_label)
        layout.addLayout(progress_row)

        # Sliders
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
        self._play_btn = QPushButton("▶  Read")
        self._play_btn.setObjectName("playButton")
        self._play_btn.clicked.connect(self._on_play)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._export_btn = QPushButton("⬇  Export All as WAV")
        self._export_btn.setObjectName("exportButton")
        self._export_btn.clicked.connect(self._on_export)
        controls.addWidget(self._export_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self._status = QLabel("")
        self._status.setObjectName("statusLabel")
        layout.addWidget(self._status)

        self._player.playback_finished.connect(self._on_chunk_finished)
        self._player.state_changed.connect(self._on_playback_state)

        self._pitch_slider.valueChanged.connect(self._invalidate_prefetch)
        self._speed_slider.valueChanged.connect(self._invalidate_prefetch)
        self._depth_slider.valueChanged.connect(self._invalidate_prefetch)

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

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", str(Path.home()),
            "Supported Files (*.txt *.pdf);;Text Files (*.txt);;PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return
        filepath = Path(path)
        if filepath.suffix.lower() == ".pdf":
            text = self._extract_pdf(filepath)
        else:
            try:
                text = filepath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = filepath.read_text(encoding="latin-1")
        self._text_display.setPlainText(text)
        self._file_label.setText(filepath.name)
        self._prepare_sentences()

    def _extract_pdf(self, path: Path) -> str:
        import pymupdf
        doc = pymupdf.open(str(path))
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages)

    def _prepare_sentences(self):
        full_text = self._text_display.toPlainText()
        self._sentences = _split_sentences(full_text)
        self._sentence_positions = []
        search_from = 0
        for sentence in self._sentences:
            idx = full_text.find(sentence, search_from)
            if idx == -1:
                idx = search_from
            self._sentence_positions.append((idx, idx + len(sentence)))
            search_from = idx + len(sentence)
        self._current_idx = 0
        self._progress.setMaximum(len(self._sentences))
        self._progress.setValue(0)
        self._full_audio_parts = []
        self._status.setText(f"{len(self._sentences)} sentences ready")

    def _on_cursor_moved(self):
        if self._is_reading:
            return
        cursor = self._text_display.textCursor()
        pos = cursor.position()
        for i, (start, end) in enumerate(self._sentence_positions):
            if start <= pos <= end:
                self._current_idx = i
                break

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return
        if self._is_reading:
            self._player.pause()
            return
        text = self._text_display.toPlainText().strip()
        if not text:
            self._status.setText("No text to read.")
            return
        cursor_pos = self._text_display.textCursor().position()
        self._prepare_sentences()
        if not self._sentences:
            self._status.setText("No sentences found.")
            return
        if cursor_pos > 0:
            for i, (start, end) in enumerate(self._sentence_positions):
                if cursor_pos <= end:
                    self._current_idx = i
                    break
        self._is_reading = True
        self._full_audio_parts = []
        self._next_audio = None
        self._next_sr = 24000
        self._prefetch_worker: ChunkWorker | None = None
        self._synthesize_current()

    def _synthesize_current(self):
        if self._current_idx >= len(self._sentences):
            self._finish_reading()
            return

        self._highlight_sentence(self._current_idx)
        self._progress.setValue(self._current_idx + 1)

        remaining = len(self._sentences) - self._current_idx
        speed_val = slider_to_speed(self._speed_slider.value())
        est_seconds = remaining * 2.5 / speed_val
        mins = int(est_seconds // 60)
        secs = int(est_seconds % 60)
        self._time_label.setText(f"~{mins}m {secs}s remaining")
        self._status.setText(f"Reading sentence {self._current_idx + 1}/{len(self._sentences)}...")

        if self._next_audio is not None:
            self._play_and_prefetch(self._next_audio, self._next_sr)
            self._next_audio = None
            return

        sentence = self._sentences[self._current_idx]
        voice = self.window().get_current_voice_id()
        speed = slider_to_speed(self._speed_slider.value())
        pitch = self._pitch_slider.value()
        depth = self._depth_slider.value()

        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        self._worker = ChunkWorker(self._engine, sentence, voice, speed, pitch, depth)
        self._worker.finished.connect(self._on_chunk_synth_done)
        self._worker.error.connect(self._on_chunk_synth_error)
        self._worker.start()

    def _play_and_prefetch(self, audio: np.ndarray, sr: int):
        self._full_audio_parts.append(audio)
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._prefetch_next()

    def _invalidate_prefetch(self):
        self._next_audio = None

    def _prefetch_next(self):
        next_idx = self._current_idx + 1
        if next_idx >= len(self._sentences):
            return
        voice = self.window().get_current_voice_id()
        speed = slider_to_speed(self._speed_slider.value())
        pitch = self._pitch_slider.value()
        depth = self._depth_slider.value()
        sentence = self._sentences[next_idx]
        self._prefetch_worker = ChunkWorker(self._engine, sentence, voice, speed, pitch, depth)
        self._prefetch_worker.finished.connect(self._on_prefetch_done)
        self._prefetch_worker.error.connect(lambda _: None)
        self._prefetch_worker.start()

    def _on_prefetch_done(self, audio: np.ndarray, sr: int):
        self._next_audio = audio
        self._next_sr = sr

    def _on_chunk_synth_done(self, audio: np.ndarray, sr: int):
        self._play_and_prefetch(audio, sr)

    def _on_chunk_synth_error(self, msg: str):
        self._status.setText(f"Error: {msg}")
        self._is_reading = False

    def _on_chunk_finished(self):
        if not self._is_reading:
            return
        if self._current_idx + 1 >= len(self._sentences):
            self._current_idx += 1
            self._finish_reading()
        else:
            self._current_idx += 1
            self._synthesize_current()

    def _finish_reading(self):
        self._is_reading = False
        self._clear_highlight()
        self._time_label.setText("")
        if self._full_audio_parts:
            self._last_audio = np.concatenate(self._full_audio_parts)
        self._status.setText("Finished reading.")
        self._progress.setValue(len(self._sentences))

    def _highlight_sentence(self, idx: int):
        if idx >= len(self._sentence_positions):
            return
        start, end = self._sentence_positions[idx]

        cursor = self._text_display.textCursor()
        cursor.beginEditBlock()

        cursor.select(QTextCursor.Document)
        default_fmt = QTextCharFormat()
        cursor.setCharFormat(default_fmt)
        cursor.clearSelection()

        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor(80, 230, 207, 36))
        highlight_fmt.setForeground(QColor(236, 236, 241))

        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.setCharFormat(highlight_fmt)
        cursor.endEditBlock()

        self._text_display.setTextCursor(cursor)
        self._text_display.ensureCursorVisible()

    def _clear_highlight(self):
        cursor = self._text_display.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()
        cursor.endEditBlock()

    def _on_stop(self):
        self._is_reading = False
        self._player.stop()
        self._clear_highlight()
        self._play_btn.setEnabled(True)
        self._time_label.setText("")
        self._status.setText("Stopped.")

    def _on_playback_state(self, state: str):
        if state == "playing":
            self._play_btn.setText("⏸ Pause")
        elif state == "paused":
            self._play_btn.setText("▶ Resume")
        else:
            self._play_btn.setText("▶ Read")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Read the text first.")
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
