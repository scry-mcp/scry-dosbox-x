# The Declarations tools

<!-- scry-reference:begin breakpoint_at -->
## `breakpoint_at`

*Declare a breakpoint*

```text
breakpoint_at(ref, by="auto")
```

Declare a code breakpoint at a symbol or `SEG:OFF`, and arm it if it can be. Stored, and
re-armed on `symbols_load`; a raw `SEG:OFF` goes `stale` over another build.

Refused: a name matching several symbols; an address another declaration holds, naming it.
A symbol absent from this build is stored `unresolved`.

Reply: `ref`, `stored`, `already_stored`, `armed`, `entry`, `state` (`armed`,
`unresolved`, `unarmable`, `pending` while the guest runs), `why`, `marked` and `note` for
a linker-marked symbol.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `by` | one of `"auto"`, `"symbol"`, `"address"` | `"auto"` |

| reply field | type |
|---|---|
| `already_stored` | boolean |
| `armed` | boolean |
| `by` | string |
| `entry` | string |
| `marked` | boolean |
| `note` | string |
| `ref` | string |
| `state` | string |
| `stored` | boolean |
| `why` | string |

Example, from a live run:

```json
{
  "ref": "0000:0002"
}
```

```json
{
  "summary": "breakpoint_at 0000:0002: armed",
  "status": "ok",
  "ref": "0000:0002",
  "by": "address",
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 0000:0002"
}
```
<!-- scry-reference:end breakpoint_at -->

A code breakpoint in ROM is acknowledged and never fires, though the same command at a RAM address
fires first time. It is neither the dynamic core nor a missing feature. Arming happens after the
machine is released, so it cannot be detected in advance; `run_to`'s non-arrival note names it.

The declaration is stored on disk keyed by the conf and stamped with this session as its `origin`, so it survives a rebuild; a raw `SEG:OFF` re-arms per build, whoever declared it: at `start` when declared before any map was loaded, after a `symbols_load` of the same map when declared over that map, and `stale` over another build (declaring it again adopts it). A symbol is stored `unresolved` rather than refused because it may be inlined this time. `by` is `auto` unless a symbol or address must be forced. Arming needs the machine stopped and the debugger to take the `BP`, and the entry is read back from its list. `pending` rows are armed at the next stop, said in `applied_on_stop`. `marked` is a fact about the linker's mark, not a refusal: whether such an address fires is open. `already_stored` is a no-op re-declaration adopted by this session.

<!-- scry-reference:begin breakpoint_interrupt -->
## `breakpoint_interrupt`

*Arm an interrupt breakpoint*

```text
breakpoint_interrupt(number, ah=null, detail=false)
```

Break on an interrupt, optionally one `ah` function. Arm it before `resume`. `number` and
`ah` are hex given as integers: `0x21` for DOS, not `21`. Pending while the guest runs.

Reply: `ref` (e.g. `BPINT 21 AH=4B`, what `declaration_clear` takes), `stored`,
`already_stored`, `armed`, `state`, `entry`; with `detail=True` also `output`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `number` | integer (>= 0, <= 255) | required |
| `ah` | integer (>= 0, <= 255) or null | `null` |
| `detail` | boolean | `false` |

| reply field | type |
|---|---|
| `already_stored` | boolean |
| `armed` | boolean |
| `clipped` | boolean |
| `entry` | string |
| `note` | string |
| `ref` | string |
| `output` | string |
| `output_chars` | integer |
| `state` | string |
| `stored` | boolean |

Example, from a live run:

```json
{
  "number": 33,
  "ah": 76
}
```

```json
{
  "summary": "breakpoint_interrupt BPINT 21 AH=4C: stored",
  "status": "ok",
  "ref": "BPINT 21 AH=4C",
  "stored": true,
  "entry": "BPINT 21 AH=4C",
  "omitted": [
    "output",
    "output_chars",
    "clipped"
  ],
  "how": "detail=True adds what the debugger printed for this command"
}
```
<!-- scry-reference:end breakpoint_interrupt -->

It is stored under its `BPINT` spelling and not cleared through the list's index, which deletes
whichever row sits there. Re-arming is a no-op checked against the live list, because `BPINT` sent
twice stacks a second row that a later clear leaves behind as `foreign`.

It brings a running guest back at that interrupt, where `stop` brings it back wherever it is and a host keypress cannot. A DJGPP program's DOS call is `0x31` with `ah=2`. The declaration is stored under its `BPINT ..` spelling, so `declaration_list` shows it and `declaration_clear` removes it by `ref`; arming the same one again is a no-op that says `already_stored`. With `detail=True` the acknowledgement's `screen_delta` is capped (`screen_chars`, `clipped`), else `omitted` names them; a fresh arm only, since a pending or already armed one typed nothing.

