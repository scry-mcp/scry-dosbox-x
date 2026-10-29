# The Captures tools

## Capturing what the screen shows

The video (`capture_video=True`, with a `program` for the recorder to wrap) is DOSBox-X's own doing and needs no keypress. A still of the running screen is `snapshot`, taken in the guest; a still out of a recording is `capture_frame`, an extraction that needs `ffmpeg`.

## A series

A series is one `scry-series/1` manifest (`server`, `source`, `crop`, a row per frame `{frame, path, sha256, bytes, signature}`) beside its PNGs; the frames are the AVI's own, numbered from 0 at its first, not the display frames a stop's `frame` counts since power-on.

<!-- scry-reference:begin captures -->
## `captures`

*List this session's captures*

```text
captures()
```

Lists the files the session's tools wrote (`record` and `audio_record` among them), in
write order, re-read when changed, then the `capture_video` AVIs, largest last. Works on a
running guest.

Reply: `captures` (each `kind`, `path`, `present`, `bytes`; a recording also `complete`, and
an AVI `riff_avi`, `avi_frames`, a WAV `samples`, `channels`, `sample_rate_hz`, a DRO
`opl_pairs`, `opl_ms`, a MIDI file `midi_bytes`). A file gone has `present: false`, no
`bytes`.

Takes no argument.

