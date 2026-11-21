"""Playing with the band: ovos-skill-jamband's jam, with the teacher on top.

Two kinds:

  - along: a song you learnt, played whole with the band (twice round).
    The screen shows what to play in each bar - the chord chart, the
    melody's keys, the bass note - as the bar comes.

  - improvise: learning to jam. The band plays a style in a key; you get
    the scale that fits (the screen lights it on your instrument, the notes
    of the chord the band plays brighter). Then you take turns, four bars
    each: the band (an instrument solos, to give you ideas), then you.
    While it is your turn the band drops back, and the teacher listens:
    how many of your notes were in the scale, and whether you landed on the
    chord's notes - and says a word about it.

Your own instrument never plays in the band.
"""
from __future__ import annotations

import threading

from ovos_skill_jamband.jam import Jam, State
from ovos_skill_jamband.music import Chord as BandChord
from ovos_skill_jamband.music import Key
from ovos_skill_jamband.styles import STYLES

from . import hearing as H
from . import instruments as I
from . import screen as S
from .exercises import ChordExercise
from .theory import Chord, Scale

TURN = 4                        # bars each, the band and you
ROUNDS_ALONG = 2                # a song played whole this many times
#: the scale to jam with, by the style (and the key's mode)
JAM_SCALE = {"blues": "blues", "rock": "minor_pentatonic", "funk": "dorian", "swing": "major_pentatonic",
             "pop": "major_pentatonic", "disco": "dorian", "reggae": "major_pentatonic", "bossa": "major",
             "tango": "harmonic_minor"}
#: who plays instead of you, and who solos to give you ideas
SOLOIST = {"piano": "sax", "guitar": "piano", "bass": "piano"}
PART = {"piano": "piano", "guitar": "guitar", "bass": "bass"}


def scale_for(style: str, key: Key, inst_name: str) -> Scale:
    kind = JAM_SCALE.get(style, "major_pentatonic")
    if key.minor and kind in ("major_pentatonic", "major"):
        kind = "minor_pentatonic" if kind == "major_pentatonic" else "minor"
    if not key.minor and kind in ("dorian", "harmonic_minor"):
        kind = "mixolydian" if kind == "dorian" else "major"
    if inst_name == "bass" and kind == "major":
        kind = "major_pentatonic"
    # a blues in a major key is played with the minor blues scale of its tonic: that is the sound
    return Scale(key.tonic, kind)


