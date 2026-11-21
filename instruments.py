"""Piano, guitar and bass: where a note is played, with which finger.

A guitar or bass place is (string, fret, finger): strings counted from the
lowest (0 is the thick E string), finger 0 for an open string, 1 the index
finger ... 4 the little finger, "T" never (no thumb over the neck here). A
piano place is (MIDI note, finger), the thumb being 1.
"""
from __future__ import annotations

from dataclasses import dataclass

from .theory import Chord, Scale

#: General MIDI sounds for the examples
PROGRAM = {"piano": 0, "guitar": 25, "bass": 33}


@dataclass(frozen=True)
class Instrument:
    name: str
    tuning: tuple = ()           # open strings, lowest first (MIDI)
    low: int = 48                # where a scale starts by default
    frets: int = 15

    @property
    def fretted(self) -> bool:
        return bool(self.tuning)


PIANO = Instrument("piano", low=60)
GUITAR = Instrument("guitar", (40, 45, 50, 55, 59, 64), low=40)
BASS = Instrument("bass", (28, 33, 38, 43), low=28)
INSTRUMENTS = {"piano": PIANO, "guitar": GUITAR, "bass": BASS}


# ------------------------------------------------------------------ piano
#: right hand, one octave up, the usual fingering (by the major or minor key's tonic)
_RH_MAJOR = {0: "12312345", 7: "12312345", 2: "12312345", 9: "12312345", 4: "12312345", 11: "12312345",
             5: "12341234", 6: "23412312", 1: "23123412", 8: "34123123", 3: "31234123", 10: "41231234"}
_RH_MINOR = {9: "12312345", 4: "12312345", 11: "12312345", 2: "12312345", 7: "12312345", 0: "12312345",
             5: "12341234", 6: "34123123", 1: "34123123", 8: "34123123", 3: "31234123", 10: "21231234"}


def piano_scale(scale: Scale, low: int = 60) -> list[tuple]:
    """[(note, finger)] one octave up; fingers for the seven-note scales, else none."""
    notes = scale.notes(low)
    if len(scale.pcs) == 7:
        table = _RH_MINOR if scale.minor else _RH_MAJOR
        fingers = [int(c) for c in table[scale.tonic]]
        return list(zip(notes, fingers))
    return [(n, 0) for n in notes]


def piano_chord(chord: Chord, low: int = 60) -> list[tuple]:
    """Close position from the root at or above `low`: thumb, middle, little
    (1-3-5), or 1-2-3-5 for four notes."""
    notes = chord.notes(low)
    fingers = (1, 3, 5) if len(notes) == 3 else (1, 2, 3, 5)
    if chord.quality in ("sus2",):
        fingers = (1, 2, 5)
    return list(zip(notes, fingers))