| reply field | type |
|---|---|
| `captures` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "captures: 7 files",
  "status": "ok",
  "captures": [
    {
      "kind": "bin",
      "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1107.bin",
      "present": true,
      "bytes": 16
    },
    {
      "kind": "png",
      "path": "$TMPDIR/dosbox-x-session-<run>/gfx/palette-1.png",
      "present": true,
      "bytes": 1009
    },
    {
      "kind": "json",
      "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1284-stopped.screen-map.json",
      "present": true,
      "bytes": 341
    },
    {
      "kind": "trace",
      "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1372.trace",
      "present": true,
      "bytes": 238
    },
    {
      "kind": "avi",
      "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1422.avi",
      "present": true,
      "bytes": 36314,
      "riff_avi": true,
      "avi_frames": 1,
      "complete": true
    },
    {
      "kind": "wav",
      "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1435.wav",
      "present": true,
      "bytes": 5420,
      "complete": true,
      "samples": 1344,
      "channels": 2,
      "sample_rate_hz": 48000
    },
    "... 1 more"
  ]
}
```
<!-- scry-reference:end captures -->

Two capture files is the normal case: the recording restarts when the guest changes video mode. An AVI's `complete: false` is not damage: frames come out of such a file perfectly well. A WAV's, a DRO's or a MIDI file's is a header that disagrees with the file: one its writer has not closed, or a damaged one. `program` is passed with `-c`, which runs after the config's `[autoexec]`: an autoexec ending in `exit` quits the emulator first, and a `captures` with no `avi` row is the symptom.

<!-- scry-reference:begin capture_frame -->
## `capture_frame`

*Extract a frame to a file*

```text
capture_frame(frame, dest, capture_path="")
```

Frame `frame` of a capture written to `dest` as PNG; `capture_path` defaults to the
largest. Needs `ffmpeg`, `capture_video`. Refused: `%` in or existing `dest`, a frame
past the end.

Reply: `path`, `bytes`, `sha256`, `capture_path`, `frame`.

| argument | type | default |
|---|---|---|
| `frame` | integer | required |
| `dest` | string | required |
| `capture_path` | string | `""` |

| reply field | type |
|---|---|
| `bytes` | integer |
| `capture_path` | string |
| `frame` | integer |
| `path` | string |
| `sha256` | string |

Example, from a live run:

```json
{
  "frame": 2,
  "dest": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/J/n11.png",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/J/n6-cap/screen_001.avi"
}
```

```json
{
  "summary": "capture_frame 2: 5072 bytes to $TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/J/n11.png",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/J/n11.png",
  "bytes": 5072,
  "sha256": "aee93b1749a9c93112b4fca12509d5ad9da94fc94b41bf781612e590a0a4342b",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/J/n6-cap/screen_001.avi",
  "frame": 2
}
```
<!-- scry-reference:end capture_frame -->

**The still is always a PNG, whatever `dest` is called**: inferring the encoder from the extension hands back a frameless video container as a still (ffmpeg exits 0 for a frame past the end of a `.mp4` destination). A `%` anywhere in `dest`, parent directories included, is refused because the image muxer reads the whole path as a numbering template; the refusal is broader than the hazard because that direction fails loudly and the other silently.

<!-- scry-reference:begin series_capture -->
## `series_capture`

*Capture a series of frames*

```text
series_capture(at_frames=null, first=null, last=null, step=1, crop=null, dest="", capture_path="")
```

Capture frames as PNGs plus a manifest (read by `image_compare`).

AVI frames from 0: `at_frames`, or `first`, `last`, `step`; max 1000. `crop`:
`[x, y, w, h]`. `dest`: new directory, kept after `close`.

Reply: `manifest`, `count`, `first`, `last`, `distinct`, `kept_after_close`, `capture_path`,
`crop`. Refused: `bad_argument` (frame, crop, `dest`), `no_channel` (no `capture_video`),
`unexpected_answer` (no capture), `host_failed` (no `ffmpeg`).

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `at_frames` | array of integer or null | `null` |
| `first` | integer or null | `null` |
| `last` | integer or null | `null` |
| `step` | integer | `1` |
| `crop` | array of integer or null | `null` |
| `dest` | string | `""` |
| `capture_path` | string | `""` |

| reply field | type |
|---|---|
| `capture_path` | string |
| `count` | integer |
| `crop` | array |
| `distinct` | integer |
| `first` | integer |
| `frame_source` | string |
| `frames_asked` | integer |
| `kept_after_close` | boolean |
| `last` | integer |
| `manifest` | string |

Example, from a live run:

```json
{
  "first": 0,
  "last": 4,
  "crop": [0, 0, 320, 8],
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/Q/n1-cap/screen_001.avi"
}
```

```json
{
  "summary": "series_capture: 5 AVI frames 0..4, 2 distinct, manifest $TMPDIR/dosbox-x-session-<run>/series/series-1/manifest.json",
  "status": "ok",
  "manifest": "$TMPDIR/dosbox-x-session-<run>/series/series-1/manifest.json",
  "count": 5,
  "first": 0,
  "last": 4,
  "distinct": 2,
  "frames_asked": 5,
  "kept_after_close": false,
  "frame_source": "avi",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/Q/n1-cap/screen_001.avi",
  "crop": [0, 0, 320, 8]
}
```
<!-- scry-reference:end series_capture -->

The frames are the AVI's own, not emulated frames, because the file is what is read. A `%` in `dest` is refused because ffmpeg would read the path as a numbering template. Without `dest` the series sits in the session scratch and is gone at `close`.

<!-- scry-reference:begin snapshot -->
## `snapshot`

*Snapshot the screen to a PNG*

```text
snapshot(dest="", seconds=10.0)
```

A still of the screen as a PNG, at `dest` if given (absolute, new). Running: taken in the
guest into the captures directory within `seconds` (`route` `guest`); refused with no `logfile`
or no stub in the log. At a stop: written from video memory through `screen_view`'s decoder
(`route` `video_memory`), unscaled, without running the machine; a text mode is refused
(`no_channel`), and `seconds` is not used.

Reply: `route`, `path`, `bytes`, `sha256`.

| argument | type | default |
|---|---|---|
| `dest` | string | `""` |
| `seconds` | number (> 0, <= 600.0) | `10.0` |

| reply field | type |
|---|---|
| `bytes` | integer |
| `path` | string |
| `route` | string |
| `sha256` | string |

Example, from a live run:

```json
{
  "dest": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/P/n4.png",
  "seconds": 20
}
```

```json
{
  "summary": "snapshot: 885 bytes at $TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/P/n4.png",
  "status": "ok",
  "route": "guest",
  "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/P/n4.png",
  "bytes": 885,
  "sha256": "5053cd8f49a0d5bea6531db5520c7dfb0c06340f05b59d4baff51012d24313f5"
}
```
<!-- scry-reference:end snapshot -->

**Two routes, chosen by whether the machine runs.** While it runs the stub takes the command inside the machine (`route: "guest"`), and only the log says which stub is resident (the command is the Delete key's scan code to an older stub), hence the `logfile` requirement there. No window or menu is needed, so any session works. At a stop no frame is drawn, so the still is written from video memory through the decoder `screen_view` uses (`route: "video_memory"`), unscaled, with no log or stub and without running the machine; a text mode has no picture to write there and is refused naming `screen_view`.

<!-- scry-reference:begin record -->
## `record`

*Record frames to an AVI*

```text
record(frames, dest="", seconds=60.0)
```

Record exactly `frames` retraces of the screen to an AVI, then stop. Needs the machine
STOPPED and a build whose debugger has `CAPTURE`; headless or windowed.

`dest`: an absolute path not there yet; empty leaves the file where the emulator wrote it.
The AVI is checked before its path is given; zero frames is INVALID.

One frame is written per retrace, but none for the first from the stop `start` leaves. A run
cut short (`verdict` `TIMEOUT`, `OTHER_STOP`) is checked for what it holds. A capture that
could not be turned off is `ended: false`, no `path`, and records until `close`.

Refused: `frames` under 1, a video capture already on (`capture_video`), a build with no
`CAPTURE`, a running machine.

Reply: `verdict`, `kind`, `frames`, `began`, `ended`, `path`, `bytes`, `avi_frames`,
`note`, the run's fields as `run_for` gives them, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause` and `e9`.

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `frames` | integer | required |
| `dest` | string | `""` |
| `seconds` | number (> 0, <= 600.0) | `60.0` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `cycles` | integer or object |
| `e9` | object |
| `emulated_after_s` | number or object |
| `emulated_before_s` | number |
| `enrichment` | object |
| `frame` | integer or object |
| `frame_after` | integer or object |
| `frame_before` | integer or object |
| `instruction` | DosboxInstruction |
| `pc` | string or object |
| `polls` | integer |
| `regs` | object |
| `retrace_pending` | boolean |
| `stop_seq` | integer |
| `verdict` | string |
| `watches` | array |
| `avi_frames` | integer |
| `began` | boolean |
| `bytes` | integer |
| `ended` | boolean |
| `frames` | integer |
| `kind` | string |
| `path` | string or object |