class BandLesson:
    def __init__(self, send, source: str, latency: float, inst: I.Instrument, words, ear=None,
                 on_feedback=None, on_screen=None, on_end=None):
        self.send = send
        self.source = source
        self.latency = latency
        self.inst = inst
        self.w = words
        self.ear = ear
        self.on_feedback = on_feedback          # (dialog, data): a word from the teacher
        self.on_screen = on_screen              # (svg data url)
        self.on_end = on_end
        self.jam: Jam | None = None
        self.mode = ""
        self.scale: Scale | None = None
        self.song = None
        self.rounds_bars = 0
        self.keys_seen = False                  # a MIDI keyboard played: the band needn't drop back
        self.listening = False
        self.turns: list[dict] = []             # how each of your turns went
        self._lock = threading.Lock()

    # ------------------------------------------------------------ starting
    def _band_parts(self, style) -> list[str]:
        mine = PART[self.inst.name]
        parts = [p for p in style.band if p != mine]
        if "drums" not in parts:
            parts.insert(0, "drums")
        return parts

    def along(self, song, tempo: int | None = None):
        """The song with the band, twice round."""
        self.mode, self.song = "along", song
        style = STYLES.get(song.style, STYLES["pop"])
        parts = self._band_parts(style)
        lead = "strings" if self.inst.name == "piano" else "piano"
        # the melody is played by someone else too: something to follow
        st = State(style=style, key=song.key, tempo=tempo or max(70, style.tempo - 20), parts=parts,
                   chords=list(song.chords), key_chosen=True, tempo_chosen=True, melody=song.mel, lead=lead)
        self.rounds_bars = ROUNDS_ALONG * max(len(song.chords), song.mel.bars)
        self._start(st)

    def improvise(self, style_name: str, key: Key, tempo: int | None = None):
        self.mode = "improvise"
        style = STYLES.get(style_name, STYLES["blues"])
        self.scale = scale_for(style.name, key, self.inst.name)
        st = State(style=style, key=key, tempo=tempo or max(72, style.tempo - 12),
                   parts=self._band_parts(style), key_chosen=True, tempo_chosen=True)
        self._start(st)

    def _start(self, st: State):
        self.jam = Jam(self.send, self.source, self.latency, on_bar=self._on_bar, state=st,
                       on_end=self._ended)
        self.jam.start()

    def stop(self):
        jam, self.jam = self.jam, None
        if self.ear:
            self.ear.cancelled.set()
        if jam:
            jam.stop()

    def finish(self):
        if self.jam:
            self.jam.finish()

    @property
    def running(self) -> bool:
        return bool(self.jam and self.jam.running)

    def _ended(self):
        self.jam = None
        if self.on_end:
            self.on_end(self)

    # ------------------------------------------------------------ each bar
    def your_turn(self, bar: int) -> bool:
        return self.mode == "improvise" and (bar // TURN) % 2 == 1

    def _on_bar(self, bar, chord, next_chord):
        jam = self.jam
        if not jam:
            return
        if self.mode == "along":
            if bar >= self.rounds_bars:
                jam.finish()
            self._show_along(bar, chord, next_chord)
            return
        # improvise: the bar before a turn changes what the band plays in it
        # (with a microphone only the drums stay, so it hears you and not them)
        if (bar + 1) % TURN == 0:
            if self.your_turn(bar + 1):
                if not self.keys_seen:
                    jam.change(parts=["drums"])
            else:
                jam.change(parts=self._band_parts(jam.state.style))
                if bar + 1 >= TURN * 2:            # the band's turn: someone solos
                    jam.solo_for(SOLOIST[self.inst.name], TURN)
        if bar % TURN == 0 and self.your_turn(bar) and not self.listening and self.ear:
            threading.Thread(target=self._listen_turn, args=(bar, jam.bar_seconds * TURN, jam), daemon=True).start()
        self._show_improvise(bar, chord, next_chord)

    # ------------------------------------------------------------ your turn
    def _listen_turn(self, bar, seconds, jam):
        self.listening = True
        try:
            heard = self.ear.hear(seconds=seconds - 0.3)
        finally:
            self.listening = False
        if self.jam is not jam:
            return
        if heard.keys:
            self.keys_seen = True
            played = [n for _, _, n in H.notes_from_keys(heard.keys)]
        elif heard.audio is not None:
            x, sr = heard.audio
            played = [n for _, _, n in H.notes(x, sr, low=self.inst.tuning[0] if self.inst.fretted else 21)]
        else:
            played = []
        prog = jam.state.progression()
        chords = [prog[jam.position(b)] for b in range(bar, bar + TURN)]
        turn = judge_turn(played, self.scale, chords)
        self.turns.append(turn)
        if self.on_feedback:
            self.on_feedback(*turn_words(turn, self.w, self.scale))

    # ------------------------------------------------------------ the screen
    def _show_improvise(self, bar, chord: BandChord, next_chord):
        if not self.on_screen:
            return
        tones = set(chord.tones())
        yours = self.your_turn(bar)
        title = f"{self.jam.state.style.name.title()} · {chord.name} → {next_chord.name}" if self.jam else ""
        status = self.w.names["your_turn"] if yours else self.w.names["band_turn"]
        sc = self.scale
        if self.inst.fretted:
            box = I.scale_box(sc, self.inst)
            dots = [(s, f, self.w.note_written(p, sc.minor), "root" if p % 12 in tones else "note")
                    for s, f, g, p in box]
            frets = [f for _, f, _, _ in box]
            first = 0 if min(frets) <= 1 else min(frets) - 1
            parts = S.fretboard(dots, self.w.string_letters(self.inst), first=first,
                                frets=max(5, max(frets) - first + 1))
        else:
            notes = sc.notes(60)[:-1] + [n + 12 for n in sc.notes(60)]
            keys = {n: (self.w.note_written(n, sc.minor), None, "root" if n % 12 in tones else "note")
                    for n in notes}
            parts = S.keyboard(keys)
        parts += S.text_lines([self.w.scale_heading(sc)], y=880, size=52)
        self.on_screen(S.page(parts, title, chord_label(chord, self.w), status, "listen" if yours else ""))

    def _show_along(self, bar, chord: BandChord, next_chord):
        if not self.on_screen or not self.song:
            return
        song = self.song
        title = f"{song.title} · {bar // max(1, len(song.chords)) + 1}/{ROUNDS_ALONG}"
        t = Chord(chord.root, chord.quality)
        if song.mode == "chords":
            ex = ChordExercise(self.inst, self.w, t)
            nxt = chord_label(next_chord, self.w)
            self.on_screen(ex.view(f"→ {nxt}", "", title))
            return
        if song.mode == "line":
            root = I.BASS.tuning[0] + (chord.root - I.BASS.tuning[0]) % 12
            s, f, g = I.fret_notes([root], I.BASS)[0]
            parts = S.fretboard([(s, f, str(g) if g else self.w.note_written(root), "root")],
                                self.w.string_letters(self.inst), first=0, frets=6)
            self.on_screen(S.page(parts, title, chord_label(chord, self.w), f"→ {chord_label(next_chord, self.w)}"))
            return
        b = bar % song.mel.bars
        notes = [(beat - 4 * b, p + song.shift, d) for beat, p, d in song.mel.notes if 4 * b <= beat < 4 * b + 4]
        labels = [self.w.note_written(p, song.key.minor) for _, p, _ in notes]
        if self.inst.fretted:
            places = I.melody_places([p for _, p, _ in notes], self.inst) if notes else []
            dots = [(s, f, str(g) if g else labels[i], "note") for i, (s, f, g) in enumerate(places)]
            parts = S.fretboard(dots, self.w.string_letters(self.inst), first=0, frets=6)
        else:
            keys = {p: (labels[i], None, "note") for i, (_, p, _) in enumerate(notes)}
            parts = S.keyboard(keys, low=min([p for _, p, _ in notes] or [60]) - 2)
        parts += S.note_row(labels)
        self.on_screen(S.page(parts, title, chord_label(chord, self.w)))


def chord_label(chord: BandChord, words) -> str:
    from .theory import chord_symbol
    return chord_symbol(Chord(chord.root, chord.quality), words.lang)


def judge_turn(played: list[int], scale: Scale, chords: list) -> dict:
    """How a turn of improvising went: how many notes, how many in the scale,
    whether the last one was a note of the chord under it."""
    pcs = set(scale.pcs)
    inside = sum(1 for n in played if n % 12 in pcs)
    last_chord = chords[-1] if chords else None
    landed = bool(played and last_chord and played[-1] % 12 in last_chord.tones())
    return {"count": len(played), "inside": inside, "share": inside / len(played) if played else 0.0,
            "landed": landed, "root": scale.tonic}


def turn_words(turn: dict, words, scale: Scale) -> tuple[str, dict]:
    """A word from the teacher after your turn: (dialog, data)."""
    root = words.spoken(scale.spelled[0])
    if turn["count"] == 0:
        return "jam_quiet", {}
    if turn["share"] < 0.7:
        return "jam_outside", {"inside": turn["inside"], "count": turn["count"]}
    if turn["count"] < 3:
        return "jam_more", {}
    if not turn["landed"]:
        return "jam_land", {"root": root}
    return "jam_good", {"count": turn["count"]}

