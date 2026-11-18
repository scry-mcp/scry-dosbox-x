# The Breakpoints tools

These tools set breakpoints and watches and keep them. Each is saved as you named it, a symbol or an address, so the server sets it again at `start` and after `symbols_load`, even after a rebuild moved the code.

The tools call a saved breakpoint or watch a declaration, as in `declaration_list`. The debugger holds what is set now; the saved breakpoints file holds what you asked for. What they share is in [REFERENCE.md, Breakpoints and watches](../../REFERENCE.md#breakpoints-and-watches).

A registerpoint (`regpoint` in the tool names) is a stop when a condition on the registers comes true. While the program runs nothing can be set: what you ask is saved, reads `pending`, and is set at the next stop. A `count`, `capture` or `freeze` watch is the exception: it is refused until the program stops.

## What each state means

Every reply of these tools, and every row they list, carries a `state`.

| `state` | what it means |
|---|---|
| `armed` | Set in the debugger and able to fire. |
| `pending` | Declared while the program runs, set at its next stop. |
| `counted` | A `control` breakpoint. Nothing is set between runs: `run_to` sets it, counts it and removes it. |
| `evaluated` | A `show` watch. Nothing is set in the debugger: the value is read at every stop. |
| `unresolved` | Its symbol is not in the loaded symbol table. It stays saved and sets nothing until a table has it. |
| `ambiguous` | Its name matches several symbols. |
| `unarmable` | It cannot be set at this stop. `why` says what it waits for. |
| `null_pointer` | A watch through a pointer that reads zero. It stays saved and is looked up again at every stop. |
| `stale` | A raw `SEG:OFF` that no loaded symbol table vouches for. It stays saved and is not set until you declare it again. |
| `orphan` | Saved with no record of the session that made it. Clear it by its `ref`, or declare it again to adopt it. |
| `gone` | Saved, but the debugger no longer lists its row. |

A row also says `inherited: true` when an earlier session saved it. `foreign` lists debugger rows the server did not set, such as one typed through `debug`: they are listed and never deleted.

<!-- scry-reference:begin breakpoint_at -->
## `breakpoint_at`

Set a breakpoint at a symbol or an address, to stop there or to count how often the code runs.

```text
breakpoint_at(ref, by="auto", role="stop")
```

### Try it

On Bricks, the game this repository builds, stopped in play with `bricks.sym` loaded.

Ask:

> Stop the game the next time a brick is hit.

Call:

```text
breakpoint_at(ref="brick_hit")
```

Reply, 5 of 9 fields:

```json
{
  "summary": "breakpoint_at brick_hit: armed",
  "status": "ok",
  "role": "stop",
  "state": "armed",
  "entry": "BP 08DF:02C8"
}
```

Then let the game run, for a minute at most:

Call:

```text
resume(seconds=60)
```

Reply, 4 of 15 fields:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002C8",
  "verdict": "OTHER_STOP",
  "cause": "breakpoint brick_hit (by symbol) at 08DF:000002C8",
  "pc": "08DF:000002C8"
}
```

The breakpoint is armed at `08DF:02C8`. `OTHER_STOP` means something other than the call's own target stopped the machine: here, `cause` names the breakpoint on `brick_hit`.

<details><summary>The two replies, whole</summary>

The first call's:

```json
{
  "summary": "breakpoint_at brick_hit: armed",
  "status": "ok",
  "ref": "brick_hit",
  "by": "symbol",
  "role": "stop",
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 08DF:02C8"
}
```

The second call's:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002C8",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:000002C8",
  "cpu_mode": "real",
  "frame": 244,
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000000",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000032",
    "EDI": "0x00006410",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "breakpoint brick_hit (by symbol) at 08DF:000002C8",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 10,
  "instruction": {
    "address": "08DF:000002C8",
    "bytes": "88DF",
    "text": "mov bh, bl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "comment": "AL = row, BL = column of the brick that falls",
    "symbol": "brick_hit",
    "delta": 0
  }
}
```

</details>

### Arguments

- `ref` (string, required): Where to break: a symbol or a `SEG:OFF` address in the code.
- `by` (one of `"auto"`, `"symbol"`, `"address"`, default `"auto"`): How `ref` is read: `symbol` or `address` forces one. Left at `auto`, a ref with a colon is an address and anything else a symbol.
- `role` (one of `"stop"`, `"control"`, default `"stop"`): `stop` halts the machine there. `control` never halts a run: every `run_to` counts how often the code runs.

### What comes back

- `state`: `armed` when set, `counted` for a `control`, `pending` while the program runs. The top of the page lists the rest.
- `entry`: The debugger's own row for the breakpoint, once armed.
- `stored`: `true` when the server saved the breakpoint. It is set again at `start` and after `symbols_load`.
- `already_stored`: `true` when the same breakpoint was saved already, so the call changed nothing.
- `why`: The reason, when `state` is `unarmable`.
- `marked`: `true` when the symbol carries the linker's mark. Whether a breakpoint there fires is an open question, and `note` says so.

<details><summary>All 10 reply fields</summary>

