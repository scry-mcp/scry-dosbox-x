# The Read tools

The typed tools parse what the debugger prints for each command, read its lists back and refuse a shape they were not captured answering; [`debug`](write.md#debug) is the raw command for the rest.

<!-- scry-reference:begin registers -->
## `registers`

*Read the registers*

```text
registers(from_last_stop=false)
```

The registers at this stop. `from_last_stop=True` returns the registers of the last stop,
never the current value; refused (`no_stop`) before any stop.

Reply: `regs` (hex strings), `superseded` (with `from_last_stop`). CR0, CR3 and descriptor
tables: `machine_map(sections=["control"])`.

| argument | type | default |
|---|---|---|
| `from_last_stop` | boolean | `false` |

| reply field | type |
|---|---|
| `regs` | object |
| `superseded` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "registers: 15 registers",
  "status": "ok",
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000124",
    "ECX": "0x0000a97e",
    "EDX": "0x00000814",
    "ESI": "0x00000100",
    "EDI": "0x0000fffe",
    "EBP": "0x0000091c",
    "ESP": "0x0000fff8",
    "EIP": "0x0000fea5",
    "CS": "0xf000",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  }
}
```
<!-- scry-reference:end registers -->

A refusal because the guest runs carries `last_stop` and names the tools that do answer while the guest runs.

<!-- scry-reference:begin read_memory -->
## `read_memory`

*Read memory*

```text
read_memory(ref, length=16)
```

`length` bytes (1..128) at `ref`, a symbol or `SEG:OFF` (a bare number is read as a
symbol).

Reply: `hex`, `length`, `seg_off`, `ref`; above 128 bytes use `memdump`. Needs the
machine stopped. An absent or ambiguous symbol is refused.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `length` | integer (>= 1, <= 128) | `16` |

| reply field | type |
|---|---|
| `hex` | string |
| `length` | integer |
| `ref` | string |
| `rows` | array |
| `seg_off` | string |

Example, from a live run:

```json
{
  "ref": "0000:0020",
  "length": 4
}
```

```json
{
  "summary": "read_memory 0000:0020: 4 bytes at 0000:00000020: a5fe00f0",
  "status": "ok",
  "ref": "0000:0020",
  "seg_off": "0000:00000020",
  "length": 4,
  "hex": "a5fe00f0"
}
```
<!-- scry-reference:end read_memory -->

The bytes come from the debugger's `MEMDUMPBIN` of exactly that span, and the reply is INVALID unless the file it writes holds exactly the bytes asked for, so a short dump is refused rather than handed back shifted.

<!-- scry-reference:begin disassemble -->
## `disassemble`

*Disassemble code*

```text
disassemble(ref, length=16)
```

Decode `length` bytes from `ref` (a symbol or `SEG:OFF`) as x86, one instruction a line. The
last is completed unless the segment ends first. A line a comment is placed on ends
` // <text>`.

Reply: `seg_off`, `length`, `code_bits`, `code_bits_from`, `lines`, `flow` (per line:
`call`, `branch`, `return`, `sequential`, `unknown`), `flow_source`, and with symbols loaded
`resolved` (direct call/branch targets and memory operands: `line`, `operand`, `seg_off`,
`addr`, `symbol`, `delta`).

Refused: `length` out of range or past the end of a 16-bit segment; `memdump`'s refusals
apply.

Reference: REFERENCE.md, Reading and writing.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `length` | integer (>= 1, <= 1024) | `16` |

| reply field | type |
|---|---|
| `code_bits` | integer |
| `code_bits_from` | string |
| `flow` | array |
| `flow_source` | string |
| `length` | integer |
| `lines` | array |
| `ref` | string |
| `resolved` | array |
| `seg_off` | string |

Example, from a live run:

```json
{
  "ref": "0000:0020",
  "length": 4
}
```

```json
{
  "summary": "disassemble 0000:0020: 3 lines at 0000:00000020, 16-bit",
  "status": "ok",
  "ref": "0000:0020",
  "seg_off": "0000:00000020",
  "length": 4,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["0000:00000020 A5                   movsw word ptr es:[di], word ptr [si]", "0000:00000021 FE00                 inc byte ptr [bx + si]", "0000:00000023 F0                   .byte 0xf0"],
  "flow": ["sequential", "sequential", "unknown"],
  "flow_source": "capstone"
}
```
<!-- scry-reference:end disassemble -->

