# The Captures tools

### Capturing what the screen shows

The video (`capture_video=True`, with a `program` for the recorder to wrap) is DOSBox-X's own doing and needs no keypress. A still of the running screen is `snapshot`, taken in the guest; a still out of a recording is `capture_frame`, an extraction that needs `ffmpeg`.

### A series

A series is one `scry-series/1` manifest (`server`, `source`, `crop`, a row per frame `{frame, path, sha256, bytes, signature}`) beside its PNGs; the frames are the AVI's own, numbered from 0, since DOS has no frame counter a stop can read.

<!-- scry-reference:begin captures -->
## `captures`

*List this session's captures*

```text
captures()
```

Lists the files the session's tools wrote, in write order, re-read now, then the
`capture_video` AVIs, largest last. Works on a running guest.

Reply: `captures` (each `kind`, `path`, `present`, `bytes`; an AVI also `riff_avi`,
`avi_frames`, `complete`). A file gone has `present: false`, no `bytes`.

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
  "summary": "captures: 5 files",
  "status": "ok",
  "captures": [
    {
      "kind": "bin",
      "path": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n733.bin",
      "present": true,
      "bytes": 16
    },
    {
      "kind": "png",
      "path": "$TMPDIR/dosbox-x-session-6nzxwtl8/gfx/palette-1.png",
      "present": true,
      "bytes": 1009
    },
    {
      "kind": "json",
      "path": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n880-stopped.scry-map.json",
      "present": true,
      "bytes": 312
    },
    {
      "kind": "trace",
      "path": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n954.trace",
      "present": true,
      "bytes": 238
    },
    {
      "kind": "tsv",
      "path": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n1058.comments.tsv",
      "present": true,
      "bytes": 85
    }
  ]
}
```
<!-- scry-reference:end captures -->

Two capture files is the normal case: the recording restarts when the guest changes video mode. `complete: false` is not damage; frames come out of such a file perfectly well. `program` is passed with `-c`, which runs after the config's `[autoexec]`: an autoexec ending in `exit` quits the emulator first, and a `captures` with no `avi` row is the symptom.

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
  "frame": 0,
  "dest": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n46.png"
}
```

```json
{
  "summary": "capture_frame: INVALID (no_session), there is no live session. `start` one first; a reply from a dead session would be a reading of nothing.",
  "status": "INVALID",
  "code": "no_session",
  "message": "there is no live session. `start` one first; a reply from a dead session would be a reading of nothing."
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
  "last": 1
}
```

```json
{
  "summary": "series_capture: INVALID (no_session), there is no live session. `start` one first; a reply from a dead session would be a reading of nothing.",
  "status": "INVALID",
  "code": "no_session",
  "message": "there is no live session. `start` one first; a reply from a dead session would be a reading of nothing."
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

A still of the running screen, taken in the guest into the captures directory within
`seconds`, moved to `dest` if given (absolute, new). Refused: parked at the debugger, no
`logfile`, no stub in the log.

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n515.png",
  "seconds": 10
}
```

```json
{
  "summary": "snapshot: INVALID (no_session), there is no live session. `start` one first; a reply from a dead session would be a reading of nothing.",
  "status": "INVALID",
  "code": "no_session",
  "message": "there is no live session. `start` one first; a reply from a dead session would be a reading of nothing."
}
```
<!-- scry-reference:end snapshot -->

The stub takes commands on the timer tick, so a parked machine cannot take one. Only the log says which stub is resident (the command is the Delete key's scan code to an older stub), hence the `logfile` requirement. No window or menu is needed, so any session works.
