"""The things to play: a scale, a chord, a piece of a song, a bass line.

An exercise knows what it asks for (the notes, or the chord), how it looks
on the screen, how it sounds (the example, as MIDI events), and how what
was played compares (check). What it says comes from the locale (Words).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import hearing as H
from . import instruments as I
from . import screen as S
from .theory import Chord, Scale, chord_symbol

EXAMPLE_TEMPO = 84             # beats a minute for a scale or a phrase played as an example
CHANNEL = 0                    # the examples' channel (the jam lessons' band uses its own)


@dataclass
class Result:
    ok: bool
    say: str                       # the dialog's name
    data: dict = field(default_factory=dict)
    marks: list | None = None      # a note row's marks
    string_marks: dict | None = None
    nothing: bool = False


class Exercise:
    kind = ""
    sequence = True                # notes one after another (else a chord, at once)

    def __init__(self, inst: I.Instrument, words):
        self.inst = inst
        self.w = words
        self.marks: list | None = None
        self.string_marks: dict | None = None

    # what is asked
    def asked(self) -> list[int]:
        raise NotImplementedError

    def labels(self) -> list[str]:
        return [self.w.note_written(n, self.minor) for n in self.asked()]

    minor = False

    # the screen
    def view(self, status: str = "", status_kind: str = "", title: str = "") -> str:
        raise NotImplementedError

    # the sound
    def example(self, tempo: int = EXAMPLE_TEMPO) -> list:
        beat = 60.0 / tempo
        ev = [["program", 0, CHANNEL, I.PROGRAM[self.inst.name]]]
        for i, n in enumerate(self.asked()):
            ev.append(["note", round(i * beat, 3), CHANNEL, n, 90, round(beat * 0.9, 3)])
        return ev

    def example_seconds(self, tempo: int = EXAMPLE_TEMPO) -> float:
        return len(self.asked()) * 60.0 / tempo + 0.8

    # what is said
    def explain(self) -> tuple[str, dict]:
        raise NotImplementedError

    # what was played
    def check(self, heard) -> Result:
        """`heard`: what listen.Ear heard (.keys or .audio)."""
        if heard.empty:
            return Result(False, "nothing", nothing=True)
        asked = self.asked()
        if heard.keys:
            played = [n for _, _, n in H.notes_from_keys(heard.keys)]
            v = H.compare(asked, played, exact_octave=True)
        else:
            x, sr = heard.audio
            played = [n for _, _, n in H.notes(x, sr, low=self.inst.tuning[0] if self.inst.fretted else 21)]
            v = H.compare(asked, played)
        self.marks = v.marks
        if v.ok:
            return Result(True, "right", marks=v.marks)
        m = v.mistake
        if m[0] == "nothing":
            return Result(False, "nothing", marks=v.marks, nothing=True)
        place = m[1] + 1
        if m[0] == "wrong":
            return Result(False, "wrong_note", {"n": place, "asked": self.w.note_spoken(m[2], self.minor),
                                                "played": self.w.note_spoken(m[3], self.minor)}, v.marks)
        if m[0] == "missing":
            return Result(False, "missing_note", {"n": place, "asked": self.w.note_spoken(m[2], self.minor)},
                          v.marks)
        return Result(False, "extra_note", {"n": max(1, m[1]), "played": self.w.note_spoken(m[3], self.minor)},
                      v.marks)

    # helpers for fretted views
    def _fret_view(self, places: list[tuple], labels: list[str], marks, status, status_kind, title, heading,
                   finger_labels=True):
        frets = [f for _, f, _ in places]
        hi = max(frets + [0])
        lo = min([f for f in frets if f] + [hi or 1])
        first = 0 if lo <= 2 else lo - 1
        span = max(5, hi - first + 1)
        kinds = {}
        for i, (s, f, g) in enumerate(places):
            mark = marks[i] if marks and i < len(marks) else None
            kind = "ok" if mark is True else "bad" if mark is False else \
                ("root" if self.asked()[i] % 12 == self.root_pc else "note")
            if (s, f) not in kinds or kind == "bad":
                kinds[(s, f)] = (str(g) if finger_labels and g else (labels[i] if not g else str(g)), kind)
        dots = [(s, f, lab, kind) for (s, f), (lab, kind) in kinds.items()]
        parts = S.fretboard(dots, self.w.string_letters(self.inst), first=first, frets=span)
        parts += S.note_row(labels, marks)
        return S.page(parts, title, heading, status, status_kind)

    root_pc = 0


# ------------------------------------------------------------------ scales
class ScaleExercise(Exercise):
    kind = "scale"

    def __init__(self, inst, words, scale: Scale):
        super().__init__(inst, words)
        self.scale = scale
        self.minor = scale.minor
        self.root_pc = scale.tonic
        if inst.fretted:
            self.places = I.fretted_scale(scale, inst)
            self._notes = [n for n, _ in self.places]
        else:
            self.places = I.piano_scale(scale, 60)
            self._notes = [n for n, _ in self.places]

    def asked(self):
        return self._notes

    def labels(self):
        return [self.w.written(sp) for sp in self.scale.spelled_up()]

    @property
    def name(self) -> str:
        return self.w.scale_name(self.scale)

    @property
    def symbol(self) -> str:
        return self.w.scale_heading(self.scale)

    def view(self, status="", status_kind="", title=""):
        labels, marks = self.labels(), self.marks
        if self.inst.fretted:
            return self._fret_view([p for _, p in self.places], labels, marks, status, status_kind, title,
                                   self.symbol)
        keys = {}
        for i, (n, finger) in enumerate(self.places):
            mark = marks[i] if marks and i < len(marks) else None
            kind = "ok" if mark is True else "bad" if mark is False else ("root" if n % 12 == self.root_pc else "note")
            keys[n] = (labels[i], finger, kind)
        parts = S.keyboard(keys) + S.note_row(labels, marks)
        return S.page(parts, title, self.symbol, status, status_kind)

    def explain(self):
        notes = self.w.join([self.w.spoken(sp) for sp in self.scale.spelled])
        if self.inst.fretted:
            s, fret, _ = self.places[0][1]
            return "scale_fretted", {"scale": self.name, "notes": notes, "where": self.w.place(self.inst, s, fret)}
        has_fingers = any(f for _, f in self.places)
        return ("scale_piano" if has_fingers else "scale_piano_free"), {"scale": self.name, "notes": notes}


# ------------------------------------------------------------------ chords
class ChordExercise(Exercise):
    kind = "chord"
    sequence = False

    def __init__(self, inst, words, chord: Chord):
        super().__init__(inst, words)
        self.chord = chord
        self.minor = chord.minor
        self.root_pc = chord.root
        if inst.name == "guitar":
            self.shape = I.guitar_chord(chord)
            self._notes = self.shape.notes()
        elif inst.name == "bass":
            self.places = I.bass_chord(chord)
            self._notes = [I.BASS.tuning[s] + f for s, f, _ in self.places]
            self.sequence = True                        # an arpeggio, a note at a time
        else:
            self.places = I.piano_chord(chord, 60)
            self._notes = [n for n, _ in self.places]

    def asked(self):
        return self._notes

    def labels(self):
        if self.inst.name == "guitar":
            return [self.w.note_written(n, self.minor, self.chord) for n in self._notes]
        return [self.w.written(sp) for sp in self.chord.spelled]

    @property
    def name(self) -> str:
        return self.w.chord_name(self.chord)

    @property
    def symbol(self) -> str:
        return chord_symbol(self.chord, self.w.lang)

    def example(self, tempo: int = EXAMPLE_TEMPO):
        ev = [["program", 0, CHANNEL, I.PROGRAM[self.inst.name]]]
        if self.sequence:
            return Exercise.example(self, tempo)
        strum = 0.03 if self.inst.name == "guitar" else 0.0
        for i, n in enumerate(self._notes):
            ev.append(["note", round(i * strum, 3), CHANNEL, n, 88, 2.2])
        return ev

    def example_seconds(self, tempo: int = EXAMPLE_TEMPO) -> float:
        return Exercise.example_seconds(self, tempo) if self.sequence else 2.6

    def view(self, status="", status_kind="", title=""):
        if self.inst.name == "guitar":
            parts = S.chord_chart(self.shape.strings, self.shape.barre, self.w.string_letters(self.inst),
                                  marks=self.string_marks)
            return S.page(parts, title, self.symbol, status, status_kind)
        if self.inst.name == "bass":
            return self._fret_view(self.places, self.labels(), self.marks, status, status_kind, title, self.symbol)
        keys = {}
        labels = self.labels()
        for i, (n, finger) in enumerate(self.places):
            kind = "root" if n % 12 == self.root_pc else "note"
            if self.string_marks is not None:
                kind = "bad" if n % 12 in self.string_marks.get("missing", []) else "ok"
            keys[n] = (labels[i], finger, kind)
        parts = S.keyboard(keys) + S.note_row(labels)
        return S.page(parts, title, self.symbol, status, status_kind)

    def explain(self):
        notes = self.w.join([self.w.spoken(sp) for sp in self.chord.spelled])
        if self.inst.name == "guitar":
            return "chord_guitar", {"chord": self.name, "fingers": self.w.guitar_fingering(self.shape)}
        if self.inst.name == "bass":
            return "chord_bass", {"chord": self.name, "notes": notes}
        return "chord_piano", {"chord": self.name, "notes": notes}

    def check(self, heard) -> Result:
        if heard.empty:
            return Result(False, "nothing", nothing=True)
        if self.sequence:
            return Exercise.check(self, heard)
        pcs = sorted({n % 12 for n in self._notes})
        if heard.keys:
            v = H.judge_keys(H.chord_keys(heard.keys), pcs)
        else:
            x, sr = heard.audio
            optional = [(self.chord.root + 7) % 12] if len(self.chord.pcs) >= 4 else []
            v = H.judge_chord(H.chroma(x, sr), pcs, optional)
        if v.nothing:
            return Result(False, "nothing", nothing=True)
        if self.inst.name == "guitar":
            marks = {}
            for s, fret, _ in self.shape.places():
                pc = (I.GUITAR.tuning[s] + fret) % 12
                marks[s] = "bad" if pc in v.missing else "ok"
            self.string_marks = marks
        else:
            self.string_marks = {"missing": v.missing}
        if v.ok:
            return Result(True, "right")
        if v.missing:
            names = self.w.join([self.w.note_spoken(pc, self.minor, self.chord) for pc in v.missing])
            if self.inst.name == "guitar":
                strings = [s for s, fret, _ in self.shape.places()
                           if (I.GUITAR.tuning[s] + fret) % 12 in v.missing and fret > 0]
                if strings:
                    s = strings[0]
                    fret = self.shape.strings[s][0]
                    return Result(False, "chord_missing_string",
                                  {"notes": names, "where": self.w.place(self.inst, s, fret)})
            return Result(False, "chord_missing", {"notes": names})
        names = self.w.join([self.w.note_spoken(pc, self.minor) for pc in v.foreign])
        return Result(False, "chord_foreign", {"notes": names})


# ------------------------------------------------------------------ songs
class PhraseExercise(Exercise):
    """A piece of a tune: its notes, a beat at a time as the tune has them."""
    kind = "phrase"

    def __init__(self, inst, words, notes: list[tuple], key_minor: bool, title: str, part: int, parts: int,
                 root_pc: int):
        super().__init__(inst, words)
        self.notes = notes                    # [(beat, pitch, beats)], beats from the phrase's start
        self.minor = key_minor
        self.title = title
        self.part, self.parts = part, parts
        self.root_pc = root_pc
        if inst.fretted:
            self.places = I.melody_places([p for _, p, _ in notes], inst)

    def asked(self):
        return [p for _, p, _ in self.notes]

    def example(self, tempo: int = EXAMPLE_TEMPO):
        beat = 60.0 / tempo
        ev = [["program", 0, CHANNEL, I.PROGRAM[self.inst.name]]]
        for b, p, d in self.notes:
            ev.append(["note", round(b * beat, 3), CHANNEL, p, 90, round(max(0.15, d * beat * 0.92), 3)])
        return ev

    def example_seconds(self, tempo: int = EXAMPLE_TEMPO) -> float:
        end = max(b + d for b, _, d in self.notes)
        return end * 60.0 / tempo + 0.6

    def view(self, status="", status_kind="", title=""):
        labels = self.labels()
        heading = f"{self.part}/{self.parts}"
        title = title or self.title
        if self.inst.fretted:
            return self._fret_view(self.places, labels, self.marks, status, status_kind, title, heading)
        keys = {}
        for i, n in enumerate(self.asked()):
            mark = self.marks[i] if self.marks and i < len(self.marks) else None
            kind = "ok" if mark is True else "bad" if mark is False else "note"
            if n not in keys or kind == "bad":
                keys[n] = (labels[i], None, kind)
        parts = S.keyboard(keys, low=min(self.asked()) - 2) + S.note_row(labels, self.marks)
        return S.page(parts, title, heading, status, status_kind)

    def explain(self):
        return "phrase", {"n": self.part, "count": self.parts}


class LineExercise(PhraseExercise):
    """A bass line: a note a bar, the root of each chord of the tune."""
    kind = "line"

    def explain(self):
        return "bass_line", {"n": self.part, "count": self.parts}
