import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QFrame, QFileDialog,
    QSlider, QSpinBox, QInputDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent

import numpy as np
import sounddevice as sd
import soundfile as sf

from src.engine.clone_tts import VoiceMatchEngine, VoiceMatchResult
from src.engine.tts import TTSEngine
from src.engine.audio_dsp import slider_to_speed
from src.utils.audio_player import AudioPlayer
from src.utils.export import export_wav


SUPPORTED_FORMATS = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus", ".wma")


def _hd_deps_dir() -> Path | None:
    if getattr(sys, 'frozen', False):
        if platform.system() == "Linux":
            return Path.home() / ".local" / "share" / "cove-narrator" / "hd-deps"
        return Path(sys.executable).parent / "dependencies" / "cove-narrator"
    if platform.system() == "Linux":
        return Path.home() / ".local" / "share" / "cove-narrator" / "hd-deps"
    return None


def _hd_log(msg: str):
    """Append a diagnostic line to hd_install.log next to the exe (frozen) so
    HD deps install/import failures are recoverable without a console."""
    try:
        if getattr(sys, 'frozen', False):
            log_path = Path(sys.executable).parent / "hd_install.log"
        else:
            d = _hd_deps_dir()
            log_path = (d.parent / "hd_install.log") if d else None
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg.rstrip() + "\n")
    except Exception:
        pass


# major.minor of transformers the vendored Qwen3-TTS model requires. The model
# was written for 4.x; the 5.x port produced degenerate (non-stop) generation.
_REQUIRED_TRANSFORMERS = (4, 57)


def _purge_stale_hd_deps():
    """If the HD deps dir holds a transformers of the wrong major.minor (e.g. a
    previous build's 5.x), delete the deps dir so a clean, correct stack
    installs. Reads the dist-info on disk — never imports the stale version —
    so the running process is not poisoned with the wrong transformers."""
    import re
    import shutil
    deps = _hd_deps_dir()
    if not deps or not deps.is_dir():
        return
    for p in deps.glob("transformers-*.dist-info"):
        m = re.match(r"transformers-(\d+)\.(\d+)", p.name)
        if m and (int(m.group(1)), int(m.group(2))) != _REQUIRED_TRANSFORMERS:
            _hd_log(f"purging stale HD deps (found {p.name}, "
                    f"need transformers {_REQUIRED_TRANSFORMERS[0]}.{_REQUIRED_TRANSFORMERS[1]}.x)")
            shutil.rmtree(deps, ignore_errors=True)
            return


def _ensure_hd_deps_on_path():
    import site
    deps_dir = _hd_deps_dir()
    if deps_dir and deps_dir.is_dir():
        deps = str(deps_dir)
        if deps not in sys.path:
            sys.path.append(deps)
            site.addsitedir(deps)


