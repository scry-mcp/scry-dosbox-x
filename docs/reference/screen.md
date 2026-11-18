# The Screen tools

These tools read the screen at a stop, from video memory, without running the machine or changing it. `screen_view` shows it, `palette` lists its colours, and `screen_signature` answers a short hash of it, so two screens can be told the same without comparing pictures.

A palette index, the number a pixel holds in place of a colour, is named `pen` in the arguments and the fields.

## The picture a reply attaches

A picture is written as a PNG and attached to the reply after its JSON; `image` names the file either way. With no `dest` it goes to the session's temporary folder, which `close` deletes.

Past 1568 pixels a side, or 1568 tiles of 28 pixels, a client's image input resamples a picture, and resampled pixel art looks right and is wrong. Such a picture is written and not attached, and `not_inlined` says why: ask for a `crop` or a smaller `scale`.

The default `scale` is the largest whole factor that fits, so each pixel stays a square of one colour. A picture inside a step of `perform` is never attached: only a reply's own picture is.

<!-- scry-reference:begin palette -->
## `palette`

Read the colours the palette holds now, as a list and as a picture of colour swatches.

```text
palette(first=0, count=0, scale=0, dest="")
```

### Try it

On Bricks, the game this repository builds, stopped once its play screen is drawn. Entries 32 to 39 are colours the game itself sets.

Ask:

> Show me palette entries 32 to 39, and save the swatches as palette.png.

Call:

```text
palette(first=32, count=8, dest="./tmp/demos/tour/files/palette.png")
```

Reply, 2 of 10 fields:

```json
{
  "summary": "palette: entries 32 to 39 of 256; 1024x128 PNG x8, inline",
  "colors": [
    "#ff2020",
    "#ff9200",
    "#fff330",
    "#41eb41",
    "#20d3eb",
    "#5161ff",
    "... 2 more"
  ]
}
```

Eight of the palette's 256 entries, from 32, each as `#rrggbb`: the VGA's six-bit components widened to eight bits. The swatches went to a PNG enlarged 8 times, attached to the reply.

<details><summary>The whole reply</summary>

```json
{
  "summary": "palette: entries 32 to 39 of 256; 1024x128 PNG x8, inline",
  "status": "ok",
  "entries": 256,
  "first": 32,
  "count": 8,
  "colors": ["#ff2020", "#ff9200", "#fff330", "#41eb41", "#20d3eb", "#5161ff", "... 2 more"],
  "rgb": ["3f0808", "3f2400", "3f3c0c", "103a10", "08343a", "14183f", "... 2 more"],
  "bits": 6,
  "pel_mask": "ffh",
  "image": {
    "path": "./tmp/demos/tour/files/palette.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 1024,
    "height": 128,
    "scale": 8,
    "indexed": true,
    "inline": true
  }
}
```

</details>

### Arguments

- `first` (integer (>= 0, <= 255) or string, default `0`): The first entry to read, 0 to 255: an integer or a `0x` string. Left out, 0.
- `count` (integer (>= 0, <= 256), default `0`): How many entries to read. Left at 0, every entry from `first` to the last.
- `scale` (integer, default `0`): The whole factor the picture is enlarged by, 1 to 8. Left at 0, the largest that fits.
- `dest` (string, default `""`): A new path for the PNG, absolute or starting with `~`. Left empty, the session's temporary folder, deleted at `close`.

### What comes back

- `colors`: Each entry read, as `#rrggbb`, in order from `first`.
- `rgb`: Each entry as the debugger prints it: three six-bit components in hex.
- `entries`: How many entries the palette has: 256.
- `bits`: The width of each component in the DAC, the chip that holds the palette: 6, or the call is refused.
- `pel_mask`: The DAC's pixel mask register, as the debugger prints it.
- `image`: The PNG: its `path`, `bytes`, `sha256`, `width`, `height` and `scale`, whether it is `indexed`, and `inline` or the reason in `not_inlined`.

<details><summary>All 8 reply fields</summary>

- `bits` (integer)
- `colors` (array)
- `count` (integer)
- `entries` (integer)
- `first` (integer)
- `image` (object)
- `pel_mask` (string)
- `rgb` (array)

