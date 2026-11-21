"""Instruments for the tests: a piano-like tone and plucked strings, so what the teacher hears is tested on sound, not data."""
import numpy as np

SR = 16000


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def piano(m, dur=0.6, sr=SR, cents=0.0):
    t = np.arange(int(dur * sr)) / sr
    f = hz(m) * 2 ** (cents / 1200)
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (2 + k)) for k, a in
            enumerate((1.0, 0.5, 0.3, 0.2, 0.12, 0.08), start=1))
    return x * np.minimum(1, t / 0.005)


def pluck(m, dur=1.2, sr=SR, cents=0.0, seed=0):
    """A plucked string: harmonics as a pick a fifth of the way along
    excites them, the high ones dying first, a little out of tune with each
    other (a real string's stiffness)."""
    t = np.arange(int(dur * sr)) / sr
    f = hz(m) * 2 ** (cents / 1200)
    x = np.zeros_like(t)
    for k in range(1, 12):
        fk = f * k * (1 + 0.0001 * k * k)
        if fk > sr / 2 - 200:
            break
        a = abs(np.sin(np.pi * k * 0.2)) / k
        x += a * np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.2 + 0.9 * k))
    rng = np.random.default_rng(seed + m)
    x += 0.3 * rng.standard_normal(len(t)) * np.exp(-t * 60)       # the pick
    return x * np.minimum(1, t / 0.002)


def seq(notes, kind=piano, gap=0.08, sr=SR, noise=0.005):
    parts = [np.zeros(int(0.3 * sr))]
    for m in notes:
        parts += [kind(m), np.zeros(int(gap * sr))]
    x = np.concatenate(parts)
    return x + noise * np.random.default_rng(3).standard_normal(len(x)), sr


def strum(notes, kind=pluck, dur=2.0, sr=SR, spread=0.02, noise=0.005):
    n = int(dur * sr) + int(spread * sr * len(notes))
    x = np.zeros(n + int(0.3 * sr))
    for i, m in enumerate(notes):
        s = int(0.3 * sr + i * spread * sr)
        tone = kind(m, dur=dur) if kind is pluck else kind(m, dur)
        x[s:s + len(tone)] += tone
    return x + noise * np.random.default_rng(4).standard_normal(len(x)), sr
