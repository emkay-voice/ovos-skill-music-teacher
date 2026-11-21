# Developing ovos-skill-music-teacher

```bash
pip install -e ".[test]"
pytest -q tests
```

(`tests/pytest.ini` keeps pytest from importing the repository root's
`__init__.py` as a plain module; the tests use the installed package.)

The tests play real sound to it: `tests/sounds.py` makes a piano-like tone
and plucked strings, and every scale, chord and tuning test is heard from
that, not handed over as data.

## The pieces

| file | |
|---|---|
| `theory.py` | notes, scales and chords, spelled (each letter once in a scale) and named per language: letters, H/B, solfège |
| `instruments.py` | piano, guitar and bass: right-hand scale fingering, chord fingering, guitar chord shapes (open and barre), notes in a position on a fretted neck, a "box" for jamming |
| `hearing.py` | from sound: notes (YIN), a chord's twelve notes (chroma), a string's pitch; comparing what was played with what was asked |
| `listen.py` | the microphone (the listener's recording mode) and a MIDI keyboard (`ovos.midi.input`) |
| `exercises.py` | a scale, a chord, a piece of a song, a bass line: what it asks for, its screen, its example, its check |
| `songs.py` | a song cut into pieces for an instrument (melody, chords or bass line), moved to another key if asked |
| `jamlesson.py` | with the band: a song played along, or jamming in turns, with a word from the teacher after each turn |
| `screen.py` | the pictures: keyboard, fretboard, chord chart, the notes in order, the tuner - SVG for `SYSTEM_ImageFrame` |
| `words.py` | what a sentence asks for (instrument, scale, chord, command) and how things are said, from the locale |
| `__init__.py` | the skill: the intents, the lesson running in a thread, converse while it runs |
| `lessons/*.json` | the courses |

Everything is pure Python and numpy, so it also runs in Pyodide (Emkay).

## What it uses from ovos-skill-jamband

So nothing is written twice: the pitch tracker and the WAV reader
(`melody.pitch_track`, `notes_from_track`, `wav_samples`), where the listener
saves recordings (`listen.recordings_folder`), the note reader that knows
"fis", "si bemol" and "B flat" (`words.note`, `normal`), the tunes
(`tunes`), their chords (`compose.chords_for`), and the jam itself
(`jam.Jam`, `State`, `styles.STYLES`, `music.Key`, `Chord`). The tests cover
each of these, so a change in jamband that breaks the teacher shows up here.

## The bus

To [ovos-phal-plugin-midi](https://github.com/emkay-voice/ovos-phal-plugin-midi):
`ovos.midi.status` (is there a band, its latency), `ovos.midi.events` (an
example, with the skill id as `source`), `ovos.midi.stop`; the jam lessons
send what jamband's jam sends. From it: `ovos.midi.input`, the keys of a MIDI
keyboard.

To the listener: `recognizer_loop:state.set` `{"state": "recording",
"recording_name": ...}`, `recognizer_loop:record_stop` when it has heard
enough; `recognizer_loop:record_end` says the WAV is in the listener's
`<save_path>/recordings/`.

## A lesson

`lessons/<instrument>.json` is a list of steps:

```json
{"do": "scale", "key": "A", "scale": "minor_pentatonic"}
{"do": "chord", "chord": ["D", "A7"]}
{"do": "song", "tune": "saints", "key": "D"}
{"do": "song", "tune": "ode_to_joy", "melody": true}
{"do": "jam", "style": "blues", "key": "E"}
{"do": "tune"}
```

Scales: `major`, `minor`, `harmonic_minor`, `dorian`, `mixolydian`,
`major_pentatonic`, `minor_pentatonic`, `blues`. Chords are written as
symbols (`Am`, `F#7`, `Bbmaj7`, `Dsus4`). A song is one of jamband's tunes
(its file name); `key` moves it. A jam's style is one of jamband's styles,
its key a letter, `m` for minor.

## Languages

Every locale has the same files (`tests/test_locale.py` checks, and that the
dialogs use the same `{fields}`): the intents, a `.voc` per word group, the
dialogs, `skill.json` (whose examples are tested to do what they say), and
`words.json` - the names of the instruments, strings and fingers, the
patterns for scale and chord names (`"{note}-dur"`, `"{note} mayor"`), and
how a place on the neck is said. Quality words are `q_*.voc`, scale kinds
`s_*.voc`; `filler.voc` holds everyday words that are also note names ("a",
"la", "mi") so they aren't taken for one.
