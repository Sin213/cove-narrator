# tests/test_dictionary.py
from src.data.dictionary import Dictionary


def test_lookup_known_word():
    d = Dictionary()
    phonemes, is_known = d.lookup("hello")
    assert is_known
    assert len(phonemes) > 0


def test_lookup_unknown_word():
    d = Dictionary()
    phonemes, is_known = d.lookup("xyzzyplugh")
    assert not is_known
    assert len(phonemes) > 0


def test_lookup_case_insensitive():
    d = Dictionary()
    lower_ph, _ = d.lookup("hello")
    upper_ph, _ = d.lookup("HELLO")
    assert lower_ph == upper_ph


def test_to_ipa_returns_string():
    d = Dictionary()
    ipa = d.to_ipa("hello world")
    assert isinstance(ipa, str)
    assert len(ipa) > 0
