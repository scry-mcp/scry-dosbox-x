# The Files tools

### The file tools

The file tools (`image_diff`, `series_diff`, `region_track`, `golden_check`) read files and touch no machine, so they answer with the guest running or with none. Every comparison carries its control, because a result that cannot come out the other way is no result: a series whose frames never change says nothing about another (`control_silent`), two series with no frame in common compare nothing, a region whose measure never moves was missed, goldens meeting no file examined nothing. A manifest is re-hashed and re-signed on reading, so a frame changed since, or a row edited by hand, is refused.

### Screen maps

A screen map is a file, `<application>.scry-map.json`, kept in the application's own repository, in the format `scry-map/1`.

```json
{"format": "scry-map/1", "application": "bricks",
 "screens": [{"name": "play", "kind": "pixel", "size": [320, 200],
              "match": [{"crop": [0, 0, 52, 8], "signature": "<16 hex>"}],
              "controls": [{"name": "court", "rect": [200, 80, 80, 40]}]}]}
```

Everything is in the screen's own units, as `screen_view` counts them. A screen is known by the signatures of regions that stay still on it, never by the whole screen, which a cursor, a ball or an animated colour changes between stops: bricks' map signs the words `SCORE` and `LIVES` and none of their digits. A screen matches when its `kind` and `size` are the screen's and every region's signature is. A file with a duplicate name or a rectangle off its screen is refused whole.

**Two layers, both kept by the server.** The FILE layer (`map_load`) survives a `start`; the SESSION layer (`map_add`) is emptied by it, since its screens were read off another run. `map_find` tries the session's screens first. `map_save` writes both as one file, the session winning, and that file becomes the file layer. `map_load` and `map_save` touch files only, so they answer while the guest runs.

**A control is named against the identification it came from.** The guest has to run for the pointer to move and a running guest cannot be read, so the click acts on the screen as last identified. A guest showing a screen of another kind or size is `needs_call`; what is drawn is not reported, so a changed screen of the same mode is yours to catch: `map_find` again after anything that may have changed it.

**In an export**, `map_load` and `map_add` are steps, so a replay knows the map an identification was made against; `map_find` is a check; `map_save` is dropped, since a replay would find its file there. A `send_mouse` never reaches an export: it needs the guest running, and the export cuts at the release before it.

<!-- scry-reference:begin image_diff -->
## `image_diff`

*Compare two pictures*

```text
image_diff(a, b, crop=null, shift=null, tolerance=0)
```

Compare two PNG files pixel by pixel, in the colours they show, and answer where they
differ without sending either picture.

`a`, `b`: paths of PNGs (8-bit, indexed or RGB). `crop` [x, y, width, height] is
the rectangle compared on both; it must lie inside both (it is never padded), and pictures
of two sizes need one. `shift` [dx, dy] compares pixel (x, y) of `a` with (x + dx, y + dy) of
`b`, over the part of the crop both stay in: a sprite that moved compares equal at its
move. `tolerance` (0..255) is the per-channel difference still counted equal.

