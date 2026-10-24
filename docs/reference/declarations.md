# The Declarations tools

<!-- scry-reference:begin breakpoint_at -->
## `breakpoint_at`

*Declare a breakpoint*

```text
breakpoint_at(ref, by="auto")
```

Declare a code breakpoint at a SYMBOL or a `SEG:OFF`, and arm it if it can be.

The declaration is STORED on disk keyed by the conf, stamped with this session as its
`origin`, so it survives a rebuild: on every `symbols_load` a symbol re-resolves and
re-arms, while a raw `SEG:OFF` re-arms per BUILD, whoever declared it: at `start` when it
was declared before any map was loaded, after a `symbols_load` of the same map when it was
declared over that map, and `stale` over another build (declaring it again adopts it). A
symbol absent from THIS
build is stored `unresolved`, not refused (it may be inlined this time). A name matching
several symbols is refused, nothing stored; so is an address another declaration of
this store already holds, naming that ref (one breakpoint row is one declaration:
clear that ref or use it). `by` is `auto` (symbol or address by shape)
unless you must force `symbol` or `address`. Arming needs the machine stopped and the
debugger to take the `BP`; the entry is read back from its list.

Reply: `ref` (the string that clears it), `by`, `stored`, `already_stored` (a no-op
re-declaration, adopted by this session), `armed`, `entry` (the debugger's row, e.g.
`BP 00AF:0017A6EC`), `state` (`armed`, `unresolved`, `unarmable`, `pending` when the
guest is running: stored now, armed at the next stop and said so in `applied_on_stop`
with `why`), `marked` and `note` when the symbol carries the linker's mark (a fact, not a
refusal: whether such an address fires is an open question).

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
  "already_stored": false,
  "armed": true,
  "state": "armed",
  "entry": "BP 0000:0002",
  "marked": false
}
```
<!-- scry-reference:end breakpoint_at -->

A code breakpoint in ROM is acknowledged and never fires, though the same command at a RAM address
fires first time. It is neither the dynamic core nor a missing feature. Arming happens after the
machine is released, so it cannot be detected in advance; `run_to`'s non-arrival note names it.

<!-- scry-reference:begin breakpoint_list -->
## `breakpoint_list`

*List the breakpoint declarations*

```text
breakpoint_list()
```

Every breakpoint DECLARATION with its state, cross-referenced with the debugger's
own list. Answers on a RUNNING guest too: then the debugger cannot be asked, so the
states are those of the last stop's survey, `debugger_read` is false and `last_stop` dates
the answer by that stop (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`); with no
stop yet, `last_stop` is unavailable and a symbol's state is `unarmable`. Stopped: read
live, `debugger_read` true.

Reply: `breakpoints`, each with `ref` (the string that clears it), `by`, `cpu`, `created_at`,
`origin` (the session that declared or last adopted it), `inherited` (true for one an earlier
session left), `age_s` (whole seconds since `created_at`), `entry`, `state` -- `armed` (its
entry is in the debugger's list), `unresolved` (the symbol table loaded now, or none, has no
such name), `gone` (armable, and the debugger's list has no such row now: it may never have
been armed in this session), `unarmable` (it cannot be placed now: why says),
`ambiguous` (a name this build defines more than once: nothing is armed for it), `pending`
(declared while the guest ran, applied at the next stop), `stale` (a raw address declared
with no map held now that vouches for it: kept, never re-armed here; declare it again to
adopt it), `orphan` (no origin recorded, where it would otherwise say `gone` or `stale`;
every such row also carries `orphan: true` whatever its state: nobody's, clear it by its
`ref` or declare it again) -- plus `marked` for symbols; and `foreign`, entries the
debugger holds that no declaration of this store resolves to now (a `run_to` whose cleanup
could not be confirmed leaves one), listed and never deleted. `breakpoint_clear` is this
family's broom and never touches a watch; `watch_clear` is the other, and the two together
empty the store.

Takes no argument.

