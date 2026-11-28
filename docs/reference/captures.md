# The Captures tools

These tools save what the machine shows and plays to files on your disk: `snapshot` a still, `record` a video and `audio_record` the sound. `captures` lists what the session wrote.

`capture_frame` takes one still out of a video and `series_capture` a series of frames; both need `ffmpeg` on your computer. The video is one `record` wrote, or the one a session started with `start(capture_video=True, program=...)` records of its whole run.

A reply names its file by path and never carries the picture or the sound. `image_compare` and `audio_compare`, on the [Files](files.md) page, read those files back as numbers.

## Two ways of counting frames

`record` and `audio_record` count frames of the emulated display, one per vertical retrace. The frames `capture_frame` and `series_capture` take are a video's own, counted from 0 at its first. Neither is the `frame` a stop reports, which counts since power-on.

<!-- scry-reference:begin captures -->
## `captures`

List the files this session's tools wrote, each read again now: whether it is still there, its size, what it holds.

```text
captures()
```

### Try it

On Bricks, the game this repository builds, at the end of a session that saved pictures, a video, a sound file and a dump of memory.

Ask:

> List the files this session has written so far.

Call:

```text
captures()
```

Reply, 1 of 3 fields:

```json
{
  "summary": "captures: 10 files"
}
```

The session wrote ten files. `captures` has a row for each, with its kind, its path and whether it is still there.

<details><summary>The whole reply</summary>

```json
{
  "summary": "captures: 10 files",
  "status": "ok",
  "captures": [
    {"kind": "png", "path": "./tmp/demos/tour/files/wall.png", "present": true, "bytes": "<volatile>"},
    {
      "kind": "png",
      "path": "./tmp/demos/tour/files/palette.png",
      "present": true,
      "bytes": "<volatile>"
    },
    {"kind": "bin", "path": "./tmp/demos/tour/files/wall.bin", "present": true, "bytes": "<volatile>"},
    {
      "kind": "json",
      "path": "./tmp/demos/tour/files/session.json",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "trace",
      "path": "./tmp/demos/tour/files/captures/trace-1.trace",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "avi",
      "path": "./tmp/demos/tour/files/second-brick.avi",
      "present": true,
      "bytes": "<volatile>",
      "riff_avi": true,
      "avi_frames": 109,
      "complete": true
    },
    "... 4 more"
  ]
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `captures`: One row per file: `kind`, `path`, `present` and `bytes`. A recording adds `complete` and what it holds, by kind.

<details><summary>All 1 reply fields</summary>

- `captures` (array)

</details>

### Why it works this way

Every file is read again when it has changed, so the list says what is on disk now, and it answers while the program runs. A file deleted since stays listed, with `present: false` and no `bytes`.

First come the files the session's tools wrote, in the order written. Then come the videos of a session started with `capture_video`, largest last; two is normal, since the recording restarts when the program changes video mode.

An AVI's `complete: false` is not damage: frames come out of such a file. For a WAV, a DRO or a MIDI file it is a header that disagrees with the file: one its writer has not closed, or a damaged one.

<details><summary>More on why</summary>

| `kind` | what the row adds |
|---|---|
| `avi` | `complete`, `riff_avi` (it opens as an AVI), `avi_frames` |
| `wav` | `complete`, `samples`, `channels`, `sample_rate_hz` |
| `dro` | `complete`, `opl_pairs`, `opl_ms` |
| `mid` | `complete`, `midi_bytes` |

Any other row's `kind` is its file's extension, or `series` for a series.

`start`'s `program` runs after the configuration's `[autoexec]` section, so an autoexec that ends in `exit` quits the emulator first. A list with no `avi` row is the sign.

</details>

### Related tools

- [`record`](#record)
- [`audio_record`](#audio_record)
- [`capture_frame`](#capture_frame)
- [`series_capture`](#series_capture)
- [`snapshot`](#snapshot)
- [`start`](session.md#start)

<details><summary>The contract your client receives</summary>

```text
Lists the files the session's tools wrote (`record` and `audio_record` among them), in
write order, re-read when changed, then the `capture_video` AVIs, largest last. Works on a
running guest.

