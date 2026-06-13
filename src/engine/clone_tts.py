import os
from pathlib import Path

import numpy as np

from portable import is_portable, portable_data_dir
from src.engine.analyzer import analyze_reference
from src.engine.voice_blend import find_best_blend
from src.engine.tts import TTSEngine
from src.engine.audio_dsp import apply_all


def find_matching_python(timeout: int = 10):
    """Return an argv prefix for a Python interpreter whose version matches the
    frozen app's (e.g. ['C:/Windows/py.exe', '-3.12'] or ['python']), or None.

    Used both to pip-install the HD deps and to run the model-download
    subprocess, so they share one reliable interpreter instead of a hardcoded
    embeddable that the installer no longer bootstraps. Falls back to that
    embeddable if it happens to exist."""
    import os
    import sys
    import shutil
    import subprocess
    import platform

    if not getattr(sys, "frozen", False):
        return [sys.executable]

    app_ver = str(sys.version_info[:2])
    ver_str = f"{sys.version_info.major}.{sys.version_info.minor}"
    kw = {}
    if platform.system() == "Windows":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    candidates = []
    if platform.system() == "Windows":
        candidates.append(["py", f"-{ver_str}"])
    candidates += [[f"python{ver_str}"], ["python"], ["python3"]]

    for cmd in candidates:
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        args = [exe, *cmd[1:]]
        try:
            r = subprocess.run(
                [*args, "-c", "import sys; print(sys.version_info[:2])"],
                capture_output=True, text=True, timeout=timeout, **kw,
            )
            if r.stdout.strip() == app_ver:
                return args
        except Exception:
            pass

    if platform.system() == "Linux":
        env = {**os.environ}
        orig_ldpath = os.environ.get("APPIMAGE_ORIG_LD_LIBRARY_PATH")
        if orig_ldpath is not None:
            env["LD_LIBRARY_PATH"] = orig_ldpath
        linux_candidates = []
        for name in ("python3", "python"):
            path = shutil.which(name)
            if path:
                linux_candidates.append(path)
        pyenv_root = Path.home() / ".pyenv" / "versions"
        if pyenv_root.is_dir():
            for ver_dir in sorted(pyenv_root.iterdir(), reverse=True):
                py = ver_dir / "bin" / "python3"
                if py.exists():
                    linux_candidates.append(str(py))
        for path in linux_candidates:
            try:
                r = subprocess.run(
                    [path, "-m", "pip", "--version"],
                    capture_output=True, text=True, timeout=timeout,
                    env=env,
                )
                if r.returncode == 0:
                    return [path]
            except Exception:
                pass

    emb = Path(sys.executable).parent / "dependencies" / "_python" / "python.exe"
    if emb.exists():
        return [str(emb)]
    return None


class VoiceMatchResult:
    def __init__(self, weights: dict, tensor: np.ndarray,
                 pitch: int, speed: int, depth: int, gender: str, median_f0: float):
        self.weights = weights
        self.tensor = tensor
        self.pitch = pitch
        self.speed = speed
        self.depth = depth
        self.gender = gender
        self.median_f0 = median_f0

    @property
    def description(self) -> str:
        return " + ".join(f"{w:.0%} {v.split('_')[1].title()}"
                          for v, w in self.weights.items())


class VoiceMatchEngine:
    def __init__(self, tts_engine: TTSEngine):
        self._engine = tts_engine

    def analyze(self, ref_audio_path: str, progress_cb=None) -> VoiceMatchResult:
        pitch, speed, depth, gender, median_f0 = analyze_reference(ref_audio_path)
        blend_cb = (lambda stage, detail: progress_cb(detail)) if progress_cb else None
        weights, tensor = find_best_blend(
            self._engine._kokoro, ref_audio_path,
            progress_cb=blend_cb,
        )
        return VoiceMatchResult(
            weights=weights, tensor=tensor,
            pitch=pitch, speed=speed, depth=depth,
            gender=gender, median_f0=median_f0,
        )

    def synthesize(self, text: str, tensor: np.ndarray,
                   speed: float = 1.0, pitch: int = 0,
                   depth: int = 0) -> tuple[np.ndarray, int]:
        audio, sr = self._engine.synthesize_text(text, voice=tensor, speed=speed)
        audio = apply_all(audio, sr, pitch=pitch, depth=depth)
        return audio, sr