class _AnalyzeWorker(QThread):
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, engine: VoiceMatchEngine, ref_path: str):
        super().__init__()
        self._engine = engine
        self._ref_path = ref_path

    def run(self):
        try:
            result = self._engine.analyze(
                self._ref_path,
                progress_cb=lambda msg: self.progress.emit(msg),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _SynthWorker(QThread):
    finished = Signal(np.ndarray, int)
    error = Signal(str)

    def __init__(self, engine, text, tensor, speed, pitch, depth):
        super().__init__()
        self._engine = engine
        self._text = text
        self._tensor = tensor
        self._speed = speed
        self._pitch = pitch
        self._depth = depth

    def run(self):
        try:
            audio, sr = self._engine.synthesize(
                self._text, self._tensor,
                speed=self._speed, pitch=self._pitch, depth=self._depth,
            )
            self.finished.emit(audio, sr)
        except Exception as e:
            self.error.emit(str(e))


class _DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(60)
        self.setProperty("state", "idle")
        self._label = QLabel("Drop a voice clip here (mp3, wav, flac…)", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: #6b6b80; border: none; background: transparent;")
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("state", "drag")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("state", "idle")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_FORMATS:
                self.setProperty("state", "hasfile")
                self.style().unpolish(self)
                self.style().polish(self)
                self._label.setText(Path(path).name)
                self.file_dropped.emit(path)


class CloneTab(QWidget):
    preset_saved = Signal()

    def __init__(self, engine: TTSEngine, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._player = player
        self._vm_engine = VoiceMatchEngine(engine)
        self._last_audio: np.ndarray | None = None
        self._last_sr: int = 24000
        self._save_dir = Path.home() / "Music" / "Cove Narrator"
        self._ref_audio_path: str | None = None
        self._temp_rec_path: str | None = None
        self._match_result: VoiceMatchResult | None = None
        self._qwen_engine = None
        self._worker = None
        self._analyze_worker = None
        self._recording = False
        self._rec_frames: list[np.ndarray] = []
        self._rec_stream = None
        self._rec_timer = QTimer()
        self._rec_timer.setInterval(100)
        self._rec_timer.timeout.connect(self._update_rec_level)
        self._rec_elapsed = 0.0

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # -- Reference audio section
        ref_header = QLabel("REFERENCE VOICE")
        ref_header.setObjectName("sectionLabel")
        layout.addWidget(ref_header)

        ref_hint = QLabel("Upload or record 5–15 seconds of clear speech. The voice will be analyzed and matched.")
        ref_hint.setObjectName("voiceDesc")
        ref_hint.setWordWrap(True)
        layout.addWidget(ref_hint)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(10)
        self._drop_zone = _DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        ref_row.addWidget(self._drop_zone, 3)

        rec_panel = QFrame()
        rec_panel.setObjectName("dropZone")
        rec_layout = QVBoxLayout(rec_panel)
        rec_layout.setContentsMargins(12, 8, 12, 8)
        self._rec_btn = QPushButton("⏺  Record")
        self._rec_btn.setObjectName("playButton")
        self._rec_btn.setFocusPolicy(Qt.NoFocus)
        self._rec_btn.clicked.connect(self._toggle_recording)
        rec_layout.addWidget(self._rec_btn)
        self._rec_level = QLabel("")
        self._rec_level.setAlignment(Qt.AlignCenter)
        self._rec_level.setObjectName("voiceDesc")
        rec_layout.addWidget(self._rec_level)
        ref_row.addWidget(rec_panel, 2)
        layout.addLayout(ref_row)

        browse_row = QHBoxLayout()
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("tagButton")
        browse_btn.setFixedHeight(26)
        browse_btn.clicked.connect(self._on_browse)
        browse_row.addWidget(browse_btn)
        self._preview_btn = QPushButton("▶ Preview")
        self._preview_btn.setObjectName("tagButton")
        self._preview_btn.setFixedHeight(26)
        self._preview_btn.clicked.connect(self._on_preview_ref)
        self._preview_btn.setEnabled(False)
        browse_row.addWidget(self._preview_btn)
        self._ref_file_label = QLabel("No reference audio loaded")
        self._ref_file_label.setObjectName("voiceDesc")
        browse_row.addWidget(self._ref_file_label)
        browse_row.addStretch()
        layout.addLayout(browse_row)

        # -- Voice match info + sliders
        self._match_label = QLabel("")
        self._match_label.setObjectName("voiceDesc")
        layout.addWidget(self._match_label)

        slider_layout = QHBoxLayout()
        self._pitch_slider, self._pitch_spin, pitch_group = self._make_slider("Pitch", "#7fd0ff")
        self._speed_slider, self._speed_spin, speed_group = self._make_slider("Speed", "#50e6cf")
        self._depth_slider, self._depth_spin, depth_group = self._make_slider("Depth", "#c89bff")
        slider_layout.addLayout(pitch_group)
        slider_layout.addLayout(speed_group)
        slider_layout.addLayout(depth_group)
        layout.addLayout(slider_layout)

        save_row = QHBoxLayout()
        self._save_btn = QPushButton("💾  Save as preset")
        self._save_btn.setObjectName("tagButton")
        self._save_btn.setFixedHeight(28)
        self._save_btn.clicked.connect(self._on_save_preset)
        self._save_btn.setEnabled(False)
        save_row.addWidget(self._save_btn)
        save_row.addStretch()
        layout.addLayout(save_row)

        # -- Text input
        synth_label = QLabel("TEXT TO SPEAK")
        synth_label.setObjectName("sectionLabel")
        layout.addWidget(synth_label)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Type the text you want spoken in the matched voice…")
        self._text_edit.setMaximumHeight(100)
        layout.addWidget(self._text_edit)

        # -- Controls
        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶  Speak")
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
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # -- Optional HD neural cloning (single button → popup)
        self._hd_btn = QPushButton("🎤  HD Voice Clone")
        self._hd_btn.setObjectName("tagButton")
        self._hd_btn.setFixedHeight(32)
        self._hd_btn.clicked.connect(self._on_hd_action)
        layout.addWidget(self._hd_btn)
        self._hd_status = QLabel("")
        self._hd_status.setObjectName("voiceDesc")
        self._hd_status.setWordWrap(True)
        layout.addWidget(self._hd_status)

        layout.addStretch()
        self._player.state_changed.connect(self._on_playback_state)

    # -- Slider builder --

    def _make_slider(self, name: str, color: str = "#50e6cf"):
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

    def apply_preset(self, preset):
        self._pitch_slider.setValue(preset.pitch)
        self._speed_slider.setValue(preset.speed)
        self._depth_slider.setValue(preset.depth)
        if preset.blend_key:
            try:
                from src.engine.voice_blend import CustomVoiceManager
                voices = CustomVoiceManager()
                tensor, meta = voices.load(preset.blend_key)
                self._match_result = VoiceMatchResult(
                    weights=meta.get("weights", {}), tensor=tensor,
                    pitch=preset.pitch, speed=preset.speed, depth=preset.depth,
                    gender="", median_f0=0,
                )
                self._match_label.setText(f"Preset: {preset.name}")
                self._save_btn.setEnabled(True)
            except Exception:
                pass
        else:
            self._match_result = None
            self._match_label.setText("")
            self._save_btn.setEnabled(False)

    def _cleanup_temp_rec(self):
        if self._temp_rec_path:
            try:
                Path(self._temp_rec_path).unlink(missing_ok=True)
            except OSError:
                pass
            self._temp_rec_path = None

    # -- File input --

    def _on_file_dropped(self, path: str):
        if self._analyze_worker and self._analyze_worker.isRunning():
            self._status.setText("Analysis already in progress…")
            return
        self._cleanup_temp_rec()
        self._ref_audio_path = path
        self._ref_file_label.setText(Path(path).name)
        self._preview_btn.setEnabled(True)
        self._start_analysis(path)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reference audio", str(Path.home()),
            f"Audio files (*{' *'.join(SUPPORTED_FORMATS)})",
        )
        if path:
            self._on_file_dropped(path)
            self._drop_zone._label.setText(Path(path).name)
            self._drop_zone.setProperty("state", "hasfile")
            self._drop_zone.style().unpolish(self._drop_zone)
            self._drop_zone.style().polish(self._drop_zone)

    def _on_preview_ref(self):
        if not self._ref_audio_path:
            return
        try:
            from src.engine import audio_features as af
            y, sr = af.load_audio(self._ref_audio_path, sr=24000)
            self._player.load(y, sr)
            self._player.play()
        except Exception as e:
            self._status.setText(f"Preview error: {e}")

    # -- Voice Match analysis --

    def _start_analysis(self, path: str):
        if self._analyze_worker and self._analyze_worker.isRunning():
            self._status.setText("Analysis already in progress…")
            return
        self._status.setText(f"Analyzing {Path(path).name}…")
        self._save_btn.setEnabled(False)
        self._analyze_worker = _AnalyzeWorker(self._vm_engine, path)
        self._analyze_worker.finished.connect(self._on_analysis_done)
        self._analyze_worker.progress.connect(lambda msg: self._status.setText(msg))
        self._analyze_worker.error.connect(lambda msg: self._status.setText(f"Analysis error: {msg}"))
        self._analyze_worker.start()

    def _on_analysis_done(self, result: VoiceMatchResult):
        self._match_result = result
        self._pitch_slider.setValue(result.pitch)
        self._speed_slider.setValue(result.speed)
        self._depth_slider.setValue(result.depth)
        self._match_label.setText(f"Matched: {result.description}  ({result.median_f0:.0f} Hz {result.gender})")
        self._save_btn.setEnabled(True)
        main = self.window()
        if main and hasattr(main, '_set_custom_voice'):
            main._set_custom_voice(result.tensor, result.weights)
        self._status.setText("Voice matched. Adjust sliders to taste, then Speak or Save.")

    # -- Recording --

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._rec_frames = []
        self._rec_elapsed = 0.0
        try:
            self._rec_stream = sd.InputStream(
                samplerate=24000, channels=1, dtype="float32",
                callback=self._rec_callback, blocksize=2400,
            )
            self._rec_stream.start()
        except Exception as e:
            self._status.setText(f"Recording failed: {e}")
            return
        self._recording = True
        self._rec_btn.setText("⏹  Stop recording")
        self._rec_btn.setStyleSheet("background: #cc3333;")
        self._rec_level.setText("0.0s")
        self._rec_timer.start()

    def _rec_callback(self, indata, frames, time_info, status):
        self._rec_frames.append(indata.copy())

    def _update_rec_level(self):
        self._rec_elapsed += 0.1
        if self._rec_frames:
            rms = np.sqrt(np.mean(self._rec_frames[-1] ** 2))
            bars = int(min(rms * 200, 20))
            meter = "█" * bars + "░" * (20 - bars)
            self._rec_level.setText(f"{self._rec_elapsed:.1f}s  {meter}")
        else:
            self._rec_level.setText(f"{self._rec_elapsed:.1f}s")

    def _stop_recording(self):
        self._recording = False
        self._rec_timer.stop()
        if self._rec_stream:
            self._rec_stream.stop()
            self._rec_stream.close()
            self._rec_stream = None
        self._rec_btn.setText("⏺  Record")
        self._rec_btn.setStyleSheet("")
        if not self._rec_frames:
            self._rec_level.setText("No audio captured")
            return
        audio = np.concatenate(self._rec_frames, axis=0).squeeze()
        duration = len(audio) / 24000
        if duration < 2.0:
            self._rec_level.setText(f"{duration:.1f}s — too short, need 3s+")
            return
        self._cleanup_temp_rec()
        tmp = NamedTemporaryFile(suffix=".wav", delete=False, prefix="cove_rec_")
        sf.write(tmp.name, audio, 24000)
        tmp.close()
        self._temp_rec_path = tmp.name
        self._ref_audio_path = tmp.name
        self._ref_file_label.setText(f"Recording ({duration:.1f}s)")
        self._preview_btn.setEnabled(True)
        self._drop_zone._label.setText(f"🎙 Recording ({duration:.1f}s)")
        self._drop_zone.setProperty("state", "hasfile")
        self._drop_zone.style().unpolish(self._drop_zone)
        self._drop_zone.style().polish(self._drop_zone)
        self._rec_level.setText(f"{duration:.1f}s ✓")
        self._start_analysis(tmp.name)

    # -- Save preset --

    def _on_save_preset(self):
        if self._match_result is None:
            return
        name, ok = QInputDialog.getText(self, "Save Clone Preset", "Preset name:")
        if not ok or not name.strip():
            return
        from src.engine.voice_blend import CustomVoiceManager
        from src.utils.presets import Preset, PresetManager
        voices = CustomVoiceManager()
        saved_path = voices.save(name.strip(), self._match_result.tensor, self._match_result.weights)
        presets = PresetManager()
        safe_key = saved_path.stem
        preset = Preset(
            name=name.strip(),
            voice_id="custom_blend",
            pitch=self._pitch_slider.value(),
            speed=self._speed_slider.value(),
            depth=self._depth_slider.value(),
            blend_key=safe_key,
        )
        presets.save_preset(preset)
        self._status.setText(f"Saved preset: {name.strip()}")
        self.preset_saved.emit()

    # -- Synthesis --

    def _on_play(self):
        if self._player.is_paused:
            self._player.play()
            return
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._status.setText("Type some text to speak.")
            return
        if self._match_result is None:
            self._status.setText("Drop a reference clip first — the voice needs to be analyzed.")
            return
        self._player.stop()
        self._status.setText("Synthesizing…")
        self._play_btn.setEnabled(False)
        speed = slider_to_speed(self._speed_slider.value())
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        self._worker = _SynthWorker(
            self._vm_engine, text, self._match_result.tensor,
            speed, self._pitch_slider.value(), self._depth_slider.value(),
        )
        self._worker.finished.connect(self._on_synth_done)
        self._worker.error.connect(self._on_synth_error)
        self._worker.start()

    def _on_synth_done(self, audio: np.ndarray, sr: int):
        self._last_audio = audio
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._play_btn.setEnabled(True)
        self._status.setText(f"Playing ({len(audio) / sr:.1f}s)")

    def _on_synth_error(self, msg: str):
        self._play_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")

    def _on_stop(self):
        self._player.stop()
        self._play_btn.setEnabled(True)
        self._status.setText("")

    def _on_export(self):
        if self._last_audio is None:
            self._status.setText("Nothing to export. Press Speak first.")
            return
        path = export_wav(self._last_audio, self._last_sr, self._save_dir)
        self._status.setText(f"Exported: {path.name}")

    def _on_playback_state(self, state: str):
        if state == "playing":
            self._play_btn.setText("⏸  Pause")
        elif state == "paused":
            self._play_btn.setText("▶  Resume")
        else:
            self._play_btn.setText("▶  Speak")

    def toggle_play_pause(self):
        if self._player.is_playing:
            self._player.pause()
        elif self._player.is_paused:
            self._player.play()
        else:
            self._on_play()

    # -- HD Neural Clone (optional download) --

    def _on_hd_action(self, _after_install=False):
        if not _after_install:
            _purge_stale_hd_deps()
        _ensure_hd_deps_on_path()
        missing = []
        import_errors = {}
        for mod in ("torch", "transformers", "huggingface_hub"):
            try:
                __import__(mod)
            except Exception as e:
                missing.append(mod.replace("_", "-"))
                import_errors[mod] = f"{type(e).__name__}: {e}"
        if missing:
            if _after_install:
                for mod, err in import_errors.items():
                    print(f"[HD deps] {mod}: {err}", file=sys.stderr)
                    _hd_log(f"import failed after install: {mod}: {err}")
                detail = "; ".join(
                    f"{m}: {e}" for m, e in import_errors.items()
                )
                self._hd_status.setText(
                    f"Still missing after install: {', '.join(missing)}.\n"
                    f"{detail}\n(details in hd_install.log next to the app)"
                )
                return
            self._offer_hd_deps_install(missing)
            return

        from src.engine.clone_tts import QwenCloneEngine
        qwen = QwenCloneEngine()
        if qwen.is_downloaded():
            self._play_hd_clone()
            return

        if not _after_install:
            from PySide6.QtWidgets import QMessageBox
            dlg = QMessageBox(self)
            dlg.setWindowTitle("HD Voice Clone")
            dlg.setIcon(QMessageBox.Information)
            dlg.setText("Download the HD voice cloning model?")
            dlg.setInformativeText(
                "This downloads Qwen3-TTS 1.7B (4.3 GB) for higher-quality "
                "neural voice cloning.\n\n"
                "Requirements:\n"
                "• NVIDIA GPU (4+ GB VRAM)\n"
                "• ~4.3 GB disk space\n\n"
                "The Voice Match mode above works without this download — "
                "HD Clone is optional for users who want closer voice similarity."
            )
            dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            dlg.button(QMessageBox.Ok).setText("Download (4.3 GB)")
            if dlg.exec() != QMessageBox.Ok:
                return

        self._hd_btn.setEnabled(False)
        self._hd_status.setText("Downloading Qwen3-TTS model…")
        self._hd_download_worker = _HDDownloadWorker(qwen)
        self._hd_download_worker.progress.connect(lambda msg: self._hd_status.setText(msg))
        self._hd_download_worker.finished.connect(self._on_hd_download_done)
        self._hd_download_worker.error.connect(lambda msg: self._on_hd_download_error(msg))
        self._hd_download_worker.start()

    def _offer_hd_deps_install(self, missing: list[str]):
        from PySide6.QtWidgets import QMessageBox
        is_frozen = getattr(sys, 'frozen', False)

        dlg = QMessageBox(self)
        dlg.setWindowTitle("HD Voice Clone — Setup Required")
        dlg.setIcon(QMessageBox.Information)
        dlg.setText("HD Voice Clone requires additional packages.")
        detail = (
            f"Missing: {', '.join(missing)}\n\n"
            "This download is ~5 GB and requires:\n"
            "  - NVIDIA GPU with 4+ GB VRAM\n"
            "  - ~5 GB disk space\n\n"
        )
        deps_dir = _hd_deps_dir()
        if deps_dir:
            detail += f"Packages will be installed to:\n  {deps_dir}"
        else:
            detail += "Packages will be installed to your Python environment."
        dlg.setInformativeText(detail)
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        dlg.button(QMessageBox.Ok).setText("Install (~5 GB)")
        if dlg.exec() != QMessageBox.Ok:
            return

        deps_dir = _hd_deps_dir()

        self._hd_btn.setEnabled(False)
        self._hd_status.setText("Installing HD dependencies…")
        self._hd_deps_worker = _HDDepsInstallWorker(deps_dir)
        self._hd_deps_worker.progress.connect(lambda msg: self._hd_status.setText(msg))
        self._hd_deps_worker.finished.connect(self._on_hd_deps_installed)
        self._hd_deps_worker.error.connect(lambda msg: self._on_hd_deps_error(msg))
        self._hd_deps_worker.start()

    def _on_hd_deps_installed(self):
        self._hd_btn.setEnabled(True)
        self._hd_status.setText(
            "Dependencies installed! Restart the app to use HD Voice Clone."
        )

    def _on_hd_deps_error(self, msg):
        self._hd_btn.setEnabled(True)
        self._hd_status.setText(f"Install failed: {msg}")

    def _on_hd_download_done(self):
        self._hd_btn.setEnabled(True)
        self._hd_btn.setText("🎤  Use HD Clone")
        self._hd_status.setText("Download complete! Drop a reference clip and click 'Use HD Clone'.")

    def _on_hd_download_error(self, msg):
        self._hd_btn.setEnabled(True)
        self._hd_status.setText(f"Download failed: {msg}")

    def _play_hd_clone(self):
        if not self._ref_audio_path:
            self._hd_status.setText("Load a reference voice clip first.")
            return
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._hd_status.setText("Type some text to speak first.")
            return
        if self._qwen_engine is None:
            from src.engine.clone_tts import QwenCloneEngine
            self._qwen_engine = QwenCloneEngine()
        self._hd_btn.setEnabled(False)
        self._hd_status.setText("Loading Qwen3-TTS…")
        self._hd_synth_worker = _HDSynthWorker(self._qwen_engine, self._ref_audio_path, text)
        self._hd_synth_worker.progress.connect(lambda msg: self._hd_status.setText(msg))
        self._hd_synth_worker.finished.connect(self._on_hd_synth_done)
        self._hd_synth_worker.error.connect(lambda msg: self._on_hd_synth_error(msg))
        self._hd_synth_worker.start()

    def _on_hd_synth_done(self, audio: np.ndarray, sr: int):
        self._hd_btn.setEnabled(True)
        self._last_audio = audio
        self._last_sr = sr
        self._player.load(audio, sr)
        self._player.play()
        self._hd_status.setText(f"Playing HD clone ({len(audio) / sr:.1f}s)")

    def _on_hd_synth_error(self, msg):
        self._hd_btn.setEnabled(True)
        self._hd_status.setText(f"Error: {msg}")


class _HDDownloadWorker(QThread):
    finished = Signal()
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, qwen_engine):
        super().__init__()
        self._engine = qwen_engine

    def run(self):
        try:
            self._engine.download(progress_cb=lambda msg: self.progress.emit(msg))
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class _HDSynthWorker(QThread):
    finished = Signal(np.ndarray, int)
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, engine, ref_audio_path, text):
        super().__init__()
        self._engine = engine
        self._ref_audio_path = ref_audio_path
        self._text = text

    def run(self):
        try:
            if not self._engine.is_loaded():
                self.progress.emit("Loading Qwen3-TTS 1.7B (first time may take a moment)…")
                self._engine.load()
            self.progress.emit("Synthesizing with HD clone…")
            audio, sr = self._engine.synthesize(self._text, self._ref_audio_path)
            self.finished.emit(audio, sr)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")


