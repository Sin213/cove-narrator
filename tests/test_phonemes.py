# tests/test_phonemes.py
from src.data.phonemes import PHONEMES, arpabet_to_ipa, PAUSE_TOKEN


def test_phoneme_count():
    assert len(PHONEMES) == 45


def test_all_phonemes_have_ipa():
    for p in PHONEMES:
        if p["arpabet"] == PAUSE_TOKEN:
            continue
        assert p["ipa"] != "", f"{p['arpabet']} has no IPA mapping"


def test_categories_present():
    categories = {p["category"] for p in PHONEMES}
    assert "vowel" in categories
    assert "consonant" in categories
    assert "pause" in categories


def test_arpabet_to_ipa_maps_known():
    assert arpabet_to_ipa("AA") is not None
    assert arpabet_to_ipa("B") is not None


def test_arpabet_to_ipa_returns_none_for_unknown():
    assert arpabet_to_ipa("ZZZZ") is None
