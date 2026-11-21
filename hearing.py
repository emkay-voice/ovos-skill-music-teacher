"""What was played: notes, a chord, a string's pitch - and what was wrong.

From a recording (the microphone) or from a MIDI keyboard's notes:

  - notes(): the notes one after another, by their pitch (YIN, as
    ovos-skill-jamband follows a hummed melody - down to a bass's low E);
  - compare(): the notes played against the notes asked for, the first
    mistake by name (a wrong note, one left out, one too many);
  - chroma() and judge_chord(): how strong every pitch class sounds while a
    chord rings, and which of the chord's notes were missing (or which
    other note was there);
  - pitch(): one string's pitch, for the tuner - in cents from the nearest
    string of the instrument.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ovos_skill_jamband import melody as M


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def midi_of(f: float) -> float:
    return 69 + 12 * math.log2(f / 440.0)


# ------------------------------------------------------------------ notes
def notes(x, sr: int, low: int = 40) -> list[tuple]:
    """[(start s, end s, MIDI note)] heard one after another. `low`: the
    lowest note the instrument has (a bass needs a lower floor)."""
    fmin = max(30.0, hz(low - 2))
    times, f0, rms = M.pitch_track(x, sr, fmin=fmin, fmax=2100.0)
    raw = M.notes_from_track(times, f0, rms, min_note=0.07)
    out = []
    for s, e, p in raw:
        n = int(round(p))
        if out and out[-1][2] == n and s - out[-1][1] < 0.04:     # one note, cut by a wobble
            out[-1] = (out[-1][0], e, n)
        else:
            out.append((s, e, n))
    return out


def notes_from_keys(keys: list) -> list[tuple]:
    """A MIDI keyboard's [(time, "on"/"off", note)] as [(start, end, note)]."""
    out, held = [], {}
    for t, kind, n in keys:
        if kind == "on":
            held[n] = t
        elif n in held:
            out.append((held.pop(n), t, n))
    end = max((t for t, _, _ in keys), default=0.0)
    out += [(t, end, n) for n, t in held.items()]
    return sorted(out)


@dataclass
class Verdict:
    """How a run of notes went: `ok`, and the first `mistake`: ("wrong", i,
    asked, played) / ("missing", i, asked, None) / ("extra", i, None, played)
    / ("nothing",) - i is the place in the notes asked for. `right` is how
    many were right; `marks` a mark for each note asked for (True right,
    False wrong or missing)."""
    ok: bool
    right: int = 0
    mistake: tuple | None = None
    marks: list = field(default_factory=list)
    played: list = field(default_factory=list)