Reply: `captures` (each `kind`, `path`, `present`, `bytes`; a recording also `complete`, and
an AVI `riff_avi`, `avi_frames`, a WAV `samples`, `channels`, `sample_rate_hz`, a DRO
`opl_pairs`, `opl_ms`, a MIDI file `midi_bytes`). A file gone has `present: false`, no
`bytes`.
```

</details>
<!-- scry-reference:end captures -->

<!-- scry-reference:begin capture_frame -->
## `capture_frame`

Extract one frame of a video the session recorded to a PNG file.

```text
capture_frame(frame, dest, capture_path="")
```

### Try it

On Bricks, the game this repository builds, after the [`record`](#record) example filmed 110 frames in which a brick falls.

Ask:

> Take frame 104 out of the video second-brick.avi and save it as brick-gone.png.

Call:

```text
capture_frame(frame=104, capture_path="./tmp/demos/tour/files/second-brick.avi",
    dest="./tmp/demos/tour/files/brick-gone.png")
```

Reply, 3 of 7 fields:

```json
{
  "path": "./tmp/demos/tour/files/brick-gone.png",
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "frame": 104
}
```

Frame 104 of the video, counted from 0, is now a PNG at `path`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "path": "./tmp/demos/tour/files/brick-gone.png",
  "bytes": "<volatile>",
  "sha256": "<volatile>",
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "frame": 104
}
```

</details>

### Arguments

- `frame` (integer, required): The frame to extract, counted from 0 at the video's first frame.
- `dest` (string, required): A new path for the PNG, absolute or starting with `~`. The file is a PNG whatever its extension.
- `capture_path` (string, default `""`): The video to take the frame from, such as one `record` wrote. Left empty, the largest video of a session started with `capture_video`.

### What comes back

- `path`: The PNG.
- `sha256`: The file's SHA-256: the value a line of reference checksums holds for `image_compare(method="golden")`.
- `capture_path`: The video the frame came from.

<details><summary>All 5 reply fields</summary>

- `bytes` (integer)
- `capture_path` (string)
- `frame` (integer)
- `path` (string)
- `sha256` (string)

</details>

### What it refuses

- A `%` anywhere in `dest`, or a `dest` that exists (`bad_argument`).
- No `capture_path`, in a session not started with `capture_video` (`no_channel`).
- No `capture_path`, in a session whose video is not written yet (`unexpected_answer`).
- A frame past the end of the video, or a computer with no `ffmpeg` on its `PATH` (`host_failed`).

### Why it works this way

The still is always a PNG, whatever `dest` is called. Choosing the format from the extension would let `ffmpeg` answer a frame past the end with an empty video file and no error.

A `%` anywhere in `dest` is refused before anything runs: `ffmpeg` reads the whole path as a numbering pattern, and the still is one file. Name that file, or take several frames with `series_capture`.

The frame shows what was displayed, in any video mode, because it comes out of a video. The call reads a file, so it answers while the program runs.

### Related tools

