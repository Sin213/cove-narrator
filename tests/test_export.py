import numpy as np
import soundfile as sf
from pathlib import Path
from src.utils.export import export_wav


def test_export_wav_creates_file(tmp_path):
    audio = np.random.randn(24000).astype(np.float32)
    path = export_wav(audio, 24000, tmp_path)
    assert path.exists()
    assert path.suffix == ".wav"
    data, sr = sf.read(str(path))
    assert sr == 24000
    assert len(data) == 24000


def test_export_wav_no_overwrite(tmp_path):
    audio = np.random.randn(24000).astype(np.float32)
    path1 = export_wav(audio, 24000, tmp_path)
    path2 = export_wav(audio, 24000, tmp_path)
    assert path1 != path2
    assert path1.exists()
    assert path2.exists()