</details>

### What it refuses

- An entry past 255, a `scale` outside 0 to 8, or a `dest` that is relative or exists (`bad_argument`).
- A machine that is running (`not_stopped`).
- A DAC that is not in six-bit mode (`unexpected_answer`).
- A picture the disk could not take whole (`host_failed`).

### Why it works this way

The colours are the VGA DAC's 256 entries, read from the debugger's `VGA DAC` and `VGA DACPAL` listings. Each six-bit component is widened to eight bits as the emulator draws it, by repeating its two top bits below.

The picture is an indexed PNG: every pixel of a swatch holds that entry's index into the DAC, so the file carries the palette as data.

### Related tools

- [`screen_view`](#screen_view)
- [`screen_signature`](#screen_signature)
- [`screen_wait`](run.md#screen_wait)

<details><summary>The contract your client receives</summary>

```text
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
```

</details>
<!-- scry-reference:end palette -->

<!-- scry-reference:begin screen_view -->
## `screen_view`

Read the screen at a stop: its text or its picture, the pixels that hold chosen palette indices, the indices in use, or one pixel.

```text
screen_view(mode="render", pens=null, point=null, crop=null, scale=0, dest="", attach=true)
```

### Try it

On Bricks, the game this repository builds, stopped once its play screen is drawn.

Ask:

> Show me the screen as it is now and save the picture as wall.png.

Call:

```text
screen_view(dest="./tmp/demos/tour/files/wall.png")
```

Reply, 8 of 12 fields:

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 1280x800 PNG x4, inline",
  "vga_mode": "M_VGA",
  "kind": "pixel",
  "width": 320,
  "height": 200,
  "mode": "render",
  "screen_indexed": true,
  "entries": 256
}
```

The screen is in the 256-colour mode the debugger names `M_VGA`, 320x200, drawn through a palette of 256 entries (`screen_indexed`). The PNG is enlarged 4 times, to 1280x800, and attached.

<details><summary>The whole reply</summary>

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 1280x800 PNG x4, inline",
  "status": "ok",
  "vga_mode": "M_VGA",
  "kind": "pixel",
  "width": 320,
  "height": 200,
  "mode": "render",
  "crop": [0, 0, 320, 200],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/tour/files/wall.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 1280,
    "height": 800,
    "scale": 4,
    "indexed": true,
    "inline": true
  },
  "display_start": "0h"
}
```

</details>

### The four modes

| mode | what it answers |
|---|---|
| `render` | The screen: its text in a text mode, else a PNG. In a mode drawn through the palette, each pixel of the file is its palette index. |
| `isolate` | The picture with the palette indices in `pens` in magenta and every other pixel grey, and how many pixels hold them. |
| `histogram` | No picture: each palette index in use with how many pixels hold it, and the ranges nothing uses. |
| `pixel` | The palette index and the colour under `point`, with a small picture of the pixels round it. |

### Arguments

- `mode` (one of `"render"`, `"isolate"`, `"histogram"`, `"pixel"`, default `"render"`): `render`, `isolate`, `histogram` or `pixel`, as above. Left out, `render`.
- `pens` (array of integer, optional): For `isolate`: the palette indices to show, 1 to 64 of them. A pen is the palette index a pixel holds.
- `point` (array of integer, optional): For `pixel`: the pixel to read, `[x, y]` on the screen.
- `crop` (array of integer, optional): The rectangle to read, `[x, y, width, height]`, in characters in a text mode and in pixels otherwise; not for `pixel`. Left out, the whole screen.
- `scale` (integer, default `0`): The whole factor the picture is enlarged by, 1 to 8; not for `histogram` or a text mode. Left at 0, the largest that fits.
- `dest` (string, default `""`): A new path for the PNG, absolute or starting with `~`. Left empty, the session's temporary folder, deleted at `close`.
- `attach` (boolean, default `true`): `false` writes the picture without attaching it to the reply. Left out, `true`.

### What comes back

- `text`: In a text mode: one string for each row of the crop, as code page 437 draws it, trailing spaces dropped.
- `cursor`: In a text mode: `[column, row]` inside the crop. Unavailable when the cursor is hidden or outside it.
- `image`: In a graphics mode: the PNG: its `path`, `bytes`, `sha256`, `width`, `height` and `scale`, whether it is `indexed`, and `inline` or the reason in `not_inlined`. Not for `histogram`.
- `pen`: For `pixel`: the palette index under the point; `color` is the colour it shows.
- `histogram`: For `histogram`: one `[pen, pixels]` pair for each palette index in use. `pens_used` counts them; `unused` lists the rest as ranges.
- `pixels`: For `isolate`: how many pixels hold the indices asked for. `bbox` is the rectangle that holds them all, as `[left, top, right, bottom]`.

<details><summary>All 24 reply fields</summary>

- `bbox` (array or object)
- `color` (string)
- `crop` (array)
- `cursor` (array or object)
- `display_start` (string)
- `entries` (integer)
- `height` (integer)
- `histogram` (array)
- `image` (object)
- `isolate_color` (string)
- `kind` (string)
- `mode` (string)
- `pen` (integer)
- `pens` (array)
- `pens_used` (integer)
- `pixels` (integer)
- `point_in_crop` (array)
- `screen_indexed` (boolean)
- `text` (array)
- `unused` (array)
- `vga_mode` (string)
- `width` (integer)
- `x` (integer)
- `y` (integer)

</details>

### What it refuses

- An argument the mode does not take, or `dest`, `scale` or `attach` in a text mode or with `histogram` (`bad_argument`).
- A `crop` or a `point` off the screen, a `scale` outside 0 to 8, or a `dest` that is relative or exists (`bad_argument`).
- `isolate`, `histogram` or `pixel` in a text mode or a direct-colour mode, which hold no palette index (`no_channel`).
- A video mode it does not read, a split screen or panning, or a build whose debugger has no `VGAMEMDUMP` command for a mode that needs it (`no_channel`).
- A machine that is running (`not_stopped`).
- A DAC that is not in six-bit mode (`unexpected_answer`).

### Why it works this way

The screen is read from video memory and never by touching the video card, so reading it does not change it. Text and mode 13h come through the CPU's own view of that memory; planar, unchained and linear modes come from the video RAM, through the debugger's `VGAMEMDUMP` command.

In a mode drawn through the palette, the PNG's pixels are the bytes the program wrote and its palette is the DAC, so the file is data. A 16-colour pixel goes through the Attribute Controller to its DAC entry; a 15- or 16-bit one is widened to eight bits a component by repeating its high bits.

The views by palette index need a mode drawn through the palette: 256 colours, 16-colour planar or 8-bit linear. Nothing says who set a colour, because the debugger does not log writes to the DAC.

<details><summary>More on why</summary>

`isolate` draws the other pixels in greys with no black or white. Dimming would lose a dark entry in a dark screen, and one hue over greys stands out whatever the entry's colour.

For `pixel` the picture is a crop of 48 pixels round the point, in colour, with the point ringed and a `border` round the crop. `point_in_crop` is the point inside it.

In protected mode the screen is read through a data segment that covers it: the lowest present one of the GDT, then of the LDT. With paging on, every page must map to the same physical address; otherwise the call is refused (`no_channel`).

A 256-colour picture, each pixel doubled each way as the emulator draws mode 13h, equals the emulator's own capture. A screen that runs past its memory window is refused, and a picture the disk could not take whole is `host_failed`.

`vga_mode` is the video mode as the debugger names it, `kind` is `text` or `pixel`, and `display_start` is where in video memory the screen begins. `screen_indexed` and `entries` come in a graphics mode drawn through the palette.

</details>

### Related tools

- [`palette`](#palette)
- [`screen_signature`](#screen_signature)
- [`snapshot`](captures.md#snapshot)
- [`capture_frame`](captures.md#capture_frame)
- [`screen_wait`](run.md#screen_wait)

<details><summary>The contract your client receives</summary>

```text
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
```

</details>
<!-- scry-reference:end screen_view -->

<!-- scry-reference:begin screen_signature -->
## `screen_signature`

Get a short hash of what the screen shows, so two screens can be told the same without comparing pictures.

```text
screen_signature(crop=null)
```

### Try it

On Bricks, the game this repository builds, stopped once its play screen is drawn. The rectangle is the word SCORE at the top left.

Ask:

> Give me the signature of the SCORE label, the 52 by 8 pixels at the top left of the screen.

Call:

```text
screen_signature(crop=[0, 0, 52, 8])
```

Reply, 5 of 8 fields:

```json
{
  "summary": "screen_signature M_VGA 52x8 at [0, 0]: f38d22147fd6e2bd",
  "signature": "f38d22147fd6e2bd",
  "kind": "pixel",
  "vga_mode": "M_VGA",
  "crop": [0, 0, 52, 8]
}
```

`f38d22147fd6e2bd` stands for those 52x8 pixels, hashed by colour (`kind` `pixel`). While the label stays unchanged, the same rectangle gives the same 16 characters.

<details><summary>The whole reply</summary>

```json
{
  "summary": "screen_signature M_VGA 52x8 at [0, 0]: f38d22147fd6e2bd",
  "status": "ok",
  "signature": "f38d22147fd6e2bd",
  "kind": "pixel",
  "vga_mode": "M_VGA",
  "width": 320,
  "height": 200,
  "crop": [0, 0, 52, 8]
}
```

</details>

### Arguments

- `crop` (array of integer, optional): The rectangle to hash, `[x, y, width, height]`, in characters in a text mode and in pixels otherwise. Left out, the whole screen.

### What comes back

- `signature`: 16 hex characters. Two screens, or two crops of one size, show the same when their signatures are equal.
- `kind`: `text` when characters were hashed, `pixel` when pixels were.
- `crop`: The rectangle that was hashed.
- `vga_mode`: The video mode, as the debugger names it.

<details><summary>All 6 reply fields</summary>

- `crop` (array)
- `height` (integer)
- `kind` (string)
- `signature` (string)
- `vga_mode` (string)
- `width` (integer)

</details>

### What it refuses

- A `crop` that leaves the screen (`bad_argument`).
- A video mode `screen_view` does not read, or a build whose debugger has no `VGAMEMDUMP` command for a mode that needs it (`no_channel`).
- A machine that is running (`not_stopped`).
- A DAC that is not in six-bit mode (`unexpected_answer`).

### Why it works this way

The signature answers "is it the same screen" with two strings, never two pictures. A caller that waits for a screen, compares two moments or keeps a reference holds 16 characters, not a PNG.

It is made of what the program put in video memory and in the palette, not of what the window drew. An unchanged screen has one signature on any computer.

A character counts by its byte and the two colours its attribute gives it, a pixel by its colour. A palette fade or a recoloured character is a new signature; the cursor's blink is not.

<details><summary>More on why</summary>

It reads what `screen_view` reads. Each row of a series carries a signature in the same format, which [Media files](../../REFERENCE.md#media-files) sets out.

The signature is BLAKE2b with an 8-byte digest, written as 16 lowercase hex characters. It hashes `scry-sig/1|<kind>|<w>x<h>|` and then the crop's cells, row by row, `w` and `h` being the crop's.

A text cell is its code page 437 byte, then its foreground and background colours as the VGA shows them. Each goes through the Attribute Controller's palette registers (`VGA AC`), then the DAC. When `mode_control` bit 7 is set, `color-select` supplies bits 5 and 4 in place of the register's. With blinking on, `mode_control` bit 3, the background has three bits and the fourth blinks.

</details>

### Related tools

- [`screen_wait`](run.md#screen_wait)
- [`screen_map_find`](read.md#screen_map_find)
- [`screen_view`](#screen_view)
- [`image_compare`](files.md#image_compare)

<details><summary>The contract your client receives</summary>

```text
One hex string for what is on screen or on `crop` `[x, y, width, height]`: the `scry-sig/1`
signature of a series row (text cells by byte and colours, 256-colour pixels by DAC colour;
no cursor). Reads what `screen_view` reads.

Reply: `signature`, `kind`, `width`, `height`, `crop`, `vga_mode`. Refusals as
`screen_view`, `dest` and `scale` aside.

Reference: REFERENCE.md, Media files.
```

</details>
<!-- scry-reference:end screen_signature -->
