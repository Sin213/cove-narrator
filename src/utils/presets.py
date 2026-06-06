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
    blend_key: str = ""

_BUILTIN_VOICES = [
    # American Female
    ("Heart — warm, friendly", "af_heart"),
    ("Bella — smooth, gentle", "af_bella"),
    ("Nova — bright, energetic", "af_nova"),
    ("Sarah — clear, neutral", "af_sarah"),
    ("Nicole — soft, calm", "af_nicole"),
    ("Sky — light, airy", "af_sky"),
    ("River — steady, soothing", "af_river"),
    ("Jessica — crisp, confident", "af_jessica"),
    ("Alloy — clean, modern", "af_alloy"),
    ("Kore — direct, focused", "af_kore"),
    ("Aoede — melodic, expressive", "af_aoede"),
    # American Male
    ("Adam — deep, authoritative", "am_adam"),
    ("Michael — balanced, narrator", "am_michael"),
    ("Eric — warm, conversational", "am_eric"),
    ("Liam — young, casual", "am_liam"),
    ("Echo — smooth, resonant", "am_echo"),
    ("Onyx — low, dramatic", "am_onyx"),
    ("Puck — playful, lively", "am_puck"),
    ("Fenrir — bold, intense", "am_fenrir"),
    # British Female
    ("Alice — poised, refined (UK)", "bf_alice"),
    ("Emma — warm, articulate (UK)", "bf_emma"),
    ("Isabella — elegant, precise (UK)", "bf_isabella"),
    ("Lily — gentle, soft (UK)", "bf_lily"),
    # British Male
    ("Daniel — classic, composed (UK)", "bm_daniel"),
    ("George — rich, dignified (UK)", "bm_george"),
    ("Fable — storyteller, expressive (UK)", "bm_fable"),
    ("Lewis — clear, steady (UK)", "bm_lewis"),
]

class PresetManager:
    def __init__(self, config_dir: Path | None = None):
        self._dir = config_dir or Path.home() / ".config" / "cove-narrator" / "presets"
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
                    blend_key=data.get("blend_key", ""),
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
        if preset.blend_key:
            data["blend_key"] = preset.blend_key
        path.write_text(json.dumps(data, indent=2))

    def delete_preset(self, name: str):
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        path = self._dir / f"{safe_name}.json"
        if path.exists():
            path.unlink()
