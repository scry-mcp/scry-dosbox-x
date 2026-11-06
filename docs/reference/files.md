# The Files tools

## The file tools

The file tools (`image_compare(method="image")`, `image_compare(method="series")`, `image_compare(method="region")`, `image_compare(method="golden")`, `audio_compare(method="measure")`, `audio_compare(method="diff")`) read files and touch no machine, so they answer with the guest running or with none. Every comparison carries its control, because a result that cannot come out the other way is no result: a series whose frames never change says nothing about another (`control_silent`), two series with no frame in common compare nothing, a region whose measure never moves was missed, goldens meeting no file examined nothing, and two silent recordings are refused (`control_silent`) rather than called equal. A manifest is re-hashed and re-signed on reading, so a frame changed since, or a row edited by hand, is refused.

## Screen maps

A screen map is a file, `<application>.screen-map.json`, kept in the application's own repository (a game both servers run keeps one map, beside its script in scry-core), in the format `scry-screen-map/1`.

```json
{"format": "scry-screen-map/1", "application": "bricks", "mode": "verified",
 "screens": [{"name": "play", "kind": "pixel", "size": [320, 200], "anchor": "main_loop",
              "match": [{"crop": [0, 0, 52, 8], "signature": "<16 hex>"}],
              "controls": [{"name": "court", "rect": [200, 80, 80, 40]}]}]}
```

Everything is in the program's own units, cells in a text mode and pixels in a graphics one, as `screen_view` counts them. A screen is known by the signatures of regions that stay still on it, never by the whole screen, which a cursor, a ball or an animated colour changes between stops: bricks' map signs the words `SCORE` and `LIVES` and none of their digits. A screen matches when its `kind` and `size` are the screen's and every region's signature is. A screen may instead say `"cells": "index"` (`screen_map_write(method="add", cells="index")`): its regions are then signed by the palette index each pixel was drawn with, not by the colour it shows, so one map knows a program on two machines whose palettes resolve one index to different colours. That needs a screen drawn through the DAC (a 15-, 16- or 32-bit linear mode has none): on any other it is refused `no_channel`. A screen that says nothing is signed in colour. A file with a duplicate name or a rectangle off its screen is refused whole.

**Who answers for a map.** `mode` is required. A `verified` map belongs to a program still being written, so every way into a screen judges its signatures and a stale map is caught by the server: `run_to(screen=)` runs to the screen's `anchor` and refuses `stale_map` when the screen there no longer matches, leaving the guest at the anchor. A `consolidated` map belongs to a finished program whose authors keep it current: every screen names its `anchor`, the symbol after which it is whole, and `run_to(screen=)` takes the screen as shown there without a read, so its controls can be clicked at once. `screen_map_find` judges the signatures on either mode, when asked.

**A port that shows the picture larger.** One program drawn in two video modes keeps one map in the units it draws in. A mode that doubles it inside a border, a 320x200 game shown in 640x480, is described at `load` by an integer `scale` and a `margin` [x, y] in the screen's own pixels on each side, so the screen is the program's size times the scale plus twice the margin. A read is sampled back into the program's units before it is signed, and a control's centre is aimed in the screen's. A read of a size the view does not fit answers `view_fits: false`.

**Two layers, both kept by the server.** The FILE layer (`screen_map_write(method="load")`) survives a `start`; the SESSION layer (`screen_map_write(method="add")`) is emptied by it, since its screens were read off another run. `screen_map_find` tries the session's screens first. `screen_map_write(method="save")` writes both as one file, the session winning, and that file becomes the file layer. `screen_map_write(method="load")` and `screen_map_write(method="save")` touch files only, so they answer while the guest runs.

**A control is named against the identification it came from.** The click acts on the screen `screen_map_find` last identified. Before the pointer moves, only the kind and size of what the guest shows are read again, off the stub's report, which answers whether the guest runs or is parked; a guest showing a screen of another kind or size is `needs_call`. What is drawn is not compared again, so a changed screen of the same mode is yours to catch: `screen_map_find` again, at a stop, after anything that may have changed it.

