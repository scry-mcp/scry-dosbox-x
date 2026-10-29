# The Screen tools

## The picture attached

A view's PNG goes to the session's scratch (`close` deletes it; `dest` keeps one) and is attached after the JSON. Past 1568 px a side, or 1568 tiles of 28 px, the API resamples, and a resampled picture of pixel art is a plausible wrong one: it is written and not attached, `not_inlined` says why, and the caller asks for a `crop` or a smaller `scale`. A picture inside a sequence's step is never attached, since only a reply's own picture crosses. The default `scale` is the largest integer factor that fits, so each pixel stays a square of one colour.

<!-- scry-reference:begin palette -->
## `palette`

*Read the palette*

```text
palette(first=0, count=0, scale=0, dest="")
```

The VGA DAC's 256 colours at this stop, read off the `VGA DAC` listings, with an indexed
PNG swatch. `first` and `count` (0 for all from `first`)
choose entries, `first + count` at most 256. `scale` 0 fits the largest enlargement up to 8;
`dest` a new path, else a scratch gone at `close`.

Reply: `entries`, `first`, `count`, `colors` (`#rrggbb`), `rgb`, `bits`, `pel_mask`,
`image`.

Refused: an entry past 255, a bad `scale`, a relative or existing `dest` (`bad_argument`);
a running guest (`not_stopped`); a DAC not six-bit (`unexpected_answer`); a picture not
taken whole (`host_failed`).

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `first` | integer (>= 0, <= 255) or string | `0` |
| `count` | integer (>= 0, <= 256) | `0` |
| `scale` | integer | `0` |
| `dest` | string | `""` |

| reply field | type |
|---|---|
| `bits` | integer |
| `colors` | array |
| `count` | integer |
| `entries` | integer |
| `first` | integer |
| `image` | object |
| `pel_mask` | string |
| `rgb` | array |

Example, from a live run:

```json
{
  "first": 0,
  "count": 2
}
```

```json
{
  "summary": "palette: entries 0 to 1 of 256; 256x128 PNG x8, inline",
  "status": "ok",
  "entries": 256,
  "first": 0,
  "count": 2,
  "colors": ["#000000", "#0000aa"],
  "rgb": ["000000", "00002a"],
  "bits": 6,
  "pel_mask": "ffh",
  "image": {
    "path": "$TMPDIR/dosbox-x-session-<run>/gfx/palette-1.png",
    "bytes": 1009,
    "sha256": "a5dff617e307a60f3bf521d96fed8809cc0f3b38409a74c904cfa5c1ad4371e1",
    "width": 256,
    "height": 128,
    "scale": 8,
    "indexed": true,
    "inline": true
  }
}
```
<!-- scry-reference:end palette -->

Each six-bit component is widened as the emulator renders it, its two top bits repeated below; `rgb` is each entry as `VGA DACPAL` printed it, three six-bit components in hex. Every pixel of the swatch is the entry's index into the DAC. The PNG is attached after the JSON when within the inline ceiling (1568 px a side, 1568 tiles of 28 px); `image` names it either way, with `indexed` and `border`. The listings cost a round trip each.

<!-- scry-reference:begin screen_view -->
## `screen_view`

*Read the screen*

```text
screen_view(mode="render", pens=null, point=null, crop=null, scale=0, dest="", attach=true)
```

What the screen shows at this stop, read from video memory: text as text, a graphics mode
as a PNG (256 colours chained or not, 16-colour planar, 8-, 15-, 16- or 32-bit linear; all
but chained through `VGAMEMDUMP`). `mode`: `render`, `isolate` (`pens`, 1..64,
in `isolate_color` over grey), `histogram` (pens used, no picture), `pixel` (`point`
`[x, y]`); the last three read a palette-indexed graphics mode, where a pen is the DAC entry
a pixel holds, and no `set_by` is answered. `crop` is `[x, y, width, height]` in characters
or pixels and narrows all but `pixel`. `scale` 0 fits the largest up to 8x; `dest` a new
path (else a scratch); `attach` false leaves it unattached.

Reply: `mode`, `vga_mode`, `kind`, `width`, `height`, `crop`, `display_start`; in text `text`,
`cursor`; in graphics `screen_indexed`, `entries` (indexed) and `image` (not for mode
histogram); `isolate`: `pixels`, `bbox`, `pens`, `isolate_color`; mode histogram: `histogram`,
`pens_used`, `unused`; `pixel`: `x`, `y`, `pen`, `color`, `point_in_crop`.

Refused: a relative or existing `dest`, a bad `scale`, `crop`, `mode`, `pens` or `point`, an
argument the mode ignores, `dest`/`scale`/`attach` in text or `histogram`, a `point` off the
screen (`bad_argument`); another mode or a build without `VGAMEMDUMP` (naming
`capture_frame`), an undecodable layout, or `isolate`/`histogram`/`pixel` on a text or
direct-colour mode (`no_channel`); a running guest (`not_stopped`); a DAC not six-bit
(`unexpected_answer`).

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `mode` | one of `"render"`, `"isolate"`, `"histogram"`, `"pixel"` | `"render"` |
| `pens` | array of integer or null | `null` |
| `point` | array of integer or null | `null` |
| `crop` | array of integer or null | `null` |
| `scale` | integer | `0` |
| `dest` | string | `""` |
| `attach` | boolean | `true` |