- `already_stored` (boolean)
- `armed` (boolean)
- `by` (string)
- `entry` (string)
- `marked` (boolean)
- `ref` (string)
- `role` (string)
- `state` (string)
- `stored` (boolean)
- `why` (string)

</details>

### What it refuses

- A name that matches several symbols (`ambiguous_ref`).
- An address another saved breakpoint already holds; the message names it (`ambiguous_ref`).
- The same `ref` under the other role: clear it first (`bad_argument`).
- A `SEG:OFF` that is not hex on both sides of the colon (`bad_argument`).

### Why it works this way

A `control` is for an address you know runs. `run_to` counts it beside its target, so a target never reached can be told from code that never ran.

A DOSBox-X breakpoint always halts, so the debugger holds a control only while a `run_to` counts it: each hit stops the machine, is counted and let go. Between runs nothing is set, so `resume`, `run_for` and a wait never stop there.

A symbol missing from the loaded symbol table is saved `unresolved`, not refused: the compiler may have inlined it this time. A raw `SEG:OFF` belongs to the build it was declared over and goes `stale` over another.

<details><summary>More on why</summary>

- A breakpoint at a ROM address is accepted and never fires, while the same command at a RAM address does. Nothing detects it in advance.
- When a `run_to` does not reach such a target, its note names this cause.
- On a dynamic cpu core, or `core=auto` once protected-mode code runs, execution can pass over a breakpoint inside a compiled block. `note` says so.
- A raw `SEG:OFF` declared before any symbol table was loaded is set again at `start`. One declared over a map is set again after a `symbols_load` of the same map.
- `run_to`'s own `control` counts for that run alone: saved as one, it would stop the machine once per hit on every later run.
- An `on_breakpoint` wait on a control is refused.
- Setting needs the machine stopped, and the row is read back from the debugger's list.
- A `pending` one is set by the first call that meets the next stop, a reader such as `registers` included. That call's reply lists it in `applied_on_stop`.
- `by` says how the ref was read and `role` which role it has. `armed` is `true` once the debugger holds the row.

</details>

### Related tools

