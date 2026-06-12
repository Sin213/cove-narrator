from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel, QInputDialog,
    QFrame, QDialog, QLineEdit, QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QMouseEvent

from src.utils.config import load_config, save_config
from src.utils.theme import COVE_STYLESHEET
from src.utils.chrome import CoveTitleBar, FramelessResizer
from src.engine.tts import TTSEngine
from src.utils.audio_player import AudioPlayer
from src.utils.presets import PresetManager, Preset
from src.engine.voice_blend import CustomVoiceManager
from src.utils.settings_dialog import SettingsDialog
from src.tabs.simple_tab import SimpleTab
from src.tabs.custom_tab import CustomTab
from src.tabs.reader_tab import ReaderTab
from src.tabs.clone_tab import CloneTab

_MODES = [
    {"icon": "≡", "title": "Simple", "desc": "Type & tag, then speak",
     "head": "Simple narration",
     "hdesc": "Write naturally and drop in inline tags for pauses, soft asides, and pacing. Unusual words get flagged so you can spell them out."},
    {"icon": "♦", "title": "Custom", "desc": "Phonemes & voice match",
     "head": "Custom pronunciation",
     "hdesc": "Spell tricky words phonetically with ARPABET, or drop a reference clip to match its pitch, speed, and depth."},
    {"icon": "☰", "title": "Reader", "desc": "Read documents aloud",
     "head": "Document reader",
     "hdesc": "Open a file and Cove reads it sentence by sentence, highlighting as it goes. Click any sentence to jump there."},
    {"icon": "🎤", "title": "Clone", "desc": "Clone any voice",
     "head": "Voice cloning",
     "hdesc": "Drop a voice clip to auto-match with Kokoro, or use neural cloning for closer results. Save matched voices as presets."},
]