- [`captures`](#captures)
- [`series_capture`](#series_capture)
- [`snapshot`](#snapshot)
- [`start`](session.md#start)
- [`image_compare`](files.md#image_compare)

<details><summary>The contract your client receives</summary>

```text
Frame `frame` of a capture written to `dest` as PNG; `capture_path` defaults to the
largest. Needs `ffmpeg`, `capture_video`. Refused: `%` anywhere in `dest` (no numbering
pattern is expanded: name the one file), an existing `dest`, a frame past the end.

Reply: `path`, `bytes`, `sha256`, `capture_path`, `frame`.
```

</details>
<!-- scry-reference:end capture_frame -->

<!-- scry-reference:begin series_capture -->
## `series_capture`

Save chosen frames of the screen as PNGs beside a manifest, for `image_compare` to read.

```text
series_capture(at_frames=null, first=null, last=null, step=1, crop=null, dest="", capture_path="")
```

### Try it

On Bricks, the game this repository builds, after the [`record`](#record) example filmed 110 frames in which a brick falls.

Ask:

> Save frames 95 to 108 of the video second-brick.avi as a series in a folder named series.

Call:

```text
series_capture(first=95, last=108, capture_path="./tmp/demos/tour/files/second-brick.avi",
    dest="./tmp/demos/tour/files/series")
```

Reply, 8 of 12 fields:

```json
{
  "summary": "series_capture: 14 AVI frames 95..108, 14 distinct, manifest ... (104 characters)",
  "count": 14,
  "first": 95,
  "last": 108,
  "distinct": 14,
  "kept_after_close": true,
  "frame_source": "avi",
  "crop": [0, 0, 640, 400]
}
```

Fourteen frames of the video were written, all different pictures (`distinct`). `frame_source` `avi` says the numbers are the video's own, and `crop` that each PNG is the whole 640x400 frame.

<details><summary>The whole reply</summary>

```json
{
  "summary": "series_capture: 14 AVI frames 95..108, 14 distinct, manifest ./tmp/demos/tour/files/series/manifest.json",
  "status": "ok",
  "manifest": "./tmp/demos/tour/files/series/manifest.json",
  "count": 14,
  "first": 95,
  "last": 108,
  "distinct": 14,
  "frames_asked": 14,
  "kept_after_close": true,
  "frame_source": "avi",
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "crop": [0, 0, 640, 400]
}
```

</details>

### Arguments

- `at_frames` (array of integer, optional): The frames to keep, as an ascending list of frame numbers. Give this or `first` and `last`, never both.
- `first` (integer, optional): The first frame of an evenly spaced range, given with `last`.
- `last` (integer, optional): The last frame of the range. A series holds at most 1000 frames.
- `step` (integer, default `1`): The spacing of the range: every `step`-th frame from `first`. Left out, 1.
- `crop` (array of integer, optional): The rectangle of the screen each PNG holds, `[x, y, width, height]`. Left out, the whole screen.
- `dest` (string, default `""`): A new folder for the series, absolute or starting with `~`, which outlives `close`. Left empty, a folder in the session's temporary folder, deleted at `close`.
- `capture_path` (string, default `""`): The video to take the frames from, such as one `record` wrote. Left empty, the largest video of a session started with `capture_video`.

### What comes back

- `manifest`: The path of the series' manifest, `manifest.json`; the PNGs sit beside it, named by frame as `f000123.png`.
- `count`: How many frames were written; `first` and `last` are their lowest and highest numbers.
- `distinct`: How many different pictures the series holds. One means nothing changed on screen.
- `kept_after_close`: `true` when the series is in a `dest` you named, `false` when `close` deletes it.
- `capture_path`: The video the frames came from.

<details><summary>All 10 reply fields</summary>

- `capture_path` (string)
- `count` (integer)
- `crop` (array)
- `distinct` (integer)
- `first` (integer)
- `frame_source` (string)
- `frames_asked` (integer)
- `kept_after_close` (boolean)
- `last` (integer)
- `manifest` (string)

</details>

### What it refuses

- Both `at_frames` and a range, or neither; a list that is not ascending; more than 1000 frames (`bad_argument`).
- A frame past the end of the video (`bad_argument`).
- A `crop` that leaves the frame, or a `dest` that exists or holds a `%` (`bad_argument`).
- No `capture_path`, in a session not started with `capture_video` (`no_channel`).
- No `capture_path`, in a session whose video is not written yet (`unexpected_answer`).
- A computer with no `ffmpeg` on its `PATH` (`host_failed`).

### Why it works this way

The frames come out of a video, so their numbers are the video's own, from 0 at its first frame. They are not the frames a stop's `frame` field counts since power-on.

The call reads a file and does not run the machine, so it answers while the program runs. A session started with `capture_video` can hold several videos: `captures` lists them, and `capture_path` picks one.

A `%` in `dest` is refused because `ffmpeg` would read the path as a numbering pattern and write somewhere else.

<details><summary>More on why</summary>

A video's frames are the size the emulator draws them: a 320x200 mode comes out 640x400, and a `crop` counts those pixels.

`frames_asked` is how many frames the call named, and `frame_source` says what the numbers count: `avi`, the video's own frames.

</details>

### Related tools

- [`image_compare`](files.md#image_compare)
- [`captures`](#captures)
- [`capture_frame`](#capture_frame)
- [`start`](session.md#start)
- [`record`](#record)

<details><summary>The contract your client receives</summary>

```text
Capture frames as PNGs plus a manifest (read by `image_compare`).

AVI frames from 0: `at_frames`, or `first`, `last`, `step`; max 1000. `crop`:
`[x, y, w, h]`. `dest`: new directory, kept after `close`.

Reply: `manifest`, `count`, `first`, `last`, `distinct`, `kept_after_close`, `capture_path`,
`crop`. Refused: `bad_argument` (frame, crop, `dest`), `no_channel` (no `capture_video`),
`unexpected_answer` (no capture), `host_failed` (no `ffmpeg`).

Reference: REFERENCE.md, Media files.
```

</details>
<!-- scry-reference:end series_capture -->

<!-- scry-reference:begin snapshot -->
## `snapshot`

Save a still of the screen as it is now to a PNG file.

```text
snapshot(dest="", seconds=10.0)
```

### Try it

On Bricks, the game this repository builds, while the game runs with the mouse holding the paddle.

Ask:

> Save a picture of the screen as it is now to held.png, without stopping the game.

Call:

```text
snapshot(dest="./tmp/demos/tour/files/held.png")
```

Reply, 2 of 6 fields:

```json
{
  "route": "guest",
  "path": "./tmp/demos/tour/files/held.png"
}
```

The `route` named `guest` is the way used while the program runs: the picture is taken inside the emulated machine. The file is at `path`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "route": "guest",
  "path": "./tmp/demos/tour/files/held.png",
  "bytes": "<volatile>",
  "sha256": "<volatile>"
}
```

</details>

### Arguments

- `dest` (string, default `""`): A new path for the PNG, absolute or starting with `~`. Left empty, the emulator's capture folder.
- `seconds` (number (> 0, <= 600.0), default `10.0`): While the program runs: how long to wait for the picture, in seconds. Left out, 10; not used at a stop.

### What comes back

- `path`: The PNG.
- `sha256`: The file's SHA-256: the value a line of reference checksums holds for `image_compare(method="golden")`.
- `route`: How the still was taken: `guest` while the program ran, `video_memory` at a stop.

<details><summary>All 4 reply fields</summary>

- `bytes` (integer)
- `path` (string)
- `route` (string)
- `sha256` (string)

</details>

### What it refuses

- While the program runs: a session with no `logfile`, or with no input helper announced in its log (`no_channel`).
- While the program runs: no new PNG within `seconds` (`wait_expired`).
- At a stop: a screen in a text mode, which has no picture (`no_channel`).
- A `dest` that exists or is relative (`bad_argument`).

### Why it works this way

The still is taken one of two ways, chosen by whether the program runs. While it runs, the input helper inside DOS takes the screenshot, with no window or menu involved.

At a stop no frame is being drawn, so the still is decoded from video memory as `screen_view` decodes it: unscaled, and without running the machine. A text mode has no picture there; `screen_view` reads its text.

The running way needs a session started with `logfile`. Only the log says which input helper is loaded, and an older one would read the command as the Delete key.

### Related tools

- [`captures`](#captures)
- [`image_compare`](files.md#image_compare)
- [`screen_view`](screen.md#screen_view)
- [`record`](#record)
- [`capture_frame`](#capture_frame)

<details><summary>The contract your client receives</summary>

```text
A still of the screen as a PNG, at `dest` if given (absolute or `~`-led, new). Running: taken
in the guest into the captures directory within `seconds` (`route` `guest`; `wait_expired` when
none appears); refused with no `logfile` or no stub in the log. At a stop: written from video
memory through `screen_view`'s decoder (`route` `video_memory`), unscaled, without running the
machine; a text mode is refused (`no_channel`), and `seconds` is not used.

Reply: `route`, `path`, `bytes`, `sha256`.
```

</details>
<!-- scry-reference:end snapshot -->

<!-- scry-reference:begin record -->
## `record`

Record an exact number of frames of the screen to an AVI video, then stop the program again.

```text
record(frames, dest="", seconds=60.0)
```

### Try it

On Bricks, the game this repository builds, stopped in play at frame 36, shortly before the ball knocks down its second brick.

Ask:

> Record the next 110 frames of the screen to a video named second-brick.avi.

Call:

```text
record(frames=110, dest="./tmp/demos/tour/files/second-brick.avi", seconds=60)
```

Reply, 9 of 25 fields:

```json
{
  "summary": "record 110 frames: ELAPSED, 109 frames at ./tmp/demos/tour/files/second-brick.avi",
  "verdict": "ELAPSED",
  "frame_before": 36,
  "frame_after": 146,
  "kind": "avi",
  "frames": 110,
  "began": true,
  "ended": true,
  "avi_frames": 109
}
```

`ELAPSED` means the 110 frames ran, from frame 36 to 146, and the capture was turned off (`ended`). The file holds 109 frames: the first frame of this run wrote none.

<details><summary>The whole reply</summary>

```json
{
  "summary": "record 110 frames: ELAPSED, 109 frames at ./tmp/demos/tour/files/second-brick.avi",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 110,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 146,
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 182, "y": 88, "dx": -2, "dy": 2},
      "bytes": "<volatile>"
    },
    {
      "ref": "score",
      "by": "symbol",
      "mode": "count",
      "length": 2,
      "fmt": "u16",
      "tally_id": "1",
      "addr": "08DF:000005C9",
      "installed": true,
      "state": "tallied",
      "total": 1,
      "since_last_stop": 1,
      "overflow_values": 0,
      "overflow_pcs": 0
    },
    {
      "ref": "paddle_x",
      "by": "symbol",
      "mode": "capture",
      "length": 1,
      "fmt": "u8",
      "tally_id": "2",
      "addr": "08DF:000005D3",
      "trigger_type": "r",
      "installed": true,
      "state": "captured",
      "total": 110,
      "since_last_stop": 110,
      "rows_path": "<volatile>",
      "rows_kept": 110,
      "overflow_rows": 0,
      "rows_max": 100000
    }
  ],
  "cause": "<volatile>",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 6"], "mark": "<volatile>"},
  "stop_seq": 8,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 36,
  "frame_after": 146,
  "cycles": 3594703,
  "kind": "avi",
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/tour/files/second-brick.avi",
  "bytes": "<volatile>",
  "avi_frames": 109
}
```

</details>

### Arguments

- `frames` (integer, required): How many frames of the emulated display to record: 2 or more.
- `dest` (string, default `""`): An absolute `.avi` path that does not exist yet. Left empty, the file goes to the session's temporary folder, deleted at `close`.
- `seconds` (number (> 0, <= 600.0), default `60.0`): The time limit of the whole call, in seconds of your clock. Left out, 60.

### What comes back

- `path`: The AVI, once the reply has read it back as a finished file.
- `avi_frames`: How many frames the file's own header says it holds.
- `ended`: `true` once the capture is turned off. `false` when it could not be: there is no `path`, and it records until `close`.
- `verdict`: How the run ended, as `run_for` reports it: `ELAPSED` when every frame ran, `TIMEOUT` when `seconds` ran out first.

<details><summary>All 26 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `cycles` (integer or object)
- `e9` (object)
- `emulated_after_s` (number or object)
- `emulated_before_s` (number)
- `enrichment` (object)
- `frame` (integer or object)
- `frame_after` (integer or object)
- `frame_before` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string or object)
- `polls` (integer)
- `regs` (object)
- `retrace_pending` (boolean)
- `stop_seq` (integer)
- `verdict` (string)
- `watches` (array)
- `avi_frames` (integer)
- `began` (boolean)
- `bytes` (integer)
- `ended` (boolean)
- `frames` (integer)
- `kind` (string)
- `path` (string or object)

</details>

### What it refuses

- `frames` under 2, or a `dest` that is not a new `.avi` path (`bad_argument`).
- A machine that is running (`not_stopped`).
- A video capture already on, as in a session started with `capture_video` (`no_channel`).
- A build whose debugger has no `CAPTURE` command (`no_channel`).
- A file that does not read back as a finished AVI with a frame in it (`readback_refused`).

### Why it works this way

The recording is counted in frames of the emulated display, one per vertical retrace, so no time of your clock goes into the file. The debugger's `CAPTURE` command turns the video on at this stop and off at the stop the run reaches.

No window or menu is involved, so a session with no window records as one with a window does. A video already on is refused, never ended by a second switch.

One frame is written per frame run, but a run can write none for its first. The run from the stop `start` leaves is one: the display has drawn nothing yet.

<details><summary>More on why</summary>

The capture is turned off whatever the run did, a cancelled call included. One that could not be turned off answers `ended: false`.

The reply is also a stop: it carries `verdict` and the fields `run_for` returns, with the readings taken at each stop.

</details>

### Related tools

- [`captures`](#captures)
- [`snapshot`](#snapshot)
- [`audio_record`](#audio_record)
- [`run_for`](run.md#run_for)
- [`capture_frame`](#capture_frame)

<details><summary>The contract your client receives</summary>

```text
Record exactly `frames` retraces of the screen to an AVI, then stop. Needs the machine
STOPPED and a build whose debugger has `CAPTURE`; headless or windowed.

`dest`: an absolute `.avi` path not there yet; empty lands in the session's scratch, gone at `close`, and the reply names it either way. `frames` is 2 or more. `seconds` bounds the wait for the recording. The AVI is read before its path is given.

One frame is written per retrace, but none for the first from the stop `start` leaves.
A run cut at that bound is released before the reply: when the release answers, the reply says `ended: true` and names the AVI it read back, and a file that does not read as finished is INVALID. A capture that could not be turned off is `ended: false`, no `path`, and
records until `close`.

Refused: `frames` under 2, a video capture already on (`capture_video`), a build with no
`CAPTURE`, a running machine.

Reply, once answered: `verdict`, `frames`, `path`, `began`, `ended`, `bytes`, `avi_frames`, `kind`, `note`, the run's fields as `run_for` gives
them, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause`, `regpoint_hit` (a registerpoint stopped it) and `e9`.

Reference: REFERENCE.md, Input and the screen.
```

</details>
<!-- scry-reference:end record -->

<!-- scry-reference:begin audio_record -->
## `audio_record`

Record an exact number of frames of sound to a WAV, a DRO or a MIDI file, then stop the program again.

```text
audio_record(frames, dest="", seconds=60.0, kind="wav")
```

### Try it

On Minesweeper, a game this repository builds, stopped a few frames after a click on a mine, with the explosion already sounding.

Ask:

> Record the sound of the next 45 frames to a file named boom.wav.

Call:

```text
audio_record(frames=45, dest="./tmp/demos/mines/boom.wav")
```

Reply, 9 of 30 fields:

```json
{
  "summary": "audio_record wav 45 frames: ELAPSED, 30768 samples at 48000  ... (92 characters)",
  "verdict": "ELAPSED",
  "kind": "wav",
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 30768,
  "emulated_s": 0.6413212,
  "sample_min": -18099,
  "sample_max": 18479
}
```

A stereo WAV of 30768 samples, about 0.64 emulated seconds. `sample_min` and `sample_max` are far apart, so the recording is not silent.

<details><summary>The whole reply</summary>

```json
{
  "summary": "audio_record wav 45 frames: ELAPSED, 30768 samples at 48000 Hz at ./tmp/demos/mines/boom.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 45,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "frame": 945,
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x00000fe3",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 668,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "emulated_before_s": 12.818086224999998,
  "emulated_after_s": 13.459407425,
  "frame_before": 900,
  "frame_after": 945,
  "cycles": 1789674,
  "kind": "wav",
  "frames": 45,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 123116,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 30768,
  "emulated_s": 0.6413212,
  "sample_min": -18099,
  "sample_max": 18479
}
```

</details>

### The three kinds

| kind | what is recorded |
|---|---|
| `wav` | The mixer's output: everything the machine plays, as samples. |
| `dro` | The writes to the OPL chip's registers, as a DRO 2.0 file. |
| `mid` | The MIDI bytes the program sends, as a MIDI file. |

### Arguments

- `frames` (integer, required): How many frames of the emulated display the recording lasts: 1 or more.
- `dest` (string, default `""`): A path that does not exist yet, absolute or starting with `~`. Left empty, the file stays where the emulator wrote it.
- `seconds` (number (> 0, <= 600.0), default `60.0`): The time limit of the whole call, in seconds of your clock. Left out, 60.
- `kind` (one of `"wav"`, `"dro"`, `"mid"`, default `"wav"`): `wav`, `dro` or `mid`, as above. Left out, `wav`.

### What comes back

- `path`: The file, once it has been checked. Unavailable, with the reason, when the run had no OPL note or MIDI byte.
- `emulated_s`: For a WAV: the emulated time the recording spans, in seconds.
- `sample_min`: For a WAV: the lowest sample value, beside `sample_max`. The two equal mean a constant level: silence.
- `opl_pairs`: For a DRO: how many register writes and delays the file holds; `opl_ms` is its length in milliseconds.
- `files`: For a DRO, when the OPL writer began a new file during the run: every file, each with its `path` and `bytes`.
- `ended`: `true` once the capture is turned off. `false` when it could not be: there is no `path`, and it records until `close`.

<details><summary>All 35 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `cycles` (integer or object)
- `e9` (object)
- `emulated_after_s` (number or object)
- `emulated_before_s` (number)
- `enrichment` (object)
- `frame` (integer or object)
- `frame_after` (integer or object)
- `frame_before` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string or object)
- `polls` (integer)
- `regs` (object)
- `retrace_pending` (boolean)
- `stop_seq` (integer)
- `verdict` (string)
- `watches` (array)
- `began` (boolean)
- `bytes` (integer)
- `channels` (integer)
- `emulated_s` (number or object)
- `ended` (boolean)
- `files` (array of object)
- `frames` (integer)
- `kind` (string)
- `midi_bytes` (integer)
- `opl_ms` (integer)
- `opl_pairs` (integer)
- `path` (string or object)
- `sample_max` (integer)
- `sample_min` (integer)
- `sample_rate_hz` (integer)
- `samples` (integer)

</details>

### What it refuses

- `frames` under 1, or a `dest` that exists (`bad_argument`).
- A machine that is running (`not_stopped`).
- That kind of capture already on, or a build whose debugger has no `CAPTURE` command (`no_channel`).
- A WAV that holds no sample, or whose samples miss the run's emulated time by more than 2 mixer ticks (`readback_refused`).
- A DRO or a MIDI file whose header disagrees with the file (`readback_refused`).

### Why it works this way

The recording is counted in frames of the emulated display, as [`record`](#record) counts them: `CAPTURE` turns the kind on at this stop and off at the stop the run reaches. The file holds what was emulated in between.

Each file is checked before its path is given. A WAV's header must agree with its file, whose two sizes the emulator fills only at close, and its samples with the run's emulated time. The mixer works in ticks of an emulated millisecond, so one tick at each end is allowed.

Silence is reported, never refused: it is a fact about the program. The OPL writer opens its file at the first note and the MIDI writer at the first byte, so a run with neither has no file.

<details><summary>More on why</summary>

A `readback_refused` that comes and goes is the configuration's clock first. When your computer cannot run the program's fixed cycles in real time, the mixer loses whole blocks and the WAV falls short. Lower the fixed `cycles` and record again.

- A DRO must be a DRO 2.0 file whose header's length is the file's: the register state at its first event, then each write.
- A MIDI file must be a header and a track whose length reaches the end of the file; `midi_bytes` counts its events' bytes.
- The OPL writer begins a new file after half a minute of emulated silence. `path` is then the last file, and the checks and counts are that file's alone.

</details>

### Related tools

- [`audio_compare`](files.md#audio_compare)
- [`captures`](#captures)
- [`record`](#record)
- [`run_for`](run.md#run_for)

<details><summary>The contract your client receives</summary>

```text
Record exactly `frames` retraces of sound, then stop: the mixer to a WAV (`kind`
`wav`), the OPL register writes to a DRO (`dro`) or the MIDI bytes to a MIDI file
(`mid`). Needs the machine STOPPED and a build whose debugger has `CAPTURE`.

`dest`: an absolute or `~`-led path not there yet; empty leaves the file where the emulator
wrote it. `seconds` bounds the wait for the recording. The file is checked before its path is
given (a rolled-over OPL run: the last); a WAV whose samples miss the run's emulated span by
more than 2 mixer ticks is INVALID. Silence is reported, never refused; a run with no
OPL note or MIDI byte has no file (`path` unavailable). A run cut short is checked for what it
holds; a capture that could not be turned off is `ended: false`, no `path`, and records until
`close`.

Refused: `frames` under 1, that kind already on, a build with no `CAPTURE`, a running
machine.

Reply: `verdict`, `kind`, `frames`, `began`, `ended`, `path` (none if the capture could not be
turned off), `bytes` (a file was written); a WAV's `channels`, `sample_rate_hz`, `samples`,
`emulated_s`, `sample_min`, `sample_max`; a DRO's `opl_pairs`, `opl_ms` (the last file's);
`files` (each `path`, `bytes`) when the OPL writer rolled over to a new file, `path` then the
last; a MIDI file's `midi_bytes`; `note`, the run's fields, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause`, `regpoint_hit` (a registerpoint stopped it) and `e9`.

Reference: REFERENCE.md, Input and the screen.
```

</details>
<!-- scry-reference:end audio_record -->