<!-- scry-reference:begin regpoint_add -->
## `regpoint_add`

*Declare a registerpoint*

```text
regpoint_add(condition)
```

Declare a registerpoint: the machine stops when `condition` comes true, wherever in the
program ("who puts this value in this register"). Stored, re-armed at `start`; pending while
the guest runs. Needs the debugger's `BPIF`.

`condition`: up to four terms joined by `&&`, each a register (`AX`, `EAX`, `AL`, `CS`, ...,
`FLAGS`), a comparison (`==`, `!=`, `<`, `<=`, `>`, `>=`) and a hex value (`AX==3B`,
`0x` allowed); compares, never assigns.

Refused: a term not in that shape (`bad_argument`); a build without `BPIF` (`no_channel`).

Reply: `ref` (the condition as the debugger prints it back, what `declaration_clear` takes),
`stored`, `already_stored`, `armed`, `state`, `while_running`, `entry`, `note`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `condition` | string | required |

| reply field | type |
|---|---|
| `already_stored` | boolean |
| `armed` | boolean |
| `by` | string |
| `condition` | string |
| `entry` | string |
| `note` | string |
| `ref` | string |
| `state` | string |
| `stored` | boolean |
| `while_running` | boolean |

Example, from a live run:

```json
{
  "condition": "AX==4C00"
}
```

```json
{
  "summary": "regpoint_add AX==4C00: armed",
  "status": "ok",
  "ref": "AX==4C00",
  "by": "expr",
  "condition": "AX==4C00",
  "stored": true,
  "while_running": false,
  "armed": true,
  "state": "armed",
  "entry": "BPIF AX==4C00"
}
```
<!-- scry-reference:end regpoint_add -->

<!-- scry-reference:begin watch_add -->
## `watch_add`

*Declare a watch*

```text
watch_add(ref, mode, length=0, fmt="auto", by="auto")
```

Declare a watch by symbol, `SEG:OFF` or through a pointer, read as `fmt`. Persists and
re-resolves on `symbols_load`.

`mode`: `show` (read at each stop) or `change` (stops when the bytes change). `ref`: a
symbol, `SEG:OFF`, or `[base]+0x28`, `base->field`. `fmt`: a scalar (`u8` .. `f64`), an
array (`u16[8]`), a string (`char[16]`) or a struct (`{x:i16,y:i16}`). `length`: total
bytes; at most 128 for show, 16 for change (a debugger row per byte,
`entries`).

Refused: one ref as both modes; a length over the ceiling; a pointer base the table lacks.

Reply: `ref`, `stored`, `already_stored`, `state` (`evaluated`, `unresolved`, `unarmable`,
`null_pointer`, `pending`), `armed`, `pointer`, `entry`, `caveat`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `mode` | one of `"show"`, `"change"` | required |
| `length` | integer | `0` |
| `fmt` | string | `"auto"` |
| `by` | one of `"auto"`, `"symbol"`, `"address"`, `"pointer"` | `"auto"` |

| reply field | type |
|---|---|
| `already_stored` | boolean |
| `armed` | boolean |
| `by` | string |
| `caveat` | string |
| `command` | string |
| `entries` | array |
| `entry` | string |
| `fmt` | string |
| `length` | integer |
| `mode` | string |
| `note` | string |
| `pointer` | object |
| `ref` | string |
| `state` | string |
| `stored` | boolean |
| `why` | string |

Example, from a live run:

```json
{
  "ref": "0040:006C",
  "mode": "show",
  "length": 4
}
```

```json
{
  "summary": "watch_add 0040:006C: evaluated",
  "status": "ok",
  "ref": "0040:006C",
  "by": "address",
  "mode": "show",
  "fmt": "u32",
  "length": 4,
  "stored": true,
  "armed": false,
  "state": "evaluated"
}
```
<!-- scry-reference:end watch_add -->

**A watch has two halves, and one ref may not be both.** A show watch arms NOTHING: it is a plain
read at every stop (a NaN or infinite `f32`/`f64` is the text `nan`, `inf` or `-inf`, which JSON
has no number for), and a region is `memdump`'s job. A change watch is read at every stop too.

**A change watch breaks when memory changes**, the thing most likely to be misread: a read never
fires it, nor does a write storing the value already there. The debugger's memory breakpoint
compares one byte, so `length` bytes arm a row per byte, each checked at every instruction, which
is why the length is capped. Arming reads the CPU mode off the machine, because the same sixteen
bits mean different things in each and the mode changes under a caller as the program boots.

**`BPLM` is deliberately not offered**: it watches a LINEAR address, and a DPMI program runs
**paged**, so the frame belongs to whoever holds it at that instant. For the same reason a `BPPM`
change-watch fires on the paging host, not the program, so in protected mode it is armed and the
reply says its firing is not to be trusted (`caveat`).