| reply field | type |
|---|---|
| `breakpoints` | array |
| `debugger_read` | boolean |
| `foreign` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "breakpoint_list: 1 declared",
  "status": "ok",
  "breakpoints": [
    {
      "ref": "0000:0002",
      "by": "address",
      "cpu": {
        "available": false,
        "why": "a DOS machine has one cpu, and every row acts on it"
      },
      "created_at": "2026-10-24T16:10:41+00:00",
      "origin": "2026-10-24T16:09:51+00:00#42835.1",
      "inherited": false,
      "age_s": 2,
      "entry": "BP 0000:0002",
      "marked": false,
      "state": "armed"
    }
  ],
  "foreign": [],
  "debugger_read": true
}
```
<!-- scry-reference:end breakpoint_list -->

<!-- scry-reference:begin breakpoint_clear -->
## `breakpoint_clear`

*Clear breakpoint declarations*

```text
breakpoint_clear(ref="", all=false)
```

Clear breakpoint declarations: all of them with `all=True`, or the one named by the
exact `ref` its declaring reply carried (a symbol, a `SEG:OFF`, or a `BPINT NN` /
`BPINT NN AH=NN` row). Removes from the debugger ONLY what this store armed, and only
while the machine is stopped; the declarations themselves are dropped either way. A
`foreign` entry is never deleted, only reported as left.

Reply: `declarations_cleared`, `disarmed` (the debugger rows removed), `pending_disarm`
(rows queued for removal at the next stop because the guest is running: the
declarations are gone now, the rows go then), `note`. A `ref` that matches no
breakpoint declaration is INVALID, naming the refs the store holds; `all=True` on an empty
store is `ok` with 0; neither `ref` nor `all`, or both, is `bad_argument`.

| argument | type | default |
|---|---|---|
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
  "ref": "0000:0002"
}
```

```json
{
  "summary": "breakpoint_clear 0000:0002: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": [
    "BP 0000:0002"
  ],
  "pending_disarm": []
}
```
<!-- scry-reference:end breakpoint_clear -->

<!-- scry-reference:begin breakpoint_interrupt -->
## `breakpoint_interrupt`

*Arm an interrupt breakpoint*

```text
breakpoint_interrupt(number, ah=null, detail=false)
```

Break on an interrupt, optionally on one `ah` function: `BPINT <number> [<ah>]`.

`number` and `ah` are the debugger's HEX values given as integers: pass `0x21` (33) for
DOS, not `21`, which would arm INT 0x15; a DJGPP program's is `0x31` with `ah=2`. This is
how control comes BACK from a running guest on this platform (a host keypress cannot break
in): arm it BEFORE `resume`. While the guest runs it is queued `pending`, as below. The
declaration is STORED under its `BPINT ..` spelling, so `breakpoint_list` shows it and
`breakpoint_clear(ref="BPINT 21")` removes it; arming the same interrupt again is a no-op
that says `already_stored`.

