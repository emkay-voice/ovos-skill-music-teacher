import time
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

import ovos_skill_music_teacher as sk
from ovos_skill_music_teacher import instruments as I
from ovos_skill_music_teacher.listen import Heard
from ovos_skill_music_teacher.theory import Scale, parse_chord
from sounds import piano, pluck, seq, strum


class FakeEar:
    """Plays what the test says the student played, one go at a time."""

    def __init__(self, goes):
        self.goes = goes                    # shared: a new ear goes on where the last stopped
        self.cancelled = MagicMock()
        self.cancelled.is_set.return_value = False

    def hear(self, **kw):
        return self.goes.pop(0) if self.goes else Heard()


@pytest.fixture
def skill(monkeypatch, tmp_path):
    monkeypatch.setattr(sk.OVOSSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.ConversationalSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.MusicTeacherSkill, "activate", lambda self, *a, **k: None, raising=False)
    s = sk.MusicTeacherSkill()
    s.skill_id = "ovos-skill-music-teacher.test"
    monkeypatch.setattr(sk.MusicTeacherSkill, "lang", "en-US", raising=False)
    bus = MagicMock()
    bus.band = {"engine": "builtin", "latency": 0.01}
    bus.wait_for_response.side_effect = lambda msg, reply, timeout=None: Message(reply, bus.band) if bus.band else None
    monkeypatch.setattr(sk.MusicTeacherSkill, "bus", bus, raising=False)
    monkeypatch.setattr(sk.MusicTeacherSkill, "gui", MagicMock(), raising=False)
    monkeypatch.setattr(sk.MusicTeacherSkill, "log", MagicMock(), raising=False)
    s.speak_dialog = MagicMock()
    s.file_system = MagicMock(path=str(tmp_path))
    s.goes = []
    monkeypatch.setattr(sk, "Ear", lambda bus: FakeEar(s.goes))
    # the examples take no time here
    monkeypatch.setattr(sk.MusicTeacherSkill, "_play_example",
                        lambda self, ex, tempo=None: self._send("ovos.midi.events", {"events": ex.example()}))
    yield s
    s.stop()


def said(skill):
    return [c[0][0] for c in skill.speak_dialog.call_args_list]


def data_of(skill, name):
    return [c[0][1] for c in skill.speak_dialog.call_args_list if c[0][0] == name and len(c[0]) > 1]


def sent(skill, t):
    return [c[0][0].data for c in skill.bus.emit.call_args_list if c[0][0].msg_type == t]


def done(skill, timeout=10):
    t0 = time.time()
    while skill.worker and skill.worker.is_alive() and time.time() - t0 < timeout:
        time.sleep(0.02)


def audio(notes, kind=piano):
    return Heard(audio=seq(notes, kind))


def teach(skill, utterance):
    skill.handle_teach(MagicMock(data={"utterance": utterance, "query": utterance}))
    done(skill)


def test_a_scale_played_right(skill):
    skill.goes.append(audio(Scale(0).notes(60)))
    teach(skill, "teach me the c major scale on piano")
    assert said(skill)[:3] == ["scale_piano", "your_turn", "right"]
    assert data_of(skill, "scale_piano")[0]["notes"] == "C, D, E, F, G, A and B"
    assert sent(skill, "ovos.midi.events")
    assert skill.gui.show_page.called


def test_a_wrong_note_is_named_then_right(skill):
    notes = Scale(7).notes(60)
    wrong = list(notes)
    wrong[6] = 65                                        # F for F sharp
    skill.goes += [audio(wrong), audio(notes)]
    teach(skill, "teach me the g major scale on piano")
    assert "wrong_note" in said(skill) and said(skill)[-1] == "right"
    d = data_of(skill, "wrong_note")[0]
    assert d == {"n": 7, "asked": "F sharp", "played": "F"}


def test_after_some_tries_it_shows_again_then_asks(skill):
    skill.goes += [audio([60, 61])] * 5
    teach(skill, "teach me the c major scale on piano")
    assert "show_again" in said(skill) and said(skill)[-1] == "pause" and skill.waiting
    # "once more": it listens again
    skill.goes.append(audio(Scale(0).notes(60)))
    assert skill.converse(Message("", {"utterances": ["once more"]}))
    done(skill)
    assert said(skill)[-1] == "right"


def test_nothing_heard_waits_for_ready(skill):
    skill.goes.append(Heard())
    teach(skill, "teach me the c major scale on piano")
    assert said(skill)[-1] == "nothing" and skill.waiting


def test_a_guitar_chord(skill):
    shape = I.guitar_chord(parse_chord("Am"))
    skill.goes.append(Heard(audio=strum(shape.notes())))
    teach(skill, "how do i play a minor on guitar")
    assert said(skill)[:3] == ["chord_guitar", "your_turn_chord", "right"]
    assert "middle finger on the D string, fret 2" in data_of(skill, "chord_guitar")[0]["fingers"]


def test_a_guitar_chord_with_a_string_that_doesnt_ring(skill):
    shape = I.guitar_chord(parse_chord("C"))
    notes = [n for n in shape.notes() if n != 60]       # the B string muffled: no high C... the low C remains
    notes = [n for n in notes if n != 48]               # ... and no C at all
    skill.goes += [Heard(audio=strum(notes)), Heard(audio=strum(shape.notes()))]
    teach(skill, "how do i play the c chord on guitar")
    assert "chord_missing_string" in said(skill)
    assert data_of(skill, "chord_missing_string")[0]["notes"] == "C"