**A program that keeps a pointer of its own** (it integrates the driver's motion and clamps the sum at the screen's edges, so after a clamp the two disagree) is steered by its map. The map declares, once, `"pointer": {"x": ref, "y": ref, "bytes": 2}`: the symbols or `SEG:OFF` where the program holds it, in its own units. A `send_mouse` to a place on a stopped machine then moves the driver, reads that pointer, and nudges the driver by the gap (learning the ratio from the first nudge, at most four times) before any button goes; `arrived` is whether the program's pointer is on the place, and `pointer.program` says where it ended and how many nudges it took. A driver at its edge loses the motion its program never sees, so the program's pointer can lag it by more than the room left to move: when four nudges do not reach the place the driver is swept once to the top-left and the bottom-right corners, where each pointer clamps and the two agree again, and the nudges start over (`corrections` then counts both rounds, eight at most). The guest sees that sweep, so a program that tracks a held button across separate calls sees the pointer cross the screen. A guest that runs cannot be read, so it is moved as ever, and a drag's end is not steered. A pointer that still does not arrive ends `arrived: false`, and `pointer.program.reach` gives the span (`x` and `y`, low and high) the program's pointer took at the driver's two corners: a program can show the driver's range on a window of its screen, and an aim outside that window cannot be reached by moving the driver. **A protected-mode program's pointer is read by linear address from a real-mode stop.** A `send_mouse` to a stopped machine ends on a retrace that is often inside a BIOS handler, in real mode, where the debugger addresses a `SEG:OFF` of 16-bit offsets and no further, and a DPMI program's data sits above the first megabyte. When the build's debugger has `MEMDUMPLIN` (it reads by linear address through the page tables CR3 holds, with paging on or off) and the table was loaded at a protected-mode stop with `base_from` a register (`DS`, or `CS` in a flat program), the pointer's symbols are placed as that register's base plus their offset and read that way, and the move is steered as at any other stop. A table with a base given by hand, or placed by `start(symbols=)` from the program's DOS load segment (which is not where a DPMI program's data is), and a build without the command have no way in: the call is refused (`unknown_ref` for a symbol, `bad_argument` for an explicit address) and the move is not steered. An Allegro program can also be made to read the driver instead: `mouse = I33` under `[mouse]` in its `allegro.cfg` (*The driver's pointer is the one placed*, [Input and the screen](input.md)).

**In an export**, `screen_map_write(method="load")` and `screen_map_write(method="add")` are steps, so a replay knows the map an identification was made against; `screen_map_find` is a check; `screen_map_write(method="save")` is dropped, since a replay would find its file there. A `send_mouse` sent to a stopped machine is a step like any input to one ([Input and the screen](input.md), *The route*); one sent while the guest runs never reaches an export, which cuts at the release before it.

<!-- scry-reference:begin image_compare -->
## `image_compare`

*Compare pictures*

```text
image_compare(method, a="", b="", crop=null, shift=null, tolerance=null, manifest="", measure="", ref="", threshold=null, limit=null, dir="", checksums="")
```

Compare PNGs, series or a region of one, in numbers. `crop` [x, y, w, h]; `limit` 1..1000
(default 40) cuts a list, its count beside it. Replies also echo the arguments they took.

`image`: PNGs `a`, `b`; two sizes need `crop`; `shift` [dx, dy] moves `b`; `tolerance`
0..255. Reply: `differing_pixels`, `bbox`, `max_delta`, `width`, `height`.

`series`: `scry-series/1` manifests `a`, `b`. Reply: `pairs`, `identical`, `differing`,
`first_differing`, `only_in_a`, `only_in_b`.

`region`: `crop` of `manifest` by `measure`: `signature`, `changed_pixels`, or `match`
against `ref` at `threshold` (0.98). Reply: `start`, `transitions`, `gaps`,
`transitions_total`, `frames`, `path`.