Example, from a live run:

```json
{
  "frames": 2,
  "dest": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1422.avi",
  "seconds": 30
}
```

```json
{
  "summary": "record 2 frames: ELAPSED, 1 frame at $TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1422.avi",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 2,
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "frame": 141,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000002b8",
    "ECX": "0x00006a9c",
    "EDX": "0x00000814",
    "ESI": "0x00000173",
    "EDI": "0x0000015d",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000130",
    "CS": "0x0814",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0814:00000130",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": 89548},
  "stop_seq": 10,
  "instruction": {
    "address": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "emulated_before_s": 1.9747018,
  "emulated_after_s": 2.003237,
  "frame_before": 139,
  "frame_after": 141,
  "cycles": 284474,
  "kind": "avi",
  "frames": 2,
  "began": true,
  "ended": true,
  "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1422.avi",
  "bytes": 36314,
  "avi_frames": 1
}
```
<!-- scry-reference:end record -->

<!-- scry-reference:begin audio_record -->
## `audio_record`

*Record the sound to a file*

```text
audio_record(frames, dest="", seconds=60.0, kind="wav")
```

Record exactly `frames` retraces of sound, then stop: the mixer to a WAV (`kind`
`wav`), the OPL register writes to a DRO (`dro`) or the MIDI bytes to a MIDI file
(`mid`). Needs the machine STOPPED and a build whose debugger has `CAPTURE`.

`dest`: an absolute path not there yet; empty leaves the file where the emulator wrote it.
The file is checked before its path is given (a rolled-over OPL run: the last); a WAV whose
samples miss the run's emulated span by more than 2 mixer ticks is INVALID.
Silence is reported, never refused; a run with no OPL note or MIDI byte has no file (`path`
unavailable). A run cut short is checked for what it holds; a capture that could not be turned
off is `ended: false`, no `path`, and records until `close`.

Refused: `frames` under 1, that kind already on, a build with no `CAPTURE`, a running
machine.

