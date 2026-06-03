from pathlib import Path
from src.utils.presets import PresetManager, Preset

def test_builtin_presets_exist():
    pm = PresetManager(config_dir=Path("/tmp/whooshy-test-presets"))
    builtins = pm.get_builtin_presets()
    assert len(builtins) > 0
    assert any(p.voice_id == "af_heart" for p in builtins)

def test_save_and_load_custom(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="My Voice", voice_id="am_adam", pitch=-20, speed=10, depth=30)
    pm.save_preset(preset)
    loaded = pm.get_custom_presets()
    assert len(loaded) == 1
    assert loaded[0].name == "My Voice"
    assert loaded[0].pitch == -20

def test_delete_custom(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="Temp", voice_id="af_heart", pitch=0, speed=0, depth=0)
    pm.save_preset(preset)
    assert len(pm.get_custom_presets()) == 1
    pm.delete_preset("Temp")
    assert len(pm.get_custom_presets()) == 0

def test_all_presets_builtins_first(tmp_path):
    pm = PresetManager(config_dir=tmp_path)
    preset = Preset(name="Custom", voice_id="af_heart", pitch=5, speed=5, depth=5)
    pm.save_preset(preset)
    all_presets = pm.get_all_presets()
    builtin_count = len(pm.get_builtin_presets())
    assert all_presets[0].is_builtin
    assert not all_presets[builtin_count].is_builtin
