import json
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Preset:
    name: str
    voice_id: str
    pitch: int = 0
    speed: int = 0
    depth: int = 0
    is_builtin: bool = False

_BUILTIN_VOICES = [
    ("Heart (F)", "af_heart"),
    ("Bella (F)", "af_bella"),
    ("Nova (F)", "af_nova"),
    ("Sarah (F)", "af_sarah"),
    ("Nicole (F)", "af_nicole"),
    ("Sky (F)", "af_sky"),
    ("River (F)", "af_river"),
    ("Adam (M)", "am_adam"),
    ("Michael (M)", "am_michael"),
    ("Eric (M)", "am_eric"),
    ("Liam (M)", "am_liam"),
    ("Alice (BF)", "bf_alice"),
    ("Emma (BF)", "bf_emma"),
    ("Daniel (BM)", "bm_daniel"),
    ("George (BM)", "bm_george"),
]

class PresetManager:
    def __init__(self, config_dir: Path | None = None):
        self._dir = config_dir or Path.home() / ".config" / "whooshy" / "presets"
        self._dir.mkdir(parents=True, exist_ok=True)

    def get_builtin_presets(self) -> list[Preset]:
        return [Preset(name=name, voice_id=vid, is_builtin=True) for name, vid in _BUILTIN_VOICES]

    def get_custom_presets(self) -> list[Preset]:
        presets = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                presets.append(Preset(
                    name=data["name"], voice_id=data["voice_id"],
                    pitch=data.get("pitch", 0), speed=data.get("speed", 0), depth=data.get("depth", 0),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return presets

    def get_all_presets(self) -> list[Preset]:
        return self.get_builtin_presets() + self.get_custom_presets()

    def save_preset(self, preset: Preset):
        safe_name = "".join(c if c.isalnum() else "_" for c in preset.name)
        path = self._dir / f"{safe_name}.json"
        data = {"name": preset.name, "voice_id": preset.voice_id,
                "pitch": preset.pitch, "speed": preset.speed, "depth": preset.depth}
        path.write_text(json.dumps(data, indent=2))

    def delete_preset(self, name: str):
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        path = self._dir / f"{safe_name}.json"
        if path.exists():
            path.unlink()
