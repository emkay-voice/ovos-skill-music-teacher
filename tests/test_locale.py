import json
import re
from unittest.mock import MagicMock

import pytest

import ovos_skill_music_teacher as sk
from ovos_skill_music_teacher import instruments as I
from ovos_skill_music_teacher.theory import parse_chord
from ovos_skill_music_teacher.words import Words
from conftest import ROOT

LOCALES = sorted(p.name for p in (ROOT / "locale").iterdir() if p.is_dir())
EN = ROOT / "locale" / "en-US"


def fields(text):
    return set(re.findall(r"{(\w+)}", text))


def test_twelve_languages():
    assert len(LOCALES) == 12


@pytest.mark.parametrize("lang", LOCALES)
def test_every_locale_has_every_file(lang):
    mine = sorted(p.name for p in (ROOT / "locale" / lang).iterdir())
    assert mine == sorted(p.name for p in EN.iterdir())


@pytest.mark.parametrize("lang", LOCALES)
def test_dialogs_use_the_same_fields(lang):
    for f in EN.glob("*.dialog"):
        want = set().union(*(fields(line) for line in f.read_text().splitlines() if line))
        for line in (ROOT / "locale" / lang / f.name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert fields(line) <= want, (lang, f.name, line)


@pytest.mark.parametrize("lang", LOCALES)
def test_intents_have_their_slot(lang):
    for name in ("teach", "tune"):
        lines = (ROOT / "locale" / lang / f"{name}.intent").read_text(encoding="utf-8").splitlines()
        assert any("{query}" in line for line in lines)


@pytest.mark.parametrize("lang", LOCALES)
def test_words_json(lang):
    en = json.loads((EN / "words.json").read_text())
    mine = json.loads((ROOT / "locale" / lang / "words.json").read_text(encoding="utf-8"))
    assert set(mine) == set(en)
    for group in ("scale", "scale_heading", "chord"):
        assert set(mine[group]) == set(en[group])
        assert all("{note}" in v for v in mine[group].values())
    assert len(mine["strings"]["guitar"]) == 6 and len(mine["strings"]["bass"]) == 4 and len(mine["fingers"]) == 5
    w = Words(ROOT / "locale", lang)
    assert w.guitar_fingering(I.guitar_chord(parse_chord("F")))      # every template formats
    assert w.place(I.GUITAR, 0, 0) and w.place(I.BASS, 2, 3)


@pytest.fixture
def skill(monkeypatch, tmp_path):
    monkeypatch.setattr(sk.OVOSSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.ConversationalSkill, "__init__", lambda self, *a, **k: None)
    s = sk.MusicTeacherSkill()
    s.file_system = MagicMock(path=str(tmp_path))
    return s


EXPECT = ["scale", "chord", "song", "jam", "tune", None, None, None]


@pytest.mark.parametrize("lang", LOCALES)
def test_the_examples_do_what_they_say(skill, monkeypatch, lang):
    monkeypatch.setattr(sk.MusicTeacherSkill, "lang", lang, raising=False)
    examples = json.loads((ROOT / "locale" / lang / "skill.json").read_text(encoding="utf-8"))["examples"]
    plans = [skill.plan(e, e) for e in examples[:5]]
    assert [p[0] for p in plans] == EXPECT[:5], (lang, plans)
    assert plans[0][1] == "piano" and plans[0][2].tonic == 0 and plans[0][2].kind == "major"
    assert plans[1][1] == "guitar" and plans[1][2].id == "A:min", (lang, plans[1])
    assert plans[2][1] == "piano" and plans[2][2] == "ode_to_joy"
    assert plans[3][1] == "guitar"
    assert plans[4][1] == "bass"


SPOT = {
    "da-DK": [("h-mol", "B:min"), ("fis syv", "F#:7"), ("b-dur", "Bb:maj")],
    "de-DE": [("h moll", "B:min"), ("es dur", "Eb:maj"), ("g sieben", "G:7")],
    "es-ES": [("la menor", "A:min"), ("el acorde de la", "A:maj"), ("sol siete", "G:7"), ("si bemol mayor", "Bb:maj")],
    "fr-FR": [("la mineur", "A:min"), ("ré majeur", "D:maj"), ("sol sept", "G:7")],
    "it-IT": [("la minore", "A:min"), ("mi minore", "E:min"), ("re sette", "D:7")],
    "pt-BR": [("lá menor", "A:min"), ("ré maior", "D:maj")],
    "nl-NL": [("a klein", "A:min"), ("bes groot", "Bb:maj")],
    "ca-ES": [("la menor", "A:min"), ("re set", "D:7")],
    "gl-ES": [("la menor", "A:min"), ("mi maior", "E:maj")],
    "eu-ES": [("la minor", "A:min"), ("sol zazpi", "G:7")],
}


@pytest.mark.parametrize("lang,text,id_", [(lang, t, i) for lang, pairs in SPOT.items() for t, i in pairs])
def test_chords_in_every_language(lang, text, id_):
    assert Words(ROOT / "locale", lang).chord(text).id == id_