`golden`: `manifest` or `dir` against `checksums` (`shasum -a 256`). Reply: `matched`,
`differing`, `missing`, `extra`, `differing_total`, `missing_total`, `extra_total`.

Refused: an argument the method does not take; `control_silent` when nothing can differ.

Reads files, and `region` writes one, `path`: it needs no machine. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `method` | one of `"image"`, `"series"`, `"region"`, `"golden"` | required |
| `a` | string | `""` |
| `b` | string | `""` |
| `crop` | array of integer or null | `null` |
| `shift` | array of integer or null | `null` |
| `tolerance` | integer or null | `null` |
| `manifest` | string | `""` |
| `measure` | string | `""` |
| `ref` | string | `""` |
| `threshold` | number or null | `null` |
| `limit` | integer or null | `null` |
| `dir` | string | `""` |
| `checksums` | string | `""` |

| reply field | type |
|---|---|
| `a` | object or string |
| `b` | object or string |
| `bbox` | array or object |
| `checksums` | string |
| `crop` | array |
| `differing` | integer or array |
| `differing_pixels` | integer |
| `differing_total` | integer |
| `dir` | string |
| `extra` | array |
| `extra_total` | integer |
| `first_differing` | object |
| `frames` | integer |
| `gaps` | array |
| `height` | integer |
| `identical` | integer |
| `manifest` | string |
| `matched` | integer |
| `max_delta` | array |
| `measure` | string |
| `missing` | array |
| `missing_total` | integer |
| `only_in_a` | array |
| `only_in_b` | array |
| `pairs` | integer |
| `path` | string |
| `shift` | array |
| `start` | array or object |
| `tolerance` | integer |
| `transitions` | array |
| `transitions_total` | integer |
| `width` | integer |

Example, from a live run:

```json
{
  "method": "image",
  "a": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/P/n22-away.png",
  "b": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/P/n21-away.png"
}
```

```json
{
  "summary": "image_compare image: no pixel differs over 48x40 at [0, 0]",
  "status": "ok",
  "differing_pixels": 0,
  "bbox": {"available": false, "why": "no pixel differs"},
  "max_delta": [0, 0, 0],
  "width": 48,
  "height": 40,
  "crop": [0, 0, 48, 40],
  "shift": [0, 0],
  "tolerance": 0,
  "a": {
    "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/P/n22-away.png",
    "sha256": "53b883b4f3a951b66be1a08574b075740bb0c26493474fbd18fb4eb3af116be5"
  },
  "b": {
    "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/P/n21-away.png",
    "sha256": "53b883b4f3a951b66be1a08574b075740bb0c26493474fbd18fb4eb3af116be5"
  }
}
```
<!-- scry-reference:end image_compare -->

Replies echo the arguments they were given (`a`, `b`, `crop`, `shift`, `tolerance`, `manifest`, `dir`, `checksums`).

<!-- scry-reference:begin audio_compare -->
## `audio_compare`

*Measure or compare WAV recordings*

```text
audio_compare(method, path="", a="", b="", window=null, channel=null, align=null)
```

Measure a WAV or compare two, in numbers. 8- or 16-bit PCM; `window` [from_s, to_s],
seconds, default the whole file.

`measure`: `path`, every channel or `channel` (0 the first). Reply: `measures`, per channel
`channel`, `peak_dbfs`, `rms_dbfs`, `silent` (RMS under 0.5% of full scale),
`silence_spans` (under -60 dBFS for 50 ms or more), `onset_s` (over 2% of the peak),
`clipping_run` (flat at 95% of the peak or above), `clipped` (a run past 8); then
`sample_rate_hz`, `channels`, `bits`, `pcm_sha256`.

`diff`: `a` against the reference `b`, of one format; `align` (default true) meets the
onsets, then the waveforms; false compares from the starts. Reply: `exact`, `snr_db`,
`class` (`exact`; `inaudible` 60 dB or more; `audible` 30 to 60; `different`),
`envelope_correlation` (64-window envelopes), `onset_delta_ms`, `length_delta_samples`,
`aligned_by_samples`.

