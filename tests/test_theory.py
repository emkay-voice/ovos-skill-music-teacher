import pytest

from ovos_skill_music_teacher.theory import (Chord, Scale, chord_symbol, parse_chord, parse_note, pc_of,
                                             spoken, written)


def names(scale, lang="en"):
    return [written(sp, lang) for sp in scale.spelled]


def test_scales_use_every_letter_once():
    assert names(Scale(5)) == ["F", "G", "A", "B♭", "C", "D", "E"]
    assert names(Scale(6)) == ["F♯", "G♯", "A♯", "B", "C♯", "D♯", "E♯"]
    assert names(Scale(1)) == ["D♭", "E♭", "F", "G♭", "A♭", "B♭", "C"]
    assert names(Scale(4, "minor")) == ["E", "F♯", "G", "A", "B", "C", "D"]
    assert names(Scale(9, "harmonic_minor")) == ["A", "B", "C", "D", "E", "F", "G♯"]
    for tonic in range(12):
        for kind in ("major", "minor", "dorian", "mixolydian", "harmonic_minor"):
            letters = [sp[0] for sp in Scale(tonic, kind).spelled]
            assert sorted(letters) == list(range(7)), (tonic, kind)


def test_pentatonic_and_blues():
    assert names(Scale(9, "minor_pentatonic")) == ["A", "C", "D", "E", "G"]
    assert names(Scale(9, "blues")) == ["A", "C", "D", "E♭", "E", "G"]
    assert names(Scale(7, "major_pentatonic")) == ["G", "A", "B", "D", "E"]


def test_notes_and_pitch_classes_agree():
    for tonic in range(12):
        for kind in ("major", "minor", "blues", "minor_pentatonic"):
            s = Scale(tonic, kind)
            assert [n % 12 for n in s.notes(60)[:-1]] == s.pcs == [pc_of(sp) for sp in s.spelled]


@pytest.mark.parametrize("text,id_", [("Am", "A:min"), ("F#7", "F#:7"), ("Bbmaj7", "Bb:maj7"), ("Dsus4", "D:sus4"),
                                      ("C", "C:maj"), ("Ebm7", "Eb:m7"), ("Bdim", "B:dim")])
def test_parse_chord(text, id_):
    assert parse_chord(text).id == id_


def test_chord_spelling():
    assert [written(sp, "en") for sp in parse_chord("F#m7").spelled] == ["F♯", "A", "C♯", "E"]
    assert [written(sp, "en") for sp in parse_chord("Bb").spelled] == ["B♭", "D", "F"]
    assert [written(sp, "en") for sp in parse_chord("E7").spelled] == ["E", "G♯", "B", "D"]


def test_names_per_language():
    b, bb, fs = (6, 0), (6, -1), (3, 1)
    assert [written(x, "da") for x in (b, bb, fs)] == ["H", "B", "F♯"]
    assert [spoken(x, "da") for x in (b, bb, fs, (2, -1), (5, -1))] == ["h", "b", "fis", "es", "as"]
    assert [spoken(x, "de") for x in (b, bb, fs)] == ["H", "B", "Fis"]
    assert [spoken(x, "nl") for x in (b, bb, fs)] == ["B", "Bes", "Fis"]
    assert [written(x, "es") for x in (b, bb, fs)] == ["Si", "Si♭", "Fa♯"]
    assert spoken(bb, "es") == "si bemol" and spoken(fs, "fr") == "fa dièse" and spoken((0, 0), "pt") == "dó"
    assert spoken(bb, "en") == "B flat"
    assert chord_symbol(parse_chord("Bm"), "da") == "Hm" and chord_symbol(parse_chord("Am"), "es") == "Lam"
    assert chord_symbol(Chord(10, "maj"), "de") == "B"


def test_parse_note():
    assert parse_note("Bb") == 10 and parse_note("F#") == 6 and parse_note("c") == 0