Reply: `differing_pixels`, `bbox` ([x, y, w, h] in `a`'s pixels, unavailable when none
differ),
`max_delta` ([r, g, b], the largest channel difference seen), `width` and `height` (`a`'s),
`crop` (the rectangle of `a` compared), `shift`, `tolerance`, and `a` and `b` (`path`,
`sha256`).

Reads files only: it needs no machine and alters nothing. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `a` | string | required |
| `b` | string | required |
| `crop` | array of integer or null | `null` |
| `shift` | array of integer or null | `null` |
| `tolerance` | integer | `0` |

| reply field | type |
|---|---|
| `a` | object |
| `b` | object |
| `bbox` | array or object |
| `crop` | array |
| `differing_pixels` | integer |
| `height` | integer |
| `max_delta` | array |
| `shift` | array |
| `tolerance` | integer |
| `width` | integer |

Example, from a live run:

```json
{
  "a": "/nonexistent/a.png",
  "b": "/nonexistent/b.png"
}
```

```json
{
  "summary": "image_diff: INVALID (bad_argument), a: /nonexistent/a.png is not a file",
  "status": "INVALID",
  "code": "bad_argument",
  "message": "a: /nonexistent/a.png is not a file"
}
```
<!-- scry-reference:end image_diff -->

<!-- scry-reference:begin series_diff -->
## `series_diff`

*Compare two series*

```text
series_diff(a, b, crop=null)
```

Compare two series frame by frame, paired by frame number, after checking that each one
can tell frames apart at all.

`a`, `b`: paths of `scry-series/1` manifests (what `series_capture` writes); every
file a manifest lists is checked against its sha256 first. `crop` [x, y, width, height] is
compared on every frame of both, inside the PNGs. THE CONTROLS: a series whose every frame
has one signature over the crop is `control_silent` naming it, since it says nothing about
the other one; two series with no frame number in common are `control_silent` too.

Reply: `pairs`, `identical`, `differing`, `first_differing` (`frame`, `differing_pixels`,
`bbox`, or unavailable), `only_in_a` and `only_in_b` (frames with no partner, as [first, last]
runs), `crop` (the rectangle compared), and `a`, `b`.

Reads files only: it needs no machine and alters nothing. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `a` | string | required |
| `b` | string | required |
| `crop` | array of integer or null | `null` |

| reply field | type |
|---|---|
| `a` | string |
| `b` | string |
| `crop` | array |
| `differing` | integer |
| `first_differing` | object |
| `identical` | integer |
| `only_in_a` | array |
| `only_in_b` | array |
| `pairs` | integer |

Example, from a live run:

```json
{
  "a": "/nonexistent/a.json",
  "b": "/nonexistent/b.json"
}
```

```json
{
  "summary": "series_diff: INVALID (bad_argument), a: /nonexistent/a.json is not a file",
  "status": "INVALID",
  "code": "bad_argument",
  "message": "a: /nonexistent/a.json is not a file"
}
```
<!-- scry-reference:end series_diff -->

<!-- scry-reference:begin region_track -->
## `region_track`

*Track a region through a series*

```text
region_track(manifest, crop=null, measure="signature", ref="", threshold=0.98, limit=40)
```

Follow one region through a series and answer the frames where it changes, as numbers,
never as pictures.

`manifest`: the path of a `scry-series/1` manifest. `crop` [x, y, width, height],
inside its PNGs (default the whole picture). `measure`: `signature` (the region's
signature; a transition is a new one), `changed_pixels` (pixels changed since the previous
frame; a transition is a frame where any did), `match` (the fraction of the region equal to
`ref`, the path of a PNG of the crop's size; on at `threshold` or more, default
0.98, and a transition is a flip). `limit` (1..1000, default 40): transitions listed. THE
CONTROL: a measure that never changes over the series is `control_silent`, the crop having
missed.

Reply: `start` ([frame, value] at the first frame; unavailable for `changed_pixels`),
`transitions` ([frame, value]: the new signature, the count, or true/false), `gaps` (frame
numbers between consecutive transitions), `transitions_total`, `frames`, `measure`, `crop`
(the rectangle measured), `manifest`, and `path`, a JSON file beside the manifest holding
every transition and each frame's value; a list cut at `limit` says so in `omitted` and
`how`.

Reads files and writes one, `path`: it needs no machine. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `manifest` | string | required |
| `crop` | array of integer or null | `null` |
| `measure` | string | `"signature"` |
| `ref` | string | `""` |
| `threshold` | number | `0.98` |
| `limit` | integer | `40` |

| reply field | type |
|---|---|
| `crop` | array |
| `frames` | integer |
| `gaps` | array |
| `manifest` | string |
| `measure` | string |
| `path` | string |
| `start` | array or object |
| `transitions` | array |
| `transitions_total` | integer |

Example, from a live run:

```json
{
  "manifest": "$TMPDIR/dosbox-x-session-2597ac8x/series/series-1/manifest.json",
  "measure": "changed_pixels"
}
```

```json
{
  "summary": "region_track changed_pixels: 1 transition over 5 frames",
  "status": "ok",
  "measure": "changed_pixels",
  "crop": [
    0,
    0,
    320,
    8
  ],
  "frames": 5,
  "start": {
    "available": false,
    "why": "`changed_pixels` counts a change from the frame before, and the first frame has none"
  },
  "transitions": [
    [
      4,
      2560
    ]
  ],
  "gaps": [],
  "transitions_total": 1,
  "path": "$TMPDIR/dosbox-x-session-2597ac8x/series/series-1/track-1.json",
  "manifest": "$TMPDIR/dosbox-x-session-2597ac8x/series/series-1/manifest.json"
}
```
<!-- scry-reference:end region_track -->

<!-- scry-reference:begin golden_check -->
## `golden_check`

*Check files against goldens*

```text
golden_check(manifest="", dir="", checksums="", limit=40)
```

Check a series, or a directory of PNGs, against goldens written by `shasum -a 256`:
exact bytes, by file name.

ONE of `manifest`, the path of a `scry-series/1` manifest (its frames), or `dir`, a
directory (its `*.png`); and `checksums`, the path of a file of
`<sha256>  <name>` lines (the name's last part is matched, so a line may carry a directory).
A file and a golden that meet nowhere compare nothing, so no name in common is
`control_silent`; a line that does not parse is refused naming it.

Reply: `matched` (a count), `differing`, `missing` (goldens with no file) and `extra` (files
with no golden), each a sorted list of names cut at `limit` (1..1000, default 40) with its
whole count beside it (`differing_total`, `missing_total`, `extra_total`; a cut list says so
in `omitted` and `how`), and `checksums`, and `manifest` or `dir`.

Reads files only: it needs no machine and alters nothing. Every path is absolute or starts with `~`.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `manifest` | string | `""` |
| `dir` | string | `""` |
| `checksums` | string | `""` |
| `limit` | integer | `40` |

| reply field | type |
|---|---|
| `checksums` | string |
| `differing` | array |
| `differing_total` | integer |
| `dir` | string |
| `extra` | array |
| `extra_total` | integer |
| `manifest` | string |
| `matched` | integer |
| `missing` | array |
| `missing_total` | integer |

Example, from a live run:

```json
{
  "manifest": "/nonexistent/m.json",
  "checksums": "/nonexistent/g.sha256"
}
```

```json
{
  "summary": "golden_check: INVALID (bad_argument), checksums: /nonexistent/g.sha256 is not a file",
  "status": "INVALID",
  "code": "bad_argument",
  "message": "checksums: /nonexistent/g.sha256 is not a file"
}
```
<!-- scry-reference:end golden_check -->

<!-- scry-reference:begin map_load -->
## `map_load`

*Load a screen map*

```text
map_load(path)
```

An application's SCREEN MAP as the FILE layer, replacing any loaded one: its screens, each known by the `scry-sig/1` signatures of declared stable regions, and the named controls on each. `path`: `<application>.scry-map.json`, absolute or `~`-led. It lives for the server; a `start` keeps it. Any state, before a session too.

Reply: `path`, `application`, `screens`, `controls` (counts). Refused whole, naming the first fault: a file that is not `scry-map/1`, a name used twice, a rectangle off its screen, an `application` other than the file's name says (`bad_argument`).

Reference: REFERENCE.md, Screen maps.

| argument | type | default |
|---|---|---|
| `path` | string | required |

| reply field | type |
|---|---|
| `application` | string |
| `controls` | integer |
| `path` | string |
| `screens` | integer |

Example, from a live run:

```json
{
  "path": "/nonexistent/probe.scry-map.json"
}
```

```json
{
  "summary": "map_load: INVALID (bad_argument), path: no map file at /nonexistent/probe.scry-map.json",
  "status": "INVALID",
  "code": "bad_argument",
  "message": "path: no map file at /nonexistent/probe.scry-map.json"
}
```
<!-- scry-reference:end map_load -->

<!-- scry-reference:begin map_save -->
## `map_save`

*Save the screen map*

```text
map_save(dest, overwrite=false)
```

The file layer and the session layer written as ONE map, the session's screens winning, and that file made the file layer (the session's screens are `promoted`). `dest` is the file to write, named as `map_load`'s `path` is; one already there is refused unless `overwrite`. Any state.

Reply: `path` (the `dest` written), `application`, `screens`, `controls`, `promoted`. Refused: nothing mapped (`needs_call`); a `dest` not named as a map is, or there without `overwrite` (`bad_argument`).

Reference: REFERENCE.md, Screen maps.

| argument | type | default |
|---|---|---|
| `dest` | string | required |
| `overwrite` | boolean | `false` |

| reply field | type |
|---|---|
| `application` | string |
| `controls` | integer |
| `path` | string |
| `promoted` | array |
| `screens` | integer |

Example, from a live run:

```json
{
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n880-stopped.scry-map.json",
  "overwrite": true
}
```

```json
{
  "summary": "map_save: 1 screen to n880-stopped.scry-map.json, 1 promoted from the session",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n880-stopped.scry-map.json",
  "application": "n880-stopped",
  "screens": 1,
  "controls": 0,
  "promoted": [
    "probe_stopped"
  ]
}
```
<!-- scry-reference:end map_save -->
