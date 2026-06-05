# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

block_cipher = None
project_root = Path(os.path.abspath(SPECPATH)).parent.parent

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=collect_dynamic_libs('espeakng_loader'),
    datas=[
        (str(project_root / 'data' / 'models' / 'kokoro-v1.0.onnx'), 'data/models'),
        (str(project_root / 'data' / 'models' / 'voices-v1.0.bin'), 'data/models'),
        (str(project_root / 'data' / 'cmudict.txt'), 'data'),
    ]
    + collect_data_files('kokoro_onnx')
    + collect_data_files('phonemizer')
    + collect_data_files('language_tags')
    + collect_data_files('espeakng_loader'),
    hiddenimports=[
        'kokoro_onnx',
        'espeakng_loader',
        'onnxruntime',
        'sounddevice',
        'soundfile',
        'librosa',
        'numpy',
        'PySide6',
        'pymupdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='cove-narrator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='cove-narrator',
)
