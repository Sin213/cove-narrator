from pathlib import Path
from src.models.loader import find_model_files

def test_find_model_files_returns_paths():
    model_path, voices_path = find_model_files()
    assert model_path.exists()
    assert voices_path.exists()
    assert model_path.name == "kokoro-v1.0.onnx"
    assert voices_path.name == "voices-v1.0.bin"

def test_find_model_files_raises_on_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.models.loader._data_dir", lambda: tmp_path / "nonexistent")
    try:
        find_model_files()
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
