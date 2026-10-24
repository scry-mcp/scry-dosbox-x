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

The files the tools below wrote and handed back, in the order they wrote them, re-read
now: `capture_frame`, `snapshot`, `memdump`, `machine_map`, `comment_save`, `perform_export`,
`map_save`, `screen_view` and `palette` (`kind` the extension), `series_capture` (`kind`
`series`, its manifest) and `trace`; then the video the emulator recorded with
`capture_video` (`kind` `avi`, in `captures_dir` or `capture/` under `cwd`), largest last,
two files being the normal case (the recording restarts when the guest changes video mode).
A file gone since is listed with `present: false` and no `bytes`; an empty list is an
answer. Works on a running guest.

Reply: `captures` (`kind`, `path`, `present`, `bytes`, and an AVI's `riff_avi`,
`avi_frames` and `complete`: the recording was finalised, `false` being information, not
damage).

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
      "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n733.bin",
      "present": true,
      "bytes": 16
    },
    {
      "kind": "png",
      "path": "$TMPDIR/dosbox-x-session-rmnni3t3/gfx/palette-1.png",
      "present": true,
      "bytes": 1009
    },
    {
      "kind": "json",
      "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n880-stopped.scry-map.json",
      "present": true,
      "bytes": 312
    },
    {
      "kind": "trace",
      "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n954.trace",
      "present": true,
      "bytes": 238
    },
    {
      "kind": "tsv",
      "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1058.comments.tsv",
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

ONE still image out of a capture, frame `frame`, written to `dest` as PNG whatever
the name says; `capture_path` defaults to the largest capture; both are absolute paths. Needs
`ffmpeg` (named when missing) and a session started with `capture_video`. Reply: `path`,
`bytes`, `sha256`, `capture_path` (the capture read), `frame`. A `%` anywhere in `dest` is
refused (ffmpeg would read the path as a template), and so is a `dest` already there: it is
never deleted or overwritten; a frame past the end is refused rather than a frameless file
handed back.

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/J/n11.png",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/J/n6-cap/screen_001.avi"
}
```

```json
{
  "summary": "capture_frame 2: 5072 bytes to $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/J/n11.png",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/J/n11.png",
  "bytes": 5072,
  "sha256": "aee93b1749a9c93112b4fca12509d5ad9da94fc94b41bf781612e590a0a4342b",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/J/n6-cap/screen_001.avi",
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

FRAMES OUT OF THE SESSION'S VIDEO CAPTURE, as PNGs and one manifest: the series
`series_diff`, `region_track` and `golden_check` read, with no picture in the reply. Needs
`ffmpeg` (named when missing) and a session started with `capture_video`.

The frames are the AVI's own, numbered from 0, NOT emulated frames: `at_frames` (a list,
ascending) or `first`, `last` and `step`, at most 1000. `capture_path`: an absolute
path of a capture, default the largest. `crop` `[x, y, width, height]` in the capture's pixels,
default the whole frame. `dest`: a new absolute directory, kept after `close`; else one in
the session's scratch, gone at `close` (`kept_after_close` says which). A `%` in `dest` is
refused (ffmpeg would read it as a template).

Reply: `manifest` (its path), `count`, `first`, `last`, `distinct` (signatures over the
crop), `frames_asked`, `kept_after_close`, `frame_source` (`avi`), `capture_path`, `crop`.
It answers on a running guest too: it reads the file. Refused: a frame past the capture's
end, a crop off its frames, a `dest` already there (`bad_argument`); a session with no
`capture_video` (`no_channel`), or no capture written yet (`unexpected_answer`); no
`ffmpeg`, or ffmpeg failing (`host_failed`).

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
  "crop": [
    0,
    0,
    320,
    8
  ],
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/Q/n1-cap/screen_001.avi"
}
```

```json
{
  "summary": "series_capture: 5 AVI frames 0..4, 2 distinct, manifest $TMPDIR/dosbox-x-session-2597ac8x/series/series-1/manifest.json",
  "status": "ok",
  "manifest": "$TMPDIR/dosbox-x-session-2597ac8x/series/series-1/manifest.json",
  "count": 5,
  "first": 0,
  "last": 4,
  "distinct": 2,
  "frames_asked": 5,
  "kept_after_close": false,
  "frame_source": "avi",
  "capture_path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/Q/n1-cap/screen_001.avi",
  "crop": [
    0,
    0,
    320,
    8
  ]
}
```
<!-- scry-reference:end series_capture -->

<!-- scry-reference:begin snapshot -->
## `snapshot`

*Snapshot the screen to a PNG*

```text
snapshot(dest="", seconds=10.0)
```

One still of the RUNNING screen, taken inside the guest through the input stub (no
window, no menu, any session), confirmed by the new `.png` under the captures directory
(`captures_dir`, or `capture/` under `cwd`) within `seconds`, and moved to `dest` when
given (absolute, its directory there, not there yet).
REFUSED with the machine parked at the debugger (the stub takes commands on the timer
tick), on a session with no `logfile` (the command is the Delete key's scan code to an
older stub, and only the log says which is resident), and on a guest whose log shows no
stub, as `send_keys` is.

Reply: `route: "guest"`, `path`, `bytes`, `sha256` (of the file).

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/P/n4.png",
  "seconds": 20
}
```

```json
{
  "summary": "snapshot: 885 bytes at $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/P/n4.png",
  "status": "ok",
  "route": "guest",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/P/n4.png",
  "bytes": 885,
  "sha256": "5053cd8f49a0d5bea6531db5520c7dfb0c06340f05b59d4baff51012d24313f5"
}
```
<!-- scry-reference:end snapshot -->