def test_a_midi_keyboard_counts_exactly(skill):
    keys = []
    for i, n in enumerate(Scale(2).notes(62)):
        keys += [(i * 0.5, "on", n), (i * 0.5 + 0.4, "off", n)]
    skill.goes.append(Heard(keys=keys))
    teach(skill, "teach me the d major scale on piano")
    assert said(skill)[-1] == "right"


def test_asks_for_the_instrument_then_remembers_it(skill):
    skill.handle_teach(MagicMock(data={"utterance": "teach me the c major scale", "query": "the c major scale"}))
    assert said(skill)[-1] == "which_instrument"
    skill.goes.append(audio(Scale(0).notes(48), pluck))
    assert skill.converse(Message("", {"utterances": ["guitar"]}))
    done(skill)
    assert "scale_fretted" in said(skill) and said(skill)[-1] == "right"
    assert skill.progress()["instrument"] == "guitar"


def test_the_course_moves_on(skill):
    p = skill.progress()
    p["instrument"] = "piano"
    skill.save_progress(p)
    skill.goes.append(audio(Scale(0).notes(60)))
    skill.handle_lesson(MagicMock(data={"utterance": "music lesson"}))
    done(skill)
    assert said(skill)[-1] == "step_done" and skill.progress()["done_piano"] == 1
    # next: C, F and G
    for c in ("C", "F", "G"):
        skill.goes.append(Heard(audio=strum(parse_chord(c).notes(55), kind=piano, spread=0.0)))
    skill.handle_lesson(MagicMock(data={"utterance": "next lesson"}))
    done(skill)
    assert said(skill).count("chord_piano") == 3 and said(skill)[-1] == "step_done"
    assert skill.progress()["done_piano"] == 2


def test_a_song_a_piece_at_a_time_then_with_the_band(skill):
    from ovos_skill_music_teacher.songs import Song
    song = Song("saints", I.PIANO, skill.words())
    for piece in song.pieces():
        skill.goes.append(audio(piece.asked()))
    teach(skill, "teach me when the saints go marching in on piano")
    assert said(skill)[0] == "song_intro" and said(skill).count("right") == len(song.pieces())
    assert said(skill)[-1] == "song_learnt"
    assert skill.converse(Message("", {"utterances": ["yes"]}))
    time.sleep(0.5)
    assert "song_together" in said(skill) and skill.band is not None
    skill.band.jam.change(tempo=220)
    t0 = time.time()
    while skill.band and time.time() - t0 < 40:
        time.sleep(0.1)
    assert "song_end" in said(skill)


def test_guitar_songs_are_chords_in_a_good_key(skill):
    from ovos_skill_music_teacher.songs import Song
    song = Song("saints", I.GUITAR, skill.words(), key=2)
    assert song.mode == "chords" and [c.id for c in song.teacher_chords()] == ["D:maj", "A:7"]
    assert Song("saints", I.BASS, skill.words()).mode == "line"
    assert Song("saints", I.GUITAR, skill.words(), melody=True).mode == "melody"


def test_jam_lesson(skill, monkeypatch):
    teach(skill, "teach me to jam a blues in a on guitar")
    assert said(skill)[0] == "jam_intro"
    d = data_of(skill, "jam_intro")[0]
    assert d["style"] == "blues" and d["scale"] == "A blues"
    band = skill.band
    assert band and band.running
    time.sleep(0.3)
    assert sent(skill, "ovos.midi.events")
    assert skill.converse(Message("", {"utterances": ["faster"]}))
    assert skill.converse(Message("", {"utterances": ["enough"]}))
    assert skill.band is None


def test_jam_feedback():
    from ovos_skill_music_teacher.jamlesson import judge_turn, turn_words
    from ovos_skill_jamband.music import Chord as BC
    sc = Scale(9, "minor_pentatonic")
    chords = [BC(9, "7")] * 4
    t = judge_turn([69, 72, 74, 76, 69], sc, chords)
    assert t["share"] == 1.0 and t["landed"]
    w = sk.Words(sk.SKILL_ROOT / "locale", "en-US")
    assert turn_words(t, w, sc)[0] == "jam_good"
    assert turn_words(judge_turn([70, 71, 73, 69], sc, chords), w, sc)[0] == "jam_outside"
    assert turn_words(judge_turn([69, 72, 74, 75], sc, chords), w, sc)[0] == "jam_land"
    assert turn_words(judge_turn([], sc, chords), w, sc)[0] == "jam_quiet"


def test_tuner(skill):
    goes = []
    for s, o in enumerate(I.GUITAR.tuning):
        if s == 1:
            goes.append(Heard(audio=(pluck(o, dur=2.5, cents=-25), 16000)))
        goes.append(Heard(audio=(pluck(o, dur=2.5, cents=2), 16000)))
    skill.goes += goes
    skill.handle_tune(MagicMock(data={"utterance": "tune my guitar", "query": "guitar"}))
    done(skill, 20)
    assert said(skill).count("tune_ok") == 6 and "tune_low" in said(skill) and said(skill)[-1] == "tune_done"


def test_no_band_for_a_jam(skill):
    skill.bus.band = None
    teach(skill, "teach me to jam on piano")
    assert said(skill)[-1] == "no_midi"


def test_stop(skill):
    skill.goes += [Heard()]
    teach(skill, "teach me the c major scale on piano")
    assert skill.waiting
    assert skill.stop()
    assert not skill.busy


def test_not_busy_converse_takes_nothing(skill):
    assert not skill.can_converse(Message("", {"utterances": ["next"]}))
    assert not skill.converse(Message("", {"utterances": ["what's the weather"]}))


def test_list(skill):
    skill.handle_list(MagicMock(data={}))
    assert said(skill) == ["list"] and "Ode to Joy" in data_of(skill, "list")[0]["songs"]
