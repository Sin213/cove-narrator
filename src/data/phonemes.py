# src/data/phonemes.py
PAUSE_TOKEN = "SIL"

PHONEMES = [
    {"arpabet": "AA", "ipa": "ɑ", "example": "father", "category": "vowel"},
    {"arpabet": "AE", "ipa": "æ", "example": "cat", "category": "vowel"},
    {"arpabet": "AH", "ipa": "ʌ", "example": "but", "category": "vowel"},
    {"arpabet": "AO", "ipa": "ɔ", "example": "law", "category": "vowel"},
    {"arpabet": "AW", "ipa": "aʊ", "example": "cow", "category": "vowel"},
    {"arpabet": "AY", "ipa": "aɪ", "example": "my", "category": "vowel"},
    {"arpabet": "EH", "ipa": "ɛ", "example": "bed", "category": "vowel"},
    {"arpabet": "ER", "ipa": "ɜː", "example": "her", "category": "vowel"},
    {"arpabet": "EY", "ipa": "eɪ", "example": "say", "category": "vowel"},
    {"arpabet": "IH", "ipa": "ɪ", "example": "sit", "category": "vowel"},
    {"arpabet": "IY", "ipa": "iː", "example": "see", "category": "vowel"},
    {"arpabet": "OW", "ipa": "oʊ", "example": "go", "category": "vowel"},
    {"arpabet": "OY", "ipa": "ɔɪ", "example": "boy", "category": "vowel"},
    {"arpabet": "UH", "ipa": "ʊ", "example": "book", "category": "vowel"},
    {"arpabet": "UW", "ipa": "uː", "example": "food", "category": "vowel"},
    {"arpabet": "B", "ipa": "b", "example": "boy", "category": "consonant"},
    {"arpabet": "CH", "ipa": "ʧ", "example": "chair", "category": "consonant"},
    {"arpabet": "D", "ipa": "d", "example": "dog", "category": "consonant"},
    {"arpabet": "DH", "ipa": "ð", "example": "the", "category": "consonant"},
    {"arpabet": "F", "ipa": "f", "example": "fish", "category": "consonant"},
    {"arpabet": "G", "ipa": "ɡ", "example": "go", "category": "consonant"},
    {"arpabet": "HH", "ipa": "h", "example": "hat", "category": "consonant"},
    {"arpabet": "JH", "ipa": "ʤ", "example": "joy", "category": "consonant"},
    {"arpabet": "K", "ipa": "k", "example": "cat", "category": "consonant"},
    {"arpabet": "L", "ipa": "l", "example": "lip", "category": "consonant"},
    {"arpabet": "M", "ipa": "m", "example": "man", "category": "consonant"},
    {"arpabet": "N", "ipa": "n", "example": "no", "category": "consonant"},
    {"arpabet": "NG", "ipa": "ŋ", "example": "sing", "category": "consonant"},
    {"arpabet": "P", "ipa": "p", "example": "pin", "category": "consonant"},
    {"arpabet": "R", "ipa": "ɹ", "example": "red", "category": "consonant"},
    {"arpabet": "S", "ipa": "s", "example": "sun", "category": "consonant"},
    {"arpabet": "SH", "ipa": "ʃ", "example": "she", "category": "consonant"},
    {"arpabet": "T", "ipa": "t", "example": "top", "category": "consonant"},
    {"arpabet": "TH", "ipa": "θ", "example": "thin", "category": "consonant"},
    {"arpabet": "V", "ipa": "v", "example": "van", "category": "consonant"},
    {"arpabet": "W", "ipa": "w", "example": "win", "category": "consonant"},
    {"arpabet": "Y", "ipa": "j", "example": "yes", "category": "consonant"},
    {"arpabet": "Z", "ipa": "z", "example": "zoo", "category": "consonant"},
    {"arpabet": "ZH", "ipa": "ʒ", "example": "vision", "category": "consonant"},
    {"arpabet": "AX", "ipa": "ə", "example": "about", "category": "vowel"},
    {"arpabet": "AXR", "ipa": "ɚ", "example": "butter", "category": "vowel"},
    {"arpabet": "IX", "ipa": "ɨ", "example": "roses", "category": "vowel"},
    {"arpabet": "UX", "ipa": "ʉ", "example": "dude", "category": "vowel"},
    {"arpabet": "EL", "ipa": "l̩", "example": "bottle", "category": "consonant"},
    {"arpabet": PAUSE_TOKEN, "ipa": " ", "example": "(silence)", "category": "pause"},
]

_ARPABET_TO_IPA = {p["arpabet"]: p["ipa"] for p in PHONEMES}


def arpabet_to_ipa(arpabet: str) -> str | None:
    clean = arpabet.rstrip("012")
    return _ARPABET_TO_IPA.get(clean)


def arpabet_sequence_to_ipa(sequence: list[str]) -> str:
    parts = []
    for symbol in sequence:
        ipa = arpabet_to_ipa(symbol)
        if ipa is not None:
            parts.append(ipa)
    return "".join(parts)