Reply: `ref`, the exact string `breakpoint_clear` takes for it (`BPINT 21`,
`BPINT 21 AH=4B`: the debugger's own row spelling, hex, `AH=` included when `ah` was
given), `stored`, `already_stored`, `entry`; with `detail=True` the acknowledgement's
`screen_delta` (capped, with `screen_chars`/`clipped`), else `omitted` names them: a
fresh arm only, since a pending or already armed one typed nothing. While the
guest runs it is stored `pending` and armed at the next stop.

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
| `screen_chars` | integer |
| `screen_delta` | string |
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
  "already_stored": false,
  "entry": "BPINT 21 AH=4C",
  "omitted": [
    "screen_delta",
    "screen_chars",
    "clipped"
  ],
  "how": "detail=True adds the debugger's repaint for this command"
}
```
<!-- scry-reference:end breakpoint_interrupt -->

It is stored under its `BPINT` spelling and not cleared through the console's index, which deletes
whichever row sits there. Re-arming is a no-op checked against the live list, because `BPINT` sent
twice stacks a second row that a later clear leaves behind as `foreign`.

<!-- scry-reference:begin watch_add -->
## `watch_add`

*Declare a watch*

```text
watch_add(ref, mode, length=0, fmt="auto", by="auto")
```

Declare a WATCH by symbol, by `SEG:OFF`, or at a place reached THROUGH a pointer, read as
`fmt` (little-endian), in one of two modes. The declaration persists like a breakpoint's and
re-resolves on `symbols_load`.

Arguments:
- `mode`: `show` (read at each stop: nothing is armed, the value rides in `watches`)
or `change` (the machine stops when the bytes change, and each stop reads them as `show`
does; trusted in REAL mode, while under a DJGPP program's paging the reply says its firing
is not to be trusted).
- `ref`: a symbol, a `SEG:OFF`, or `[base]`, `[base]+0x28`, `[base]-0x4`, `base->field`, with
`base` a symbol or address holding a POINTER (read at its type's width, else four bytes in
protected mode and two in real), re-resolved at every stop.
- `fmt`: the value grammar: a scalar (`u8` .. `f64`), an array (`u16[8]`), a string
(`char[16]`) or a struct (`{x:i16,y:i16}`). With no `fmt` a typed symbol reads as its type,
else the widest unsigned scalar `length` divides.
- `length`: TOTAL bytes, a whole number of `fmt` values; a sized format needs none. A show
watch is at most 128 bytes; a change watch at most 16, a debugger
row per byte (`entries`), `armed` while every row is held.
- `by`: `auto` (by shape) unless you must force `symbol`, `address` or `pointer`.

Refused: one ref as both show and change; a length over the ceiling; a pointer base the
table lacks (most likely a stack local).  Reply: `ref` (the string `watch_clear` takes),
`by`, `mode`, `stored`, `already_stored`, `state` (`evaluated` for a placed show watch,
`unresolved`, `unarmable`, `null_pointer`; a change watch adds `armed`, or `pending` while
the guest runs, armed at the next stop and said in `applied_on_stop`), `pointer` through a
pointer (`at`, `length`, `value`, `offset`, `field`), and `entry`/`command` for a change
watch.

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
  "already_stored": false,
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
pointer (`moved: {from, to}`), and a null pointer is `null_pointer`, never a watch at zero.

<!-- scry-reference:begin watch_list -->
## `watch_list`

*List the watch declarations*

```text
watch_list()
```

Every watch DECLARATION and its state, on a stopped OR a running guest (running:
states as of the last stop's survey, `debugger_read` false, `last_stop` dating the answer;
see `breakpoint_list`). Reply: `watches`, each with `ref`, `by`,
`cpu`, `created_at`, `origin` (the session that declared or last adopted it), `inherited`,
`age_s`, `mode`,
`length`, `fmt`, `state` (a show watch: `evaluated` once placed, its value in each stop's
reply and not here, or `unresolved`/`ambiguous`/`unarmable`/`null_pointer`; a change watch
additionally
`armed` or `gone`; either `orphan` when it comes from a store that kept no origin: it is
nobody's, clear it by its `ref` or declare it again to adopt it), and `foreign`, memory
breakpoints the debugger holds that no declaration of this store resolves to now. No
watch is re-armed
across sessions, so none is ever `stale`; the origin says whose it is. `watch_clear` is
this family's broom; `breakpoint_clear` never touches a watch, and the two together
empty the store.

Takes no argument.

| reply field | type |
|---|---|
| `debugger_read` | boolean |
| `foreign` | array |
| `watches` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "watch_list: 1 declared",
  "status": "ok",
  "watches": [
    {
      "ref": "0040:006C",
      "by": "address",
      "cpu": {
        "available": false,
        "why": "a DOS machine has one cpu, and every row acts on it"
      },
      "created_at": "2026-10-24T16:10:44+00:00",
      "origin": "2026-10-24T16:09:51+00:00#42835.1",
      "inherited": false,
      "age_s": 0,
      "mode": "show",
      "length": 4,
      "fmt": "u32",
      "state": "evaluated"
    }
  ],
  "foreign": [],
  "debugger_read": true
}
```
<!-- scry-reference:end watch_list -->

<!-- scry-reference:begin watch_clear -->
## `watch_clear`

*Clear watch declarations*

```text
watch_clear(ref="", all=false)
```

Clear watch declarations: all with `all=True`, or the one named by the exact `ref`
its `watch_add` reply carried. Disarms from the debugger only the change-watches this
store armed (show watches armed nothing), and only while the machine is stopped;
declarations are dropped either way. A foreign memory breakpoint is never deleted, only
reported as left.

Reply: `declarations_cleared`, `disarmed`, `pending_disarm` (rows queued for removal
at the next stop because the guest is running), `note`. A `ref` that matches no watch
declaration is INVALID, naming the refs the store holds; `all=True` on an empty store is
`ok` with 0; neither `ref` nor `all`, or both, is `bad_argument`.

| argument | type | default |
|---|---|---|
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
  "ref": "0040:006C"
}
```

```json
{
  "summary": "watch_clear 0040:006C: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": [],
  "pending_disarm": []
}
```
<!-- scry-reference:end watch_clear -->
