from pathlib import Path

MODEL_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"

def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "models"

def find_model_files() -> tuple[Path, Path]:
    base = _data_dir()
    model_path = base / MODEL_FILENAME
    voices_path = base / VOICES_FILENAME
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not voices_path.exists():
        raise FileNotFoundError(f"Voices not found: {voices_path}")
    return model_path, voices_path
