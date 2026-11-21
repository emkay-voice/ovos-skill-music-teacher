"""The teacher's ear: the microphone, and a MIDI keyboard.

The microphone is the listener's recording mode (ovos-dinkum-listener;
Emkay does the same): recognizer_loop:state.set {"state": "recording",
"recording_name": ...} records until it is quiet - or until
recognizer_loop:record_stop - then the WAV is in <listener
save_path>/recordings/ and recognizer_loop:record_end is said. Keys played
on a MIDI keyboard come meanwhile as ovos.midi.input (ovos-phal-plugin-midi):
when they do, they are what counts - exact, no guessing from sound.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ovos_bus_client.message import Message

from ovos_skill_jamband.listen import recordings_folder
from ovos_skill_jamband.melody import wav_samples

KEYS_DONE = 1.6            # this long after the last key the keyboard is done


@dataclass
class Heard:
    keys: list = field(default_factory=list)       # [(time, "on"/"off", note)] from a MIDI keyboard
    audio: tuple | None = None                      # (samples, rate) from the microphone

    @property
    def empty(self) -> bool:
        return not self.keys and (self.audio is None or len(self.audio[0]) == 0)


class Ear:
    def __init__(self, bus, folder: Path | None = None):
        self.bus = bus
        self.folder = folder or recordings_folder()
        self.cancelled = threading.Event()

    def hear(self, seconds: float = 12.0, notes_wanted: int = 0, chord: bool = False) -> Heard:
        """Listen once: at most `seconds`; a keyboard is done when the notes
        wanted have been played (or it rests); a chord after it has rung."""
        keys: list = []
        last = [0.0]
        ended = threading.Event()
        ons = [0]

        def on_key(message):
            d = message.data or {}
            kind = d.get("type")
            if kind == "note_on" and d.get("velocity", 0) > 0:
                keys.append((time.time(), "on", d.get("note")))
                ons[0] += 1
            elif kind in ("note_off", "note_on"):
                keys.append((time.time(), "off", d.get("note")))
            else:
                return
            last[0] = time.time()

        name = f"music-teacher-{int(time.time() * 1000)}"
        self.bus.on("ovos.midi.input", on_key)
        on_end = lambda _m=None: ended.set()          # noqa: E731
        self.bus.on("recognizer_loop:record_end", on_end)
        try:
            self.bus.emit(Message("recognizer_loop:state.set", {"state": "recording", "recording_name": name}))
            t0, stopped = time.time(), False
            while time.time() - t0 < seconds + 5:
                if ended.wait(0.05) or self.cancelled.is_set():
                    break
                idle = keys and time.time() - last[0] > (1.0 if chord else KEYS_DONE)
                enough = notes_wanted and ons[0] >= notes_wanted and time.time() - last[0] > 0.5
                if not stopped and (idle or enough or time.time() - t0 > seconds):
                    self.bus.emit(Message("recognizer_loop:record_stop"))
                    stopped = True
                    if keys:
                        break
        finally:
            self.bus.remove("ovos.midi.input", on_key)
            self.bus.remove("recognizer_loop:record_end", on_end)
        if keys:
            self._drop(name)
            return Heard(keys=keys)
        wav = self.folder / f"{name}.wav"
        for _ in range(30):                    # written just before record_end, or just after
            if wav.exists():
                break
            time.sleep(0.1)
        if not wav.exists():
            return Heard()
        try:
            return Heard(audio=wav_samples(wav))
        except (OSError, ValueError):
            return Heard()
        finally:
            self._drop(name)

    def _drop(self, name: str):
        for suffix in (".wav", ".json"):
            try:
                (self.folder / f"{name}{suffix}").unlink()
            except OSError:
                pass
