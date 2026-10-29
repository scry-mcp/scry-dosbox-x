# The Declarations tools

<!-- scry-reference:begin breakpoint_at -->
## `breakpoint_at`

*Declare a breakpoint*

```text
breakpoint_at(ref, by="auto")
```

Declare a code breakpoint at a symbol or `SEG:OFF`, and arm it if it can be. Stored, and
re-armed on `symbols_load`; a raw `SEG:OFF` goes `stale` over another build.

Refused: a name matching several symbols; an address another declaration holds, naming it. On
a dynamic cpu core, which can pass over it inside a compiled block, `note` says so. A symbol
absent from this build is stored `unresolved`.

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

The declaration is stored on disk keyed by the conf and the program run under it, and stamped with this session as its `origin`, so it survives a rebuild; a raw `SEG:OFF` re-arms per build, whoever declared it: at `start` when declared before any map was loaded, after a `symbols_load` of the same map when declared over that map, and `stale` over another build (declaring it again adopts it). A symbol is stored `unresolved` rather than refused because it may be inlined this time. `by` is `auto` unless a symbol or address must be forced. Arming needs the machine stopped and the debugger to take the `BP`, and the entry is read back from its list. `pending` rows are armed at the next stop, said in `applied_on_stop`. `marked` is a fact about the linker's mark, not a refusal: whether such an address fires is open. `already_stored` is a no-op re-declaration adopted by this session.

<!-- scry-reference:begin breakpoint_interrupt -->
## `breakpoint_interrupt`

*Arm an interrupt breakpoint*

```text
breakpoint_interrupt(number, ah=null, detail=false)
```

Break on an interrupt, optionally one `ah` function. Arm it before `resume`. `number` and
`ah` are hex given as integers: `0x21` for DOS, not `21`. Pending while the guest runs.