**What `BPLIST` prints is not what you send, nor is it uniform**, so a fixture authored from the
same belief as the code cannot catch a wrong spelling:

```
BPM  0040:006C   ->  00. BPMEM 0040:006C (00)        offset %04X, keyword gains MEM
BPPM 00AF:6024   ->  00. BPPM 00AF:00006024 (00)     offset %08X, keyword does not
```

A watch at a raw `SEG:OFF` keeps the CPU mode of the stop that placed it, as a raw breakpoint
does, and at a stop of the other mode is `unarmable` with no value, its bytes there being another
place's. A watch by symbol or through a pointer is resolved at each stop and keeps no mode.

**Through a pointer**, the pointer is read as a NEAR pointer in the base's own segment, at the
width its type declares (`ptr16{...}`/`ptr32{...}` in the `types` file) or else the CPU mode's. A
class after the width (`ptr16@CODE`) parses and is applied to nothing. A change watch moves with the
pointer (`moved: {from, to}`) and with the CPU mode: a row armed in the other mode is armed again
in this one at the same place, `moved`'s `why` saying so. A null pointer is `null_pointer`, never a
watch at zero.

A pointer base is read as a near pointer at its type's width, else four bytes in protected mode and two in real; a pointer base the table lacks is most likely a stack local. A change watch is trusted in real mode, while under a DJGPP program's paging the reply says its firing is not to be trusted (`caveat`); `command` is the debugger command sent for it. With no `fmt` a typed symbol reads as its type, else the widest unsigned scalar `length` divides; a sized format needs no `length`, which otherwise is a whole number of `fmt` values. `pending` is stored now, armed at the next stop, said in `applied_on_stop`. A change watch moves with its pointer and a null pointer is `null_pointer`, never a watch at zero.

<!-- scry-reference:begin declaration_list -->
## `declaration_list`

*List the declarations*

```text
declaration_list(kind="")
```

List the declarations of `kind` (empty: every kind) with their state, cross-referenced
with the debugger's own list. On a running guest the states are the last stop's survey
(`debugger_read` false).

Reply: `breakpoints`, `regpoints`, `watches` (each kind asked; each row `ref`, `by`, `cpu`,
`created_at`, `origin`, `inherited`, `age_s`, `state`, plus its kind's fields), `foreign`
(debugger entries no declaration resolves to), `debugger_read`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `kind` | one of `""`, `"breakpoint"`, `"regpoint"`, `"watch"` | `""` |

| reply field | type |
|---|---|
| `breakpoints` | array |
| `debugger_read` | boolean |
| `foreign` | object |
| `regpoints` | array |
| `watches` | array |

Example, from a live run:

```json
{
  "kind": "breakpoint"
}
```

```json
{
  "summary": "declaration_list breakpoint: 1 breakpoints declared",
  "status": "ok",
  "breakpoints": [
    {
      "ref": "0000:0002",
      "by": "address",
      "cpu": {
        "available": false,
        "why": "a DOS machine has one cpu, and every row acts on it"
      },
      "created_at": "2026-10-26T13:39:35+00:00",
      "origin": "2026-10-26T13:39:24+00:00#25537.1",
      "inherited": false,
      "age_s": 0,
      "entry": "BP 0000:0002",
      "marked": false,
      "state": "armed"
    }
  ],
  "debugger_read": true
}
```
<!-- scry-reference:end declaration_list -->

<!-- scry-reference:begin declaration_clear -->
## `declaration_clear`

*Clear declarations*

```text
declaration_clear(kind, ref="", all=false)
```

Clear the declarations of `kind`: all with `all=True`, or the one named by the exact `ref`
its declaring reply carried; `breakpoint` takes `breakpoint_interrupt` rows too. Removes only
what this store armed, the declarations at once and, on a running guest, their debugger
rows at the next stop (`pending_disarm`); a `foreign` entry is never deleted.

Refused: a `ref` matching none, naming the refs held; neither `ref` nor `all`, or both
(`bad_argument`).

Reply: `declarations_cleared`, `disarmed`, `pending_disarm` (removed at the next stop),
`note`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `kind` | one of `"breakpoint"`, `"regpoint"`, `"watch"` | required |
| `ref` | string | `""` |
| `all` | boolean | `false` |

| reply field | type |
|---|---|
| `declarations_cleared` | integer |
| `disarmed` | array |
| `note` | string |
| `pending_disarm` | array |

Example, from a live run:

```json
{
  "kind": "breakpoint",
  "ref": "0000:0002"
}
```

```json
{
  "summary": "declaration_clear breakpoint 0000:0002: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": [
    "BP 0000:0002"
  ]
}
```
<!-- scry-reference:end declaration_clear -->
