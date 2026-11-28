# The Machine tools

These tools describe the DOS machine a session runs and read what it logs. `machine_map` and `interrupt_vectors` read the debugger's own listings, so they need the program stopped at the debugger. `log` and `log_wait` answer while it runs.

The log is the file `start` writes when given `logfile`. It holds the emulator's own lines and the program's: what a DOS program writes to port 0xE9, a debug port, is its log. `log` reads those lines when asked for `guest`, and a stop's reply shows the new ones as `e9`.

<!-- scry-reference:begin machine_map -->
## `machine_map`

Get the layout of the DOS machine at this stop: its memory blocks, device drivers, extended memory handles and the cpu's control registers.

```text
machine_map(sections=null, dest="")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at its play screen.

Ask:

> List the blocks of memory DOS holds right now.

Call:

```text
machine_map(sections=["mcbs"])
```

Reply, 4 of 10 fields:

```json
{
  "cpu_mode": "real",
  "counts": {"mcbs": 9},
  "sources": {"mcbs": ["DOS MCBS"]},
  "truncated": false
}
```

In real mode the debugger's `DOS MCBS` listing gave 9 memory blocks, and none was cut from the reply. Their rows are too long to show here: the whole reply, below, has them.

<details><summary>The whole reply</summary>

```json
{
  "summary": "machine_map (real): 9 mcbs, left out: devs, kern, xms, ems, ems_pages, bios_mem, callbacks, emu_mem, machine, control, vga (see `omitted`)",
  "status": "ok",
  "cpu_mode": "real",
  "mcbs": [
    {
      "memory": "conventional",
      "mcb_seg": "0450",
      "size_bytes": 10992,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "\"\u0005"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0700",
      "size_bytes": 2464,
      "psp_seg": "0701",
      "filename": "COMMAND"
    },
    {
      "memory": "conventional",
      "mcb_seg": "079B",
      "size_bytes": 720,
      "psp_seg": "0701",
      "filename": "COMMAND"
    },
    {
      "memory": "conventional",
      "mcb_seg": "07C9",
      "size_bytes": 1168,
      "psp_seg": "0814",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0813",
      "size_bytes": 2048,
      "psp_seg": "0814",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0894",
      "size_bytes": 1168,
      "psp_seg": "08DF",
      "filename": "BRICKS"
    },
    "... 3 more"
  ],
  "counts": {"mcbs": 9},
  "sources": {"mcbs": ["DOS MCBS"]},
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["devs", "kern", "xms", "ems", "ems_pages", "bios_mem", "... 5 more"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole"
}
```

</details>

### Arguments

- `sections` (array of one of `"mcbs"`, `"devs"`, `"kern"`, `"xms"`, `"ems"`, `"ems_pages"`, `"bios_mem"`, `"callbacks"`, `"emu_mem"`, `"machine"`, `"control"`, `"gdt"`, `"ldt"`, `"paging"`, `"vga"`, optional): Which sections to read. Left out, all of them but `bios_mem`, `callbacks`, `paging` and `vga`.
- `dest` (string, default `""`): A file to write every row of the sections read, as JSON: an absolute or `~` path that does not exist yet. Left empty, no file is written.

### What comes back

- `cpu_mode`: `real`, `protected` or `paged`, read from the control register `cr0`. It decides which sections exist.
- `mcbs`: DOS's chain of memory blocks, one row each: `memory`, `mcb_seg`, `size_bytes`, `psp_seg`, `notes`, `filename`.
- `coverage_note`: Why each absent section is absent: the mode has none, or the debugger's listing could not be read.
- `sources`: For each section, the debugger command its rows came from.
- `counts`: How many rows each section has in full, so a list cut short shows.
- `truncated`: `true` when a section had more than 400 rows and its list was cut; `dest` gets them all.

<details><summary>All 21 reply fields</summary>

- `bios_mem` (array)
- `callbacks` (array)
- `control` (object)
- `counts` (object)
- `coverage_note` (string)
- `cpu_mode` (string or object)
- `devs` (array)
- `ems` (array)
- `ems_pages` (array)
- `emu_mem` (object)
- `gdt` (array)
- `kern` (array)
- `ldt` (array)
- `machine` (string)
- `mcbs` (array)
- `paging` (array)
- `path` (string)
- `sources` (object)
- `truncated` (boolean)
- `vga` (object)
- `xms` (array)

</details>

### What it refuses

- An empty `sections`, a name that is no section, or a `dest` that already exists (`bad_argument`).
- A program that is running: the listings are read at a stop (`not_stopped`).
- A listing longer than the debugger hands back in one reply: it would come back cut (`unexpected_answer`).

### Why it works this way

Each section is one listing of the debugger, read whole. A section the debugger refused, or printed in a form the server does not know, is absent, never partial. A chain of memory blocks with one block skipped would read as the whole chain.

Which sections exist depends on the cpu mode. In real mode `gdt` and `ldt` are absent, because there the debugger reads the interrupt vector table as descriptors; `paging` exists only with paging on.

`cpu_mode` comes from `cr0`, which cannot tell virtual 8086 mode from protected mode. At such a stop it says `protected` where the stop's own reply and `status` say `VM86`.

<details><summary>More on why</summary>

- `mcbs`: a free block has a `psp_seg` of `0000` and keeps in `filename` the old name DOS left there.
- The chain in `mcbs` is checked by its sizes, each block right after the one before; a chain that fails is absent.
- `devs`: `header`, `attr`, `strat`, `intr`, `name`.
- `kern`: `seg`, `size_bytes`, `what`.
- `xms`: `handle`, `status`, `location`, `size_bytes`.
- `ems`: `handle`, `addr`, `size_bytes`, `name`. `ems_pages`: `handle`, `page`, `start`, `end`.
- `bios_mem`: `start`, `end`, `status`, `what`. `callbacks`: `number`, `desc`.
- `control`: `cr0`, `cr2`, `cr3`, `cpl`, `eflags`, `vm`, `iopl`, `nt`, `gdtr`, `idt`, `tr`, `ldtr`.
- `gdt` and `ldt`: `selector`, `base`, `limit`, `type`, `dpl`, `p`, `a`, `r`, `b`, `g`.
- `paging`: runs of pages next to each other in linear and physical memory with the same flags: `start`, `end`, `phy`, `flags`, `d`, `a`.
- `vga`: `mode`, `crtc`, `seq`, `gc`, `ac`, `dac`, `draw`.
- `emu_mem` holds the emulator's memory listing, a key per line; `machine` is the emulated machine's name.
- Each listing is one exchange with the debugger. `omitted` and `how` name the sections of this mode that were not read.
- When the listing behind `control` cannot be read, `cpu_mode` is unavailable and `gdt`, `ldt` and `paging` are absent.

</details>

### Related tools

- [`interrupt_vectors`](#interrupt_vectors)
- [`registers`](read.md#registers)
- [`read_memory`](read.md#read_memory)
- [`status`](session.md#status)
- [`a20`](hardware.md#a20)

<details><summary>The contract your client receives</summary>

```text
What the DOS machine is at this stop: one section per debugger listing. `sections` left
out reads the DOS machine, `control` (the control registers, the flags and the
descriptor-table and task registers) and, in protected mode, `gdt` and `ldt` (the tables'
rows); `bios_mem`, `callbacks`, `vga`, `paging` only when named. `dest` (absolute or `~`-led,
new) writes every row of the sections read as JSON. Writes nothing to the guest.

Reply: `cpu_mode`, one key per section read as rows, `counts`, `truncated` (cut at
400 rows), `sources`, `coverage_note` (why a section is absent), `path` (with
`dest`). Refused: bad `sections` or an existing `dest` (`bad_argument`); a running guest
(`not_stopped`).

Reference: REFERENCE.md, Reading and writing.
```

</details>
<!-- scry-reference:end machine_map -->

<!-- scry-reference:begin interrupt_vectors -->
## `interrupt_vectors`

See which handler each interrupt vector points at, and which program, DOS block or BIOS block holds that handler.

```text
interrupt_vectors(number=null)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at its play screen.

Ask:

> Who handles the mouse interrupt, INT 33h?

Call:

```text
interrupt_vectors(number="0x33")
```

Reply, 3 of 7 fields:

```json
{
  "summary": "interrupt_vectors INT 33: C402:00000010, mcbs 9FFF SC (DOS)",
  "cpu_mode": "real",
  "counts": {"vectors": 256, "held": 112, "named": 0}
}
```

INT 33h points at `C402:0010`, inside the memory block at segment 9FFF, which is marked as DOS's. Of the 256 vectors, 112 sit in a known block (`held`) and none has a symbol (`named`).

<details><summary>The whole reply</summary>

```json
{
  "summary": "interrupt_vectors INT 33: C402:00000010, mcbs 9FFF SC (DOS)",
  "status": "ok",
  "cpu_mode": "real",
  "vectors": [
    {
      "number": "0x33",
      "seg_off": "C402:00000010",
      "addr": "0x000c4030",
      "mcbs": {
        "memory": "upper",
        "mcb_seg": "9FFF",
        "size_bytes": 180224,
        "psp_seg": "0008",
        "notes": "DOS",
        "filename": "SC"
      }
    }
  ],
  "counts": {"vectors": 256, "held": 112, "named": 0},
  "sources": {
    "vectors": ["INTVEC"],
    "mcbs": ["DOS MCBS"],
    "kern": ["DOS KERN"],
    "bios_mem": ["BIOS MEM"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off"
}
```

</details>

### Arguments

- `number` (integer or string, optional): One vector to return, `0x00` to `0xFF`, as an integer or `0x` text. Left out, all 256 come back.

### What comes back

- `vectors`: One row per vector: `number`, the handler's `seg_off` and linear `addr`, the block that holds it under `mcbs`, `kern` or `bios_mem`, and the nearest `symbol`.
- `counts`: `vectors`, how many the table has; `held`, how many sit in a known block; `named`, how many have a symbol.
- `cpu_mode`: The mode at this stop: `real`, `VM86`, `protected` or `paged`. In protected mode the table read is the IDT.
- `coverage_note`: What could not be worked out, and why: a vector with no `addr`, a handler no block holds, a table still empty.
- `sources`: The debugger command behind the vectors and behind each listing the blocks came from.

<details><summary>All 5 reply fields</summary>

- `counts` (object)
- `coverage_note` (string)
- `cpu_mode` (string or object)
- `sources` (object)
- `vectors` (array)

</details>

### What it refuses

- A `number` outside `0x00` to `0xFF` (`bad_argument`).
- A file named `MCPIVT.TXT` already in the emulator's working directory: move it aside, it is never deleted (`bad_argument`).
- A program that is running (`not_stopped`).
- A table the debugger did not write whole, or a listing too long for one reply (`unexpected_answer`).

### Why it works this way

Each handler is matched to the block of memory that holds it, so the reply says which program hooked a vector with no earlier table to compare. The first block holding the address wins: `mcbs`, then `kern`, then `bios_mem`.

Right after `start` every vector reads `0000:0000`: DOS has not filled the table yet.

`symbol` is what `symbols_find(linear=...)` answers for the handler, given only between the table's lowest and highest symbol.

<details><summary>More on why</summary>

The debugger writes the table to a file, `MCPIVT.TXT`, which the server reads and removes. The whole table is read even for one `number`, with the listings `machine_map` reads, one exchange with the debugger each.

</details>

### Related tools

- [`machine_map`](#machine_map)
- [`breakpoint_interrupt`](breakpoints.md#breakpoint_interrupt)
- [`symbols_find`](symbols.md#symbols_find)
- [`disassemble`](read.md#disassemble)
- [`symbols_load`](symbols.md#symbols_load)

<details><summary>The contract your client receives</summary>

```text
Which handler every interrupt vector points at and what holds it, from the debugger's
`INTVEC` table: a handler is placed in the MCB, kernel or BIOS block holding it and named by
loaded symbols. `number` (`0x` hex or an integer, 0x00 to 0xFF) narrows the reply to one
vector. In protected mode the
table is the IDT.

Reply: `cpu_mode`, `vectors` (each `number` as `0x` hex, `seg_off`, `addr`, a holder row,
`symbol`),
`counts`, `sources`, `coverage_note`.

Refused: `number` out of range or a `MCPIVT.TXT` already there (`bad_argument`); a running
guest (`not_stopped`); an incomplete table (`unexpected_answer`); `machine_map`'s listing
refusals.

Reference: REFERENCE.md, Reading and writing.
```

</details>
<!-- scry-reference:end interrupt_vectors -->

<!-- scry-reference:begin log -->
## `log`

Read the newest log lines that match a pattern: the program's, the emulator's, both, or the DOS calls the program made.

```text
log(pattern, channel, limit=40, labels=false, since_mark=0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, started with `logfile`, after a ball was served and lost.

Ask:

> What did the game log about serves, hits and lost balls?

Call:

```text
log(pattern="SERVE|HIT|LOST", channel="guest")
```

Reply, 2 of 7 fields:

```json
{
  "summary": "log guest /SERVE|HIT|LOST/: 6 of 6 lines",
  "lines": [
    "Bochs port E9h: HIT 0 7",
    "Bochs port E9h: HIT 5 6",
    "Bochs port E9h: HIT 5 0",
    "Bochs port E9h: SERVE",
    "Bochs port E9h: HIT 5 9",
    "Bochs port E9h: LOST"
  ]
}
```

Six lines of the game's own log match, oldest first. Each opens with `Bochs port E9h:`, the emulator's mark on a line the program wrote to port 0xE9.

<details><summary>The whole reply</summary>

```json
{
  "summary": "log guest /SERVE|HIT|LOST/: 6 of 6 lines",
  "status": "ok",
  "pattern": "SERVE|HIT|LOST",
  "channel": "guest",
  "lines_total": 6,
  "truncated": false,
  "lines": ["Bochs port E9h: HIT 0 7", "Bochs port E9h: HIT 5 6", "Bochs port E9h: HIT 5 0", "Bochs port E9h: SERVE", "Bochs port E9h: HIT 5 9", "Bochs port E9h: LOST"]
}
```

</details>

### Arguments

- `pattern` (string, required): A regular expression each line is searched for. It is never empty: `.` matches every line.
- `channel` (one of `"guest"`, `"emulator"`, `"all"`, `"dos"`, required): Which log to read. `guest` is the program's port 0xE9 lines, `emulator` DOSBox-X's own, `all` both with each line tagged, `dos` the program's INT 21h calls.
- `limit` (integer (>= 1, <= 400), default `40`): How many of the newest matching lines to return: 1 to 400. Left out, 40.
- `labels` (boolean, default `false`): `true` adds `labels`: the lines returned, counted by their first word. Left out, no count.
- `since_mark` (integer (>= 0), default `0`): A byte position in the log: only lines written after it are read. Left out or 0, the whole log is read.

### What comes back

- `lines`: The newest `limit` matching lines, oldest first. Not on `dos`.
- `lines_total`: How many lines matched in all, not how many came back.
- `truncated`: `true` when more matched than came back.
- `labels`: With `labels=true`, the returned lines counted by their first word: a quick view of who is writing.
- `calls`: On `dos`, the matching calls in place of `lines`, each with the registers DOS took, the ones it handed back and its result.
- `calls_dropped`: On `dos`, how many of the oldest calls the server no longer holds.

<details><summary>All 8 reply fields</summary>

- `calls` (array)
- `calls_dropped` (integer)
- `channel` (string)
- `labels` (object)
- `lines` (array)
- `lines_total` (integer)
- `pattern` (string)
- `truncated` (boolean)

</details>

### What it refuses

- An empty pattern, or one that is not a regular expression (`bad_argument`).
- A `limit` outside 1 to 400 (`bad_argument`).
- A session started without `logfile`, a log not written yet, or `guest` on a log with no line from the program (`no_channel`).
- `dos` on a session not started with `dos_calls` (`no_channel`).
- `dos` with `labels` or `since_mark`: the calls are not lines of the log file (`bad_argument`).
- `channel` `process`: the emulator's own output is not a log; `close(detail=true)` returns its last lines (`bad_argument`).
- A `since_mark` past the end of the log (`bad_argument`).

### Why it works this way

`guest`, `emulator` and `all` are three views of one file, so one `since_mark` position serves all three. `all` is the file in order, each line tagged `[guest] ` or `[emulator] `.

`dos` is another record: every INT 21h call the program made, with its result, on a session started with `dos_calls`. There `pattern` is matched against each call's `line` and `lines_total` counts calls.

An empty `lines` is an answer: nothing matched. A log with no line from the program at all is refused, so that silence is never read as no match. While the program runs a line it has only now written may not be in the file yet, and `note` says so.

<details><summary>More on why</summary>

- On `dos`, each call is two rows of the debugger's `DOSTRACE`, one as DOS takes it and one as DOS hands it back, paired by number.
- On `dos`, each call of `calls` holds `in` and `out`, the registers DOS took and handed back; `out.cf` is the carry flag.
- `error` is the code and its name, for the calls that report failure by the carry: AH 38h and up. An older call answers in AL and gets none.
- `returned` is `false` for a call DOS has not handed back yet, as at a stop inside it.
- `switched: true` marks a call that never returned to its caller, as an EXEC or an exit: the registers are then another program's, so no result is claimed.
- The emulator's own `int21` and `fileio` lines, switched on in the conf's `[log]` section, are written before DOS runs the call, so they never carry its result.
- `time_s` and `returned_s` are seconds of emulated time since power-on, the clock `run_for` reports.

</details>

### Related tools

- [`log_wait`](#log_wait)
- [`start`](session.md#start)
- [`state_write`](states.md#state_write)
- [`drive`](sequences.md#drive)
- [`close`](session.md#close)

<details><summary>The contract your client receives</summary>

```text
The session's log, one `channel` (`guest`, `emulator`, `all`, `dos`) filtered by the
Python regex `pattern`; `limit` keeps the newest matches; `labels=True` adds `labels`, the
matching lines counted by first word.
`since_mark` (a byte position, from a `mark`) reads only what follows. Needs a session with
`logfile`. `dos`, the guest's INT 21h calls and no other interrupt, instead needs a session
started with `dos_calls`, matches `pattern` against each call's `line` (`#20 08BC:0139 psp
0x08BC 0x3D MISSING.TXT -> error 2`), counts calls where the others count
lines (the matches among the calls the server holds), and takes no `since_mark` or `labels`;
past those, `calls_dropped` says how many of the oldest went. Works on a running guest.

Reply: `channel`, `lines` (not on `dos`), `lines_total`, `truncated`, `labels`, `pattern`,
`note`; on the DOS channel `calls` instead of `lines` (each `n`, `time_s`, `cpu_mode`,
`caller`, `psp`, `function`, `name` (its number where the base has no confirmed name),
`file`, `in`, `out`, `error`, `returned`, `returned_s`,
`switched`, `line`), and `calls_dropped` (on `dos`, past the calls held). INVALID with `code`:
no `logfile`, no log yet, no guest instrumentation, `limit` out of range, an empty or bad
pattern, an unknown channel (`process` is refused by name), a `since_mark` naming no
position. To wait for a line use `log_wait`.

Reference: REFERENCE.md, The log.
```

</details>
<!-- scry-reference:end log -->

<!-- scry-reference:begin log_wait -->
## `log_wait`

Wait until a log line matches a pattern, or get the line at once when the log already has it.

```text
log_wait(pattern, channel, seconds=30.0, since_mark=0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, started with `logfile` and running, a ball served and nobody at the paddle.

Ask:

> Wait up to a minute for the game to log that the ball was lost.

Call:

```text
log_wait(pattern="LOST$", channel="guest", seconds=60)
```

Reply, 4 of 12 fields:

```json
{
  "verdict": "TARGET",
  "pattern": "LOST$",
  "channel": "guest",
  "line": "Bochs port E9h: LOST"
}
```

`TARGET` means a line matched within the minute: the game logged `LOST`, a line of its own, written to port 0xE9.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "LOST$",
  "channel": "guest",
  "line": "Bochs port E9h: LOST",
  "already": "<volatile>",
  "lines_total": "<volatile>",
  "lines_before": "<volatile>",
  "arrived_during": "<volatile>",
  "waited_s": "<volatile>",
  "lines_examined": "<volatile>"
}
```

</details>

### Arguments

- `pattern` (string, required): A regular expression each line is searched for. It is never empty: `.` matches every line.
- `channel` (one of `"guest"`, `"emulator"`, `"all"`, `"dos"`, required): Which log to wait on: `guest`, `emulator`, `all` or `dos`, as in [`log`](#log).
- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to wait at most, in seconds, up to 600. Left out, 30.
- `since_mark` (integer (>= 0), default `0`): A byte position in the log: only lines written after it count, the ones already there included. Left out or 0, the whole log counts.

### What comes back

- `verdict`: `TARGET` when a line matched, `TIMEOUT` when the time ran out with none; `note` then says what was read.
- `line`: The first line that matched; for the newest one, use `log`. On `dos`, `call` holds the matching call in its place.
- `already`: `true` when the log held the line before the call, so nothing was waited for.
- `waited_s`: Seconds spent waiting; 0 when the line was already there.
- `arrived_during`: How many lines were written during the wait, whether or not they matched.
- `lines_examined`: How many lines were read in all: those the log held and those that came during the wait. On `dos`, the calls the server holds.

<details><summary>All 12 reply fields</summary>

- `already` (boolean)
- `arrived_during` (integer)
- `channel` (string)
- `line` (string)
- `lines_before` (integer)
- `lines_examined` (integer)
- `lines_total` (integer)
- `pattern` (string)
- `verdict` (string)
- `waited_s` (number)
- `call` (object)
- `calls_dropped` (integer)

</details>

### What it refuses

- A machine stopped at the debugger, or one that stops during the wait, while the log lacks the line. It logs nothing, and `last_stop` says where it stopped (`wait_stopped`).
- An emulator that exits during the wait (`session_broken`).
- `seconds` out of range, an empty or malformed pattern, or a `since_mark` past the end of the log (`bad_argument`).
- A session started without `logfile` (`no_channel`).
- `dos` on a session not started with `dos_calls` (`no_channel`).
- `dos` with a `since_mark` (`bad_argument`).

### Why it works this way

The log is read before any waiting, so a line written before the call is found at once, where a tool that only waited would report that it never came. `already` marks such a line.

A `TIMEOUT` says what it read. `arrived_during` counts the lines written during the wait and `lines_examined` every line read, so a program that wrote nothing is told apart from one whose lines did not match.

A log that does not exist yet is not refused: that is the state right after `resume`. When the wait returns the program is usually still running: use the line to choose an address for `run_to` or `watch_add` on the next run.

<details><summary>More on why</summary>

- `lines_before` counts the lines read before the match and `lines_total` the matches in that read. On `dos` both count calls, and `calls_dropped` the oldest ones the server let go.
- A debugger that does not answer, inside a long host call, is asked once, and then only the file is read. A `TIMEOUT` says the run state is unknown.
- No breakpoint can be set on a log line; the nearest is a watch for changes on the variable whose change produces it.
- `expect` on `send_keys` and `drive` is this wait on `guest`, from a position taken before the keys are sent.

</details>

### Related tools

- [`log`](#log)
- [`resume`](run.md#resume)
- [`drive`](sequences.md#drive)
- [`run_to`](run.md#run_to)
- [`watch_add`](breakpoints.md#watch_add)
- [`send_keys`](input.md#send_keys)

<details><summary>The contract your client receives</summary>

```text
When a line of `channel` matching `pattern` was logged: at once if the log already holds it,
else wait up to `seconds`. `channel` and `since_mark` as in `log`. Works on a running guest.

Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the first match, not on `dos`),
`call` (on `dos`), `already`, `waited_s`, `lines_before`, `lines_total`, `arrived_during`,
`lines_examined` (the calls held on `dos`), `calls_dropped` (on `dos`, past the calls held);
on timeout `verdict` `TIMEOUT`
with `note`, `arrived_during`, `lines_examined`, `waited_s`. `status: INVALID`: `wait_stopped`
on a stopped machine whose
log lacks the line, `session_broken` when the emulator went away; no `logfile`, a bad
`seconds`, regex, channel or `since_mark` are refused.

Reference: REFERENCE.md, The log.
```

</details>
<!-- scry-reference:end log_wait -->
