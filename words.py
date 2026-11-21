"""The teacher's words in a language: what a sentence asks for (an
instrument, a scale, a chord, a command), and how notes, scales, chords,
strings and fingers are said.

Each locale has .voc files (a word or phrase a line) and words.json: the
names of the instruments, the strings, the fingers, and the patterns for
scale and chord names ("{note} major", "{note}-dur", "{note} mayor").
Note names come from theory (letters, H/B, solfège) and are read with
ovos-skill-jamband's note reader, so "fis", "si bemol" and "B flat" work.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ovos_skill_jamband.words import normal, note as read_note

from .instruments import GUITAR, Instrument
from .theory import LETTER_PC, Chord, Scale, base_lang, pc_spelled, spoken, written

#: chord suffixes as written in a chord symbol ("Am", "G7", "Cmaj7")
SUFFIX_QUALITY = {"": "maj", "m": "min", "min": "min", "7": "7", "maj7": "maj7", "m7": "m7", "dim": "dim",
                  "sus2": "sus2", "sus4": "sus4", "sus": "sus4", "6": "6"}
SYMBOL_RE = re.compile(r"^([a-h])(#|♯|b|♭|is|es|s)?(maj7|m7|min|m|7|dim|sus2|sus4|sus|6)?$")
#: what a quality is called, from the most specific
QUALITY_ORDER = ("maj7", "m7", "7", "dim", "sus2", "sus4", "6", "min", "maj")
SCALE_ORDER = ("harmonic_minor", "major_pentatonic", "minor_pentatonic", "blues", "dorian", "mixolydian",
               "minor", "major")


#: solfège as Portuguese writes it, for the note reader
ACCENTED = {"dó": "do", "fá": "fa", "lá": "la"}


def clean(text: str) -> str:
    """Lower case, words only: "C-dur-skalaen" is "c dur skalaen", "l'escala" is "l escala"."""
    return normal(text).replace("-", " ").replace("'", " ").replace("’", " ")


class Words:
    def __init__(self, locale_dir: Path, lang: str):
        self.lang = base_lang(lang)
        folder = self._folder(locale_dir, lang)
        self.voc: dict[str, list[str]] = {}
        for f in folder.glob("*.voc"):
            lines = [clean(w) for w in f.read_text(encoding="utf-8").splitlines()
                     if w.strip() and not w.startswith("#")]
            self.voc[f.stem] = sorted(lines, key=len, reverse=True)
        self.names = json.loads((folder / "words.json").read_text(encoding="utf-8"))

    @staticmethod
    def _folder(locale_dir: Path, lang: str) -> Path:
        want = lang.lower()
        for d in locale_dir.iterdir():
            if d.name.lower() == want:
                return d
        for d in locale_dir.iterdir():
            if d.name.lower().split("-")[0] == want.split("-")[0]:
                return d
        return locale_dir / "en-US"

    # ------------------------------------------------------------ reading
    def has(self, utterance: str, name: str) -> bool:
        u = f" {clean(utterance)} "
        return any(f" {w} " in u for w in self.voc.get(name, []))

    def instrument(self, utterance: str) -> str | None:
        u = f" {clean(utterance)} "
        found = []
        for name in ("piano", "guitar", "bass"):
            for w in self.voc.get(name, []):
                i = u.find(f" {w} ")
                if i >= 0:
                    found.append((i, name))
                    break
        return min(found)[1] if found else None

    def _tokens(self, text: str) -> list[str]:
        return [ACCENTED.get(t, t) for t in clean(text).split()]

    def _root(self, tokens: list[str], loose: bool):
        """(pitch class, index after it, quality from a symbol) of the note
        the sentence is about. A note name is also an everyday word ("a",
        "la", "mi", "en"), so the one that stands with a quality, a scale
        kind, "scale" or "chord" wins (the last such); else, when `loose`,
        the last note name that isn't a filler word ("the", "me", ...)."""
        filler = set(self.voc.get("filler", []))
        anchors = set()
        for v in ("chord", "scale"):
            anchors |= set(self.voc.get(v, []))
        found = []
        for i, tok in enumerate(tokens):
            m = SYMBOL_RE.match(tok)
            if m and m.group(3) and len(tok) > 1:            # "am", "g7", "f#m7"
                acc = (m.group(2) or "").replace("is", "#").replace("es", "b").replace("s", "b")
                pc, _ = read_note(m.group(1) + acc, "", self.lang)
                if pc is not None:
                    found.append((True, pc, i + 1, SUFFIX_QUALITY[m.group(3)]))
                    continue
            pc, used = read_note(tok, " ".join(tokens[i + 1:i + 3]), self.lang)
            if pc is None:
                continue
            nxt = tokens[i + 1 + used:]
            # "la escala": an article before "scale" is not a note; "la menor" is
            strong = bool(used) or any(c in tok for c in "#♯♭") or bool(nxt and (
                self._quality_at(nxt) or self._kind_at(nxt) or (nxt[0] in anchors and tok not in filler)))
            found.append((strong, pc, i + 1 + used, None))
        strong = [f for f in found if f[0]]
        if strong:
            return strong[-1][1:]
        if loose:
            # a filler word ("a", "la", "mi") is a note only at the very end: "el acorde de la"
            weak = [f for f in found if tokens[f[2] - 1] not in filler or f[2] == len(tokens)]
            if weak:
                return weak[-1][1:]
        return None

    def _kind_at(self, tokens: list[str]) -> str | None:
        text = " " + " ".join(tokens[:3]) + " "
        for k in SCALE_ORDER + ("pentatonic",):
            for w in self.voc.get(f"s_{k}", []):
                if text.startswith(f" {w} "):
                    return k
        return None

    def _quality_at(self, tokens: list[str]) -> str | None:
        text = " " + " ".join(tokens[:3]) + " "
        for q in QUALITY_ORDER:
            for w in self.voc.get(f"q_{q}", []):
                if text.startswith(f" {w} "):
                    return q
        return None

    def chord(self, text: str, loose: bool = True) -> Chord | None:
        """"A minor", "am", "g7", "g seven", "c major seven", "a-mol", "la menor"."""
        tokens = self._tokens(text)
        found = self._root(tokens, loose)
        if not found:
            return None
        pc, after, quality = found
        if quality is None:
            quality = self._quality_at(tokens[after:]) or "maj"
        return Chord(pc, quality)

    def scale(self, text: str, loose: bool = True) -> Scale | None:
        """"C major", "a minor pentatonic", "e blues", "d-mol", "sol mayor"."""
        tokens = self._tokens(text)
        found = self._root(tokens, loose)
        if not found:
            return None
        pc, after, quality = found
        rest = " " + " ".join(tokens) + " "
        kind = None
        for k in SCALE_ORDER:
            if any(f" {w} " in rest for w in self.voc.get(f"s_{k}", [])):
                kind = k
                break
        if kind in ("major_pentatonic", "minor_pentatonic") or kind is None:
            minorish = quality in ("min", "m7") or any(f" {w} " in rest for w in self.voc.get("s_minor", []))
            if kind is None and any(f" {w} " in rest for w in self.voc.get("s_pentatonic", [])):
                kind = "minor_pentatonic" if minorish else "major_pentatonic"
            elif kind is None:
                kind = "minor" if minorish else "major"
        return Scale(pc, kind)

    # ------------------------------------------------------------ saying
    def written(self, sp) -> str:
        return written(sp, self.lang)

    def spoken(self, sp) -> str:
        return spoken(sp, self.lang)

    def spell(self, midi_or_pc: int, minor: bool = False, chord: Chord | None = None):
        pc = midi_or_pc % 12
        if chord is not None:
            for sp in chord.spelled:
                if (LETTER_PC[sp[0]] + sp[1]) % 12 == pc:
                    return sp
        return pc_spelled(pc, minor)

    def note_written(self, n: int, minor: bool = False, chord: Chord | None = None) -> str:
        return self.written(self.spell(n, minor, chord))

    def note_spoken(self, n: int, minor: bool = False, chord: Chord | None = None) -> str:
        return self.spoken(self.spell(n, minor, chord))

    def scale_name(self, scale: Scale) -> str:
        return self.names["scale"][scale.kind].format(note=self.spoken(scale.spelled[0]))

    def scale_heading(self, scale: Scale) -> str:
        return self.names["scale_heading"][scale.kind].format(note=self.written(scale.spelled[0]))

    def chord_name(self, chord: Chord) -> str:
        return self.names["chord"][chord.quality].format(note=self.spoken(chord.root_spelled))

    def instrument_name(self, name: str) -> str:
        return self.names["instrument"][name]

    def join(self, items: list[str]) -> str:
        items = [str(i) for i in items]
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + f" {self.names['and']} " + items[-1]

    def string_name(self, inst: Instrument, s: int) -> str:
        return self.names["strings"][inst.name][s]

    def string_letters(self, inst: Instrument) -> list[str]:
        """Under the diagram, lowest first: E A D G B E (Danish H)."""
        out = [self.written(pc_spelled(o % 12)) for o in inst.tuning]
        if inst.name == "guitar":
            out[-1] = out[-1].lower()
        return out

    def place(self, inst: Instrument, s: int, fret: int) -> str:
        string = self.string_name(inst, s)
        if fret == 0:
            return self.names["open_string"].format(string=string)
        return self.names["place"].format(string=string, fret=fret)

    def finger(self, f: int) -> str:
        return self.names["fingers"][f]

    def guitar_fingering(self, shape) -> str:
        """"Index finger on the B string, fret 1, middle finger on ... -
        leave out the low E string." Lowest string first, as it is fretted."""
        parts = []
        if shape.barre:
            parts.append(self.names["barre"].format(fret=shape.barre))
        for s, (fret, finger) in enumerate(shape.strings):
            if fret and not (shape.barre and fret == shape.barre and finger == 1):
                parts.append(self.names["finger_place"].format(
                    finger=self.finger(finger), string=self.string_name(GUITAR, s), fret=fret))
        muted = [self.string_name(GUITAR, s) for s, (fret, _) in enumerate(shape.strings) if fret is None]
        text = self.join(parts) if parts else self.names["all_open"]
        if muted:
            text += ". " + self.names["mute"].format(strings=self.join(muted))
        return text