# ------------------------------------------------------------------ guitar chords
#: open chords as on every chord chart: per string, lowest first, fret
#: (None: not played) and finger (0 open)
_OPEN = {
    "C:maj": ((None, 0), (3, 3), (2, 2), (0, 0), (1, 1), (0, 0)),
    "A:maj": ((None, 0), (0, 0), (2, 1), (2, 2), (2, 3), (0, 0)),
    "G:maj": ((3, 2), (2, 1), (0, 0), (0, 0), (0, 0), (3, 3)),
    "E:maj": ((0, 0), (2, 2), (2, 3), (1, 1), (0, 0), (0, 0)),
    "D:maj": ((None, 0), (None, 0), (0, 0), (2, 1), (3, 3), (2, 2)),
    "A:min": ((None, 0), (0, 0), (2, 2), (2, 3), (1, 1), (0, 0)),
    "E:min": ((0, 0), (2, 2), (2, 3), (0, 0), (0, 0), (0, 0)),
    "D:min": ((None, 0), (None, 0), (0, 0), (2, 2), (3, 3), (1, 1)),
    "E:7": ((0, 0), (2, 2), (0, 0), (1, 1), (0, 0), (0, 0)),
    "A:7": ((None, 0), (0, 0), (2, 2), (0, 0), (2, 3), (0, 0)),
    "D:7": ((None, 0), (None, 0), (0, 0), (2, 2), (1, 1), (2, 3)),
    "G:7": ((3, 3), (2, 2), (0, 0), (0, 0), (0, 0), (1, 1)),
    "C:7": ((None, 0), (3, 3), (2, 2), (3, 4), (1, 1), (0, 0)),
    "B:7": ((None, 0), (2, 2), (1, 1), (2, 3), (0, 0), (2, 4)),
    "C:maj7": ((None, 0), (3, 3), (2, 2), (0, 0), (0, 0), (0, 0)),
    "F:maj7": ((None, 0), (None, 0), (3, 3), (2, 2), (1, 1), (0, 0)),
    "A:maj7": ((None, 0), (0, 0), (2, 2), (1, 1), (2, 3), (0, 0)),
    "D:maj7": ((None, 0), (None, 0), (0, 0), (2, 1), (2, 2), (2, 3)),
    "G:maj7": ((3, 2), (2, 1), (0, 0), (0, 0), (0, 0), (2, 3)),
    "A:m7": ((None, 0), (0, 0), (2, 2), (0, 0), (1, 1), (0, 0)),
    "E:m7": ((0, 0), (2, 2), (0, 0), (0, 0), (0, 0), (0, 0)),
    "D:m7": ((None, 0), (None, 0), (0, 0), (2, 2), (1, 1), (1, 1)),
    "A:sus2": ((None, 0), (0, 0), (2, 1), (2, 2), (0, 0), (0, 0)),
    "A:sus4": ((None, 0), (0, 0), (2, 1), (2, 2), (3, 3), (0, 0)),
    "D:sus2": ((None, 0), (None, 0), (0, 0), (2, 1), (3, 3), (0, 0)),
    "D:sus4": ((None, 0), (None, 0), (0, 0), (2, 1), (3, 3), (3, 4)),
    "E:sus4": ((0, 0), (2, 2), (2, 3), (2, 4), (0, 0), (0, 0)),
    "C:6": ((None, 0), (3, 3), (2, 2), (2, 4), (1, 1), (0, 0)),
}
#: movable barre shapes: (string the root is on, frets above the barre, fingers)
#: the E shape has its root on the 6th string, the A shape on the 5th
_BARRE = {
    "maj": ("E", (0, 2, 2, 1, 0, 0), (1, 3, 4, 2, 1, 1)),
    "min": ("E", (0, 2, 2, 0, 0, 0), (1, 3, 4, 1, 1, 1)),
    "7": ("E", (0, 2, 0, 1, 0, 0), (1, 3, 1, 2, 1, 1)),
    "m7": ("E", (0, 2, 0, 0, 0, 0), (1, 3, 1, 1, 1, 1)),
    "maj7": ("A", (None, 0, 2, 1, 2, 0), (0, 1, 3, 2, 4, 1)),
    "sus4": ("E", (0, 2, 2, 2, 0, 0), (1, 2, 3, 4, 1, 1)),
    "sus2": ("A", (None, 0, 2, 2, 0, 0), (0, 1, 3, 4, 1, 1)),
    "dim": ("A", (None, 0, 1, 2, 1, None), (0, 1, 2, 4, 3, 0)),
    "6": ("A", (None, 0, 2, 2, 2, 2), (0, 1, 3, 3, 3, 3)),
}
_A_SHAPE = {"maj": ((None, 0, 2, 2, 2, 0), (0, 1, 2, 3, 4, 1)),
            "min": ((None, 0, 2, 2, 1, 0), (0, 1, 3, 4, 2, 1)),
            "7": ((None, 0, 2, 0, 2, 0), (0, 1, 3, 1, 4, 1)),
            "m7": ((None, 0, 2, 0, 1, 0), (0, 1, 3, 1, 2, 1))}


@dataclass(frozen=True)
class Shape:
    """A chord on the guitar: per string (fret or None, finger); `barre` is
    the fret the index finger lies across (0: none)."""
    strings: tuple
    barre: int = 0

    def notes(self, tuning=GUITAR.tuning) -> list[int]:
        return [tuning[i] + f for i, (f, _) in enumerate(self.strings) if f is not None]

    def places(self) -> list[tuple]:
        """[(string, fret, finger)] of the strings that sound."""
        return [(i, f, g) for i, (f, g) in enumerate(self.strings) if f is not None]

    @property
    def lowest_fret(self) -> int:
        frets = [f for f, _ in self.strings if f]
        return min(frets) if frets else 0


def guitar_chord(chord: Chord) -> Shape:
    """The open chord when there is one, else a barre chord low on the neck."""
    if chord.id in _OPEN:
        return Shape(_OPEN[chord.id])
    for alias in _enharmonic_ids(chord):
        if alias in _OPEN:
            return Shape(_OPEN[alias])
    options = []
    root_string, frets, fingers = _BARRE.get(chord.quality, _BARRE["maj"])
    shapes = [(root_string, frets, fingers)]
    if chord.quality in _A_SHAPE:
        shapes.append(("A", *_A_SHAPE[chord.quality]))
    for rs, fr, fi in shapes:
        open_note = GUITAR.tuning[0 if rs == "E" else 1]
        base = (chord.root - open_note) % 12
        if base == 0:
            base = 12 if any(f is not None and f > 0 for f in fr) else 0
        strings = tuple((None, 0) if f is None else (base + f, g) for f, g in zip(fr, fi))
        options.append(Shape(strings, barre=base))
    return min(options, key=lambda s: s.barre)


def _enharmonic_ids(chord: Chord) -> list[str]:
    names = {1: ["C#", "Db"], 3: ["D#", "Eb"], 6: ["F#", "Gb"], 8: ["G#", "Ab"], 10: ["A#", "Bb"]}
    return [f"{n}:{chord.quality}" for n in names.get(chord.root, [])]


