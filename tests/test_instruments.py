from ovos_skill_music_teacher import instruments as I
from ovos_skill_music_teacher.theory import CHORDS, Chord, Scale


def test_every_guitar_chord_has_its_notes():
    for q in CHORDS:
        for root in range(12):
            ch = Chord(root, q)
            shape = I.guitar_chord(ch)
            pcs = {n % 12 for n in shape.notes()}
            assert pcs <= set(ch.pcs), (ch.id, shape)
            missing = set(ch.pcs) - pcs
            assert not missing or missing == {(root + 7) % 12}, (ch.id, shape)     # a fifth left out at most
            assert (shape.notes()[0] % 12) == root or q in ("sus2", "sus4", "6"), ch.id   # the root in the bass
            frets = [f for f, _ in shape.strings if f]
            assert not frets or max(frets) - min(frets) <= 4


def test_open_chords_are_the_ones_on_every_chart():
    assert I.guitar_chord(Chord(0)).strings == ((None, 0), (3, 3), (2, 2), (0, 0), (1, 1), (0, 0))
    f = I.guitar_chord(Chord(5))
    assert f.barre == 1 and f.notes()[0] == 41
    bm = I.guitar_chord(Chord(11, "min"))
    assert bm.barre == 2 and bm.strings[0][0] is None


def test_scales_on_guitar_and_bass_play_the_right_notes():
    for inst in (I.GUITAR, I.BASS):
        for tonic in range(12):
            for kind in ("major", "minor", "minor_pentatonic", "blues"):
                sc = Scale(tonic, kind)
                for note, (s, fret, finger) in I.fretted_scale(sc, inst):
                    assert inst.tuning[s] + fret == note
                    assert 0 <= finger <= 4 and (fret == 0) == (finger == 0)
                frets = [f for _, (_, f, _) in I.fretted_scale(sc, inst) if f]
                assert max(frets) - min(frets) <= 5


def test_open_position_c_major_on_guitar():
    places = [p for _, p in I.fretted_scale(Scale(0), I.GUITAR)]
    assert places == [(1, 3, 3), (2, 0, 0), (2, 2, 2), (2, 3, 3), (3, 0, 0), (3, 2, 2), (4, 0, 0), (4, 1, 1)]


def test_scale_box_for_jamming():
    box = I.scale_box(Scale(9, "minor_pentatonic"), I.GUITAR)
    assert [(s, f) for s, f, _, _ in box] == [(0, 5), (0, 8), (1, 5), (1, 7), (2, 5), (2, 7), (3, 5), (3, 7),
                                              (4, 5), (4, 8), (5, 5), (5, 8)]
    assert len({p for *_, p in box}) == len(box)


def test_piano_fingering():
    places = I.piano_scale(Scale(0))
    assert [f for _, f in places] == [1, 2, 3, 1, 2, 3, 4, 5]
    assert [f for _, f in I.piano_scale(Scale(5))] == [1, 2, 3, 4, 1, 2, 3, 4]
    assert [f for _, f in I.piano_chord(Chord(0))] == [1, 3, 5]
    for tonic in range(12):
        assert len(I.piano_scale(Scale(tonic, "minor"))) == 8


def test_octave_for():
    tune = [60, 62, 64, 65, 67]
    assert I.octave_for(tune, I.PIANO) == 0
    assert I.octave_for(tune, I.GUITAR) in (-12, 0)
    assert min(tune) + I.octave_for(tune, I.BASS) >= I.BASS.tuning[0]