Reply: `ref` (e.g. `BPINT 21 AH=4B`, what `declaration_clear` takes), `stored`,
`already_stored`, `armed`, `state` (while the guest runs), `entry` (once armed at a stop);
with `detail=True` also `output`.

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
  "armed": true,
  "entry": "BPINT 21 AH=4C",
  "omitted": ["output", "output_chars", "clipped"],
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
`stored`, `already_stored`, `armed`, `state`, `while_running`, `entry` (on a stopped machine),
`note`.

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
watch_add(ref, mode, length=0, fmt="auto", by="auto", trigger="", trigger_type="w")
```

Declare a watch by symbol, `SEG:OFF` or through a pointer, read as `fmt`. Persists and
re-resolves on `symbols_load`.

`mode`: `show` (read at each stop), `change` (stops when the bytes change), `count` (tallies
every write and its writer), `capture` (a row per access of `trigger`, with the beam line
and the time), `freeze` (pins the bytes at their value: the guest's writes are undone, and
the session is `altered`);
count, capture and freeze never stop the machine. `ref`: a symbol, `SEG:OFF`, or
`[base]+0x28`, `base->field`. `fmt`: a scalar (`u8` .. `f64`), an array (`u16[8]`), a string
(`char[16]`) or a struct (`{x:i16,y:i16}`). `length`: total bytes; at most 128 for
show, 16 for change and 16 for freeze (a debugger row per byte,
`entries`), 1024 for count, 128 for capture. `trigger`,
`trigger_type`: capture only; a capture of reads (`r`) is of `ref` itself, with no
`trigger`, `length` or `fmt`. A count or capture is declared at a stop, by symbol or
`SEG:OFF`, on a build whose debugger has `TAP`; from then on it records while the guest
runs. A freeze likewise, on a heavy-debug build, pinning the values of that stop; each stop
reads its bytes back (`holding`, or `not_held` when something ran past it), and a stored
freeze is not armed again at `start` or `symbols_load`, where its bytes hold other values.

Refused: one ref declared two ways; a length over the ceiling; a pointer base the table
lacks; a count, capture or freeze through a pointer or on a running machine (`not_stopped`);
a count or capture with no `TAP`, a freeze with no heavy debugger (`no_channel`); a freeze
on an offset already frozen (`ambiguous_ref`); a write capture with no `trigger`; `trigger`
or `trigger_type` on another mode.

Reply: `ref`, `by`, `mode`, `fmt`, `length`, `stored`, `already_stored`, `state` (`evaluated`,
`unresolved`, `unarmable`, `null_pointer`, `pending`, `armed`), `armed`, `pointer` (a pointer
`ref`), `entry` (once armed), `caveat` (protected mode); a count or capture's `tally_id`,
`addr`, `trigger`, `trigger_addr`, `trigger_type`; a freeze's `addr`, `entries`, `frozen_hex`;
its account is `declaration_list`'s.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `mode` | one of `"show"`, `"change"`, `"count"`, `"capture"`, `"freeze"` | required |
| `length` | integer | `0` |
| `fmt` | string | `"auto"` |
| `by` | one of `"auto"`, `"symbol"`, `"address"`, `"pointer"` | `"auto"` |
| `trigger` | string | `""` |
| `trigger_type` | one of `"w"`, `"r"` | `"w"` |

| reply field | type |
|---|---|
| `addr` | string |
| `already_stored` | boolean |
| `armed` | boolean |
| `by` | string |
| `caveat` | string |
| `command` | string |
| `entries` | array |
| `entry` | string |
| `fmt` | string |
| `frozen_hex` | string |
| `length` | integer |
| `mode` | string |
| `pointer` | object |
| `ref` | string |
| `state` | string |
| `stored` | boolean |
| `tally_id` | string |
| `trigger` | string |
| `trigger_addr` | string |
| `trigger_type` | string |
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

**A watch has five modes, and one ref is one declaration.** A show watch arms NOTHING: it is a
plain read at every stop (a NaN or infinite `f32`/`f64` is the text `nan`, `inf` or `-inf`, which
JSON has no number for), and a region is `memdump`'s job. A change watch is read at every stop
too. Count and capture never stop the machine; each is a tap the debugger's `TAP` puts in. A
freeze never stops it either: each byte is a debugger `FM` row.

**A freeze is the debugger putting the byte back**, after every instruction its heavy path
steps, so it holds against the guest's own writes and runs past anything that is not an
instruction stepped there: a dynamic core, a DMA transfer. Each stop reads the bytes back and
says `holding` or `not_held`, rather than trusting the row (`gone` when a row was deleted,
`unarmed` in a session that has not armed it, `unlisted` on a running guest). It pins the values
of the stop it is declared at, so a stored freeze is never armed again by `start` or
`symbols_load`, where those bytes hold something else. The debugger lists a freeze by its
offset alone, so any freeze already at the same offset refuses a new one: the two rows could not
be told apart. For the same reason a reply's `entries` are those rows as the debugger lists them,
offset and value with no segment; `addr` is where the freeze is.

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

**Count and capture: every access, without a stop.** A change watch stops at the first write, and
sees only a write that changes a byte; a census of the values a variable takes over a pass, or the
block as it stood at each write of one byte, needs every access. `TAP` wraps the handler of the
physical page holding the place and keeps that page's host pointer out of the TLB for the side it
taps, so every guest access of that side reaches the wrapper, a write storing the value already
there included; the debugger's own reads and writes go past it unrecorded. A count tallies each
dword an access touches in its range, by its data and lanes and by writer, so `total` counts a
write that straddles two dwords twice; a capture of writes keeps one row per write of
`trigger` with the block at `ref` as it stood BEFORE the write landed (the write's own value is the
row's `data`); a capture of reads (`trigger_type="r"`) keeps one row per read of `ref` and no
block. Rows past the cap are counted in `overflow_rows`, values and writers past theirs in
`overflow_values` and `overflow_pcs`, so a cut table says so.

**A row is the access as a 386 put it on its bus**: `data` and `mask` are the lanes of the dword
holding the trigger, little-endian, so a word written over the trigger and its neighbour shows both
lanes and the byte it covered. `pc` is the instruction that made the access, `SSSS:OOOOOOOO`, with
`symbol` when a table places it. `time_s` is the emulated clock, `line` the beam's line computed as
the light pen latches it, and `frame` is the display frame count a stop reads (unavailable only on a build whose `TAP` writes a row's time and line alone); `line` is unavailable before the display has
timed its first frame. A read capture
on code also sees the instruction fetches of that byte.

**What a survey and a listing say.** Each count or capture carries `tally_id` (the debugger's
tap), `addr`, `trigger_addr` and `trigger_type` where it has them, `installed`, `state`
(`tallied` or `captured`; `displaced`; `unlisted` when `TAPLIST` did not list it or could not be read, as on a running guest; `unarmed` when
this session holds no tap for it) and `total`. A stop's survey adds `since_last_stop` (with
`reset` when the total fell) and never the rows or the tables, which would drown every reply.
`declaration_list` adds a count's `values` (each `at`, `raw_hex`, `count`, and `value` when one
access covered the range whole, else `partial`), `values_total`, `writers` (`pc`, `count`,
`symbol`) and `writers_total`, and a capture's `rows_path`, `rows_kept`, `rows_max` and
`first_rows` (each `n`, `frame`, `line`, `time_s`, `pc`, `data`, `mask`, and a write capture's
`raw_hex` and `block`, decoded in `fmt`).

**A tap goes in at a stop.** It replaces a page handler, which the debugger does between
instructions, so a count or capture declared on a running machine is refused `not_stopped`, and
one is armed again at `start` and after `symbols_load` where its ref resolves. Something that
replaces the page's handler afterwards (a video mode set remaps video memory) displaces the tap:
it lists `displaced` and sees nothing more. A dynamic core, which runs code pages through handlers
of its own, is refused when the tap goes in (a conf whose core is `auto` can switch to it later,
in protected mode, and a tap then may miss accesses); the HMA is refused because its alias follows the A20 gate, and a range that
paging splits across non-adjacent pages is refused. Every stop with a tap declared costs one
`TAPLIST`, which flushes the rows and rewrites the tables; `since_last_stop` counts what came since
the previous stop, and a list between stops consumes nothing.

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
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "2026-10-29T04:45:56+00:00",
      "origin": "2026-10-29T04:45:52+00:00#6382.1",
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
  "disarmed": ["BP 0000:0002"]
}
```
<!-- scry-reference:end declaration_clear -->