def bass_chord(chord: Chord) -> list[tuple]:
    """A chord on the bass is an arpeggio: root, third (or second/fourth),
    fifth (and seventh), low on the neck, one finger per fret."""
    root = BASS.tuning[0] + (chord.root - BASS.tuning[0]) % 12
    if root - BASS.tuning[0] > 4:               # high on the E string: from the A string
        root = BASS.tuning[1] + (chord.root - BASS.tuning[1]) % 12
    return fret_notes(chord.notes(root), BASS)


# ------------------------------------------------------------------ positions
def _window(start: int) -> tuple[int, int]:
    """The frets one finger per fret covers: the open position is frets 0-4."""
    return (0, 4) if start == 0 else (start, start + 3)


def _finger(fret: int, start: int) -> int:
    if fret == 0:
        return 0
    return max(1, min(4, fret if start == 0 else fret - start + 1))


def fret_notes(notes: list[int], inst: Instrument, start: int | None = None) -> list[tuple]:
    """[(string, fret, finger)] for each note, in one position: the index
    finger on fret `start` and one finger per fret (start 0: the open
    position, with open strings). Of the strings that reach a note, the one
    with the lowest fret - as scales are taught (open B, not the G string's
    fourth fret)."""
    if start is None:
        start = best_start(notes, inst)
    lo, hi = _window(start)
    out = []
    for n in notes:
        cands = [(s, n - o) for s, o in enumerate(inst.tuning) if lo <= n - o <= hi]
        if not cands:                            # a stretch: one fret either side
            cands = [(s, n - o) for s, o in enumerate(inst.tuning) if max(0, lo - 1) <= n - o <= hi + 1]
        if not cands:
            cands = [min(((s, n - o) for s, o in enumerate(inst.tuning) if n >= o),
                         key=lambda c: abs(c[1] - lo), default=(0, max(0, n - inst.tuning[0])))]
        s, fret = min(cands, key=lambda c: (c[1], -c[0]))
        out.append((s, fret, _finger(fret, start)))
    return out


def best_start(notes: list[int], inst: Instrument) -> int:
    """The lowest position where every note lies under a finger."""
    for start in range(0, inst.frets - 3):
        lo, hi = _window(start)
        if all(any(lo <= n - o <= hi for o in inst.tuning) for n in notes):
            return start
    return 0


def fretted_scale(scale: Scale, inst: Instrument, low: int | None = None) -> list[tuple]:
    """[(note, (string, fret, finger))] one octave up from the root on the
    lowest string that has it in a comfortable position."""
    root = _scale_root(scale, inst, low)
    notes = scale.notes(root)
    places = fret_notes(notes, inst)
    return list(zip(notes, places))


def _scale_root(scale: Scale, inst: Instrument, low: int | None) -> int:
    if low is not None:
        return low + (scale.tonic - low) % 12
    # the root on the lowest string, frets 0-7 (E: open E; A: 5th fret)
    root = inst.tuning[0] + (scale.tonic - inst.tuning[0]) % 12
    if root - inst.tuning[0] > 7:          # high on the E string: from the A string instead
        root = inst.tuning[1] + (scale.tonic - inst.tuning[1]) % 12
    return root


def scale_box(scale: Scale, inst: Instrument) -> list[tuple]:
    """Every note of the scale in one position (a "box", as for jamming), on
    every string: [(string, fret, finger, pitch)]. The position is the one
    from the root on the lowest string (or the next, when that is high)."""
    root = _scale_root(scale, inst, None)
    s0 = 0 if root - inst.tuning[0] <= 7 else 1
    root_fret = root - inst.tuning[s0]
    start = 0 if root_fret <= 2 else root_fret
    lo, hi = _window(start)
    if start:
        hi += 1                               # boxes reach a fret further with the little finger
    out = {}
    for s, o in enumerate(inst.tuning):
        for fret in range(lo, hi + 1):
            if (o + fret) % 12 in scale.pcs and o + fret not in out:     # each pitch once, lowest string first
                out[o + fret] = (s, fret, _finger(fret, start), o + fret)
    # a pitch on two strings: the higher string, lower fret (as the box is taught)
    for p, (s, fret, g, _) in list(out.items()):
        for s2, o2 in enumerate(inst.tuning):
            if s2 > s and lo <= p - o2 < fret:
                out[p] = (s2, p - o2, _finger(p - o2, start), p)
    return sorted(out.values(), key=lambda x: (x[0], x[1]))


def melody_places(notes: list[int], inst: Instrument) -> list[tuple]:
    """A tune on a guitar or bass, low on the neck (the open position when it fits)."""
    return fret_notes(notes, inst)


def octave_for(notes: list[int], inst: Instrument) -> int:
    """How many octaves to move a tune (written for voice or piano) so it
    lies well on `inst`: guitar sounds an octave below written; a bass
    plays it two octaves down."""
    if inst.name == "piano":
        return 0
    lo = min(notes)
    shift = -12 if inst.name == "guitar" else -24
    while lo + shift < inst.tuning[0]:
        shift += 12
    while lo + shift - 12 >= inst.tuning[0] + (0 if inst.name == "bass" else 5):
        shift -= 12
    return shift