class ModeButton(QFrame):
    clicked = Signal()

    def __init__(self, icon_char, title, desc, parent=None):
        super().__init__(parent)
        self.setObjectName("modeButton")
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(11, 10, 11, 10)
        lay.setSpacing(11)
        self._icon = QLabel(icon_char)
        self._icon.setObjectName("modeIcon")
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setFixedSize(30, 30)
        lay.addWidget(self._icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(QLabel(title, objectName="modeTitle"))
        col.addWidget(QLabel(desc, objectName="modeDesc"))
        lay.addLayout(col)
        lay.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def setChecked(self, on):
        self.setProperty("checked", "true" if on else "false")
        self._icon.setProperty("active", "true" if on else "false")
        for w in (self, self._icon):
            w.style().unpolish(w)
            w.style().polish(w)


class VoiceCard(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("voiceCard")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        self._avatar = QLabel("H")
        self._avatar.setObjectName("voiceAvatar")
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setFixedSize(38, 38)
        top.addWidget(self._avatar)
        nc = QVBoxLayout()
        nc.setSpacing(1)
        self._name = QLabel("Heart")
        self._name.setObjectName("voiceName")
        self._desc = QLabel("warm, friendly")
        self._desc.setObjectName("voiceDesc")
        nc.addWidget(self._name)
        nc.addWidget(self._desc)
        top.addLayout(nc)
        top.addStretch()
        lay.addLayout(top)

        bot = QHBoxLayout()
        bot.setSpacing(5)
        self._region = QLabel("US")
        self._region.setObjectName("chipRegion")
        self._gender = QLabel("Female")
        self._gender.setObjectName("chipGender")
        bot.addWidget(self._region)
        bot.addWidget(self._gender)
        bot.addStretch()
        bot.addWidget(QLabel("↕ Change", objectName="changeVoice"))
        lay.addLayout(bot)

    def set_voice(self, preset):
        name = preset.name.split(" — ")[0] if " — " in preset.name else preset.name
        desc = preset.name.split(" — ")[1] if " — " in preset.name else ""
        self._name.setText(name)
        self._desc.setText(desc)
        self._avatar.setText(name[0] if name else "?")
        vid = preset.voice_id
        self._region.setText("UK" if vid.startswith("b") else "US")
        self._gender.setText("Female" if len(vid) > 1 and vid[1] == "f" else "Male")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class VoiceGalleryDialog(QDialog):
    def __init__(self, presets, current_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a voice")
        self.setMinimumSize(660, 460)
        self._selected = current_id
        self._presets = [p for p in presets if p.is_builtin or p.blend_key]

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 16, 18, 14)

        hd = QHBoxLayout()
        hd.addWidget(QLabel(f"Choose a voice · {len(self._presets)} voices",
                            objectName="headerTitle",
                            styleSheet="font-size: 16px;"))
        hd.addStretch()
        self._search = QLineEdit(placeholderText="Search voices…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._rebuild)
        hd.addWidget(self._search)
        lay.addLayout(hd)

        fr = QHBoxLayout()
        fr.setSpacing(6)
        self._filters = []
        self._cur_filter = "All"
        for f in ("All", "US", "UK", "Female", "Male"):
            b = QPushButton(f, objectName="filterChip", checkable=True, checked=(f == "All"))
            b.clicked.connect(lambda _, n=f: self._set_filter(n))
            fr.addWidget(b)
            self._filters.append((f, b))
        fr.addStretch()
        lay.addLayout(fr)

        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._gw = QWidget()
        self._gl = QGridLayout(self._gw)
        self._gl.setSpacing(10)
        scroll.setWidget(self._gw)
        lay.addWidget(scroll, 1)

        ft = QHBoxLayout()
        self._count = QLabel(objectName="voiceDesc")
        ft.addWidget(self._count)
        ft.addStretch()
        ft.addWidget(QPushButton("Done", objectName="exportButton", clicked=self.accept))
        lay.addLayout(ft)
        self._rebuild()

    def _set_filter(self, name):
        self._cur_filter = name
        for f, b in self._filters:
            b.setChecked(f == name)
        self._rebuild()

    def _rebuild(self):
        while self._gl.count():
            w = self._gl.takeAt(0).widget()
            if w:
                w.deleteLater()
        q = self._search.text().lower()
        vis = []
        for p in self._presets:
            vid = p.voice_id
            if self._cur_filter == "US" and not vid.startswith("a"):
                continue
            if self._cur_filter == "UK" and not vid.startswith("b"):
                continue
            if self._cur_filter == "Female" and (len(vid) < 2 or vid[1] != "f"):
                continue
            if self._cur_filter == "Male" and (len(vid) < 2 or vid[1] != "m"):
                continue
            if q and q not in p.name.lower():
                continue
            vis.append(p)
        for i, p in enumerate(vis):
            self._gl.addWidget(self._tile(p), i // 3, i % 3)
        self._count.setText(f"Showing {len(vis)} of {len(self._presets)}")

    def _tile(self, preset):
        f = QFrame()
        f.setObjectName("voiceTile")
        f.setCursor(Qt.PointingHandCursor)
        key = preset.blend_key if preset.blend_key else preset.voice_id
        active = key == self._selected
        if active:
            f.setStyleSheet(
                "#voiceTile { background: rgba(80,230,207,15);"
                " border: 1px solid rgba(80,230,207,89); border-radius: 12px; }")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(13, 12, 13, 12)
        lay.setSpacing(6)
        name = preset.name.split(" — ")[0] if " — " in preset.name else preset.name
        desc = preset.name.split(" — ")[1] if " — " in preset.name else ""
        top = QHBoxLayout()
        top.setSpacing(8)
        av = QLabel(name[0], objectName="voiceAvatar", alignment=Qt.AlignCenter)
        av.setFixedSize(32, 32)
        top.addWidget(av)
        nc = QVBoxLayout()
        nc.setSpacing(1)
        nc.addWidget(QLabel(name, objectName="voiceName"))
        nc.addWidget(QLabel(desc, objectName="voiceDesc"))
        top.addLayout(nc)
        top.addStretch()
        lay.addLayout(top)
        vid = preset.voice_id
        pick_key = preset.blend_key if preset.blend_key else vid
        chips = QHBoxLayout()
        chips.setSpacing(5)
        if preset.blend_key:
            chips.addWidget(QLabel("Clone", objectName="chipRegion"))
        else:
            chips.addWidget(QLabel("UK" if vid.startswith("b") else "US", objectName="chipRegion"))
            chips.addWidget(QLabel("Female" if len(vid) > 1 and vid[1] == "f" else "Male",
                                   objectName="chipGender"))
        chips.addStretch()
        lay.addLayout(chips)
        f.mousePressEvent = lambda e, v=pick_key: self._pick(v)
        return f

    def _pick(self, vid):
        self._selected = vid
        self.accept()

    def selected_voice_id(self):
        return self._selected


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cove Narrator v2.2.0")
        self._icon_path = Path(__file__).resolve().parent.parent / "build" / "icon.png"
        if self._icon_path.exists():
            self.setWindowIcon(QIcon(str(self._icon_path)))
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(900, 600)
        self._engine = TTSEngine()
        self._player = AudioPlayer(self)
        self._presets = PresetManager()
        self._config = load_config()
        self._current_voice_preset = None
        self._custom_voice_tensor = None
        self._custom_voice_weights = None
        self._custom_voices = CustomVoiceManager()
        self._resizer = FramelessResizer(self)
        self.setMouseTracking(True)

        self.setStyleSheet(COVE_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        chrome = QVBoxLayout(central)
        chrome.setContentsMargins(0, 0, 0, 0)
        chrome.setSpacing(0)

        self._titlebar = CoveTitleBar(
            self,
            icon_path=str(self._icon_path) if self._icon_path.exists() else None,
            title="Cove Narrator",
            version="v2.2.0",
        )
        chrome.addWidget(self._titlebar)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        chrome.addWidget(body, 1)

        root.addWidget(self._build_sidebar())

        main = QWidget(objectName="mainArea")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        header = QFrame()
        hl = QVBoxLayout(header)
        hl.setContentsMargins(26, 22, 26, 16)
        hl.setSpacing(5)
        self._header_title = QLabel(objectName="headerTitle")
        self._header_desc = QLabel(objectName="headerDesc", wordWrap=True)
        hl.addWidget(self._header_title)
        hl.addWidget(self._header_desc)
        ml.addWidget(header)

        self._stack = QStackedWidget()
        self._simple_tab = SimpleTab(self._engine, self._player, self)
        self._custom_tab = CustomTab(self._engine, self._player, self)
        self._reader_tab = ReaderTab(self._engine, self._player, self)
        self._clone_tab = CloneTab(self._engine, self._player, self)
        self._clone_tab.preset_saved.connect(self._populate_presets)
        self._stack.addWidget(self._simple_tab)
        self._stack.addWidget(self._custom_tab)
        self._stack.addWidget(self._reader_tab)
        self._stack.addWidget(self._clone_tab)
        ml.addWidget(self._stack, 1)
        root.addWidget(main, 1)

        from PySide6.QtGui import QGuiApplication
        default_w, default_h = 1050, 680
        w = self._config.get("window_width", default_w)
        h = self._config.get("window_height", default_h)
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            # A previously maximized session can save full-screen dimensions;
            # fall back to a normal default so the app never starts filling
            # the screen, then clamp to fit and center.
            if w >= avail.width() * 0.95 or h >= avail.height() * 0.95:
                w, h = default_w, default_h
            w = min(w, avail.width() - 80)
            h = min(h, avail.height() - 80)
            self.resize(w, h)
            self.move(avail.x() + (avail.width() - w) // 2,
                      avail.y() + (avail.height() - h) // 2)
        else:
            self.resize(w, h)
        self._apply_config()
        self._setup_shortcuts()
        self._set_mode(0)
        self._select_initial_voice()

    # ---- sidebar -----------------------------------------------------------
    def _build_sidebar(self):
        sb = QFrame(objectName="sidebar")
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(14, 18, 14, 14)
        lay.setSpacing(18)

        ms = QVBoxLayout()
        ms.setSpacing(4)
        ms.addWidget(QLabel("MODE", objectName="sectionLabel"))
        self._mode_btns = []
        for i, m in enumerate(_MODES):
            b = ModeButton(m["icon"], m["title"], m["desc"])
            b.clicked.connect(lambda idx=i: self._set_mode(idx))
            self._mode_btns.append(b)
            ms.addWidget(b)
        lay.addLayout(ms)

        vs = QVBoxLayout()
        vs.setSpacing(7)
        vs.addWidget(QLabel("VOICE", objectName="sectionLabel"))
        self._voice_card = VoiceCard()
        self._voice_card.clicked.connect(self._open_voice_gallery)
        vs.addWidget(self._voice_card)
        lay.addLayout(vs)

        ps = QVBoxLayout()
        ps.setSpacing(4)
        ps.addWidget(QLabel("PRESETS", objectName="sectionLabel"))
        self._preset_container = QVBoxLayout()
        self._preset_container.setSpacing(4)
        self._populate_presets()
        ps.addLayout(self._preset_container)
        ps.addWidget(QPushButton("+ Save current", objectName="addPreset",
                                 clicked=self._save_preset))
        lay.addLayout(ps)

        lay.addStretch()

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,15);")
        lay.addWidget(sep)
        lay.addWidget(QPushButton("⚙  Settings", objectName="settingsButton",
                                  clicked=self._open_settings))
        return sb

    # ---- mode switching ----------------------------------------------------
    def _set_mode(self, idx):
        for i, b in enumerate(self._mode_btns):
            b.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)
        m = _MODES[idx]
        self._header_title.setText(m["head"])
        self._header_desc.setText(m["hdesc"])

    # ---- voice management --------------------------------------------------
    def _select_initial_voice(self):
        all_p = self._presets.get_all_presets()
        last_blend = self._config.get("last_blend_key", "")
        if last_blend:
            for p in all_p:
                if p.blend_key == last_blend:
                    self._apply_full_preset(p)
                    return
        last = self._config.get("last_voice", "af_heart")
        for p in all_p:
            if p.voice_id == last:
                self._apply_voice(p)
                return
        if all_p:
            self._apply_voice(all_p[0])

    def _apply_voice(self, preset):
        self._current_voice_preset = preset
        self._custom_voice_tensor = None
        self._custom_voice_weights = None
        self._voice_card.set_voice(preset)

    def _open_voice_gallery(self):
        all_p = self._presets.get_all_presets()
        cur = self._current_voice_preset.voice_id if self._current_voice_preset else "af_heart"
        dlg = VoiceGalleryDialog(all_p, cur, self)
        if dlg.exec():
            selected = dlg.selected_voice_id()
            for p in all_p:
                key = p.blend_key if p.blend_key else p.voice_id
                if key == selected:
                    if p.blend_key:
                        self._apply_full_preset(p)
                    else:
                        self._apply_voice(p)
                    break

    def get_current_voice_id(self):
        if self._custom_voice_tensor is not None:
            return self._custom_voice_tensor
        if self._current_voice_preset:
            return self._current_voice_preset.voice_id
        return "af_heart"

    def _set_custom_voice(self, tensor, weights):
        import numpy as np
        self._custom_voice_tensor = tensor
        self._custom_voice_weights = weights
        desc = " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                          for v, w in weights.items())
        self._voice_card._name.setText("Custom blend")
        self._voice_card._desc.setText(desc)
        self._voice_card._avatar.setText("✦")
        first_vid = next(iter(weights))
        self._voice_card._region.setText("UK" if first_vid.startswith("b") else "US")
        self._voice_card._gender.setText("Female" if len(first_vid) > 1 and first_vid[1] == "f" else "Male")

    def _save_custom_voice(self):
        if self._custom_voice_tensor is None:
            return
        name, ok = QInputDialog.getText(self, "Save Custom Voice", "Voice name:")
        if not ok or not name.strip():
            return
        self._custom_voices.save(name.strip(), self._custom_voice_tensor,
                                  self._custom_voice_weights)
        self._populate_presets()

    def _pick_closest_voice(self, target_f0: float) -> tuple[str, float]:
        """Pick the kokoro voice whose natural F0 is closest to target_f0.
        Returns (voice_display_name, voice_f0_hz).
        Caches F0 measurements so subsequent calls are instant."""
        if not hasattr(self, '_voice_f0_cache'):
            self._voice_f0_cache = self._measure_voice_f0s()
        best_id, best_f0, best_gap = "am_michael", 117.0, 9999.0
        for vid, f0 in self._voice_f0_cache.items():
            gap = abs(f0 - target_f0)
            if gap < best_gap:
                best_id, best_f0, best_gap = vid, f0, gap
        for p in self._presets.get_all_presets():
            if p.voice_id == best_id:
                self._apply_voice(p)
                name = p.name.split(" — ")[0] if " — " in p.name else p.name
                return name, best_f0
        return "Michael", 117.0

    def _measure_voice_f0s(self) -> dict[str, float]:
        """Synthesize a short phrase with each voice and measure median F0."""
        from src.engine import audio_features as af
        phrase = "Hello, this is a test."
        cache = {}
        for p in self._presets.get_builtin_presets():
            try:
                samples, sr = self._engine.synthesize_raw(phrase, voice=p.voice_id, speed=1.0)
                med = af.median_f0(samples, sr, fmin=50, fmax=600)
                if med is not None:
                    cache[p.voice_id] = med
            except Exception:
                continue
        return cache

    # ---- presets -----------------------------------------------------------
    def _populate_presets(self):
        while self._preset_container.count():
            w = self._preset_container.takeAt(0).widget()
            if w:
                w.deleteLater()
        for p in self._presets.get_custom_presets():
            btn = QPushButton(f"  ⭐  {p.name}", objectName="presetButton")
            btn.clicked.connect(lambda _, pr=p: self._apply_full_preset(pr))
            self._preset_container.addWidget(btn)
        for cv in self._custom_voices.list_voices():
            name = cv.get("name", "Custom")
            key = cv.get("key", name)
            btn = QPushButton(f"  ✦  {name}", objectName="presetButton")
            btn.clicked.connect(lambda _, k=key: self._load_custom_voice(k))
            self._preset_container.addWidget(btn)

    def _load_custom_voice(self, key: str):
        tensor, meta = self._custom_voices.load(key)
        self._custom_voice_tensor = tensor
        self._custom_voice_weights = meta.get("weights", {})
        display_name = meta.get("name", key)
        desc = " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                          for v, w in self._custom_voice_weights.items())
        self._voice_card._name.setText(display_name)
        self._voice_card._desc.setText(desc)
        self._voice_card._avatar.setText("✦")

    def _apply_full_preset(self, preset):
        if preset.blend_key:
            try:
                tensor, meta = self._custom_voices.load(preset.blend_key)
                self._set_custom_voice(tensor, meta.get("weights", {}))
                self._current_voice_preset = preset
                self._voice_card.set_voice(preset)
            except Exception:
                self._apply_voice(preset)
        else:
            self._apply_voice(preset)
        self._simple_tab.apply_preset(preset)
        self._custom_tab.apply_preset(preset)
        self._reader_tab.apply_preset(preset)
        self._clone_tab.apply_preset(preset)

    def _save_preset(self):
        if self._custom_voice_tensor is not None:
            self._save_custom_voice()
            return
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        tab = self._stack.currentWidget()
        sliders = tab.get_slider_values()
        preset = Preset(
            name=name.strip(),
            voice_id=self.get_current_voice_id(),
            pitch=sliders["pitch"],
            speed=sliders["speed"],
            depth=sliders["depth"],
        )
        self._presets.save_preset(preset)
        self._populate_presets()

    # ---- config / settings -------------------------------------------------
    def _apply_config(self):
        save_dir = Path(self._config.get("save_dir",
                                         str(Path.home() / "Music" / "Cove Narrator")))
        self._simple_tab.set_save_dir(save_dir)
        self._custom_tab.set_save_dir(save_dir)
        self._reader_tab.set_save_dir(save_dir)
        self._clone_tab.set_save_dir(save_dir)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._config = dlg.get_config()
            self._apply_config()
            self._play_shortcut.setKey(
                QKeySequence(self._config.get("hotkey_play_pause", "Space")))
            self._stop_shortcut.setKey(
                QKeySequence(self._config.get("hotkey_stop", "Escape")))
            self._export_shortcut.setKey(
                QKeySequence(self._config.get("hotkey_export", "Ctrl+E")))

    # ---- shortcuts ---------------------------------------------------------
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
        self._stack.currentWidget().toggle_play_pause()

    def _stop_all(self):
        self._player.stop()
        self._simple_tab._play_btn.setEnabled(True)
        self._custom_tab._play_btn.setEnabled(True)
        self._clone_tab._play_btn.setEnabled(True)
        self._reader_tab._on_stop()

    def _export_current(self):
        self._stack.currentWidget()._on_export()

    def mousePressEvent(self, event: QMouseEvent):
        if self._resizer.try_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._resizer.try_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._resizer.try_release(event):
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._resizer.clear_hover()
        super().leaveEvent(event)

    def closeEvent(self, event):
        # Save the restored (non-maximized) size so the next launch doesn't
        # start full-screen.
        if self.isMaximized() or self.isFullScreen():
            geo = self.normalGeometry()
            self._config["window_width"] = geo.width()
            self._config["window_height"] = geo.height()
        else:
            self._config["window_width"] = self.width()
            self._config["window_height"] = self.height()
        if self._current_voice_preset:
            self._config["last_voice"] = self._current_voice_preset.voice_id
            if self._current_voice_preset.blend_key:
                self._config["last_blend_key"] = self._current_voice_preset.blend_key
            elif "last_blend_key" in self._config:
                del self._config["last_blend_key"]
        save_config(self._config)
        self._player.stop()
        self._clone_tab._cleanup_temp_rec()
        for attr in ("_hd_download_worker", "_hd_synth_worker", "_worker", "_analyze_worker"):
            w = getattr(self._clone_tab, attr, None)
            if w and w.isRunning():
                w.wait(1000)
        event.accept()