The debugger has no disassembly command, hence capstone on the host. The width is the segment's own D bit: real mode 16-bit; in protected mode the stop's `Pr32`/`Pr16` for CS, `SELINFO` for a selector another segment register holds, the descriptor listings for one no register holds. `lines` are `SSSS:OOOOOOOO BYTES TEXT`; a byte no instruction starts with is `.byte 0x..` with flow `unknown`. In a 16-bit segment IP wraps at its end, which is why a longer range is refused, naming the most bytes from there. `resolved` rows carry the segment register a memory operand is read through at this stop; an address unavailable outside the table's span.

<!-- scry-reference:begin call_stack -->
## `call_stack`

*Guess the call stack*

```text
call_stack()
```

A heuristic chain of the stop's callers, never a verdict: frame pointers walked (`push
bp`/`mov bp, sp`, `enter`), each return kept only when a call instruction ends there. Row 0
is the stop.

Reply: `heuristic`, `code_bits`, `calls` (innermost first: `seg_off`, `addr`, `symbol`,
`delta`, `via`, `call`, `bp`), `truncated`, `ended_why`. Refused when the registers come
back without SS, ESP or EBP. A routine with no frame pointer is invisible.

Reference: REFERENCE.md, Reading and writing.

Takes no argument.

| reply field | type |
|---|---|
| `calls` | array |
| `code_bits` | integer |
| `ended_why` | string |
| `heuristic` | boolean |
| `truncated` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "call_stack: 1 call, innermost F000:0000FEA5, heuristic",
  "status": "ok",
  "heuristic": true,
  "code_bits": 16,
  "calls": [
    {
      "seg_off": "F000:0000FEA5",
      "via": "stop",
      "call": {"available": false, "why": "the stop itself: no call leads to it"},
      "bp": {"available": false, "why": "no frame was read beside it"},
      "addr": "0x000ffea5",
      "symbol": {"available": false, "why": "no symbol table is loaded"},
      "delta": {"available": false, "why": "no symbol table is loaded"}
    }
  ],
  "truncated": false,
  "ended_why": "the return address beside the frame at SS:91C follows no call instruction"
}
```
<!-- scry-reference:end call_stack -->

Outside a routine's frame (at its `push bp` or `enter`, the `mov bp, sp` after it, the `ret`) the caller is read off the stack pointer (`via` `entry`); then the chain from BP, near or far as the call before it says. The walk ends at a zero or non-rising saved frame pointer, a frame past the stack segment's end, a return no call precedes (not listed), a return outside the loaded table (listed), or its bound. A routine that keeps no frame pointer shows its caller's caller in its place, or nothing. `call` is unavailable on row 0, `bp` on row 0 and `entry` rows.

<!-- scry-reference:begin memdump -->
## `memdump`

*Dump memory to a file*

```text
memdump(ref, length, dest)
```

`length` bytes from `ref` (a symbol or `SEG:OFF`) to the new file `dest` (absolute or
`~`-led).

Reply: `ref`, `seg_off`, `length`, `path`, `bytes`. Refused: a dump file already where the
debugger writes or at `dest`, a `dest` directly in that directory, an absent or ambiguous
symbol; in protected mode a 16-bit segment, a range past its limit, or no descriptor.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `length` | integer | required |
| `dest` | string | required |

| reply field | type |
|---|---|
| `bytes` | integer |
| `length` | integer |
| `path` | string |
| `ref` | string |
| `seg_off` | string |

Example, from a live run:

```json
{
  "ref": "0000:0400",
  "length": 16,
  "dest": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1143.bin"
}
```

```json
{
  "summary": "memdump 0000:0400: 16 bytes to $TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1143.bin",
  "status": "ok",
  "ref": "0000:0400",
  "seg_off": "0000:00000400",
  "length": 16,
  "path": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1143.bin",
  "bytes": 16
}
```
<!-- scry-reference:end memdump -->

