# src/data/dictionary.py
from pathlib import Path
from src.data.phonemes import arpabet_to_ipa

_DICT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cmudict.txt"

_G2P_RULES = {
    "a": "AH", "b": "B", "c": "K", "d": "D", "e": "EH",
    "f": "F", "g": "G", "h": "HH", "i": "IH", "j": "JH",
    "k": "K", "l": "L", "m": "M", "n": "N", "o": "AA",
    "p": "P", "q": "K", "r": "R", "s": "S", "t": "T",
    "u": "AH", "v": "V", "w": "W", "x": "K", "y": "Y", "z": "Z",
    "ch": "CH", "sh": "SH", "th": "TH", "ng": "NG", "zh": "ZH",
}


class Dictionary:
    def __init__(self, dict_path: Path | None = None):
        self._entries: dict[str, list[str]] = {}
        path = dict_path or _DICT_PATH
        if path.exists():
            self._load(path)

    def _load(self, path: Path):
        with open(path, encoding="latin-1") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";;;"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                word = parts[0].lower()
                if word.endswith(")"):
                    word = word.rsplit("(", 1)[0]
                if word not in self._entries:
                    self._entries[word] = parts[1:]

    def lookup(self, word: str) -> tuple[list[str], bool]:
        key = word.lower().strip()
        if key in self._entries:
            return self._entries[key], True
        return self._g2p_fallback(key), False

    def _g2p_fallback(self, word: str) -> list[str]:
        result = []
        i = 0
        while i < len(word):
            if i + 1 < len(word) and word[i:i+2] in _G2P_RULES:
                result.append(_G2P_RULES[word[i:i+2]])
                i += 2
            elif word[i] in _G2P_RULES:
                result.append(_G2P_RULES[word[i]])
                i += 1
            else:
                i += 1
        return result if result else ["AH"]

    def to_ipa(self, text: str) -> str:
        words = text.split()
        ipa_parts = []
        for word in words:
            clean = "".join(c for c in word if c.isalpha())
            if not clean:
                continue
            phonemes, _ = self.lookup(clean)
            ipa_word = []
            for p in phonemes:
                ipa = arpabet_to_ipa(p)
                if ipa:
                    ipa_word.append(ipa)
            ipa_parts.append("".join(ipa_word))
        return " ".join(ipa_parts)

    def lookup_with_flags(self, text: str) -> list[tuple[str, list[str], bool]]:
        words = text.split()
        result = []
        for word in words:
            clean = "".join(c for c in word if c.isalpha())
            if not clean:
                result.append((word, [], True))
                continue
            phonemes, is_known = self.lookup(clean)
            result.append((word, phonemes, is_known))
        return result