- [`run_to`](run.md#run_to)
- [`breakpoint_interrupt`](#breakpoint_interrupt)
- [`declaration_list`](#declaration_list)
- [`declaration_clear`](#declaration_clear)
- [`symbols_load`](names.md#symbols_load)
- [`watch_add`](#watch_add)

<details><summary>The contract your client receives</summary>

```text
Declare a code breakpoint at a symbol or `SEG:OFF`, as a `stop` (armed if it can be) or a
`control` (never halts; armed only while a `run_to` counts its hits). Stored, and re-armed on
`symbols_load`; a raw `SEG:OFF` goes `stale` over another build. `by`: `auto` (this server's
choice), `symbol` or `address`, which is how the ref is read.

Refused: a name matching several symbols; an address another declaration holds, naming it; one
ref under the other role. On a dynamic cpu core, or `auto` (protected-mode code runs dynamic),
which can pass over it inside a compiled block, `note` says so. A symbol absent from this
build is stored `unresolved`.

Reply: `ref`, `role`, `stored`, `already_stored`, `armed`, `entry` (once armed), `state`
(`armed`, `counted` for a control, `unresolved`, `unarmable`, `pending` while the guest runs),
`why`, `marked` and `note` for a linker-marked symbol.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end breakpoint_at -->

<!-- scry-reference:begin breakpoint_interrupt -->
## `breakpoint_interrupt`

Stop the machine when the program calls an interrupt, optionally only one `ah` function of it.

```text
breakpoint_interrupt(number, ah=null, detail=false)
```

### Try it

On Bricks, the game this repository builds, stopped in play just after its quit flag was written, so its next pass of the main loop exits.

Ask:

> Stop the game when it calls DOS to exit.

Call:

```text
breakpoint_interrupt(number="0x21", ah="0x4C")
```

Reply, 6 of 8 fields:

```json
{
  "summary": "breakpoint_interrupt BPINT 21 AH=4C: stored",
  "status": "ok",
  "ref": "BPINT 21 AH=4C",
  "stored": true,
  "armed": true,
  "entry": "BPINT 21 AH=4C"
}
```

Then let the game run, for a minute at most:

Call:

```text
resume(seconds=60)
```

Reply, 4 of 15 fields:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:0000013C",
  "verdict": "OTHER_STOP",
  "cause": "most likely the held `BPINT 21 AH=4C`: the guest is at `int 21`, at 08DF:0000013C",
  "pc": "08DF:0000013C"
}
```

`BPINT 21 AH=4C` is the breakpoint's name, which `declaration_clear` takes. The game then stops at its exit call, and `cause` gives that interrupt breakpoint as the most likely reason.

<details><summary>The two replies, whole</summary>

The first call's:

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

The second call's:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:0000013C",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:0000013C",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": {
    "EAX": "0x00004c00",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x00000615",
    "EDI": "0x00006192",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x0000013c",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:00000617",
      "frozen_hex": "03",
      "entries": ["FM 00000617 (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "most likely the held `BPINT 21 AH=4C`: the guest is at `int 21`, at 08DF:0000013C",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 0"], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": {
    "address": "08DF:0000013C",
    "bytes": "CD21",
    "text": "int 0x21",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 33
  }
}
```

</details>

### Arguments

- `number` (integer or string, required): The interrupt, `0x00` to `0xFF`, as an integer or a `0x` string: `"0x21"` is DOS.
- `ah` (integer or string, optional): Stop only when `AH` holds this function number, `0x00` to `0xFF`. Left out, every call of the interrupt stops.
- `detail` (boolean, default `false`): `true` adds what the debugger printed for the command, as `output`.

### What comes back

- `ref`: The breakpoint's name, such as `BPINT 21 AH=4B`. `declaration_clear` takes it.
- `armed`: `true` once the debugger holds it. `false` while the program runs: it is set at the next stop.
- `state`: `pending`, and only while the program runs.
- `entry`: The debugger's own row for it, once armed.
- `already_stored`: `true` when the same breakpoint was saved already: nothing was stacked.
- `output`: With `detail=True`, the end of what the debugger printed. `output_chars` is its full length, and `clipped` says it was cut.

<details><summary>All 9 reply fields</summary>

- `already_stored` (boolean)
- `armed` (boolean)
- `clipped` (boolean)
- `entry` (string)
- `ref` (string)
- `output` (string)
- `output_chars` (integer)
- `state` (string)
- `stored` (boolean)

</details>

### What it refuses

- A `number` or an `ah` outside `0x00` to `0xFF` (`bad_argument`).

### Why it works this way

It brings a running program back at that interrupt. `stop` brings it back wherever it is, and a key pressed on the host cannot. Set it before `resume`.

It is saved under its `BPINT` text, so `declaration_list` shows it and `declaration_clear(kind="breakpoint")` removes it by `ref`. It is never cleared by the debugger's row number, which would delete whichever row sits there.

Setting the same one again does nothing, checked against the debugger's list. Sent twice, the debugger stacks a second row that a later clear leaves behind as `foreign`.

<details><summary>More on why</summary>

- A DJGPP program can be caught at interrupt `0x31` with `ah=2`.
- `output` comes only from a call that set a new breakpoint: one left `pending` or already armed typed nothing.
- Without `detail`, `omitted` names the fields left out.
- `stored` is `true` once the server saved it.

</details>

### Related tools

- [`resume`](run.md#resume)
- [`stop`](run.md#stop)
- [`interrupt_vectors`](machine.md#interrupt_vectors)
- [`declaration_list`](#declaration_list)
- [`declaration_clear`](#declaration_clear)
- [`breakpoint_at`](#breakpoint_at)

<details><summary>The contract your client receives</summary>

```text
Break on an interrupt, optionally one `ah` function. Arm it before `resume`. `number` and
`ah` are `0x` hex (`"0x21"` for DOS) or integers, 0x00 to 0xFF. Pending while the guest
runs.

Reply: `ref` (e.g. `BPINT 21 AH=4B`, what `declaration_clear` takes), `stored`,
`already_stored`, `armed`, `state` (while the guest runs), `entry` (once armed);
with `detail=True` also `output`.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end breakpoint_interrupt -->

<!-- scry-reference:begin regpoint_add -->
## `regpoint_add`

Stop the machine when a condition on the registers comes true, wherever the program is, to find who puts a value in a register.

```text
regpoint_add(condition)
```

### Try it

On Bricks, the game this repository builds, stopped inside `brick_hit` with `bricks.sym` loaded.

Ask:

> Stop as soon as DX holds 3DAh, the VGA status port.

Call:

```text
regpoint_add(condition="DX==3DA")
```

Reply, 5 of 10 fields:

```json
{
  "summary": "regpoint_add DX==3DA: armed",
  "status": "ok",
  "ref": "DX==3DA",
  "state": "armed",
  "entry": "BPIF DX==3DA"
}
```

Then let the game run, for a minute at most:

Call:

```text
resume(seconds=60)
```

Reply, 4 of 16 fields:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:00000583",
  "verdict": "OTHER_STOP",
  "cause": "registerpoint DX==3DA, whose condition came true at 08DF:00000583",
  "pc": "08DF:00000583"
}
```

The registerpoint is armed as the debugger's `BPIF DX==3DA`. The game then stops where DX takes that value: `cause` names the registerpoint and the address.

<details><summary>The two replies, whole</summary>

The first call's:

```json
{
  "summary": "regpoint_add DX==3DA: armed",
  "status": "ok",
  "ref": "DX==3DA",
  "by": "expr",
  "condition": "DX==3DA",
  "stored": true,
  "while_running": false,
  "armed": true,
  "state": "armed",
  "entry": "BPIF DX==3DA"
}
```

The second call's:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:00000583",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:00000583",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x0000000f",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000615",
    "EDI": "0x00006266",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000583",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": 2},
      "bytes": "e6004e0002000200"
    }
  ],
  "cause": "registerpoint DX==3DA, whose condition came true at 08DF:00000583",
  "regpoint_hit": {
    "ref": "DX==3DA",
    "condition": "DX==3DA",
    "pc": "08DF:00000583",
    "note": "still armed: a registerpoint stops at every instruction where its condition holds, so the next advance stops again; `declaration_clear(kind=\"regpoint\")` removes it"
  },
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 0 7"], "mark": "<volatile>"},
  "stop_seq": 7,
  "instruction": {
    "address": "08DF:00000583",
    "bytes": "EC",
    "text": "in al, dx",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 3
  }
}
```

</details>

### Arguments

- `condition` (string, required): Up to four terms joined by `&&`. Each is a register (`AX`, `EAX`, `AL`, `CS`, `FLAGS`), a comparison and a hex value: `AX==3B`.

### What comes back

- `state`: `armed` when set, `pending` while the program runs. The top of the page lists the rest.
- `ref`: The condition as the debugger prints it back. `declaration_clear` takes it.
- `entry`: The debugger's own row for the registerpoint, once armed.
- `already_stored`: `true` when the same registerpoint was saved already, so the call changed nothing.
- `while_running`: `true` when the program was running as the call arrived.

<details><summary>All 9 reply fields</summary>

- `already_stored` (boolean)
- `armed` (boolean)
- `by` (string)
- `condition` (string)
- `entry` (string)
- `ref` (string)
- `state` (string)
- `stored` (boolean)
- `while_running` (boolean)

</details>

### What it refuses

- A term that is not a register, a comparison and a hex value (`bad_argument`).
- A DOSBox-X whose debugger has no `BPIF` command (`no_channel`).

### Why it works this way

The debugger compiles the terms once and checks them before every instruction. It fires as the condition comes true: one set while it already holds waits until it no longer does, and a resumed machine does not stop again at once.

When the debugger's `RUNSTATE` command names the row that fired, the stop is credited to that registerpoint. Otherwise the stop's `attribution.regpoints_holding` lists the registerpoints whose condition holds, as the likely cause.

A registerpoint has no address, so it is never `stale` and has no `role`. It compares and never assigns.

<details><summary>More on why</summary>

- The comparisons are `==`, `!=`, `<`, `<=`, `>` and `>=`, and the value may carry `0x`.
- `by` is always `expr`, and `condition` repeats `ref`. `armed` is `true` once the debugger holds the row.

</details>

### Related tools

- [`breakpoint_at`](#breakpoint_at)
- [`registers`](read.md#registers)
- [`declaration_list`](#declaration_list)
- [`declaration_clear`](#declaration_clear)
- [`watch_add`](#watch_add)
- [`build_check`](session.md#build_check)

<details><summary>The contract your client receives</summary>

```text
Declare a registerpoint: the machine stops when `condition` comes true, wherever in the
program ("who puts this value in this register"). Stored, re-armed at `start`; pending while
the guest runs. Needs the debugger's `BPIF`.

`condition`: up to four terms joined by `&&`, each a register (`AX`, `EAX`, `AL`, `CS`, ...,
`FLAGS`), a comparison (`==`, `!=`, `<`, `<=`, `>`, `>=`) and a hex value (`AX==3B`,
`0x` allowed); compares, never assigns.

Refused: a term not in that shape (`bad_argument`); a build without `BPIF` (`no_channel`).

Reply: `ref` (the condition as the debugger prints it back, what `declaration_clear` takes),
`stored`, `already_stored`, `armed`, `state`, `while_running`, `entry` (once armed),
`note`.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end regpoint_add -->

<!-- scry-reference:begin watch_add -->
## `watch_add`

Keep a variable in view at every stop, stop the machine when it changes, or count every write to it, by name.

```text
watch_add(ref, mode, length=0, fmt="auto", by="auto", trigger="", trigger_type="w")
```

### Try it

On Bricks, the game this repository builds, stopped inside `brick_hit` as the first brick falls, with `bricks.sym` loaded.

Ask:

> Stop the game when the score changes, and show me where it stopped.

Call:

```text
watch_add(ref="score", mode="change", fmt="u16")
```

Reply, 5 of 13 fields:

```json
{
  "summary": "watch_add score: armed",
  "status": "ok",
  "state": "armed",
  "entry": "BPMEM 08DF:0615",
  "entries": ["BPMEM 08DF:0615", "BPMEM 08DF:0616"]
}
```

Then let the game run, for a minute at most:

Call:

```text
resume(seconds=60)
```

Reply, 5 of 15 fields:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002EB",
  "verdict": "OTHER_STOP",
  "pc": "08DF:000002EB",
  "cpu_mode": "real",
  "frame": 36
}
```

`OTHER_STOP` is a stop the call did not target, and its `cause` cannot name a watch. `pc` is just past the instruction that wrote the score, and `watches` in the whole reply holds the new value.

<details><summary>The two replies, whole</summary>

The first call's:

```json
{
  "summary": "watch_add score: armed",
  "status": "ok",
  "ref": "score",
  "by": "symbol",
  "mode": "change",
  "fmt": "u16",
  "length": 2,
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BPMEM 08DF:0615",
  "entries": ["BPMEM 08DF:0615", "BPMEM 08DF:0616"],
  "command": "BPM 08DF:0615"
}
```

The second call's:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002EB",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:000002EB",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x0000003c",
    "EBX": "0x00000700",
    "ECX": "0x005b001e",
    "EDX": "0x00000000",
    "ESI": "0x00000007",
    "EDI": "0x00001ee1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002eb",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": -2},
      "bytes": "e6004e000200feff"
    },
    {
      "ref": "score",
      "by": "symbol",
      "mode": "change",
      "length": 2,
      "fmt": "u16",
      "state": "armed",
      "value": 60,
      "bytes": "3c00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:000002EB, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 6,
  "instruction": {
    "address": "08DF:000002EB",
    "bytes": "F71E2706",
    "text": "neg word ptr [0x627]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 35
  }
}
```

</details>

### The five modes

| mode | what it does | stops? |
|---|---|---|
| `show` | Reads the value at every stop. | no |
| `change` | Stops when the bytes change. | yes |
| `count` | Counts every write and which instruction made it. | no |
| `capture` | Logs a row per access, with the screen line being drawn and the time. | no |
| `freeze` | Holds the bytes at their value: whatever the program writes is undone. | no |

### Arguments

- `ref` (string, required): What to watch: a symbol, a `SEG:OFF` address, or an address reached through a pointer (`[base]+0x28`, `base->field`).
- `mode` (one of `"show"`, `"change"`, `"count"`, `"capture"`, `"freeze"`, required): `show`, `change`, `count`, `capture` or `freeze`, as above.
- `length` (integer, default `0`): Total bytes; not needed when `fmt` has a size or the symbol has a type. At most 128 for `show` and `capture`, 16 for `change` and `freeze`, 1024 for `count`.
- `fmt` (string, default `"auto"`): How the bytes read: a scalar (`u8` to `f64`), an array (`u16[8]`), a string (`char[16]`) or a struct (`{x:i16,y:i16}`).
- `by` (one of `"auto"`, `"symbol"`, `"address"`, `"pointer"`, default `"auto"`): How `ref` is read: `symbol`, `address` or `pointer` forces one; `auto` lets the server choose.
- `trigger` (string, default `""`): For `capture` only: the address whose every write takes a row holding the block at `ref`.
- `trigger_type` (one of `"w"`, `"r"`, default `"w"`): `w` takes writes. On a `capture`, `r` takes reads of `ref` itself, with no `trigger`, `length` or `fmt`.

### What comes back

- `state`: `armed` when set in the debugger and able to fire, `evaluated` for a `show` watch, `pending` while the program runs. The top of the page lists the rest.
- `entry`: The debugger's own row for the watch, once armed.
- `stored`: The server saved the watch, and sets it again after `symbols_load`.
- `caveat`: A warning: in protected mode a `change` watch can fire when nothing changed.
- `entries`: Every debugger row the watch uses, one per byte, for `change` and `freeze`.
- `frozen_hex`: For `freeze`: the bytes being held, in hex.

<details><summary>All 21 reply fields</summary>

- `addr` (string)
- `already_stored` (boolean)
- `armed` (boolean)
- `by` (string)
- `caveat` (string)
- `command` (string)
- `entries` (array)
- `entry` (string)
- `fmt` (string)
- `frozen_hex` (string)
- `length` (integer)
- `mode` (string)
- `pointer` (object)
- `ref` (string)
- `state` (string)
- `stored` (boolean)
- `tally_id` (string)
- `trigger` (string)
- `trigger_addr` (string)
- `trigger_type` (string)
- `why` (string)

</details>

### What it refuses

- One `ref` declared two ways (`bad_argument`).
- A `length` over the mode's maximum (`bad_argument`).
- A `count`, `capture` or `freeze` while the program runs (`not_stopped`), or through a pointer.
- A `count` or `capture` on a DOSBox-X without the `TAP` debugger command, or a `freeze` on one built without heavy debugging (`no_channel`).
- A `freeze` on an offset already frozen (`ambiguous_ref`).
- `trigger` on any mode but `capture`, and a write capture without one (`bad_argument`).
- A pointer base the symbol table lacks, most likely a stack local (`unknown_ref`).
- A name that matches several symbols, or a `change` watch on a byte another watch already holds (`ambiguous_ref`).

### Why it works this way

A `change` watch breaks when memory changes, which is the thing most likely to be misread: a read never fires it, nor does a write storing the value already there. The debugger compares one byte, so a watch arms a row per byte, and that is why its length is capped.

`count` and `capture` exist for what a stop cannot give: every value a variable takes over a stretch, and who wrote each, while the program keeps running.

A `freeze` is the debugger putting each byte back after every instruction, so it holds against the program's own writes. It holds the values of the stop it is declared at, so a saved freeze is never set again by `start` or `symbols_load`.

<details><summary>More on why</summary>

On every watch:

- A `show` watch sets nothing: it is a plain read at every stop. A `change` watch is read at every stop too.
- A `change` watch declared while the program runs is `pending`. The first call that meets the next stop sets it, a reader included, and lists it in `applied_on_stop`.
- A watch saved with no record of its session, marked `orphan: true`, is still read at every stop.
- A NaN or infinite `f32` or `f64` reads as the text `nan`, `inf` or `-inf`, which JSON has no number for.
- A region is `memdump`'s job, which is why lengths are limited.
- With `fmt` left at `auto`, a typed symbol reads as its type, else as the widest unsigned scalar that divides `length`. Otherwise `length` is a whole number of `fmt` values.
- `why` gives the reason for a state that sets nothing, and `addr` is where a `count`, `capture` or `freeze` sits.

On `change`:

- Arming reads the CPU mode off the machine: the same `SEG:OFF` is a different byte in each mode, and the mode changes as the program boots.
- The debugger's `BPLM`, a watch on a linear address, is not offered.
- A DPMI program, a DOS program in protected mode, runs paged, so a memory frame belongs to whoever holds it at that instant.
- For the same reason a protected-mode `change` watch fires on the paging host, not on the program. It is armed, and `caveat` says not to trust its firing.
- In real mode a `change` watch is trusted.
- A watch at a raw `SEG:OFF` keeps the CPU mode of the stop that set it. At a stop of the other mode it reads `unarmable` with no value.
- A watch by symbol or through a pointer is resolved at each stop and keeps no mode.
- `command` is the debugger command sent, and `entry` the row as the debugger lists it: `BPM 0040:006C` lists as `BPMEM 0040:006C`.
- A protected-mode row, `BPPM`, lists its offset in eight digits.

Through a pointer:

- The pointer is read as a near pointer in the base's own segment, at the width its type gives (`ptr16{...}`, `ptr32{...}` in the `types` file).
- With no such type it is four bytes in protected mode and two in real mode. A class after the width (`ptr16@CODE`) is accepted and changes nothing.
- A `change` watch moves with its pointer (`moved`, with `from` and `to`) and with the CPU mode: a row armed in the other mode is armed again in this one.
- A null pointer is `null_pointer`, never a watch at address zero.
- `pointer` holds where the pointer was read (`at`, `length`), its `value`, and the `offset` and `field` added.

On `count` and `capture`:

- The debugger's `TAP` records every access the program makes to that memory, a write storing the value already there included. The debugger's own reads and writes are not recorded.
- A `count` adds up each 32-bit word an access touches, by value and by writer, so `total` counts a write that straddles two words twice.
- A capture of writes keeps the block at `ref` as it stood before the write landed; the write's own value is the row's `data`.
- A capture of reads keeps one row per read of `ref` and no block. On code it also sees the instruction fetches of that byte.
- It goes in at a stop, because it replaces the handler of a memory page, which the debugger does between instructions.
- It is set again at `start` and after `symbols_load`, where its `ref` resolves.
- Something that replaces the page's handler later, such as a video mode change, displaces it: it lists `displaced` and sees nothing more until declared again.
- It needs a cpu core that reads memory through the page handlers, so the dynamic core is refused. Under `core=auto` a protected-mode program is already on that core when stopped.
- One set from real mode cannot cover extended memory. For a DPMI or DJGPP program's variables, start on the normal core: `flags=["-set","cpu core=normal"]`.
- The high memory area is refused because its alias follows the A20 line. So is a range that paging splits across pages that are not adjacent.
- Each stop with one saved costs one `TAPLIST`, which writes its rows and tables to disk.
- `tally_id` is the debugger's number for it, and `trigger_addr` where `trigger` resolves.

On `freeze`:

- It does not hold against what is not an instruction the debugger steps: a dynamic core, a DMA transfer. Each stop reads the bytes back and says `holding` or `not_held`.
- The debugger lists a freeze by its offset alone, so a second one at the same offset is refused: the two rows could not be told apart.
- `entries` are those rows, offset and value with no segment. `addr` is where the freeze is.
- A freeze writes to the machine, so the session reads `altered`, which means written to.

</details>

### Related tools

- [`declaration_list`](#declaration_list)
- [`declaration_clear`](#declaration_clear)
- [`breakpoint_at`](#breakpoint_at)
- [`symbols_load`](names.md#symbols_load)
- [`scan`](scan.md#scan)
- [`memdump`](read.md#memdump)

<details><summary>The contract your client receives</summary>

```text
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

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end watch_add -->

<!-- scry-reference:begin declaration_list -->
## `declaration_list`

List the saved breakpoints, registerpoints and watches, each with its state checked against the debugger's own list.

```text
declaration_list(kind="")
```

### Try it

On Bricks, the game this repository builds, stopped after a recording, with three watches saved: one shown at every stop, one counting writes, one capturing reads.

Ask:

> Which breakpoints and watches are set right now?

Call:

```text
declaration_list()
```

Reply, 5 of 6 fields:

```json
{
  "summary": "declaration_list: 0 breakpoints declared, 0 regpoints declared, 3 watches declared",
  "status": "ok",
  "breakpoints": [],
  "regpoints": [],
  "debugger_read": true
}
```

Three watches are saved, and no breakpoint or registerpoint. `debugger_read` is `true`: the states come from the debugger's own list, read at this stop.

<details><summary>The whole reply</summary>

```json
{
  "summary": "declaration_list: 0 breakpoints declared, 0 regpoints declared, 3 watches declared",
  "status": "ok",
  "breakpoints": [],
  "regpoints": [],
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated"
    },
    {
      "ref": "score",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "count",
      "length": 2,
      "fmt": "u16",
      "tally_id": "1",
      "addr": "08DF:00000615",
      "installed": true,
      "state": "tallied",
      "total": 1,
      "overflow_values": 0,
      "overflow_pcs": 0,
      "values": [
        {"at": "08DF:00000615", "raw_hex": "4600", "count": 1, "value": 70}
      ],
      "values_total": 1,
      "writers": [
        {"pc": "08DF:000002E7", "count": 1, "symbol": "brick_hit+0x1f"}
      ],
      "writers_total": 1
    },
    {
      "ref": "paddle_x",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "capture",
      "length": 1,
      "fmt": "u8",
      "tally_id": "2",
      "addr": "08DF:0000061F",
      "trigger_type": "r",
      "installed": true,
      "state": "captured",
      "total": 110,
      "rows_path": "<volatile>",
      "rows_kept": 110,
      "overflow_rows": 0,
      "rows_max": 100000,
      "first_rows": [
        {
          "n": 1,
          "frame": 37,
          "line": 417,
          "time_s": 0.532617,
          "pc": "08DF:000003E4",
          "data": "0xd4000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 2,
          "frame": 38,
          "line": 417,
          "time_s": 0.5468845999999999,
          "pc": "08DF:000003E4",
          "data": "0xd6000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 3,
          "frame": 39,
          "line": 417,
          "time_s": 0.5611531,
          "pc": "08DF:000003E4",
          "data": "0xd8000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 4,
          "frame": 40,
          "line": 417,
          "time_s": 0.5754217,
          "pc": "08DF:000003E4",
          "data": "0xda000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 5,
          "frame": 41,
          "line": 417,
          "time_s": 0.589689,
          "pc": "08DF:000003E4",
          "data": "0xdc000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 6,
          "frame": 42,
          "line": 417,
          "time_s": 0.6039579,
          "pc": "08DF:000003E4",
          "data": "0xde000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        "... 18 more"
      ]
    }
  ],
  "debugger_read": true
}
```

</details>

### Arguments

- `kind` (one of `""`, `"breakpoint"`, `"regpoint"`, `"watch"`, default `""`): `breakpoint`, `regpoint` or `watch`. Left empty, every kind.

### What comes back

- `breakpoints`: The saved breakpoints, interrupt breakpoints included. Each row has `ref`, `role`, `state` and, once armed, the debugger's `entry`.
- `regpoints`: The saved registerpoints, each with its `condition`, `state` and `entry`.
- `watches`: The saved watches, each with `mode`, `length`, `fmt` and `state`. A `count` or a `capture` adds its tables.
- `foreign`: Debugger rows the server did not set, by kind, as the debugger lists them. They are listed and never deleted.
- `debugger_read`: `false` while the program runs: the states are then the last stop's, which `last_stop` dates.

<details><summary>All 5 reply fields</summary>

- `breakpoints` (array)
- `debugger_read` (boolean)
- `foreign` (object)
- `regpoints` (array)
- `watches` (array)

</details>

### Why it works this way

At a stop each state is the debugger's own answer: the call reads its list back. While the program runs the debugger cannot be asked, so the rows carry the last stop's states.

`inherited` is `true` on a row an earlier session saved, since no reply names this session to compare with. Nothing expires: a row another session left stays until it is cleared by its `ref`.

<details><summary>More on why</summary>

What a row carries:

- Every row: `ref`, `by` (how the ref is read), `cpu`, `created_at`, `origin` (the session that saved it), `inherited`, `age_s`, `state`, and `why` where the state needs a reason.
- `cpu` is always an object with `available` set to `false` and a `why`: a DOS machine has one cpu.
- A breakpoint adds `role`, `entry` and `marked`. A row with no session recorded adds `orphan: true`.
- A registerpoint adds `condition` and `entry`.
- A watch adds `mode`, `length`, `fmt`, `pointer` for a ref through one, and a `change` watch's `entry`.
- A `count` or a `capture` adds `tally_id`, `addr`, `trigger`, `trigger_addr`, `trigger_type`, `installed` and `total`.
- A `count` adds `values` (each `at`, `raw_hex`, `count`, and `value` or `partial`), `values_total` and `overflow_values`.
- It also adds `writers` (each `pc`, `count`, `symbol`), `writers_total` and `overflow_pcs`.
- A `capture` adds `rows_path`, `rows_kept`, `rows_max`, `overflow_rows` and `first_rows`.
- Each of `first_rows` has `n`, `frame`, `line`, `time_s`, `pc`, `symbol`, `data`, `mask`, and a write capture's `raw_hex` and `block`.
- A `freeze` adds `addr`, `entries`, `frozen_hex` and `bytes`, what the memory holds now.

The states of a `count`, a `capture` and a `freeze`, beside those at the top of the page:

| `state` | what it means |
|---|---|
| `tallied`, `captured` | Installed and recording. |
| `displaced` | The memory page's handler was replaced since, so it sees nothing more. Declare it again. |
| `unlisted` | The debugger's list did not show it or could not be read, as while the program runs. |
| `unarmed` | This session has not set it. |
| `holding`, `not_held` | A freeze whose bytes still are, or no longer are, the frozen ones. |
| `unreadable` | A freeze whose bytes could not be read. `why` says the reason. |

What the tables say:

- A value's `value` is given when one access covered the range whole; otherwise the row is `partial`.
- `data` and `mask` are the 32-bit word that holds the trigger and which of its bytes the access touched. A word written over the trigger and its neighbour shows both.
- `pc` is the instruction that made the access, with `symbol` when a symbol table names it.
- `time_s` is the emulated clock, `line` the screen line being drawn and `frame` the display's frame count.
- `line` is unavailable before the display has timed its first frame, and `frame` on a DOSBox-X whose `TAP` writes only a row's time and line.
- Rows past the limit are counted in `overflow_rows`, values and writers past theirs in `overflow_values` and `overflow_pcs`, so a table that was cut says so.
- A stop's reply adds `since_last_stop`, and `reset` when the total fell, and never the rows or tables. A listing between two stops uses up nothing.

</details>

### Related tools

- [`declaration_clear`](#declaration_clear)
- [`breakpoint_at`](#breakpoint_at)
- [`breakpoint_interrupt`](#breakpoint_interrupt)
- [`regpoint_add`](#regpoint_add)
- [`watch_add`](#watch_add)
- [`status`](session.md#status)

<details><summary>The contract your client receives</summary>

```text
List the declarations of `kind` (empty: every kind) with their state, cross-referenced
with the debugger's own list. On a running guest the states are the last stop's survey
(`debugger_read` false).

Reply: `breakpoints`, `regpoints`, `watches` (each kind asked; each row `ref`, `by`, `cpu`,
`created_at`, `origin`, `inherited`, `age_s`, `state`, plus its kind's fields), `foreign`
(debugger entries no declaration resolves to), `debugger_read`.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end declaration_list -->

<!-- scry-reference:begin declaration_clear -->
## `declaration_clear`

Remove saved breakpoints, registerpoints or watches: one by its `ref`, or every one of a kind.

```text
declaration_clear(kind, ref="", all=false)
```

### Try it

On Bricks, the game this repository builds, stopped with the watch on the score that the `watch_add` entry sets.

Ask:

> Remove the watch on the score.

Call:

```text
declaration_clear(kind="watch", ref="score")
```

Reply, 4 of 4 fields:

```json
{
  "summary": "declaration_clear watch score: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BPMEM 08DF:0615 (3C)", "BPMEM 08DF:0616 (00)"]
}
```

The watch on `score` is gone, and `disarmed` lists the two debugger rows it used, one per byte.

<details><summary>The whole reply</summary>

```json
{
  "summary": "declaration_clear watch score: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BPMEM 08DF:0615 (3C)", "BPMEM 08DF:0616 (00)"]
}
```

</details>

### Arguments

- `kind` (one of `"breakpoint"`, `"regpoint"`, `"watch"`, required): `breakpoint`, `regpoint` or `watch`: what to clear. `breakpoint` covers interrupt breakpoints too.
- `ref` (string, default `""`): The one to clear, as the reply that saved it gave its `ref`. Left empty with `all=True`.
- `all` (boolean, default `false`): `true` clears every one of `kind`, and takes no `ref`.

### What comes back

- `declarations_cleared`: How many were removed from the saved breakpoints file.
- `disarmed`: The debugger rows removed, as the debugger listed them, checked by reading its list back.
- `pending_disarm`: Debugger rows still to remove: at the next stop while the program runs, or on the next call when a removal failed.

<details><summary>All 3 reply fields</summary>

- `declarations_cleared` (integer)
- `disarmed` (array)
- `pending_disarm` (array)

</details>

### What it refuses

- An empty `ref` without `all`, or both together (`bad_argument`).
- A `ref` that matches nothing: the message names the refs saved (`unknown_ref`).

### Why it works this way

It removes only what this server set: a `foreign` row, one typed through `debug`, is never deleted.

The saved breakpoint or watch is removed at once. While the program runs the debugger cannot be asked, so its rows go at the next stop: `pending_disarm` lists them, and that stop's reply confirms it in `applied_on_stop`.

A `SEG:OFF` and a registerpoint's condition match in any spelling. A symbol or an interrupt breakpoint's `BPINT` text must be the exact text the saving reply carried.

### Related tools

- [`declaration_list`](#declaration_list)
- [`breakpoint_at`](#breakpoint_at)
- [`breakpoint_interrupt`](#breakpoint_interrupt)
- [`regpoint_add`](#regpoint_add)
- [`watch_add`](#watch_add)

<details><summary>The contract your client receives</summary>

```text
Clear the declarations of `kind`: all with `all=True`, or the one named by the exact `ref`
its declaring reply carried; `breakpoint` takes `breakpoint_interrupt` rows too. Removes only
what this store armed, the declarations at once and, on a running guest, their debugger
rows at the next stop (`pending_disarm`); a `foreign` entry is never deleted.

Refused: a `ref` matching none, naming the refs held; neither `ref` nor `all`, or both
(`bad_argument`).

Reply: `declarations_cleared`, `disarmed`, `pending_disarm` (removed at the next stop),
`note`.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end declaration_clear -->
