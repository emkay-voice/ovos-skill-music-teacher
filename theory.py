"""Notes, scales and chords - spelled the way a teacher writes them.

A spelled note is (letter, accidental): letter 0-6 for C D E F G A B,
accidental -2..2 (flats, sharps). F major has a B flat, not an A sharp; a
scale uses every letter once, and a chord's third is two letters up from
its root. How a spelled note is written and said depends on the language:
letters (C D E ... B), German and Danish letters (H for B, B for B flat,
"cis", "es"), or solfège (do re mi ...).
"""
from __future__ import annotations

from dataclasses import dataclass

LETTER_PC = (0, 2, 4, 5, 7, 9, 11)
LETTERS = "CDEFGAB"

#: scales: semitones above the tonic, and the letter steps (None: derived)
SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
}
#: letter steps above the tonic for each scale tone (a heptatonic scale: 0..6)
SCALE_LETTERS = {
    "major": (0, 1, 2, 3, 4, 5, 6), "minor": (0, 1, 2, 3, 4, 5, 6),
    "harmonic_minor": (0, 1, 2, 3, 4, 5, 6), "dorian": (0, 1, 2, 3, 4, 5, 6),
    "mixolydian": (0, 1, 2, 3, 4, 5, 6),
    "major_pentatonic": (0, 1, 2, 4, 5), "minor_pentatonic": (0, 2, 3, 4, 6),
    "blues": (0, 2, 3, 4, 4, 6),     # the blue note: a flat fifth (A blues: E flat)
}
#: is the scale's tonic spelled as a minor key's?
MINOR_SCALES = {"minor", "harmonic_minor", "dorian", "minor_pentatonic", "blues"}

#: chords: (semitones, letter steps) above the root
CHORDS = {
    "maj": ((0, 4, 7), (0, 2, 4)),
    "min": ((0, 3, 7), (0, 2, 4)),
    "7": ((0, 4, 7, 10), (0, 2, 4, 6)),
    "maj7": ((0, 4, 7, 11), (0, 2, 4, 6)),
    "m7": ((0, 3, 7, 10), (0, 2, 4, 6)),
    "dim": ((0, 3, 6), (0, 2, 4)),
    "sus2": ((0, 2, 7), (0, 1, 4)),
    "sus4": ((0, 5, 7), (0, 3, 4)),
    "6": ((0, 4, 7, 9), (0, 2, 4, 5)),
}
SYMBOL = {"maj": "", "min": "m", "7": "7", "maj7": "maj7", "m7": "m7", "dim": "dim", "sus2": "sus2",
          "sus4": "sus4", "6": "6"}

#: how a tonic (or a chord's root) is usually spelled
MAJOR_TONIC = {0: (0, 0), 1: (1, -1), 2: (1, 0), 3: (2, -1), 4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0),
               8: (5, -1), 9: (5, 0), 10: (6, -1), 11: (6, 0)}
MINOR_TONIC = {0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (2, -1), 4: (2, 0), 5: (3, 0), 6: (3, 1), 7: (4, 0),
               8: (4, 1), 9: (5, 0), 10: (6, -1), 11: (6, 0)}


def pc_of(sp) -> int:
    letter, acc = sp
    return (LETTER_PC[letter] + acc) % 12


def spell_from(tonic, letter_steps: int, semis: int):
    """The note `semis` above the spelled `tonic`, written `letter_steps` letters up."""
    letter = (tonic[0] + letter_steps) % 7
    want = (pc_of(tonic) + semis) % 12
    acc = (want - LETTER_PC[letter] + 6) % 12 - 6
    return letter, acc


def tonic_spelling(pc: int, minor: bool):
    return (MINOR_TONIC if minor else MAJOR_TONIC)[pc % 12]


# ------------------------------------------------------------------ scales and chords
@dataclass(frozen=True)
class Scale:
    tonic: int                # pitch class
    kind: str = "major"

    @property
    def spelled(self) -> list:
        tonic = tonic_spelling(self.tonic, self.kind in MINOR_SCALES)
        return [spell_from(tonic, l, s) for s, l in zip(SCALES[self.kind], SCALE_LETTERS[self.kind])]

    @property
    def pcs(self) -> list[int]:
        return [(self.tonic + s) % 12 for s in SCALES[self.kind]]

    def notes(self, low: int) -> list[int]:
        """One octave up from the tonic at or above MIDI note `low`, ending on the tonic."""
        root = low + (self.tonic - low) % 12
        return [root + s for s in SCALES[self.kind]] + [root + 12]

    def spelled_up(self) -> list:
        """Spelled as notes(): one octave, the tonic again on top."""
        sp = self.spelled
        return sp + [sp[0]]

    @property
    def minor(self) -> bool:
        return self.kind in MINOR_SCALES


