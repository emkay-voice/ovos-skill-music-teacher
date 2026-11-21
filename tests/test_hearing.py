import pytest

from ovos_skill_music_teacher import hearing as H
from ovos_skill_music_teacher import instruments as I
from ovos_skill_music_teacher.theory import Chord, Scale, parse_chord
from sounds import piano, pluck, seq, strum


def heard(x_sr, low=40):
    return [n for _, _, n in H.notes(*x_sr, low=low)]


@pytest.mark.parametrize("kind", [piano, pluck])
def test_a_scale_is_heard_note_by_note(kind):
    for tonic in (0, 7, 9):
        asked = Scale(tonic).notes(48 if kind is pluck else 60)
        assert heard(seq(asked, kind)) == asked


def test_the_bass_low_e_is_heard():
    asked = Scale(4).notes(28)
    assert heard(seq(asked, pluck), low=28) == asked


def test_compare_names_the_first_mistake():
    asked = Scale(0).notes(60)
    assert H.compare(asked, asked).ok
    played = list(asked)
    played[3] = 66                                       # F sharp for F
    v = H.compare(asked, played)
    assert not v.ok and v.mistake == ("wrong", 3, 65, 66) and v.marks[3] is False and v.right == 7
    v = H.compare(asked, asked[:4] + asked[5:])
    assert v.mistake == ("missing", 4, 67, None)
    v = H.compare(asked, asked[:2] + [61] + asked[2:])
    assert v.mistake[0] == "extra" and v.mistake[3] == 61
    assert H.compare(asked, []).mistake == ("nothing",)


def test_noise_before_and_after_is_forgiven():
    asked = [60, 62, 64]
    assert H.compare(asked, [50, 60, 62, 64, 71]).ok


def test_octaves():
    asked = [60, 62, 64]
    assert H.compare(asked, [72, 74, 76], exact_octave=True).ok          # all an octave up: fine
    assert not H.compare(asked, [60, 74, 64], exact_octave=True).ok
    assert H.compare(asked, [60, 74, 64]).ok                              # a microphone can't be that sure


def test_every_guitar_chord_strummed_is_right():
    for q in ("maj", "min", "7", "m7", "maj7", "sus2", "sus4"):
        for root in range(12):
            ch = Chord(root, q)
            shape = I.guitar_chord(ch)
            pcs = sorted({n % 12 for n in shape.notes()})
            v = H.judge_chord(H.chroma(*strum(shape.notes())), pcs)
            assert v.ok, (ch.id, v)


def test_piano_chords_are_right():
    for q in ("maj", "min", "7", "m7"):
        for root in range(12):
            ch = Chord(root, q)
            v = H.judge_chord(H.chroma(*strum(ch.notes(55), kind=piano, spread=0.0)), ch.pcs)
            assert v.ok, (ch.id, v)


@pytest.mark.parametrize("asked,played,missing", [("Am", "A", 0), ("A", "Am", 1), ("Em", "E", 7), ("E", "Em", 8),
                                                  ("D", "Dm", 6), ("C", "Am", 7)])
def test_the_wrong_chord_says_which_note_is_missing(asked, played, missing):
    a = parse_chord(asked)
    v = H.judge_chord(H.chroma(*strum(I.guitar_chord(parse_chord(played)).notes())), a.pcs)
    assert not v.ok and missing in v.missing


def test_a_string_not_pressed_is_found():
    c = I.guitar_chord(parse_chord("C"))
    notes = c.notes()
    notes[3] = 59                                        # the B string open, not fretted: B instead of C
    v = H.judge_chord(H.chroma(*strum(notes)), parse_chord("C").pcs)
    assert not v.ok and v.foreign == [11]


def test_silence():
    import numpy as np
    v = H.judge_chord(H.chroma(np.zeros(16000), 16000), [0, 4, 7])
    assert v.nothing and not v.ok


@pytest.mark.parametrize("string,cents", [(0, -20), (1, 15), (3, -8), (5, 3), (2, 35)])
def test_tuner_guitar(string, cents):
    x = pluck(I.GUITAR.tuning[string], dur=2.5, cents=cents)
    t = H.tune(H.pitch(x, 16000), I.GUITAR.tuning)
    assert t.string == string and abs(t.cents - cents) < 6


@pytest.mark.parametrize("string", range(4))
def test_tuner_bass(string):
    x = pluck(I.BASS.tuning[string], dur=3, cents=-12)
    t = H.tune(H.pitch(x, 16000, low=28), I.BASS.tuning)
    assert t.string == string and abs(t.cents + 12) < 6


def test_tuner_asked_string_an_octave_off_still_names_it():
    x = pluck(I.GUITAR.tuning[0] + 12, dur=2.5, cents=10)
    t = H.tune(H.pitch(x, 16000), I.GUITAR.tuning, string=0)
    assert t.string == 0 and abs(t.cents - 10) < 6


def test_keyboard():
    keys = [(0.0, "on", 60), (0.1, "on", 64), (0.1, "on", 67), (1.0, "off", 60), (1.0, "off", 64), (1.0, "off", 67)]
    assert H.chord_keys(keys) == [60, 64, 67]
    assert H.judge_keys([60, 64, 67], [0, 4, 7]).ok
    v = H.judge_keys([60, 63, 67], [0, 4, 7])
    assert v.missing == [4] and v.foreign == [3]
    assert [n for *_, n in H.notes_from_keys(keys)] == [60, 64, 67]