def compare(asked: list[int], played: list[int], exact_octave: bool = False) -> Verdict:
    """The notes played against the ones asked for. By pitch class unless
    `exact_octave` (a microphone can hear an octave wrong; a keyboard can't).
    A note or two of noise before the first or after the last is not held
    against you."""
    if not played:
        return Verdict(False, 0, ("nothing",), [False] * len(asked), [])
    key = (lambda n: n) if exact_octave else (lambda n: n % 12)
    a, p = [key(n) for n in asked], [key(n) for n in played]
    if exact_octave:                       # the whole run an octave off is fine
        shift = 12 * round((np.median(played) - np.median(asked)) / 12)
        p = [n - shift for n in p]
    n, m = len(a), len(p)
    # edit distance; leading and trailing extra notes are free
    INF = 10 ** 9
    d = [[INF] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        d[0][j] = 0
    for i in range(1, n + 1):
        d[i][0] = i
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (a[i - 1] != p[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)
    j = min(range(m + 1), key=lambda j: (d[n][j], -j))
    ops, i = [], n
    while i > 0:
        if j > 0 and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != p[j - 1]):
            ops.append(("same" if a[i - 1] == p[j - 1] else "wrong", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            ops.append(("missing", i - 1, None))
            i -= 1
        elif j > 0:
            ops.append(("extra", i, j - 1))
            j -= 1
        else:
            ops.append(("missing", i - 1, None))
            i -= 1
    ops.reverse()
    marks = [False] * n
    mistake = None
    for kind, i, j in ops:
        if kind == "same":
            marks[i] = True
        elif mistake is None:
            if kind == "wrong":
                mistake = ("wrong", i, asked[i], played[j])
            elif kind == "missing":
                mistake = ("missing", i, asked[i], None)
            else:
                mistake = ("extra", i, None, played[j])
    right = sum(marks)
    return Verdict(mistake is None and right == n, right, mistake, marks, list(played))


# ------------------------------------------------------------------ chords
def chroma(x, sr: int, fmin: float = 60.0, fmax: float = 2000.0) -> np.ndarray:
    """How strong each pitch class (C=0 ... B=11) sounds, 0-1, while the
    chord rings: the loud part of the recording, its spectral peaks put on
    their pitch class. A peak a twelfth or a seventeenth above a stronger
    one (the 3rd and 5th harmonics) counts less - a string's overtones are
    not notes you played."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if x.size < sr // 10 or not np.any(x):
        return np.zeros(12)
    n = 4096 if sr >= 16000 else 2048
    hop = n // 4
    win = np.hanning(n)
    frames = [x[i:i + n] * win for i in range(0, len(x) - n, hop)]
    if not frames:
        return np.zeros(12)
    rms = np.array([math.sqrt(float(np.mean(f * f))) for f in frames])
    loud = rms >= 0.35 * rms.max()
    idx = np.where(loud)[0]
    if len(idx) > 2:                         # skip the strum's attack
        idx = idx[1:]
    spec = np.mean([np.abs(np.fft.rfft(frames[i])) for i in idx], axis=0)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    band = (freqs >= fmin) & (freqs <= fmax)
    s = np.where(band, spec, 0.0)
    # peaks: local maxima well above the floor
    floor = np.median(s[band]) * 4 + 1e-12
    peaks = [(freqs[k], s[k]) for k in range(1, len(s) - 1)
             if s[k] > floor and s[k] >= s[k - 1] and s[k] >= s[k + 1]]
    peaks.sort(key=lambda p: -p[1])
    peaks = peaks[:40]
    out = np.zeros(12)
    strong = []
    for f, a in peaks:
        # parabolic: the peak's true frequency
        m = midi_of(f)
        weight = a
        for f2, a2 in strong:
            r = f / f2
            for h in (2, 3, 4, 5, 6):
                if abs(r - h) / h < 0.02 and a2 > a:
                    weight *= 0.35 if h in (3, 5, 6) else 0.6
                    break
        strong.append((f, a))
        if abs(m - round(m)) > 0.4:
            continue
        out[int(round(m)) % 12] += weight
    top = out.max()
    return out / top if top > 0 else out


@dataclass
class ChordVerdict:
    ok: bool
    missing: list = field(default_factory=list)     # pitch classes of the chord not heard
    foreign: list = field(default_factory=list)     # pitch classes heard that are not in it
    heard: list = field(default_factory=list)       # the chroma, 12 values
    nothing: bool = False


#: a chord note counts as heard at this share of the strongest pitch class
HEARD = 0.18
#: another pitch class this strong is a wrong note ...
FOREIGN = 0.4
#: ... unless it is a fifth or a major third above a chord note (an overtone) and no stronger than this
OVERTONE = 0.45


def judge_chord(c: np.ndarray, pcs: list[int], optional: list[int] = ()) -> ChordVerdict:
    """`pcs`: the chord's pitch classes; `optional`: those it may leave out
    (a four-note chord's fifth - many guitar shapes do)."""
    if not np.any(c):
        return ChordVerdict(False, list(pcs), [], list(c), nothing=True)
    missing = [pc for pc in pcs if c[pc] < HEARD and pc not in optional]
    # a foreign pitch class a harmonic of a chord note explains (a fifth or
    # a major third above it) is the instrument, not you
    explained = {(pc + 7) % 12 for pc in pcs} | {(pc + 4) % 12 for pc in pcs}
    foreign = [pc for pc in range(12) if pc not in pcs and c[pc] >= FOREIGN
               and not (pc in explained and c[pc] < OVERTONE)]
    return ChordVerdict(not missing and not foreign, missing, foreign, [round(float(v), 3) for v in c])


def judge_keys(held: list[int], pcs: list[int]) -> ChordVerdict:
    """A chord played on a MIDI keyboard: exactly which keys."""
    if not held:
        return ChordVerdict(False, list(pcs), [], [], nothing=True)
    got = {n % 12 for n in held}
    missing = [pc for pc in pcs if pc not in got]
    foreign = sorted(pc for pc in got if pc not in pcs)
    heard = [1.0 if pc in got else 0.0 for pc in range(12)]
    return ChordVerdict(not missing and not foreign, missing, foreign, heard)


def chord_keys(keys: list) -> list[int]:
    """The keys held down together the longest while a chord was played:
    the biggest set pressed at one time."""
    held, best = set(), set()
    for _, kind, n in keys:
        if kind == "on":
            held.add(n)
            if len(held) >= len(best):
                best = set(held)
        else:
            held.discard(n)
    return sorted(best)


# ------------------------------------------------------------------ the tuner
@dataclass
class Tuning:
    string: int              # which string (0: the lowest)
    target: int              # its MIDI note
    cents: float             # + sharp (too high), - flat
    freq: float


def pitch(x, sr: int, low: int = 28) -> float | None:
    """The steady pitch of one string, in Hz (the median over the sustained part)."""
    times, f0, rms = M.pitch_track(x, sr, fmin=max(28.0, hz(low - 3)), fmax=1400.0)
    if len(f0) == 0:
        return None
    voiced = (f0 > 0) & (rms > 0.15 * (rms.max() if len(rms) else 0))
    if voiced.sum() < 8:
        return None
    f = f0[voiced]
    # the attack is sharp, the end can lose the pitch: the middle
    f = f[len(f) // 6: max(len(f) // 6 + 4, len(f) * 5 // 6)]
    med = float(np.median(f))
    # octave mistakes: keep the values near the median
    near = f[np.abs(12 * np.log2(f / med)) < 0.7]
    return float(np.median(near)) if len(near) else med


def tune(freq: float, tuning: tuple, string: int | None = None) -> Tuning:
    """How far `freq` is from the string asked for (or the nearest string)."""
    m = midi_of(freq)
    if string is None:
        string = min(range(len(tuning)), key=lambda s: abs(m - tuning[s]))
    target = tuning[string]
    cents = 100 * (m - target)
    # a string tuned a whole octave off still names its string; say how far
    while cents > 600:
        cents -= 1200
    while cents < -600:
        cents += 1200
    return Tuning(string, target, round(cents, 1), freq)
