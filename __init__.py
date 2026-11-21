"""ovos-skill-music-teacher: piano, guitar and bass lessons - it shows you,
plays it for you, then listens to you play it.

  "teach me the C major scale on piano"   the keys and fingers on the screen,
                                          played for you; then "Now you" - and
                                          what was right, or the first mistake
  "how do I play A minor on guitar"       the chord chart, said finger by finger;
                                          strum it, and it tells you which string
                                          didn't ring
  "teach me Ode to Joy on piano"          a song, two bars at a time, then the
                                          whole song with the band
  "teach me to jam a blues in A on guitar"  the scale to jam with; the band plays
                                          four bars, you play four, and it says
                                          how it went
  "tune my guitar"                        string by string, with a needle
  "music lesson" / "next lesson"          the course for your instrument, step
                                          by step (remembered)

While a lesson is on: "again", "play it", "slower", "next", "enough".

It hears you through the microphone (OVOS' recording mode, as
ovos-skill-jamband hears a hummed melody) or exactly, through a MIDI
keyboard on ovos-phal-plugin-midi, which also plays the examples and the
band (ovos-skill-jamband's jam).

The pieces: theory.py (notes, scales, chords, spelled and named in every
language), instruments.py (where a note is played, with which finger),
hearing.py (notes, chords and pitch from sound), listen.py (the microphone
and the keyboard), exercises.py (a scale, a chord, a piece of a song),
songs.py (the songs), jamlesson.py (with the band), screen.py (the
pictures), words.py (what is said and asked), lessons/ (the courses).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ovos_bus_client.message import Message
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill

try:   # ovos-workshop 8: converse is ConversationalSkill's
    from ovos_workshop.skills.converse import ConversationalSkill
except ImportError:  # before it, every OVOSSkill could converse
    ConversationalSkill = OVOSSkill

from ovos_skill_jamband.music import Key
from ovos_skill_jamband.styles import STYLES
from ovos_skill_jamband.words import Words as BandWords

from . import hearing as H
from . import instruments as I
from . import screen as S
from . import songs as SG
from .exercises import ChordExercise, ScaleExercise
from .jamlesson import BandLesson, scale_for
from .listen import Ear
from .theory import Scale, parse_chord, parse_note
from .words import Words

SKILL_ROOT = Path(__file__).resolve().parent
BAND_LOCALE = Path(__import__("ovos_skill_jamband").__file__).resolve().parent / "locale"
MIDI_WAIT = 3.0
TRIES = 3                    # wrong this many times: it plays it again, slowly
GIVE_UP = 5                  # ... and after this many, asks whether to go on
TUNE_TRIES = 8               # a string
IN_TUNE = 7                  # cents either way
FAR = 30
JAM_TURNS = 6                # your turns in a jam lesson, then the ending
ANSWER_WAIT = 30.0


class MusicTeacherSkill(ConversationalSkill):

    def __init__(self, *args, **kwargs):
        self._words: dict = {}
        self._lock = threading.RLock()
        self.queue: list = []           # the exercises still to do
        self.current = None             # the exercise being done
        self.step: dict | None = None   # the course step being done (to count it done after)
        self.song = None                # a song being learnt
        self.band: BandLesson | None = None
        self.tuning = False
        self.waiting = False            # paused: a question asked, an answer expected
        self.tries = 0
        self.tempo = 84
        self.ear: Ear | None = None
        self.worker: threading.Thread | None = None
        self.stopped = threading.Event()
        self.asked_instrument: str | None = None     # "which instrument?" - what for
        self.midi_latency: float | None = None
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------ helpers
    def words(self) -> Words:
        if self.lang not in self._words:
            self._words[self.lang] = Words(SKILL_ROOT / "locale", self.lang)
        return self._words[self.lang]

    def band_words(self) -> BandWords:
        key = "band:" + self.lang
        if key not in self._words:
            self._words[key] = BandWords(BAND_LOCALE, self.lang)
        return self._words[key]

    @property
    def progress_file(self) -> Path:
        try:
            return Path(self.file_system.path) / "progress.json"
        except Exception:
            return Path.home() / ".local/share/ovos-skill-music-teacher/progress.json"

    def progress(self) -> dict:
        try:
            return json.loads(self.progress_file.read_text())
        except (OSError, ValueError):
            return {}

    def save_progress(self, data: dict):
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            self.progress_file.write_text(json.dumps(data))
        except OSError:
            pass

    def _midi(self) -> dict | None:
        r = self.bus.wait_for_response(Message("ovos.midi.status"), "ovos.midi.status.response", timeout=MIDI_WAIT)
        if r is None or r.data.get("engine") in (None, "none"):
            return None
        self.midi_latency = float(r.data.get("latency", 0.3))
        return r.data

    def _send(self, msg_type: str, data: dict):
        self.bus.emit(Message(msg_type, data, {"skill_id": self.skill_id}))

    def _show(self, image: str):
        self.gui["image"] = image
        self.gui["title"] = ""
        self.gui["caption"] = ""
        self.gui["fill"] = "PreserveAspectFit"
        self.gui["background_color"] = S.BG
        self.gui.show_page("SYSTEM_ImageFrame", override_idle=True)

    def _keep_active(self):
        activate = getattr(self, "activate", None) or getattr(self, "make_active", None)
        if activate:
            try:
                activate()
            except Exception:
                pass

    def _instrument(self, utterance: str) -> str | None:
        """The instrument said, else the last one used."""
        name = self.words().instrument(utterance)
        if name:
            p = self.progress()
            p["instrument"] = name
            self.save_progress(p)
            return name
        return self.progress().get("instrument")

    # ------------------------------------------------------------ intents
    @intent_handler("teach.intent")
    def handle_teach(self, message):
        utterance = message.data.get("utterance", "")
        query = message.data.get("query") or utterance
        self.route(query, utterance)

    @intent_handler("lesson.intent")
    def handle_lesson(self, message):
        utterance = message.data.get("utterance", "")
        inst = self._instrument(utterance)
        if not inst:
            self._ask_instrument("course")
            return
        self.course(inst)

    @intent_handler("tune.intent")
    def handle_tune(self, message):
        utterance = message.data.get("query") or message.data.get("utterance", "")
        inst = self.words().instrument(utterance) or self.progress().get("instrument")
        if inst not in ("guitar", "bass"):
            inst = "guitar"
        self.start_tuner(inst)

    @intent_handler("list.intent")
    def handle_list(self, message):
        names = [SG.title(t, self.lang) for t in SG.library()]
        self.speak_dialog("list", {"songs": self.words().join(names)})

    # ------------------------------------------------------------ what was asked
    def plan(self, query: str, utterance: str = "") -> tuple:
        """What `query` asks for: ("tune", inst) / ("jam", inst, text) /
        ("song", inst, tune, melody) / ("scale", inst, Scale) / ("chord",
        inst, Chord) / ("course", inst) / ("nothing",). `inst` is None when
        it wasn't said and none was used before."""
        w = self.words()
        text = f"{utterance} {query}".strip()
        said = w.instrument(text)
        inst = said or self.progress().get("instrument")
        if w.has(text, "tune_word") and not SG.find(text):
            return ("tune", said if said in ("guitar", "bass") else "guitar")
        if w.has(text, "jam"):
            return ("jam", inst, text)
        tune = SG.find(text)
        if tune:
            return ("song", inst, tune, w.has(text, "melody"))
        special = any(w.has(text, f"s_{k}") for k in ("harmonic_minor", "dorian", "mixolydian", "pentatonic",
                                                        "blues"))
        if w.has(text, "scale") or (special and not w.has(text, "chord")):
            scale = w.scale(query)
            if scale:
                return ("scale", inst, scale)
        chord = w.chord(query, loose=w.has(text, "chord"))
        if chord:
            return ("chord", inst, chord)
        if said:
            return ("course", inst)
        return ("nothing",)

    def route(self, query: str, utterance: str = "") -> bool:
        """Start what `query` asks for. False if it asks for nothing this skill does."""
        plan = self.plan(query, utterance)
        kind = plan[0]
        if kind == "nothing":
            self.speak_dialog("dont_know")
            return False
        if kind == "tune":
            self.start_tuner(plan[1])
            return True
        inst = plan[1]
        if not inst:
            return self._ask_instrument(kind, query if kind in ("scale", "chord") else f"{utterance} {query}")
        said = self.words().instrument(f"{utterance} {query}")
        if said:                                        # remembered for next time
            p = self.progress()
            p["instrument"] = said
            self.save_progress(p)
        w, ins = self.words(), I.INSTRUMENTS[inst]
        if kind == "jam":
            self.start_jam(inst, plan[2])
        elif kind == "song":
            self.start_song(inst, plan[2], melody=plan[3])
        elif kind == "scale":
            self.start_exercises(inst, [ScaleExercise(ins, w, plan[2])])
        elif kind == "chord":
            self.start_exercises(inst, [ChordExercise(ins, w, plan[2])])
        else:
            self.course(inst)
        return True

    def _ask_instrument(self, what: str, text: str = "") -> bool:
        self.asked_instrument = text or what
        self.waiting = True
        self._keep_active()
        self.speak_dialog("which_instrument", expect_response=True)
        return True

    # ------------------------------------------------------------ the course
    def course_steps(self, inst: str) -> list[dict]:
        return json.loads((SKILL_ROOT / "lessons" / f"{inst}.json").read_text(encoding="utf-8"))["steps"]

    def course(self, inst: str):
        steps = self.course_steps(inst)
        p = self.progress()
        done = int(p.get(f"done_{inst}", 0))
        if done >= len(steps):
            self.speak_dialog("course_done", {"instrument": self.words().instrument_name(inst)})
            p[f"done_{inst}"] = 0                       # round again next time
            self.save_progress(p)
            return
        step = steps[done]
        self.do_step(inst, step)

    def do_step(self, inst: str, step: dict):
        self.stop_activity()
        self.step = {"inst": inst, **step}
        w, ins = self.words(), I.INSTRUMENTS[inst]
        kind = step["do"]
        if kind == "scale":
            self.start_exercises(inst, [ScaleExercise(ins, w, Scale(parse_note(step["key"]), step.get("scale", "major")))],
                                 keep_step=True)
        elif kind == "chord":
            chords = step["chord"] if isinstance(step["chord"], list) else [step["chord"]]
            self.start_exercises(inst, [ChordExercise(ins, w, parse_chord(c)) for c in chords], keep_step=True)
        elif kind == "song":
            self.start_song(inst, step["tune"], melody=step.get("melody", False), key=step.get("key"),
                            keep_step=True)
        elif kind == "jam":
            self.start_jam(inst, "", style=step.get("style", "blues"), key=step.get("key"), keep_step=True)
        elif kind == "tune":
            self.start_tuner(inst, keep_step=True)

    def step_done(self):
        """The course step being done is done: count it, and say so."""
        step, self.step = self.step, None
        if not step:
            return False
        inst = step["inst"]
        p = self.progress()
        p[f"done_{inst}"] = int(p.get(f"done_{inst}", 0)) + 1
        self.save_progress(p)
        self.speak_dialog("step_done", {"n": p[f"done_{inst}"],
                                        "instrument": self.words().instrument_name(inst)})
        return True

    # ------------------------------------------------------------ exercises
    def start_exercises(self, inst: str, exercises: list, keep_step: bool = False, after=None):
        if not keep_step:
            self.stop_activity()
            self.step = None
        self.queue = list(exercises)
        self.after = after
        self.tries = 0
        self.tempo = 84
        self._run(self._next_exercise)

    def _run(self, target, *args):
        self.stopped.clear()
        self.ear = Ear(self.bus)
        self.worker = threading.Thread(target=self._guard, args=(target, *args), daemon=True)
        self.worker.start()

    def _guard(self, target, *args):
        try:
            target(*args)
        except Exception as e:                    # a lesson must never take OVOS down
            self.log.exception(f"music teacher: {e}")

    def _next_exercise(self):
        if self.stopped.is_set():
            return
        if not self.queue:
            self.current = None
            after, self.after = getattr(self, "after", None), None
            if after:
                after()
            elif not self.step_done():
                self.gui.release()
            return
        self.current = self.queue.pop(0)
        self.tries = 0
        self._teach(self.current)

    def _teach(self, ex, show_example: bool = True):
        """Show it, say it, play it - then listen."""
        if self.stopped.is_set():
            return
        self._show(ex.view())
        name, data = ex.explain()
        self.speak_dialog(name, data, wait=True)
        if show_example:
            self._play_example(ex)
        self._attempt(ex)

    def _play_example(self, ex, tempo: int | None = None):
        if self.midi_latency is None and not self._midi():
            return
        tempo = tempo or self.tempo
        self._send("ovos.midi.events", {"source": self.skill_id, "at": time.time() + (self.midi_latency or 0.3) + 0.1,
                                        "events": ex.example(tempo)})
        self.stopped.wait(ex.example_seconds(tempo) + (self.midi_latency or 0.3))

    def _attempt(self, ex):
        if self.stopped.is_set():
            return
        self.speak_dialog("your_turn" if ex.sequence else "your_turn_chord", wait=True)
        self._show(ex.view(self.words().names["listening"], "listen"))
        n = len(ex.asked())
        seconds = min(25.0, 4.0 + n * 1.3) if ex.sequence else 6.0
        heard = self.ear.hear(seconds=seconds, notes_wanted=n if ex.sequence else 0, chord=not ex.sequence)
        if self.stopped.is_set():
            return
        result = ex.check(heard)
        w = self.words()
        if result.ok:
            self._show(ex.view(w.names["right"], "ok"))
            self.speak_dialog("right", wait=True)
            if self.queue:
                self.speak_dialog("next_one", wait=True)
            self._next_exercise()
            return
        if result.nothing:
            self._show(ex.view())
            self._pause("nothing")
            return
        self.tries += 1
        self._show(ex.view(w.names["wrong"], "bad"))
        self.speak_dialog(result.say, result.data, wait=True)
        if self.tries >= GIVE_UP:
            self._pause("pause")
            return
        if self.tries == TRIES:
            self.speak_dialog("show_again", wait=True)
            self._play_example(ex, int(self.tempo * 0.7))
        else:
            self.speak_dialog("try_again", wait=True)
        self._attempt(ex)

    def _pause(self, dialog: str):
        """Wait for "again", "next", "play it" ... (converse)."""
        self.waiting = True
        self._keep_active()
        self.speak_dialog(dialog, expect_response=True)

    # ------------------------------------------------------------ songs
    def start_song(self, inst: str, tune_id: str, melody: bool = False, key: str | None = None,
                   keep_step: bool = False):
        if not keep_step:
            self.stop_activity()
            self.step = None
        song = SG.Song(tune_id, I.INSTRUMENTS[inst], self.words(), melody=melody,
                       key=parse_note(key) if key else None)
        self.song = song
        pieces = song.pieces()
        w = self.words()
        if song.mode == "chords":
            names = w.join([w.chord_name(c) for c in song.teacher_chords()])
            self.speak_dialog("song_chords", {"tune": song.title, "chords": names}, wait=True)
        elif song.mode == "line":
            self.speak_dialog("song_line", {"tune": song.title, "count": len(pieces)}, wait=True)
        else:
            self.speak_dialog("song_intro", {"tune": song.title, "count": len(pieces)}, wait=True)
        self.queue = pieces
        self.after = self._song_learnt
        self.tries = 0
        self.tempo = 84
        self._run(self._next_exercise)

    def _song_learnt(self):
        self.waiting = True
        self.asking_band = True
        self._keep_active()
        self.speak_dialog("song_learnt", expect_response=True)

    def play_along(self):
        song = self.song
        if not song:
            return
        if not self._midi():
            self.speak_dialog("no_midi")
            self.step_done()
            return
        self.band = BandLesson(self._send, self.skill_id, self.midi_latency or 0.3, song.inst, self.words(),
                               on_screen=self._show, on_end=self._band_ended)
        self.speak_dialog("song_together", wait=True)
        self.band.along(song)
        self._keep_active()

    # ------------------------------------------------------------ jamming
    def start_jam(self, inst: str, text: str, style: str | None = None, key: str | None = None,
                  keep_step: bool = False):
        if not keep_step:
            self.stop_activity()
            self.step = None
        if not self._midi():
            self.speak_dialog("no_midi")
            return
        bw = self.band_words()
        style = bw.style(text) or style or "blues"
        k = bw.key(text) or (Key(parse_note(key.rstrip("m")), key.endswith("m")) if key else STYLES[style].key)
        w = self.words()
        ins = I.INSTRUMENTS[inst]
        self.stopped.clear()
        self.ear = Ear(self.bus)
        self.band = BandLesson(self._send, self.skill_id, self.midi_latency or 0.3, ins, w, ear=self.ear,
                               on_feedback=self._jam_feedback, on_screen=self._show, on_end=self._band_ended)
        scale = scale_for(style, k, inst)
        self.speak_dialog("jam_intro", {"style": style, "key": bw.spoken_key(k), "scale": w.scale_name(scale)},
                          wait=True)
        self.band.improvise(style, k)
        self._keep_active()

    def _jam_feedback(self, dialog: str, data: dict):
        band = self.band
        if not band:
            return
        self.speak_dialog(dialog, data)
        self._keep_active()
        if len(band.turns) >= JAM_TURNS:
            band.finish()

    def _band_ended(self, band: BandLesson):
        if self.band is not band:
            return
        self.band = None
        self.gui.release()
        if band.mode == "along" and band.song:
            self.speak_dialog("song_end", {"tune": band.song.title}, wait=True)
        elif band.mode == "improvise":
            count = sum(t["count"] for t in band.turns)
            inside = sum(t["inside"] for t in band.turns)
            if count:
                self.speak_dialog("jam_end", {"inside": inside, "count": count}, wait=True)
            else:
                self.speak_dialog("jam_end_quiet", wait=True)
        self.step_done()

    # ------------------------------------------------------------ the tuner
    def start_tuner(self, inst: str, keep_step: bool = False):
        if not keep_step:
            self.stop_activity()
            self.step = None
        self.tuning = True
        self._run(self._tune, I.INSTRUMENTS[inst])

    def _tune(self, ins: I.Instrument):
        w = self.words()
        self.speak_dialog("tune_start", {"instrument": w.instrument_name(ins.name)}, wait=True)
        letters = w.string_letters(ins)
        for s in range(len(ins.tuning)):
            if self.stopped.is_set():
                return
            self._show(S.page(S.tuner(letters[s], None), w.instrument_name(ins.name)))
            self.speak_dialog("tune_string", {"string": w.string_name(ins, s)}, wait=True)
            for _ in range(TUNE_TRIES):
                if self.stopped.is_set() or self.skip_string:
                    break
                self._show(S.page(S.tuner(letters[s], None, w.names["listening"]), w.instrument_name(ins.name)))
                heard = self.ear.hear(seconds=4.0)
                if self.stopped.is_set():
                    return
                freq = None
                if heard.audio is not None:
                    freq = H.pitch(*heard.audio, low=ins.tuning[0])
                elif heard.keys:
                    notes = H.notes_from_keys(heard.keys)
                    freq = H.hz(notes[0][2]) if notes else None
                if not freq:
                    self.speak_dialog("tune_didnt_hear", wait=True)
                    continue
                t = H.tune(freq, ins.tuning, s)
                hint = w.names["tune_ok"] if abs(t.cents) <= IN_TUNE else \
                    w.names["tune_low"] if t.cents < 0 else w.names["tune_high"]
                self._show(S.page(S.tuner(letters[s], t.cents, hint), w.instrument_name(ins.name)))
                if abs(t.cents) <= IN_TUNE:
                    self.speak_dialog("tune_ok", wait=True)
                    break
                if t.cents < 0:
                    self.speak_dialog("tune_far_low" if t.cents < -FAR else "tune_low", wait=True)
                else:
                    self.speak_dialog("tune_far_high" if t.cents > FAR else "tune_high", wait=True)
            self.skip_string = False
        if not self.stopped.is_set():
            self.tuning = False
            self.speak_dialog("tune_done", wait=True)
            if not self.step_done():
                self.gui.release()

    skip_string = False

    # ------------------------------------------------------------ while a lesson is on
    @property
    def busy(self) -> bool:
        return bool(self.waiting or self.current or self.band or self.tuning)

    def can_converse(self, message=None) -> bool:
        if not self.busy:
            return False
        utterances = (message.data.get("utterances") if message else None) or []
        return not utterances or any(self.understand(u) for u in utterances)

    def understand(self, utterance: str) -> str | None:
        w = self.words()
        if w.has(utterance, "enough"):
            return "enough"
        if self.asked_instrument and w.instrument(utterance):
            return "instrument"
        if self.band:
            if w.has(utterance, "faster"):
                return "faster"
            if w.has(utterance, "slower"):
                return "slower"
            return None
        if getattr(self, "asking_band", False):
            if w.has(utterance, "yes") or w.has(utterance, "together"):
                return "together"
            if w.has(utterance, "no"):
                return "no"
        if self.tuning:
            return "next" if w.has(utterance, "next") else None
        if not self.waiting:
            return None
        for cmd in ("next", "slower", "faster", "show", "again", "yes"):
            if w.has(utterance, cmd):
                return "again" if cmd == "yes" else cmd
        return None

    def converse(self, message=None):
        if message is None:
            return False
        for utterance in message.data.get("utterances") or []:
            what = self.understand(utterance)
            if what:
                self.do(what, utterance)
                return True
        return False

    def do(self, what: str, utterance: str = ""):
        w = self.words()
        if what == "enough":
            self.stop_activity()
            self.step = None
            self.speak_dialog("bye")
            self.gui.release()
            return
        if what == "instrument":
            inst = w.instrument(utterance)
            asked, self.asked_instrument = self.asked_instrument, None
            self.waiting = False
            p = self.progress()
            p["instrument"] = inst
            self.save_progress(p)
            if asked == "course":
                self.course(inst)
            else:
                self.route(f"{asked} {utterance}")
            return
        if self.band:
            jam = self.band.jam
            if jam:
                jam.change(tempo=round(jam.state.tempo * (1.12 if what == "faster" else 0.89)))
            self.speak_dialog("ok")
            return
        if what == "together":
            self.asking_band = False
            self.waiting = False
            threading.Thread(target=self.play_along, daemon=True).start()
            return
        if what == "no":
            self.asking_band = False
            self.waiting = False
            self.step_done() or self.speak_dialog("ok")
            self.gui.release()
            return
        if self.tuning and what == "next":
            self.skip_string = True
            return
        ex = self.current
        self.waiting = False
        if ex is None:
            return
        if what == "next":
            self._run(self._next_exercise)
        elif what in ("slower", "faster"):
            self.tempo = max(50, min(140, int(self.tempo * (0.8 if what == "slower" else 1.2))))
            self.tries = 0
            self._run(self._teach, ex, True)
        elif what == "show":
            self.tries = 0
            self._run(self._teach, ex, True)
        else:
            self.tries = 0
            self._run(self._attempt, ex)

    # ------------------------------------------------------------ stopping
    def stop_activity(self):
        self.stopped.set()
        if self.ear:
            self.ear.cancelled.set()
        band, self.band = self.band, None
        if band:
            band.stop()
        self.queue = []
        self.current = None
        self.waiting = False
        self.tuning = False
        self.asking_band = False
        self.asked_instrument = None
        self.song = None
        self._send("ovos.midi.stop", {"source": self.skill_id})

    asking_band = False
    after = None

    def stop(self):
        was = self.busy
        self.stop_activity()
        self.step = None
        if was:
            self.gui.release()
        return was
