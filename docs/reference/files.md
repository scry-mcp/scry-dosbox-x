# The Files tools

### The file tools

The file tools (`image_compare(method="image")`, `image_compare(method="series")`, `image_compare(method="region")`, `image_compare(method="golden")`) read files and touch no machine, so they answer with the guest running or with none. Every comparison carries its control, because a result that cannot come out the other way is no result: a series whose frames never change says nothing about another (`control_silent`), two series with no frame in common compare nothing, a region whose measure never moves was missed, goldens meeting no file examined nothing. A manifest is re-hashed and re-signed on reading, so a frame changed since, or a row edited by hand, is refused.

### Screen maps

A screen map is a file, `<application>.scry-map.json`, kept in the application's own repository, in the format `scry-map/1`.

```json
{"format": "scry-map/1", "application": "bricks",
 "screens": [{"name": "play", "kind": "pixel", "size": [320, 200],
              "match": [{"crop": [0, 0, 52, 8], "signature": "<16 hex>"}],
              "controls": [{"name": "court", "rect": [200, 80, 80, 40]}]}]}
```

Everything is in the screen's own units, as `screen_view` counts them. A screen is known by the signatures of regions that stay still on it, never by the whole screen, which a cursor, a ball or an animated colour changes between stops: bricks' map signs the words `SCORE` and `LIVES` and none of their digits. A screen matches when its `kind` and `size` are the screen's and every region's signature is. A file with a duplicate name or a rectangle off its screen is refused whole.

**Two layers, both kept by the server.** The FILE layer (`map_write(method="load")`) survives a `start`; the SESSION layer (`map_write(method="add")`) is emptied by it, since its screens were read off another run. `map_find` tries the session's screens first. `map_write(method="save")` writes both as one file, the session winning, and that file becomes the file layer. `map_write(method="load")` and `map_write(method="save")` touch files only, so they answer while the guest runs.

**A control is named against the identification it came from.** The guest has to run for the pointer to move and a running guest cannot be read, so the click acts on the screen as last identified. A guest showing a screen of another kind or size is `needs_call`; what is drawn is not reported, so a changed screen of the same mode is yours to catch: `map_find` again after anything that may have changed it.

**In an export**, `map_write(method="load")` and `map_write(method="add")` are steps, so a replay knows the map an identification was made against; `map_find` is a check; `map_write(method="save")` is dropped, since a replay would find its file there. A `send_mouse` never reaches an export: it needs the guest running, and the export cuts at the release before it.












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
  "method": "region",
  "manifest": "$TMPDIR/dosbox-x-session-xgqgp8b6/series/series-1/manifest.json",
  "measure": "changed_pixels"
}
```

```json
{
  "summary": "image_compare region: changed_pixels, 1 transition over 5 frames",
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
  "path": "$TMPDIR/dosbox-x-session-xgqgp8b6/series/series-1/track-1.json",
  "manifest": "$TMPDIR/dosbox-x-session-xgqgp8b6/series/series-1/manifest.json"
}
```
<!-- scry-reference:end image_compare -->

Replies echo the arguments they were given (`a`, `b`, `crop`, `shift`, `tolerance`, `manifest`, `dir`, `checksums`).