Refused: an argument the method does not take; `control_silent` when both are silent.

Reads files only: it needs no machine and alters nothing. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `method` | one of `"measure"`, `"diff"` | required |
| `path` | string | `""` |
| `a` | string | `""` |
| `b` | string | `""` |
| `window` | array of number or null | `null` |
| `channel` | integer or null | `null` |
| `align` | boolean or null | `null` |

| reply field | type |
|---|---|
| `a` | string |
| `b` | string |
| `aligned_by_samples` | integer |
| `bits` | integer |
| `channels` | integer |
| `envelope_correlation` | number |
| `exact` | boolean |
| `length_delta_samples` | integer |
| `measures` | array |
| `onset_delta_ms` | number |
| `path` | string |
| `pcm_sha256` | string |
| `sample_rate_hz` | integer |
| `snr_db` | number or object |
| `window` | array |
| `class` | string |

Example, from a live run:

```json
{
  "method": "measure",
  "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/T/n4.wav"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -6.97 dBFS, onset 0.0 s, ch1 peak -6.97 dBFS, onset 0.0 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": [0.0, 0.999],
  "measures": [
    {
      "channel": 0,
      "peak_dbfs": -6.97,
      "rms_dbfs": -14.86,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 5,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -6.97,
      "rms_dbfs": -14.86,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 5,
      "clipped": false
    }
  ],
  "pcm_sha256": "e60ff11bce0c03f6caa4a04e9e3654b9e40a70a8c156d9e6d2ec7c33a3703a62",
  "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/T/n4.wav"
}
```
<!-- scry-reference:end audio_compare -->

A model cannot listen, so a recording `audio_record` wrote is judged by these numbers. Each channel is measured and compared on its own, never mixed down first: a channel in antiphase would cancel, and two swapped channels would average to the same sound. `diff` meets the two onsets unless `align` is false, so a recording that starts a few samples later is not called different; with `align` false a recording made from the same stop on the same fixed clock is held sample for sample. Replies echo `path`, `a`, `b` and `window`; the sound itself never comes back.

<!-- scry-reference:begin guest_file -->
## `guest_file`

*What the guest left in a file*

```text
guest_file(path)
```

What the guest left at `path`, a host file `start(guest_files=)` fingerprinted before
the emulator booted: `absent`, `empty`, `unchanged` (the bytes and time from before the
run) or `written`. Reads the host's file, so it answers with the guest running or after
`close`.

Reply: `path`, `state`, `bytes`, `sha256`, `before` (`exists`, `bytes`, `sha256`),
`same_bytes` (written again with the bytes it held). INVALID `readback_refused` on the
first three, which hand nothing back; a path `start` did not name is refused.

Reference: REFERENCE.md, The guest's files.

| argument | type | default |
|---|---|---|
| `path` | string | required |

| reply field | type |
|---|---|
| `before` | object |
| `bytes` | integer |
| `path` | string |
| `same_bytes` | boolean |
| `sha256` | string |
| `state` | string |

Example, from a live run:

```json
{
  "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/Y/n1-dosio/OUT.TXT"
}
```

```json
{
  "summary": "guest_file /var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/Y/n1-dosio/OUT.TXT: written, 4 bytes",
  "status": "ok",
  "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/Y/n1-dosio/OUT.TXT",
  "state": "written",
  "before": {"exists": false},
  "bytes": 4,
  "sha256": "580175b2969134a0d8c6f325b442c6d25cf5b10f0643150ed45ffd3a8905bcba"
}
```
<!-- scry-reference:end guest_file -->

**The fingerprint is the size, the modification time and the SHA-256 together.** A file written
again with the same bytes moves its time, so it is `written`, with `same_bytes`, and never
`unchanged`; a file that keeps all three is the one from before the run. `close` judges each file
after the emulator has exited: on a clean `quit` every handle the guest left open has been closed
and flushed; an emulator that was killed may have left bytes unwritten. A file the host cannot
read (the guest made a directory of it) is `unreadable`, and `close` still closes.