class _HDDepsInstallWorker(QThread):
    finished = Signal()
    progress = Signal(str)
    error = Signal(str)

    # transformers 4.x — the version Qwen3-TTS was written for. The 5.x port
    # produced degenerate generation (non-stop buzzing); 4.57.3 generates
    # correct, properly-terminated speech. hf-hub must stay <1.0 (4.57.3
    # requires it), which pulls requests/urllib3 instead of the httpx stack.
    HD_PACKAGES = [
        "torch==2.12.0",
        "transformers==4.57.3",
        "huggingface-hub==0.36.2",
        "tokenizers==0.22.2",
        "numpy", "pyyaml", "regex", "safetensors", "accelerate", "psutil",
        "tqdm", "packaging", "filelock", "fsspec", "typing-extensions",
        "setuptools", "requests", "urllib3", "charset-normalizer",
        "certifi", "idna", "colorama",
        "jinja2", "markupsafe", "mpmath", "networkx", "sympy",
        "soundfile", "cffi", "pycparser",
    ]
    ESTIMATED_TOTAL_MB = 800

    def __init__(self, deps_dir: Path | None):
        super().__init__()
        self._deps_dir = deps_dir

    @staticmethod
    def _popen_kwargs() -> dict:
        kw = {}
        if platform.system() == "Windows":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        return kw

    def run(self):
        try:
            pip_cmd = self._find_pip()
            if not pip_cmd:
                self.error.emit(
                    "Could not find pip or Python on this system.\n"
                    "Install Python from python.org, then restart the app."
                )
                return

            cmd = [*pip_cmd, "install", "--progress-bar", "off"]
            if self._deps_dir:
                self._deps_dir.mkdir(parents=True, exist_ok=True)
                cmd += ["--target", str(self._deps_dir)]
            cmd += list(self.HD_PACKAGES)

            self.progress.emit("Installing HD dependencies…")
            # Drain pip's output to a log file, NOT a PIPE. The progress loop
            # below polls proc.poll() without ever reading stdout, so a PIPE
            # fills the ~64 KB OS buffer and deadlocks pip mid-install — the UI
            # hangs on "Resolving dependencies…" forever. Mirrors the
            # model-download fix in clone_tts._download_subprocess.
            pip_log_path = (
                (self._deps_dir.parent if self._deps_dir else Path.cwd())
                / "hd_pip_install.log"
            )
            pip_log = open(
                pip_log_path, "w", encoding="utf-8", errors="replace"
            )
            proc = subprocess.Popen(
                cmd, stdout=pip_log, stderr=subprocess.STDOUT,
                **self._popen_kwargs(),
            )

            start = time.monotonic()
            last_progress = 0.0

            while proc.poll() is None:
                time.sleep(2)
                elapsed = time.monotonic() - start
                elapsed_min = int(elapsed / 60)
                elapsed_sec = int(elapsed % 60)
                ts = f"{elapsed_min}:{elapsed_sec:02d}"

                actual_mb = 0.0
                if self._deps_dir and self._deps_dir.is_dir():
                    try:
                        actual_mb = sum(
                            f.stat().st_size
                            for f in self._deps_dir.rglob("*")
                            if f.is_file()
                        ) / 1_000_000
                    except OSError:
                        actual_mb = last_progress
                    last_progress = actual_mb

                pct = min(95, int(actual_mb / self.ESTIMATED_TOTAL_MB * 100))
                if pct > 2 and elapsed > 10:
                    eta_sec = elapsed / pct * (100 - pct)
                    eta_min = max(1, int(eta_sec / 60))
                    self.progress.emit(
                        f"Installing… {pct}%  —  "
                        f"ETA ~{eta_min} min  "
                        f"({actual_mb:.0f} / ~{self.ESTIMATED_TOTAL_MB} MB)")
                elif actual_mb > 0:
                    self.progress.emit(
                        f"Installing… "
                        f"({actual_mb:.0f} MB)  [{ts}]")
                else:
                    self.progress.emit(
                        f"Resolving dependencies… [{ts}]")

            proc.wait(timeout=3600)
            pip_log.close()

            if proc.returncode != 0:
                try:
                    tail = pip_log_path.read_text(
                        encoding="utf-8", errors="replace")[-800:]
                except OSError:
                    tail = ""
                _hd_log(f"pip install failed (exit {proc.returncode}):\n{tail}")
                self.error.emit(
                    "Installation failed. Check your internet connection.\n"
                    "(details in hd_install.log next to the app)"
                )
                return

            import importlib
            if self._deps_dir:
                _ensure_hd_deps_on_path()
                py_dir = self._deps_dir.parent / "_python"
                if py_dir.is_dir():
                    for zf in py_dir.glob("python*.zip"):
                        if str(zf) not in sys.path:
                            sys.path.append(str(zf))
            importlib.invalidate_caches()

            self.progress.emit("Verifying imports…")
            failed = {}
            for mod in ("torch", "transformers", "huggingface_hub"):
                try:
                    __import__(mod)
                except Exception as e:
                    failed[mod] = f"{type(e).__name__}: {e}"

            if failed:
                details = "\n".join(
                    f"  {m}: {e}" for m, e in failed.items()
                )
                for m, e in failed.items():
                    _hd_log(f"worker verify import failed: {m}: {e}")
                self.error.emit(
                    f"Packages installed but imports failed:\n{details}"
                )
                return

            self.finished.emit()
        except subprocess.TimeoutExpired:
            self.error.emit("Installation timed out.")
        except Exception as e:
            self.error.emit(str(e))

    def _find_pip(self) -> list[str] | None:
        if not getattr(sys, 'frozen', False):
            return [sys.executable, "-m", "pip"]

        from src.engine.clone_tts import find_matching_python
        py = find_matching_python()
        if py:
            _hd_log(f"_find_pip: using {' '.join(py)} -m pip")
            return [*py, "-m", "pip"]

        ver_str = f"{sys.version_info.major}.{sys.version_info.minor}"
        if platform.system() == "Windows":
            self.progress.emit(
                f"No compatible Python {ver_str} found on PATH. "
                "Bootstrapping one…"
            )
            _hd_log(f"_find_pip: no system Python {ver_str}; bootstrapping embeddable")
            return self._bootstrap_windows_pip()
        return None

    def _bootstrap_windows_pip(self) -> list[str] | None:
        py_dir = self._deps_dir.parent / "_python"
        py_exe = py_dir / "python.exe"

        if py_exe.exists():
            return [str(py_exe), "-m", "pip"]

        try:
            import urllib.request
            import zipfile

            py_dir.mkdir(parents=True, exist_ok=True)

            ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            arch = "amd64" if platform.machine().endswith("64") else "win32"
            url = (
                f"https://www.python.org/ftp/python/{ver}/"
                f"python-{ver}-embed-{arch}.zip"
            )
            zip_path = py_dir / "python.zip"
            self.progress.emit("Downloading Python runtime (~15 MB)…")
            urllib.request.urlretrieve(url, zip_path)

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(py_dir)
            zip_path.unlink()

            for pth in py_dir.glob("python*._pth"):
                text = pth.read_text()
                pth.write_text(text.replace("#import site", "import site"))

            self.progress.emit("Setting up pip…")
            get_pip = py_dir / "get-pip.py"
            urllib.request.urlretrieve(
                "https://bootstrap.pypa.io/get-pip.py", get_pip,
            )
            subprocess.run(
                [str(py_exe), str(get_pip)],
                capture_output=True, timeout=300,
                **self._popen_kwargs(),
            )
            get_pip.unlink(missing_ok=True)

            self.progress.emit("Installing build tools…")
            subprocess.run(
                [str(py_exe), "-m", "pip", "install",
                 "setuptools", "wheel"],
                capture_output=True, timeout=300,
                **self._popen_kwargs(),
            )

            if py_exe.exists():
                return [str(py_exe), "-m", "pip"]
        except Exception:
            pass
        return None