Reply: `verdict`, `kind`, `frames`, `began`, `ended`, `path` (none if the capture could not be
turned off), `bytes` (a file was written); a WAV's `channels`, `sample_rate_hz`, `samples`,
`emulated_s`, `sample_min`, `sample_max`; a DRO's `opl_pairs`, `opl_ms` (the last file's);
`files` (each `path`, `bytes`) when the OPL writer rolled over to a new file, `path` then the
last; a MIDI file's `midi_bytes`; `note`, the run's fields, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause` and `e9`.

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `frames` | integer | required |
| `dest` | string | `""` |
| `seconds` | number (> 0, <= 600.0) | `60.0` |
| `kind` | one of `"wav"`, `"dro"`, `"mid"` | `"wav"` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `cycles` | integer or object |
| `e9` | object |
| `emulated_after_s` | number or object |
| `emulated_before_s` | number |
| `enrichment` | object |
| `frame` | integer or object |
| `frame_after` | integer or object |
| `frame_before` | integer or object |
| `instruction` | DosboxInstruction |
| `pc` | string or object |
| `polls` | integer |
| `regs` | object |
| `retrace_pending` | boolean |
| `stop_seq` | integer |
| `verdict` | string |
| `watches` | array |
| `began` | boolean |
| `bytes` | integer |
| `channels` | integer |
| `emulated_s` | number or object |
| `ended` | boolean |
| `files` | array of object |
| `frames` | integer |
| `kind` | string |
| `midi_bytes` | integer |
| `opl_ms` | integer |
| `opl_pairs` | integer |
| `path` | string or object |
| `sample_max` | integer |
| `sample_min` | integer |
| `sample_rate_hz` | integer |
| `samples` | integer |

Example, from a live run:

```json
{
  "frames": 2,
  "dest": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1435.wav",
  "seconds": 30
}
```

```json
{
  "summary": "audio_record wav 2 frames: ELAPSED, 1344 samples at 48000 Hz, silent at $TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1435.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 2,
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "frame": 143,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000002b4",
    "ECX": "0x0000135a",
    "EDX": "0x00000814",
    "ESI": "0x00000173",
    "EDI": "0x0000015d",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000130",
    "CS": "0x0814",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0814:00000130",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": 93059},
  "stop_seq": 11,
  "instruction": {
    "address": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "emulated_before_s": 2.003237,
  "emulated_after_s": 2.0317731,
  "frame_before": 141,
  "frame_after": 143,
  "cycles": 284494,
  "kind": "wav",
  "frames": 2,
  "began": true,
  "ended": true,
  "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1435.wav",
  "bytes": 5420,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 1344,
  "emulated_s": 0.0285361,
  "sample_min": 0,
  "sample_max": 0
}
```
<!-- scry-reference:end audio_record -->

**A stretch is bounded at stops, in retraces.** The debugger's `CAPTURE` turns a kind on while the
machine stands still, `run_for`'s own loop runs the retraces, and `CAPTURE` turns it off at the stop
that loop reached, so the file holds what was emulated in between and no wall time. No window is
needed, and no menu: a headless session records as a windowed one does. A capture already on (a
session started with `capture_video` records video for its whole run) is refused rather than ended
by a second toggle. The capture is turned off whatever the run did, cancelled included; one that
could not be turned off says so (`ended: false`) and records until `close`.

**Each file is checked before its path is given.** A WAV's header must agree with its file (the
emulator writes both sizes only at close) and its samples with the run's emulated span: the mixer
works in whole ticks of an emulated millisecond and each end of the span falls inside one, so one
tick at each end is the tolerance. An AVI must be finished and hold a frame: one is written per retrace,
except that a run from the very stop `start` leaves writes none for its first, the display having
drawn no frame yet. A DRO must be a DRO 2.0 stream whose header's length is the file's, its
register state dumped at its first event and then each write; a MIDI file a header and a track
whose length reaches the file's end. The OPL writer opens its file at the first note keyed on and the
MIDI writer at the first byte, so a run with neither has no file, and `path` says why; the OPL
writer also starts a new file after half a minute of emulated silence: `files` then names every
file of the run, `path` the last, and the checks and the counts (`opl_pairs`, `opl_ms`) are the
last file's alone.
Silence is a fact about the guest: a constant level is reported as `sample_min` equal to
`sample_max`, never refused.