class QwenCloneEngine:
    _MODEL_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

    def __init__(self):
        self._model = None

    @staticmethod
    def model_dir() -> Path:
        import sys
        import platform as _plat
        if is_portable():
            d = Path(os.path.join(portable_data_dir("cove-narrator"), "models", "qwen3-tts-1.7b"))
        elif getattr(sys, 'frozen', False) and _plat.system() != "Linux":
            d = Path(sys.executable).parent / "dependencies" / "models" / "qwen3-tts-1.7b"
        else:
            d = Path.home() / ".config" / "cove-narrator" / "models" / "qwen3-tts-1.7b"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def is_downloaded(self) -> bool:
        return (self.model_dir() / "model.safetensors").exists()

    def is_loaded(self) -> bool:
        return self._model is not None

    def download(self, progress_cb=None):
        import sys
        import platform as _plat
        if progress_cb:
            progress_cb("Starting Qwen3-TTS download…")
        if getattr(sys, 'frozen', False) and _plat.system() != "Linux":
            self._download_subprocess(progress_cb)
        else:
            self._download_direct(progress_cb)
        if progress_cb:
            progress_cb("Download complete.")

    def _download_direct(self, progress_cb=None):
        import os
        import threading
        import time as _time

        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from huggingface_hub import snapshot_download

        model_dir = self.model_dir()
        error_holder = [None]

        def _do_download():
            try:
                snapshot_download(
                    self._MODEL_REPO, local_dir=str(model_dir),
                    local_dir_use_symlinks=False,
                )
            except Exception as e:
                error_holder[0] = e

        dl_thread = threading.Thread(target=_do_download, daemon=True)
        dl_thread.start()

        ESTIMATED_BYTES = 4_300_000_000
        start = _time.monotonic()
        while dl_thread.is_alive():
            dl_thread.join(timeout=2.0)
            if not progress_cb or not model_dir.is_dir():
                continue
            try:
                total = sum(
                    f.stat().st_size
                    for f in model_dir.rglob("*") if f.is_file()
                )
            except OSError:
                continue
            mb = total / 1_000_000
            pct = min(99, int(total / ESTIMATED_BYTES * 100))
            elapsed = _time.monotonic() - start
            if pct > 1 and elapsed > 5:
                eta_sec = elapsed / pct * (100 - pct)
                eta_min = max(1, int(eta_sec / 60))
                progress_cb(
                    f"Downloading… {pct}%  —  "
                    f"ETA ~{eta_min} min  "
                    f"({mb:.0f} / ~4300 MB)"
                )
            else:
                progress_cb(f"Downloading… ({mb:.0f} MB)")

        if error_holder[0] is not None:
            raise error_holder[0]

    def _download_subprocess(self, progress_cb=None):
        import subprocess
        import sys
        import platform
        import time as _time

        py_args = find_matching_python()
        if not py_args:
            ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            raise RuntimeError(
                f"No compatible Python {ver} found to download the model. "
                f"Install Python {ver} from python.org and restart the app."
            )

        model_dir = self.model_dir()
        if is_portable():
            deps_dir = Path(os.path.join(portable_data_dir("cove-narrator"), "deps"))
        else:
            deps_dir = Path(sys.executable).parent / "dependencies" / "cove-narrator"
        script = (
            "import sys, os;"
            f"sys.path.insert(0, {str(deps_dir)!r});"
            "os.environ['HF_HUB_ENABLE_HF_TRANSFER']='0';"
            "os.environ['HF_HUB_DISABLE_XET']='1';"
            "from huggingface_hub import snapshot_download;"
            f"snapshot_download({self._MODEL_REPO!r}, local_dir={str(model_dir)!r})"
        )

        kw = {}
        if platform.system() == "Windows":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW

        # Drain output to a log file rather than PIPE — the progress loop below
        # never reads the pipes, so a chatty download could fill the OS buffer
        # and deadlock the subprocess.
        log_path = model_dir.parent / "model_download.log"
        log_f = open(log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [*py_args, "-c", script],
            stdout=log_f, stderr=subprocess.STDOUT, **kw,
        )

        ESTIMATED_BYTES = 4_300_000_000
        start = _time.monotonic()
        while proc.poll() is None:
            _time.sleep(3)
            if not progress_cb:
                continue
            try:
                total = sum(
                    f.stat().st_size
                    for f in model_dir.rglob("*") if f.is_file()
                )
            except OSError:
                continue
            mb = total / 1_000_000
            pct = min(99, int(total / ESTIMATED_BYTES * 100))
            elapsed = _time.monotonic() - start
            if pct > 1 and elapsed > 5:
                eta_sec = elapsed / pct * (100 - pct)
                eta_min = max(1, int(eta_sec / 60))
                progress_cb(
                    f"Downloading… {pct}%  —  "
                    f"ETA ~{eta_min} min  "
                    f"({mb:.0f} / ~4300 MB)"
                )
            else:
                progress_cb(f"Downloading… ({mb:.0f} MB)")

        log_f.close()
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
        except OSError:
            tail = ""

        if proc.returncode != 0:
            raise RuntimeError(
                f"Model download failed (exit {proc.returncode}):\n{tail}"
            )

        # Verify the model actually landed — otherwise the UI would report
        # "Download complete" while is_downloaded() stays False, re-looping the
        # user back to the download prompt.
        if not self.is_downloaded():
            raise RuntimeError(
                "Download finished but model.safetensors is missing from\n"
                f"{model_dir}\n\n{tail}"
            )

    def load(self, progress_cb=None):
        if self._model is not None:
            return
        import torch
        from src.vendor.qwen_tts import Qwen3TTSModel
        if progress_cb:
            progress_cb("Loading Qwen3-TTS 1.7B…")
        kwargs = {}
        if torch.cuda.is_available():
            kwargs["device_map"] = "auto"
            kwargs["dtype"] = torch.bfloat16
        else:
            kwargs["device_map"] = "cpu"
            kwargs["dtype"] = torch.float32
        self._model = Qwen3TTSModel.from_pretrained(str(self.model_dir()), **kwargs)
        if progress_cb:
            progress_cb("Qwen3-TTS ready.")

    def synthesize(self, text: str, ref_audio_path: str) -> tuple[np.ndarray, int]:
        if self._model is None:
            raise RuntimeError("Qwen3-TTS not loaded")
        wavs, sr = self._model.generate_voice_clone(
            text=text, language="English",
            ref_audio=ref_audio_path, ref_text="unused",
            x_vector_only_mode=True,
            non_streaming_mode=True,
            do_sample=False,
        )
        audio = wavs[0]
        if not isinstance(audio, np.ndarray):
            audio = audio.cpu().numpy()
        audio = audio.astype(np.float32).squeeze()
        fade_len = min(int(sr * 0.15), len(audio))
        if fade_len > 0:
            audio[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        pad = np.zeros(int(sr * 0.2), dtype=np.float32)
        audio = np.concatenate([audio, pad])
        return audio, int(sr)