| reply field | type |
|---|---|
| `bbox` | array or object |
| `color` | string |
| `crop` | array |
| `cursor` | array or object |
| `display_start` | string |
| `entries` | integer |
| `height` | integer |
| `histogram` | array |
| `image` | object |
| `isolate_color` | string |
| `kind` | string |
| `mode` | string |
| `pen` | integer |
| `pens` | array |
| `pens_used` | integer |
| `pixels` | integer |
| `point_in_crop` | array |
| `screen_indexed` | boolean |
| `text` | array |
| `unused` | array |
| `vga_mode` | string |
| `width` | integer |
| `x` | integer |
| `y` | integer |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "screen_view M_TEXT: 80x25 at [0, 0] text, cursor at 0,4",
  "status": "ok",
  "vga_mode": "M_TEXT",
  "kind": "text",
  "width": 80,
  "height": 25,
  "mode": "render",
  "crop": [0, 0, 80, 25],
  "text": ["Z:\\>mount c \".\"", "Drive C is mounted as local directory ./", "Z:\\>c:", "C:\\>PROBE.COM", "", "", "... 19 more"],
  "cursor": [0, 4],
  "display_start": "0h"
}
```
<!-- scry-reference:end screen_view -->

**Every VGA mode is read, and none is read by touching the card.** Text and 13h's chained bytes come through the CPU's window; a planar 16-colour mode, an unchained 256-colour one (mode X) and an 8-, 15-, 16- or 32-bit linear mode come from the video RAM itself through the debugger's `VGAMEMDUMP`, since the window answers one plane per read in the first two and is smaller than the frame in the others. A build without that command refuses those modes naming it. A 16-colour pixel goes through the Attribute Controller to its DAC entry; a 15- or 16-bit one is widened to eight bits a channel by repeating its high bits. The 256-colour PNG's pixels are the bytes the guest wrote and its PLTE the DAC, so each pixel, doubled each way as the emulator renders 13h, equals the emulator's own capture.

**In protected mode the screen is read through a data segment that covers it** (the lowest present one of the GDT, then of the LDT), with paging on only when every page maps to the same physical address; none qualifying is `no_channel`.

Protected mode reads through a covering GDT or LDT segment. `text` is one string a row of the crop as code page 437 draws it, trailing spaces dropped; `cursor` is `[column, row]` in the crop, unavailable when hidden or outside it. The PNG's PLTE is the DAC and its pixels the indices the guest wrote. It is attached after the JSON when within the inline ceiling (1568 px a side, 1568 tiles of 28 px); `image` names it either way (`path`, `bytes`, `sha256`, `width`, `height`, `scale`, `indexed`, `border`, `inline`, `not_inlined`). `mode` chooses the view: `render` is the picture; `isolate`, `histogram` and `pixel` read a palette-indexed graphics mode (256 colours chained or not, 16-colour planar, 8-bit linear), where a pen is the DAC entry a pixel holds, and are refused `no_channel` in a text or direct-colour mode. `isolate` draws the pens asked for in magenta over the rest in grey and counts them (`pixels`, `bbox`); `histogram` answers the pens a region uses and the runs it leaves unused, with no picture; `pixel` answers the pen and colour under a point with a 48-pixel crop round it. There is no `set_by`: the debugger does not log who wrote a DAC entry. A dump file left in the emulator's working directory, a screen past its window, one no segment or page reaches, a layout with split or panning is refused, and a picture the disk could not take whole is `host_failed`.

<!-- scry-reference:begin screen_signature -->
## `screen_signature`

*Signature of the screen*

```text
screen_signature(crop=null)
```

One hex string for what is on screen or on `crop` `[x, y, width, height]`: the `scry-sig/1`
signature of a series row (text cells by byte and colours, 256-colour pixels by DAC colour;
no cursor). Reads what `screen_view` reads.

Reply: `signature`, `kind`, `width`, `height`, `crop`, `vga_mode`. Refusals as
`screen_view`, `dest` and `scale` aside.

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `crop` | array of integer or null | `null` |

| reply field | type |
|---|---|
| `crop` | array |
| `height` | integer |
| `kind` | string |
| `signature` | string |
| `vga_mode` | string |
| `width` | integer |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "screen_signature M_TEXT 80x25 at [0, 0]: ecc689ffb2847738",
  "status": "ok",
  "signature": "ecc689ffb2847738",
  "kind": "text",
  "vga_mode": "M_TEXT",
  "width": 80,
  "height": 25,
  "crop": [0, 0, 80, 25]
}
```
<!-- scry-reference:end screen_signature -->
