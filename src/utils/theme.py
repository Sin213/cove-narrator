COVE_STYLESHEET = """
/* ================================================================
   Cove Narrator — Dark Theme (Cove Design Language)
   Accent: teal #50e6cf · Canvas: #0b0b10
   ================================================================ */

QMainWindow { background: #0b0b10; }
QWidget { color: #ececf1; outline: none; }
QLabel { background: transparent; }
QFrame { background: transparent; }
QToolTip {
    background: #09090e; color: #ececf1;
    border: 1px solid rgba(255,255,255,25); border-radius: 8px;
    padding: 6px 9px; font-size: 11px;
}

/* ---- Sidebar ---- */
#sidebar {
    background: #0b0b10;
    border-right: 1px solid rgba(255,255,255,15);
    min-width: 252px; max-width: 252px;
}
#sectionLabel {
    font-size: 10px; font-weight: 700; letter-spacing: 2px;
    color: #6b6b80; padding: 0 8px;
}

/* Mode buttons */
#modeButton {
    background: transparent; border: 1px solid transparent; border-radius: 10px;
}
#modeButton:hover { background: #13131b; }
#modeButton[checked="true"] {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(80,230,207,23), stop:1 rgba(80,230,207,5));
    border: 1px solid rgba(80,230,207,89);
}
#modeIcon {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1f1f2b, stop:1 #181822);
    border: 1px solid rgba(255,255,255,25); border-radius: 8px;
    color: #9a9aae; font-size: 14px;
}
#modeIcon[active="true"] {
    color: #50e6cf; background: rgba(80,230,207,36);
    border-color: rgba(80,230,207,89);
}
#modeTitle { font-size: 13px; font-weight: 600; color: #ececf1; }
#modeDesc { font-size: 11px; color: #6b6b80; }

/* Voice card */
#voiceCard {
    background: #13131b; border: 1px solid rgba(255,255,255,15); border-radius: 12px;
}
#voiceCard:hover { background: #181822; border-color: rgba(255,255,255,25); }
#voiceAvatar {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #50e6cf, stop:1 #3ddc97);
    border-radius: 10px; color: #07120f; font-size: 13px; font-weight: 700;
}
#voiceName { font-size: 13px; font-weight: 600; color: #ececf1; }
#voiceDesc { font-size: 11px; color: #6b6b80; }
#chipRegion {
    font-size: 10px; color: #50e6cf; padding: 2px 7px; border-radius: 999px;
    background: rgba(80,230,207,36); border: 1px solid rgba(80,230,207,89);
}
#chipGender {
    font-size: 10px; color: #9a9aae; padding: 2px 7px; border-radius: 999px;
    background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,15);
}
#changeVoice { font-size: 10px; color: #50e6cf; background: transparent; border: none; }

/* Presets */
#presetButton {
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 7px 9px; color: #9a9aae; font-size: 12px; text-align: left;
}
#presetButton:hover { background: #13131b; color: #ececf1; }
#presetButton[active="true"] {
    background: #181822; color: #ececf1; border-color: rgba(255,255,255,15);
}
#addPreset {
    background: transparent; border: 1px dashed rgba(255,255,255,41);
    border-radius: 8px; padding: 8px; color: #9a9aae; font-size: 12px;
}
#addPreset:hover {
    color: #50e6cf; border-color: rgba(80,230,207,89); background: rgba(80,230,207,36);
}
#settingsButton {
    background: transparent; border: none; color: #9a9aae;
    font-size: 12px; text-align: left; padding: 4px 0;
}
#settingsButton:hover { color: #ececf1; }

/* ---- Header ---- */
#headerTitle { font-size: 22px; font-weight: 600; letter-spacing: -0.3px; color: #ececf1; }
#headerDesc { font-size: 12px; color: #9a9aae; line-height: 18px; }
#statusPill {
    font-size: 11px; color: #9a9aae; background: #13131b;
    border: 1px solid rgba(255,255,255,15); border-radius: 999px; padding: 4px 11px;
}

/* ---- Editor surfaces ---- */
QTextEdit {
    background: #13131b; color: #ececf1;
    border: 1px solid rgba(255,255,255,15); border-radius: 12px;
    padding: 14px 16px; font-size: 15px;
    selection-background-color: rgba(80,230,207,50); selection-color: #ececf1;
}
QTextEdit:focus { border-color: rgba(80,230,207,89); }
QTextEdit[readOnly="true"] { color: #9a9aae; font-size: 16px; }

/* Tag buttons */
#tagButton {
    font-size: 11px; color: #9a9aae; background: #181822;
    border: 1px solid rgba(255,255,255,15); border-radius: 6px; padding: 4px 9px;
}
#tagButton:hover {
    color: #50e6cf; border-color: rgba(80,230,207,89); background: rgba(80,230,207,36);
}
#toolbarLabel {
    font-size: 10px; font-weight: 600; letter-spacing: 1px; color: #6b6b80;
}

/* Phoneme buttons */
QPushButton[phoneme="vowel"] {
    font-size: 11px; font-weight: 600; color: #9bd8ff;
    background: rgba(90,183,255,25); border: 1px solid rgba(90,183,255,40);
    border-radius: 7px; min-width: 36px; min-height: 28px; padding: 0 8px;
}
QPushButton[phoneme="vowel"]:hover {
    background: rgba(90,183,255,50); border-color: rgba(90,183,255,100);
}
QPushButton[phoneme="vowel"]:pressed { background: rgba(90,183,255,70); }
QPushButton[phoneme="consonant"] {
    font-size: 11px; font-weight: 600; color: #cda9ff;
    background: rgba(168,120,255,25); border: 1px solid rgba(168,120,255,40);
    border-radius: 7px; min-width: 36px; min-height: 28px; padding: 0 8px;
}
QPushButton[phoneme="consonant"]:hover {
    background: rgba(168,120,255,50); border-color: rgba(168,120,255,100);
}
QPushButton[phoneme="consonant"]:pressed { background: rgba(168,120,255,70); }

/* Phoneme panel */
#phonemePanel {
    background: #13131b; border: 1px solid rgba(255,255,255,15); border-radius: 12px;
}
#phonemeHeader { border-bottom: 1px solid rgba(255,255,255,15); }
#vowelLabel { font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #7fd0ff; }
#consonantLabel { font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #c89bff; }

/* Drop zone */
#dropZone {
    background: #181822; border: 1.5px dashed rgba(255,255,255,41); border-radius: 11px;
}
#dropZone[state="drag"] {
    border-color: rgba(80,230,207,255); background: rgba(80,230,207,36);
}
#dropZone[state="hasfile"] {
    border-style: solid; border-color: rgba(80,230,207,89);
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(80,230,207,15), stop:1 transparent);
}

/* ---- Sliders ---- */
QSlider::groove:horizontal {
    height: 4px; background: #262635; border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 15px; height: 15px; margin: -6px 0; border-radius: 7px;
    background: #50e6cf; border: 2px solid #0b0b10;
}
QSlider::handle:horizontal:pressed { width: 17px; height: 17px; margin: -7px 0; }
#sliderName { font-size: 10px; font-weight: 600; letter-spacing: 1px; color: #9a9aae; }

QSpinBox {
    background: #13131b; color: #ececf1;
    border: 1px solid rgba(255,255,255,15); border-radius: 6px;
    padding: 2px 6px; font-size: 12px;
}
QSpinBox:focus { border-color: rgba(80,230,207,89); }
QSpinBox::up-button, QSpinBox::down-button { width: 0; height: 0; border: none; }

/* ---- Buttons ---- */
#playButton {
    background: #50e6cf; color: #07120f;
    border: 1px solid rgba(255,255,255,25); border-radius: 10px;
    padding: 8px 17px; font-size: 13px; font-weight: 600; min-height: 36px;
}
#playButton:hover { background: #5eecd6; }
#playButton:pressed { background: #45d4be; }
#playButton:disabled { background: rgba(80,230,207,100); color: rgba(7,18,15,100); }

#stopButton {
    background: #2b2b38; color: #ececf1;
    border: 1px solid rgba(255,255,255,41); border-radius: 10px;
    padding: 8px 17px; font-size: 13px; font-weight: 600; min-height: 36px;
}
#stopButton:hover { background: #34343f; }

#exportButton {
    background: #181822; color: #9a9aae;
    border: 1px solid rgba(255,255,255,15); border-radius: 10px;
    padding: 8px 17px; font-size: 13px; font-weight: 500; min-height: 36px;
}
#exportButton:hover { color: #ececf1; background: #1f1f2b; border-color: rgba(255,255,255,25); }

#openFileButton {
    background: #181822; color: #9a9aae;
    border: 1px solid rgba(255,255,255,15); border-radius: 8px;
    padding: 5px 12px; font-size: 12px; font-weight: 500;
}
#openFileButton:hover { color: #ececf1; background: #1f1f2b; border-color: rgba(255,255,255,25); }

/* ---- Progress ---- */
QProgressBar {
    background: #1f1f2b; border: none; border-radius: 3px;
    max-height: 6px; min-height: 6px; text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,x2:1, stop:0 #3ddc97, stop:1 #50e6cf);
    border-radius: 3px;
}

/* ---- Status ---- */
#statusLabel { font-size: 11px; color: #6b6b80; }

/* ---- Scrollbars ---- */
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,15); border-radius: 5px; min-height: 20px; margin: 2px;
}
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,30); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: transparent; height: 10px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,15); border-radius: 5px; min-width: 20px; margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: rgba(255,255,255,30); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---- Dialogs ---- */
QDialog { background: #0e0e16; color: #ececf1; }
QGroupBox {
    background: #13131b; border: 1px solid rgba(255,255,255,15); border-radius: 10px;
    margin-top: 14px; padding-top: 20px; font-weight: 600; color: #9a9aae;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 14px; padding: 0 6px;
    color: #6b6b80; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QLineEdit {
    background: #13131b; color: #ececf1;
    border: 1px solid rgba(255,255,255,15); border-radius: 9px;
    padding: 6px 11px; font-size: 13px;
    selection-background-color: rgba(80,230,207,50);
}
QLineEdit:focus { border-color: rgba(80,230,207,89); }
QComboBox {
    background: #13131b; color: #ececf1;
    border: 1px solid rgba(255,255,255,15); border-radius: 8px;
    padding: 6px 12px; min-height: 28px;
}
QComboBox:hover { border-color: rgba(255,255,255,25); }
QComboBox:focus { border-color: rgba(80,230,207,89); }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView {
    background: #0e0e16; color: #ececf1;
    border: 1px solid rgba(255,255,255,25); border-radius: 8px;
    selection-background-color: rgba(80,230,207,36); selection-color: #ececf1;
    padding: 4px;
}
QKeySequenceEdit {
    background: #13131b; color: #ececf1;
    border: 1px solid rgba(255,255,255,15); border-radius: 8px; padding: 4px 8px;
}
QKeySequenceEdit:focus { border-color: rgba(80,230,207,89); }

/* Dialog buttons */
QDialog QPushButton {
    background: #181822; color: #9a9aae;
    border: 1px solid rgba(255,255,255,15); border-radius: 8px;
    padding: 6px 16px; font-size: 13px; font-weight: 500; min-height: 32px;
}
QDialog QPushButton:hover { color: #ececf1; background: #1f1f2b; }
QDialog QPushButton:default {
    background: #50e6cf; color: #07120f;
    border: 1px solid rgba(255,255,255,25); font-weight: 600;
}
QDialog QPushButton:default:hover { background: #5eecd6; }
QInputDialog { background: #0e0e16; }

/* Gallery filter chips */
#filterChip {
    background: #181822; color: #9a9aae;
    border: 1px solid rgba(255,255,255,15); border-radius: 999px;
    padding: 5px 11px; font-size: 12px;
}
#filterChip:hover { color: #ececf1; }
#filterChip:checked {
    background: #50e6cf; color: #07120f;
    border-color: #50e6cf; font-weight: 600;
}

/* Gallery tiles */
#voiceTile {
    background: #13131b; border: 1px solid rgba(255,255,255,15); border-radius: 12px;
}
"""
