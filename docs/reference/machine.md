# The Machine tools

<!-- scry-reference:begin machine_map -->
## `machine_map`

*Map the machine*

```text
machine_map(sections=null, dest="")
```

What the DOS machine is at this stop: one section per debugger listing. `sections` left
out reads the DOS machine and `control`; `bios_mem`, `callbacks`, `vga`, `paging` only when
named. `dest` (absolute, new) writes all sections whole as JSON. Writes nothing to the guest.

Reply: `cpu_mode`, one key per section read as rows, `counts`, `truncated` (cut at
400 rows), `sources`, `coverage_note` (why a section is absent), `path` (with
`dest`). Refused: bad `sections` or an existing `dest` (`bad_argument`); a running guest
(`not_stopped`).

Reference: REFERENCE.md, Reading and writing.

| argument | type | default |
|---|---|---|
| `sections` | array of one of `"mcbs"`, `"devs"`, `"kern"`, `"xms"`, `"ems"`, `"ems_pages"`, `"bios_mem"`, `"callbacks"`, `"emu_mem"`, `"machine"`, `"control"`, `"gdt"`, `"ldt"`, `"paging"`, `"vga"` or null | `null` |
| `dest` | string | `""` |

| reply field | type |
|---|---|
| `bios_mem` | array |
| `callbacks` | array |
| `control` | object |
| `counts` | object |
| `coverage_note` | string |
| `cpu_mode` | string or object |
| `devs` | array |
| `ems` | array |
| `ems_pages` | array |
| `emu_mem` | object |
| `gdt` | array |
| `kern` | array |
| `ldt` | array |
| `machine` | string |
| `mcbs` | array |
| `paging` | array |
| `path` | string |
| `sources` | object |
| `truncated` | boolean |
| `vga` | object |
| `xms` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "machine_map (real): 7 mcbs, 2 devs, 20 kern, 1 ems, 4 ems_pages, left out: bios_mem, callbacks, vga (see `omitted`)",
  "status": "ok",
  "cpu_mode": "real",
  "mcbs": [
    {
      "memory": "conventional",
      "mcb_seg": "0450",
      "size_bytes": 10992,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "\u0002"
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
      "filename": "PROBE"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0813",
      "size_bytes": 622256,
      "psp_seg": "0814",
      "filename": "PROBE"
    },
    {
      "memory": "upper",
      "mcb_seg": "9FFF",
      "size_bytes": 180224,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "SC"
    },
    "... 1 more"
  ],
  "devs": [
    {"header": "0071:0048", "attr": "8004", "strat": "0000", "intr": "0000", "name": "NUL"},
    {"header": "00F9:0000", "attr": "8013", "strat": "FFFF", "intr": "FFFF", "name": "CON"}
  ],
  "kern": [
    {"seg": "0070", "size_bytes": 16, "what": "DOS_IHSEG"},
    {"seg": "0071", "size_bytes": 800, "what": "DOS_INFOBLOCK_SEG"},
    {"seg": "00a3", "size_bytes": 1376, "what": "DOS_SDA_SEG"},
    {"seg": "00f9", "size_bytes": 64, "what": "DOS_CONDRV_SEG"},
    {"seg": "00fd", "size_bytes": 256, "what": "DOS_CDA_SEG"},
    {"seg": "010d", "size_bytes": 64, "what": "dos.tables.tempdta"},
    "... 14 more"
  ],
  "xms": [],
  "ems": [
    {"handle": 0, "addr": "0x00110000", "size_bytes": 393216, "name": ""}
  ],
  "ems_pages": [
    {"handle": "--", "page": "0/", "start": "000e0000", "end": "000e3fff"},
    {"handle": "--", "page": "1/", "start": "000e4000", "end": "000e7fff"},
    {"handle": "--", "page": "2/", "start": "000e8000", "end": "000ebfff"},
    {"handle": "--", "page": "3/", "start": "000ec000", "end": "000effff"}
  ],
  "emu_mem": {
    "a20_gate": "ON",
    "cpu_address_bits": 32,
    "cpu_address_mask": "0xffffffff",
    "cpu_address_mask_current": "0xffffffff",
    "memory_reported_size_bytes": 16777216
  },
  "machine": "VGA S3 Trio",
  "control": {
    "cr0": "00000010",
    "cr2": "00000000",
    "cr3": "00000000",
    "cpl": 0,
    "eflags": "00007006",
    "vm": 0,
    "iopl": 3,
    "nt": 1,
    "gdtr": {"base": "00000000", "limit": "0000FFFF"},
    "idt": {"base": "00000000", "limit": "000003FF"},
    "tr": {"selector": "0000", "base": "000EF000", "limit": "0000CA60*1"},
    "ldtr": {"selector": "0000", "base": "000EF000", "limit": "0000CA60*1"}
  },
  "counts": {"mcbs": 7, "devs": 2, "kern": 20, "xms": 0, "ems": 1, "ems_pages": 4},
  "sources": {
    "mcbs": ["DOS MCBS"],
    "devs": ["DOS DEVS"],
    "kern": ["DOS KERN"],
    "xms": ["DOS XMS"],
    "ems": ["DOS EMS"],
    "ems_pages": ["DOS EMS"],
    "emu_mem": ["EMU MEM"],
    "machine": ["EMU MACHINE"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["bios_mem", "callbacks", "vga"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole"
}
```
<!-- scry-reference:end machine_map -->

The rows come from the lines the debugger printed for each listing, whole; a listing longer than
the channel keeps of one reply is refused, never read as complete.

**Which sections exist depends on the mode, and an absent one says why.** `cpu_mode` is read off the
`CPU` listing's cr0, which cannot tell VM86 from protected mode: at a VM86 stop it says `protected`
where the stop and `status` say `VM86`. In real mode `gdt` and `ldt` are absent, because there the
debugger reads the interrupt vector table as descriptors. `paging` comes back as runs of pages
contiguous in linear and physical memory with the same flags.

A section the debugger refused or printed in no known shape is ABSENT rather than partial, because
a chain with one block skipped would read as the whole chain. A free block keeps the stale name DOS
leaves in it, and its `psp_seg` of `0000` says it is free. The MCB chain is checked by its sizes
(each block starts right past the one above, `END OF CHAIN` right past the last); a chain that
breaks that walk is cut, and `mcbs` is absent.

Each listing costs one round trip. `cpu_mode` is `real`, `protected` or `paged`, unavailable when the `CPU` listing is unreadable. `gdt` and `ldt` exist in protected mode. Row fields per section: `mcbs` (`memory`, `mcb_seg`, `size_bytes`, `psp_seg`, `notes`, `filename`), `devs` (`header`, `attr`, `strat`, `intr`, `name`), `kern` (`seg`, `size_bytes`, `what`), `xms` (`handle`, `status`, `location`, `size_bytes`), `ems` (`handle`, `addr`, `size_bytes`, `name`), `ems_pages` (`handle`, `page`, `start`, `end`), `bios_mem` (`start`, `end`, `status`, `what`), `callbacks` (`number`, `desc`), `control` (control registers, flags, `gdtr`, `idt`, `tr`, `ldtr`), `gdt`/`ldt` (`selector`, `base`, `limit`, `type`, `dpl`, `p`, `a`, `r`, `b`, `g`), `paging` runs (`start`, `end`, `phy`, `flags`, `d`, `a`), `vga` (`mode`, `crtc`, `seq`, `gc`, `ac`, `dac`, `draw`). `omitted` and `how` name the sections of this mode that were not read.

<!-- scry-reference:begin interrupt_vectors -->
## `interrupt_vectors`

*Read the interrupt vectors*

```text
interrupt_vectors(number=null)
```

Which handler every interrupt vector points at and what holds it, from the debugger's
`INTVEC` table: a handler is placed in the MCB, kernel or BIOS block holding it and named by
loaded symbols. `number` (0 to 255) narrows the reply to one vector. In protected mode the
table is the IDT.

Reply: `cpu_mode`, `vectors` (each `number`, `seg_off`, `addr`, a holder row, `symbol`),
`counts`, `sources`, `coverage_note`.

Refused: `number` out of range or a `MCPIVT.TXT` already there (`bad_argument`); a running
guest (`not_stopped`); an incomplete table (`unexpected_answer`); `machine_map`'s listing
refusals.

Reference: REFERENCE.md, Reading and writing.

| argument | type | default |
|---|---|---|
| `number` | integer (>= 0, <= 255) or null | `null` |

| reply field | type |
|---|---|
| `counts` | object |
| `coverage_note` | string |
| `cpu_mode` | string or object |
| `sources` | object |
| `vectors` | array |

Example, from a live run:

```json
{
  "number": 33
}
```

```json
{
  "summary": "interrupt_vectors INT 21: F000:0000D100, bios_mem DOSBox callback area",
  "status": "ok",
  "cpu_mode": "real",
  "vectors": [
    {
      "number": 33,
      "seg_off": "F000:0000D100",
      "addr": "0x000fd100",
      "bios_mem": {"start": "000fca00", "end": "000fdfff", "status": "ALLOC DYN", "what": "DOSBox callback area"}
    }
  ],
  "counts": {"vectors": 256, "held": 113, "named": 0},
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
<!-- scry-reference:end interrupt_vectors -->

The holder row says which program
hooked a vector without comparing against an earlier table; a table taken at `start` is all zeros,
since the park comes before DOS fills it.

The debugger writes `MCPIVT.TXT` into the emulator's working directory, which this reads and removes; it then reads the listings `machine_map` reads, a round trip each. The whole table is read either way. The holder is the first match in the order mcbs, kern, bios_mem; `symbol` is given only between the table's lowest and highest symbol, as `symbols_find(linear=)` answers it. Before DOS fills the table every vector is 0000:0000, as read. `cpu_mode` has `VM86` among its words.

<!-- scry-reference:begin log -->
## `log`

*Read the log*

```text
log(pattern, channel, limit=40, labels=false, since_mark=0)
```

The session's log, one `channel` (`guest`, `emulator`, `all`, `dos`) filtered by the
Python regex `pattern`; `limit` keeps the newest matches; `labels=True` adds `labels`, the
matching lines counted by first word.
`since_mark` (a byte position, from a `mark`) reads only what follows. Needs a session with
`logfile`. `dos`, the guest's INT 21h calls and no other interrupt, instead needs a session
started with `dos_calls`, matches `pattern` against each call's `line` (`#20 08BC:0139 psp
0x08BC 0x3D open MISSING.TXT -> error 2 file not found`), counts calls where the others count
lines (the matches among the calls the server holds), and takes no `since_mark` or `labels`;
past those, `calls_dropped` says how many of the oldest went. Works on a running guest.

Reply: `channel`, `lines` (not on `dos`), `lines_total`, `truncated`, `labels`, `pattern`,
`note`; on the DOS channel `calls` instead of `lines` (each `n`, `time_s`, `cpu_mode`,
`caller`, `psp`, `function`, `name`, `file`, `in`, `out`, `error`, `returned`, `returned_s`,
`switched`, `line`), and `calls_dropped` (on `dos`, past the calls held). INVALID with `code`:
no `logfile`, no log yet, no guest instrumentation, `limit` out of range,
a bad pattern, an unknown channel (`process` is refused by name), a `since_mark` naming no
position. To wait for a line use `log_wait`.

Reference: REFERENCE.md, The log.

| argument | type | default |
|---|---|---|
| `pattern` | string | required |
| `channel` | one of `"guest"`, `"emulator"`, `"all"`, `"dos"` | required |
| `limit` | integer (>= 1, <= 400) | `40` |
| `labels` | boolean | `false` |
| `since_mark` | integer (>= 0) | `0` |

| reply field | type |
|---|---|
| `calls` | array |
| `calls_dropped` | integer |
| `channel` | string |
| `labels` | object |
| `lines` | array |
| `lines_total` | integer |
| `pattern` | string |
| `truncated` | boolean |

Example, from a live run:

```json
{
  "pattern": ".",
  "channel": "emulator"
}
```

```json
{
  "summary": "log emulator /./: 40 of 134 lines",
  "status": "ok",
  "pattern": ".",
  "channel": "emulator",
  "lines_total": 134,
  "truncated": true,
  "lines": ["Breakpoint list:", "-------------------------------------------------------------------------", "00. BPINT 21 AH=4B", "DEBUG: Breakpoint deletion success.", "Breakpoint list:", "-------------------------------------------------------------------------", "... 34 more"]
}
```
<!-- scry-reference:end log -->

**On the `dos` channel a call is a row, not a line.** `in` and `out` hold the registers DOS took
and handed back, `out.cf` the carry, and `error` the code with its name for the calls that report
by the carry (AH 38h and up); an older call answers in AL and gets no `error`. `returned` is false
for a call DOS has not handed back yet, as at a stop inside it. `time_s` and `returned_s` are
seconds of emulated time since power-on, the clock `run_for`'s `emulated_before_s` and
`emulated_after_s` read.

`guest` is the program's own 0xE9 instrumentation, one line per write; `emulator` is DOSBox-X's own lines; `all` is the file in order, each line tagged `[guest] ` or `[emulator] `. `labels` counts returned lines by first word (BOOT, PERF, UI...), one glance at who is talking. `lines_total` counts all matches, not those returned, and an empty `lines` is an answer. One file holds those three channels, so one mark position serves each; `dos` reads the DOS call trace instead and takes no mark. There is no `process` channel: the emulator's own stdout is `close(detail=True)`'s. Queued work applies on a stop, saying so in `applied_on_stop`.

<!-- scry-reference:begin log_wait -->
## `log_wait`

*Wait for a log line*

```text
log_wait(pattern, channel, seconds=30.0, since_mark=0)
```

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

| argument | type | default |
|---|---|---|
| `pattern` | string | required |
| `channel` | one of `"guest"`, `"emulator"`, `"all"`, `"dos"` | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |
| `since_mark` | integer (>= 0) | `0` |

| reply field | type |
|---|---|
| `already` | boolean |
| `arrived_during` | integer |
| `channel` | string |
| `line` | string |
| `lines_before` | integer |
| `lines_examined` | integer |
| `lines_total` | integer |
| `pattern` | string |
| `verdict` | string |
| `waited_s` | number |
| `call` | object |
| `calls_dropped` | integer |

Example, from a live run:

```json
{
  "pattern": "PROBE",
  "channel": "guest",
  "seconds": 10
}
```

```json
{
  "summary": "log_wait guest /PROBE/: matched already in the log",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "PROBE",
  "channel": "guest",
  "line": "Bochs port E9h: [+ 00000.000] PROBE . tick",
  "already": true,
  "lines_total": 1,
  "lines_before": 0,
  "arrived_during": 0,
  "waited_s": 0.0,
  "lines_examined": 1
}
```
<!-- scry-reference:end log_wait -->

A tool that only waited would sit out its bound for a line that went past before the call and report it never happened; hence the log is read first.

**A `TIMEOUT` is never an empty answer.** `arrived_during` and `lines_examined` are different facts: the second under the first's name makes a silent guest on a log of old traces look like a live channel.

No breakpoint can be armed on a log line: the guest is usually still running then. The nearest is a change watch on the variable whose change produces the line.

It reads what the log already holds first, so a line that went past before the call is found. A log that does not exist yet is not refused: that is the state right after `resume`. The moment it returns is for choosing an address to `run_to` or `watch_add` on the next run; the guest is usually still running then, and console tools refuse. `expect` on `send_keys`/`drive` is this wait on the guest channel, from a mark taken before the act. `already` marks history rather than something you were present for.