**`memdump` names the debugger's file itself**, `MCPDUMP.BIN` in the emulator's working directory, so `captures_dir` is not where a dump lands. A build whose `MEMDUMPBIN` is given no name reads one from past the end of the line; a build that takes no name writes `MEMDUMP.BIN`, collected from the working directory and the captures directory alike, because where that lands is one build's behaviour.

A `dest` that is, or lives under, one of the debugger's file names is refused too, compared on the filesystem rather than the spelling: a dump collected into the directory it is collected FROM cannot be told from the leftover, and would poison every later dump.

The debugger writes its dump into the emulator's working directory, so a dangling link there counts as a leftover. The size handed back is checked for equality against `length`. Past offset 0xFFFF the debugger would wrap a 16-bit segment or read zeros past a limit: in real mode the range is read in 64 KiB windows, up to `FFFF:FFFF`; in protected mode the selector's descriptor is read instead. Inside 0 to 0xFFFF the limit is not judged and the debugger reads zeros past it.

<!-- scry-reference:begin find -->
## `find`

*Find bytes in memory*

```text
find(data_hex, ref, length)
```

Every address holding `data_hex` (whole hex bytes) in `length` bytes from `ref`; both
required. `memdump`'s refusals apply. For a value narrowed over time use `scan`.

Reply: `seg_off`, `length`, `span`, `hits` (`SEG:OFF`, at most 400, highest kept),
`hits_total`, `truncated`.

| argument | type | default |
|---|---|---|
| `data_hex` | string | required |
| `ref` | string | required |
| `length` | integer | required |

| reply field | type |
|---|---|
| `hits` | array |
| `hits_total` | integer |
| `length` | integer |
| `ref` | string |
| `seg_off` | string |
| `span` | object |
| `truncated` | boolean |

Example, from a live run:

```json
{
  "data_hex": "00",
  "ref": "8000:0000",
  "length": 16
}
```

```json
{
  "summary": "find 8000:0000: 16 hits of 00 in 16 bytes",
  "status": "ok",
  "ref": "8000:0000",
  "seg_off": "8000:00000000",
  "length": 16,
  "span": {"from": "8000:00000000", "length": 16, "source": "ref+length"},
  "hits": ["8000:00000000", "8000:00000001", "8000:00000002", "8000:00000003", "8000:00000004", "8000:00000005", "... 10 more"],
  "hits_total": 16,
  "truncated": false
}
```
<!-- scry-reference:end find -->

The debugger has no pattern search, so the range is dumped by the `memdump` route (windows past offset 0xFFFF included) into a scratch file of the call's own, gone before the reply, and searched exactly. In real mode a hit past offset 0xFFFF is named from its own paragraph. `span` is always `ref+length` here since the range is the caller's own.

<!-- scry-reference:begin screen_map_find -->
## `screen_map_find`

*Which mapped screen is this*

```text
screen_map_find()
```

Which mapped screen the machine shows. Reply: `matched`, `kind` and `size`; when matched,
`screen`, `layer`, `controls` (`name`, `rect`, `centre`), in the program's units; when not,
`screens_mapped` and, if the view fits the map, `screens_tried` and `screens_unjudged`
(signed by index on a screen whose pens cannot be read), else `view_fits` false. None mapped:
`needs_call`.

Reference: REFERENCE.md, Screen maps.

Takes no argument.