@dataclass(frozen=True)
class Chord:
    root: int                 # pitch class
    quality: str = "maj"

    @property
    def symbol_parts(self):
        return self.root_spelled, SYMBOL[self.quality]

    @property
    def root_spelled(self):
        minorish = self.quality in ("min", "m7", "dim")
        return tonic_spelling(self.root, minorish)

    @property
    def spelled(self) -> list:
        semis, letters = CHORDS[self.quality]
        return [spell_from(self.root_spelled, l, s) for s, l in zip(semis, letters)]

    @property
    def pcs(self) -> list[int]:
        return [(self.root + s) % 12 for s in CHORDS[self.quality][0]]

    def notes(self, low: int = 60) -> list[int]:
        root = low + (self.root - low) % 12
        return [root + s for s in CHORDS[self.quality][0]]

    @property
    def minor(self) -> bool:
        return self.quality in ("min", "m7", "dim")

    @property
    def id(self) -> str:
        """Language-free: "A:min"."""
        return f"{LETTERS[self.root_spelled[0]]}{'#' * max(0, self.root_spelled[1])}" \
               f"{'b' * max(0, -self.root_spelled[1])}:{self.quality}"


def parse_chord(text: str) -> Chord:
    """"Am", "F#7", "Bbmaj7", "Dsus4", "C" (letters, as in the lessons' files)."""
    t = text.strip()
    letter = LETTERS.index(t[0].upper())
    i, acc = 1, 0
    while i < len(t) and t[i] in "#b":
        acc += 1 if t[i] == "#" else -1
        i += 1
    rest = t[i:]
    quality = {v: k for k, v in SYMBOL.items()}.get(rest)
    if quality is None:
        quality = {"min": "min", "-": "min", "M7": "maj7", "min7": "m7", "°": "dim"}.get(rest)
    if quality is None:
        raise ValueError(f"not a chord: {text}")
    return Chord(pc_of((letter, acc)), quality)


def parse_note(text: str) -> int:
    """A pitch class from "C", "F#", "Bb"."""
    t = text.strip()
    acc = sum(1 if c == "#" else -1 for c in t[1:] if c in "#b")
    return pc_of((LETTERS.index(t[0].upper()), acc))


# ------------------------------------------------------------------ names, per language
SOLFEGE = {
    "fr": ["do", "ré", "mi", "fa", "sol", "la", "si"],
    "pt": ["dó", "ré", "mi", "fá", "sol", "lá", "si"],
}
SOLFEGE_DEFAULT = ["do", "re", "mi", "fa", "sol", "la", "si"]
#: spoken sharp / flat
ACCIDENTAL_WORDS = {
    "en": ("sharp", "flat"), "es": ("sostenido", "bemol"), "fr": ("dièse", "bémol"),
    "it": ("diesis", "bemolle"), "pt": ("sustenido", "bemol"), "ca": ("sostingut", "bemoll"),
    "gl": ("sostido", "bemol"), "eu": ("diesa", "bemol"),
}
GERMANIC = ("de", "da", "nl")
LATIN = ("es", "fr", "it", "pt", "ca", "gl", "eu")


def base_lang(lang: str) -> str:
    return (lang or "en").split("-")[0].lower()


def written(sp, lang: str) -> str:
    """How the note is written on the screen: "B♭", "B" (Danish/German for
    B flat), "H", "Si♭"."""
    letter, acc = sp
    lang = base_lang(lang)
    sign = "♯" * max(0, acc) + "♭" * max(0, -acc)
    if lang in LATIN:
        name = (SOLFEGE.get(lang) or SOLFEGE_DEFAULT)[letter]
        return name[:1].upper() + name[1:] + sign
    if lang in ("de", "da") and letter == 6:
        if acc == 0:
            return "H"
        if acc == -1:
            return "B"
        return "H" + sign if acc > 0 else "B" + "♭" * (-acc - 1)
    return LETTERS[letter] + sign


def spoken(sp, lang: str) -> str:
    """How the note is said: "B flat", "b" (Danish), "Fis", "si bemol"."""
    letter, acc = sp
    lang = base_lang(lang)
    if lang in GERMANIC:
        name = LETTERS[letter]
        if lang in ("de", "da") and letter == 6:
            name = "H" if acc >= 0 else "B"
            acc = acc if acc >= 0 else acc + 1
        elif lang == "nl" and letter == 6 and acc < 0:
            name, acc = "Bes", acc + 1
        if acc > 0:
            name += "is" * acc
        elif acc < 0:
            for _ in range(-acc):
                name += "s" if name[-1] in "EA" else "es"
        return name.lower() if lang == "da" else name
    if lang in LATIN:
        name = (SOLFEGE.get(lang) or SOLFEGE_DEFAULT)[letter]
    else:
        name = LETTERS[letter]
    sharp, flat = ACCIDENTAL_WORDS.get(lang, ACCIDENTAL_WORDS["en"])
    words = [name] + [sharp] * max(0, acc) + [flat] * max(0, -acc)
    return " ".join(words)


def chord_symbol(chord: Chord, lang: str) -> str:
    """"Am", "H7" (Danish), "Lam" (Spanish)."""
    root, suffix = chord.symbol_parts
    return written(root, lang) + suffix


def pc_spelled(pc: int, context_minor: bool = False):
    """A pitch class alone, spelled as its key would spell it."""
    return tonic_spelling(pc, context_minor)
