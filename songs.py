"""Simple songs to learn: ovos-skill-jamband's tunes (folk songs, nursery
rhymes, the old classics - all free to use), cut into pieces to learn one
at a time, then played whole with the band.

  piano, or guitar "the melody": the tune, two bars at a time;
  guitar:   the chords the song uses, one by one, then strummed with the band;
  bass:     the bass line - the root of each bar's chord - then with the band.
"""
from __future__ import annotations

from ovos_skill_jamband import tunes as T
from ovos_skill_jamband.compose import chords_for
from ovos_skill_jamband.music import Chord as BandChord
from ovos_skill_jamband.music import Key

from . import instruments as I
from .exercises import ChordExercise, LineExercise, PhraseExercise
from .theory import Chord

STYLE = "pop"                  # how the band plays along, unless a lesson says otherwise
BARS_A_PIECE = 2


def find(utterance: str) -> str | None:
    return T.find(utterance)


def title(tune_id: str, lang: str) -> str:
    return T.title(tune_id, lang)


def library() -> list[str]:
    """The tunes that come with jamband (not the karaoke songbook's long songs)."""
    return sorted(T.TUNES)


class Song:
    def __init__(self, tune_id: str, inst: I.Instrument, words, melody: bool = False, style: str = STYLE,
                 key: int | None = None):
        """`key`: a pitch class to move the song to (guitar songs lie well in G or D)."""
        self.id = tune_id
        self.inst = inst
        self.w = words
        self.style = style
        self.mel = T.melody(tune_id)
        self.key = T.key(tune_id)
        self.chords: list[BandChord] = chords_for(tune_id, self.mel, self.key, style)
        if key is not None and key != self.key.tonic:
            semis = (key - self.key.tonic + 6) % 12 - 6
            self.mel = self.mel.transposed(semis)
            self.chords = [BandChord((c.root + semis) % 12, c.quality) for c in self.chords]
            self.key = Key(key, self.key.minor)
        self.shift = I.octave_for(self.mel.pitches(), inst)
        self.title = T.title(tune_id, words.lang)
        self.mode = "melody" if inst.name == "piano" or (melody and inst.name != "bass") else \
            ("chords" if inst.name == "guitar" else "line")

    def teacher_chords(self) -> list[Chord]:
        """The song's chords as the teacher spells them, once each, in the order they come."""
        out = []
        for c in self.chords:
            t = Chord(c.root, c.quality)
            if t not in out:
                out.append(t)
        return out

    def pieces(self) -> list:
        """The exercises, in order."""
        if self.mode == "chords":
            return [ChordExercise(self.inst, self.w, c) for c in self.teacher_chords()]
        bars = self.mel.bars
        per = BARS_A_PIECE if bars >= 4 else 1
        starts = list(range(0, bars, per))
        out = []
        for k, b0 in enumerate(starts):
            if self.mode == "line":
                notes = []
                for b in range(b0, min(bars, b0 + per)):
                    c = self.chords[b % len(self.chords)]
                    root = I.BASS.tuning[0] + (c.root - I.BASS.tuning[0]) % 12
                    notes.append(((b - b0) * 4, root, 3.6))
                out.append(LineExercise(self.inst, self.w, notes, self.key.minor, self.title, k + 1, len(starts),
                                        self.key.tonic))
                continue
            notes = [(beat - 4 * b0, p + self.shift, d) for beat, p, d in self.mel.notes
                     if 4 * b0 <= beat < 4 * (b0 + per)]
            if notes:
                out.append(PhraseExercise(self.inst, self.w, notes, self.key.minor, self.title, k + 1,
                                          len(starts), self.key.tonic))
        for i, p in enumerate(out):              # numbered as they are, with empty bars left out
            p.part, p.parts = i + 1, len(out)
        return out