| reply field | type |
|---|---|
| `controls` | array |
| `kind` | string |
| `layer` | string |
| `matched` | boolean |
| `screen` | string |
| `screens_mapped` | integer |
| `screens_tried` | integer |
| `screens_unjudged` | integer |
| `size` | array |
| `view_fits` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "screen_map_find: probe_stopped (session), 0 controls",
  "status": "ok",
  "matched": true,
  "screen": "probe_stopped",
  "layer": "session",
  "kind": "text",
  "size": [80, 25],
  "controls": []
}
```
<!-- scry-reference:end screen_map_find -->

Session layer first, then the file's; a screen matches when its kind and size are the screen's and every region's signature is. Matched controls are what `send_mouse(target=)` acts on. The modes `screen_view` refuses are refused.

<!-- scry-reference:begin screen_map_write -->
## `screen_map_write`

*Write the screen map*

```text
screen_map_write(method, screen="", match=null, controls=null, cells="", anchor="", path="", scale=null, margin=null, dest="", overwrite=null, pointer=null)
```

The screen map: an application's screens, each known by the signatures of its stable regions, and their controls, in a session layer and a file layer.

`add`: the screen shown now as `screen` in the session layer, one read signing each `match` crop ([x, y, width, height], 1..16), `controls` ([{"name", "rect"}]) in the screen's own units; needs the machine stopped. Reply: `screen`, `kind`, `size`, `cells`, `match`, `controls`, `replaced`, `shadows_file`, `anchor` (when given), `kept` (a complete map is kept for `promote`).

`pointer`: the program's own pointer as an object, `{"x": ref, "y": ref, "bytes": 2}` (a symbol or
`SEG:OFF` for each axis; `bytes` 1, 2 or 4), as a map file declares it; kept by `save`, replaced by a `load`; a misshapen object is `bad_argument`. Reply: `pointer`.

`add`'s `cells` `index` (a pixel screen; default
`rgb`) signs the palette indices drawn, not the colours shown, so one map knows a program
shown through two palettes; a screen with no palette refuses it (`no_channel`).

`add`'s `anchor` (a symbol or an address, as `run_to`'s `ref`) is the place after which the screen is whole,
what `run_to(screen=)` runs to: a consolidated map refuses an `add` without one (`bad_argument`),
since it enters its screens by theirs.

`load`: `path` (`<application>-screen-map.json`, absolute or `~`-led) as the file layer, held by the
server; nothing is written to disk. `scale` (1..8) and `margin` [x, y] (machine pixels on
each side) say how the program's picture sits on this machine's screen; maps and `add`'s
crops are in the program's units. Reply: `path`, `application`, `mode`, `screens`, `controls`, `pointer`
(a map that declares the program's pointer).

`save`: both layers as one map to `dest`, refused there without `overwrite`, made the file
layer, in the loaded map's `mode` (`verified` when none was loaded). Reply: `path`,
`application`, `mode`, `screens`, `controls`, `promoted`.

Refused: an argument the method does not take; a misshapen name, crop, control, view or file; an `add` without an `anchor` to a consolidated map, and a save of one holding a screen with none (`bad_argument`); neither a screen nor a `pointer` to save (`needs_call`); the modes `screen_view` refuses.

Reference: REFERENCE.md, Screen maps.

| argument | type | default |
|---|---|---|
| `method` | one of `"add"`, `"pointer"`, `"load"`, `"save"` | required |
| `screen` | string | `""` |
| `match` | array of array of integer or null | `null` |
| `controls` | array of object or null | `null` |
| `cells` | one of `""`, `"rgb"`, `"index"` | `""` |
| `anchor` | string | `""` |
| `path` | string | `""` |
| `scale` | integer or null | `null` |
| `margin` | array of integer or null | `null` |
| `dest` | string | `""` |
| `overwrite` | boolean or null | `null` |
| `pointer` | object or null | `null` |

| reply field | type |
|---|---|
| `anchor` | string |
| `application` | string |
| `cells` | string |
| `controls` | integer |
| `kind` | string |
| `kept` | string |
| `match` | array |
| `mode` | string |
| `path` | string |
| `pointer` | object |
| `promoted` | array |
| `replaced` | boolean |
| `screen` | string |
| `screens` | integer |
| `shadows_file` | boolean |
| `size` | array |

Example, from a live run:

```json
{
  "method": "pointer",
  "pointer": {"x": "2000:94CA", "y": "2000:94CC"}
}
```

```json
{
  "summary": "screen_map_write pointer: the program's pointer at 2000:94CA and 2000:94CC, 2 bytes each",
  "status": "ok",
  "pointer": {"x": "2000:94CA", "y": "2000:94CC", "bytes": 2}
}
```
<!-- scry-reference:end screen_map_write -->

Units are cells in a text mode and pixels in a graphics mode, whichever depth `screen_view` reads (256 colours, planar, 15-, 16- or 32-bit).
