import pytest

from ovos_skill_music_teacher.words import Words
from conftest import ROOT


def w(lang="en-US"):
    return Words(ROOT / "locale", lang)


@pytest.mark.parametrize("text,id_", [
    ("a minor", "A:min"), ("the a minor chord", "A:min"), ("a g chord", "G:maj"), ("g7", "G:7"),
    ("g seven", "G:7"), ("c major seven", "C:maj7"), ("am", "A:min"), ("f sharp minor", "F#:min"),
    ("b flat", "Bb:maj"), ("d sus four", "D:sus4"), ("e", "E:maj"), ("f#m7", "F#:m7"), ("the chord b minor", "B:min"),
])
def test_chords_en(text, id_):
    assert w().chord(text).id == id_


@pytest.mark.parametrize("text,tonic,kind", [
    ("c major", 0, "major"), ("the a minor", 9, "minor"), ("a minor pentatonic", 9, "minor_pentatonic"),
    ("e blues", 4, "blues"), ("g", 7, "major"), ("d dorian", 2, "dorian"), ("a pentatonic", 9, "major_pentatonic"),
    ("b flat major", 10, "major"), ("a harmonic minor", 9, "harmonic_minor"),
])
def test_scales_en(text, tonic, kind):
    s = w().scale(text)
    assert (s.tonic, s.kind) == (tonic, kind)


def test_instruments():
    assert w().instrument("teach me the c major scale on piano") == "piano"
    assert w().instrument("on my bass guitar") == "bass"
    assert w().instrument("how do i play g on the guitar") == "guitar"
    assert w().instrument("teach me something") is None


def test_saying():
    from ovos_skill_music_teacher import instruments as I
    from ovos_skill_music_teacher.theory import Scale, parse_chord
    e = w()
    assert e.scale_name(Scale(10)) == "B flat major"
    assert e.chord_name(parse_chord("F#m7")) == "F sharp minor seven"
    assert e.join(["a", "b", "c"]) == "a, b and c"
    assert e.place(I.GUITAR, 4, 1) == "the B string, fret 1"
    assert e.place(I.GUITAR, 0, 0) == "the open low E string"
    text = e.guitar_fingering(I.guitar_chord(parse_chord("C")))
    assert text.startswith("ring finger on the A string, fret 3") and "Don't play the low E string" in text
    assert "across all the strings at fret 1" in e.guitar_fingering(I.guitar_chord(parse_chord("F")))
    assert e.string_letters(I.GUITAR) == ["E", "A", "D", "G", "B", "e"]
