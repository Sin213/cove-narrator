from pathlib import Path
from datetime import datetime
import numpy as np
import soundfile as sf


def export_wav(audio: np.ndarray, sr: int, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"cove-narrator-{timestamp}.wav"
    counter = 2
    while path.exists():
        path = directory / f"cove-narrator-{timestamp}-{counter}.wav"
        counter += 1
    sf.write(str(path), audio, sr, subtype="PCM_16")
    return path
