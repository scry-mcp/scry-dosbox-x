# The Scan tools

<!-- scry-reference:begin scan_start -->
## `scan_start`

*Start a value scan*

```text
scan_start(ref, length, cell_bytes=1)
```

Open the debugger's value scanner (`MEMFIND`) over `length` bytes from `ref`, in cells
of `cell_bytes` (1, 2 or 4, little-endian): every cell is a candidate
until `scan_filter` narrows them. The debugger holds ONE scan at a time, so a scan
already open is refused in its words: `scan_clear` it, or keep filtering it.

This is the cheat-search loop for a program with no map: open the scan, play, filter
by what the value must have done (`=` a known value, `!` with no value for "changed
since the scan opened"), until the survivors are the cells that move the way the
program does. `length` is a whole number of cells.
Needs the machine stopped. Reply: `seg_off`, `length`, `cell_bytes`, `addr` (the linear
address the scan opened at), `hits_total` (every cell is a candidate).

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `length` | integer | required |
| `cell_bytes` | one of `1`, `2`, `4` | `1` |

| reply field | type |
|---|---|
| `addr` | string |
| `cell_bytes` | integer |
| `hits_total` | integer |
| `length` | integer |
| `line_recovered` | boolean |
| `note` | string |
| `ref` | string |
| `seg_off` | string |

Example, from a live run:

```json
{
  "ref": "8000:0000",
  "length": 16
}
```

```json
{
  "summary": "scan_start 8000:0000: 16 cells of 1 byte",
  "status": "ok",
  "ref": "8000:0000",
  "seg_off": "8000:00000000",
  "length": 16,
  "cell_bytes": 1,
  "addr": "0x00080000",
  "hits_total": 16
}
```
<!-- scry-reference:end scan_start -->

<!-- scry-reference:begin scan_filter -->
## `scan_filter`

*Filter the value scan*

```text
scan_filter(operator="=", value=null, limit=40)
```

Keep the scan's cells whose current content satisfies `operator` (`=`, `!`, `>`,
`>=`, `<`, `<=`) against `value`; with no `value`, against what each cell held when
`scan_start` opened the scan: `!` alone keeps the cells that CHANGED since then, `=`
alone those that did not, `>` alone those that grew. The debugger's `MEMS`.

`value` is an integer or a `0x` hex string; one wider than the cell of a scan `scan_start`
opened is refused before `MEMS` is typed. Needs the machine stopped and a scan open. Reply:
`operator`, `value` (`0x` at the cell's width), `iterations` (the filters so far, this one
included; on the closing reply the server's own count, unavailable for a scan `debug`
touched), `closed` (a step that leaves NO survivor closes the scan, which is what the
debugger does), `hits` (the first `limit`, each survivor's `seg_off`, `addr` and current
`value`), `hits_total` and `truncated` (more survive than `hits` shows). Past 400
survivors none is listed, with a `note`: the debugger pages its listing, so filter again.

THE COMMAND LINE IS LEFT CLEAN even when the answer cannot be read. The debugger eats a
command character by character while a paged-content prompt waits, one page per
keystroke, so a listing that ends with a page unturned swallows the front of the next
command and strands its tail on the line, and from there every later call concatenates
instead of running until `close`. So a listing turns its last page, and an
`unexpected_answer` clears the line before it refuses, saying so in `line_recovered`.

| argument | type | default |
|---|---|---|
| `operator` | one of `"="`, `"!"`, `">"`, `">="`, `"<"`, `"<="` | `"="` |
| `value` | integer or string or null | `null` |
| `limit` | integer (>= 1, <= 400) | `40` |

| reply field | type |
|---|---|
| `closed` | boolean |
| `hits` | array |
| `hits_total` | integer |
| `iterations` | integer or object |
| `line_recovered` | boolean |
| `note` | string |
| `operator` | string |
| `rows` | integer |
| `survivors` | integer |
| `truncated` | boolean |
| `value` | string or object |

Example, from a live run:

```json
{
  "operator": "="
}
```

```json
{
  "summary": "scan_filter =: 16 survivors",
  "status": "ok",
  "operator": "=",
  "value": {
    "available": false,
    "why": "no `value` was given, so each cell was compared with its value at `scan_start`"
  },
  "iterations": 1,
  "closed": false,
  "hits": [
    {
      "seg_off": "8000:00000000",
      "addr": "0x00080000",
      "value": "0x00"
    },
    {
      "seg_off": "8000:00000001",
      "addr": "0x00080001",
      "value": "0x00"
    },
    {
      "seg_off": "8000:00000002",
      "addr": "0x00080002",
      "value": "0x00"
    },
    {
      "seg_off": "8000:00000003",
      "addr": "0x00080003",
      "value": "0x00"
    },
    {
      "seg_off": "8000:00000004",
      "addr": "0x00080004",
      "value": "0x00"
    },
    {
      "seg_off": "8000:00000005",
      "addr": "0x00080005",
      "value": "0x00"
    },
    "... 10 more"
  ],
  "hits_total": 16,
  "truncated": false
}
```
<!-- scry-reference:end scan_filter -->

<!-- scry-reference:begin scan_clear -->
## `scan_clear`

*Clear the value scan*

```text
scan_clear()
```

Cancel the debugger's open scan (`MEMFIND !`). Nothing open is a no-op that says so.
Needs the machine stopped. Reply: `cleared`. An answer this cannot read clears the
debugger's command line before refusing (`line_recovered`): see `scan_filter`.

Takes no argument.

| reply field | type |
|---|---|
| `cleared` | boolean |
| `line_recovered` | boolean |
| `note` | string |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "scan_clear: cleared",
  "status": "ok",
  "cleared": true
}
```
<!-- scry-reference:end scan_clear -->
