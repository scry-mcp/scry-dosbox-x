# The Read tools

The typed tools parse what the debugger prints for each command, read its lists back and refuse a shape they were not captured answering; `debug` is the raw command for the rest.

### The picture attached

A view's PNG goes to the session's scratch (`close` deletes it; `dest` keeps one) and is attached after the JSON. Past 1568 px a side, or 1568 tiles of 28 px, the API resamples, and a resampled picture of pixel art is a plausible wrong one: it is written and not attached, `not_inlined` says why, and the caller asks for a `crop` or a smaller `scale`. A picture inside a sequence's step is never attached, since only a reply's own picture crosses. The default `scale` is the largest integer factor that fits, so each pixel stays a square of one colour.

<!-- scry-reference:begin registers -->
## `registers`

*Read the registers*

```text
registers(from_last_stop=false)
```

The registers at this stop. `from_last_stop=True` returns the registers of the last stop,
never the current value; refused before any stop.

Reply: `regs` (hex strings), `superseded`. CR0, CR3 and descriptor tables:
`machine_map(sections=["control"])`.

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
  "summary": "read_memory 0000:0020: 4 bytes at 0000:00000020",
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
  "lines": [
    "0000:00000020 A5                   movsw word ptr es:[di], word ptr [si]",
    "0000:00000021 FE00                 inc byte ptr [bx + si]",
    "0000:00000023 F0                   .byte 0xf0"
  ],
  "flow": [
    "sequential",
    "sequential",
    "unknown"
  ],
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
      "call": {
        "available": false,
        "why": "the stop itself: no call leads to it"
      },
      "bp": {
        "available": false,
        "why": "no frame was read beside it"
      },
      "addr": "0x000ffea5",
      "symbol": {
        "available": false,
        "why": "no symbol table is loaded"
      },
      "delta": {
        "available": false,
        "why": "no symbol table is loaded"
      }
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

`length` bytes from `ref` (a symbol or `SEG:OFF`) to the new file `dest` (absolute).

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-60ef74d68aef/jobs-scratch/A/n1083.bin"
}
```

```json
{
  "summary": "memdump 0000:0400: 16 bytes to $TMPDIR/dosbox-x-live-matrix-60ef74d68aef/jobs-scratch/A/n1083.bin",
  "status": "ok",
  "ref": "0000:0400",
  "seg_off": "0000:00000400",
  "length": 16,
  "path": "$TMPDIR/dosbox-x-live-matrix-60ef74d68aef/jobs-scratch/A/n1083.bin",
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
  "span": {
    "from": "8000:00000000",
    "length": 16,
    "source": "ref+length"
  },
  "hits": [
    "8000:00000000",
    "8000:00000001",
    "8000:00000002",
    "8000:00000003",
    "8000:00000004",
    "8000:00000005",
    "... 10 more"
  ],
  "hits_total": 16,
  "truncated": false
}
```
<!-- scry-reference:end find -->

The debugger has no pattern search, so the range is dumped by the `memdump` route (windows past offset 0xFFFF included) into a scratch file of the call's own, gone before the reply, and searched exactly. In real mode a hit past offset 0xFFFF is named from its own paragraph. `span` is always `ref+length` here since the range is the caller's own.

<!-- scry-reference:begin log -->
## `log`

*Read the log*

```text
log(pattern, channel, limit=40, labels=false, since_mark=0)
```

The session's log, one `channel` (`guest`, `emulator`, `all`, `dos`) filtered by the
Python regex `pattern`; `limit` keeps the newest matches; `labels=True` adds `labels`.
`since_mark` (a byte position, from a `mark`) reads only what follows. Needs a session with
`logfile`. `dos`, the guest's INT 21h calls and no other interrupt, instead needs a session
started with `dos_calls`, matches `pattern` against each call's `line`, counts calls where
the others count lines, and takes no `since_mark` or `labels`. Works on a running guest.

Reply: `channel`, `lines`, `lines_total`, `truncated`, `labels`, `pattern`, `note`; on the
DOS channel `calls` instead of `lines` (each `n`, `time_s`, `cpu_mode`, `caller`, `psp`,
`function`, `name`, `file`, `in`, `out`, `error`, `returned`, `returned_s`, `switched`,
`line`). INVALID with `code`: no
`logfile`, no log yet, no guest instrumentation, `limit` out of range, a bad pattern, an
unknown channel (`process` is refused by name), a `since_mark` naming no position.
To wait for a line use `log_wait`.

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
| `channel` | string |
| `labels` | object |
| `lines` | array |
| `lines_total` | integer |
| `note` | string |
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
  "summary": "log emulator /./: 40 of 123 lines",
  "status": "ok",
  "pattern": ".",
  "channel": "emulator",
  "lines_total": 123,
  "truncated": true,
  "lines": [
    "DEBUG: RUNSTATE running cycles=319 ms=0.732100000",
    "DEBUG: RUNSTATE stopped cycles=1253 ms=0.825500000",
    "EV of 'EAX EBX ECX EDX ESI EDI EBP ESP EIP CS DS ES FS GS SS EFLAGS CR0' is:",
    "4b00 5fe 2026 61e 0 0 0 5fe dac6 f000 71b 71b 0 0 71b 7002 10",
    "Breakpoint list:",
    "-------------------------------------------------------------------------",
    "... 34 more"
  ]
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

Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the first match; `call` on `dos`),
`already`,
`waited_s`, `lines_before`, `lines_total`, `arrived_during`, `lines_examined`; on timeout
`verdict` `TIMEOUT` with `note`, `arrived_during`, `lines_examined`, `waited_s`. `status:
INVALID`: `wait_stopped` on a stopped machine whose log lacks the line, `session_broken`
when the emulator went away; no `logfile`, a bad `seconds`, regex, channel or `since_mark`
are refused.

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
| `call` | object |
| `channel` | string |
| `line` | string |
| `lines_before` | integer |
| `lines_examined` | integer |
| `lines_total` | integer |
| `note` | string |
| `pattern` | string |
| `verdict` | string |
| `waited_s` | number |

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
400 rows), `sources`, `coverage_note` (why a section is absent), `path`.
Refused: bad `sections` or an existing `dest` (`bad_argument`); a running guest
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
    {
      "header": "0071:0048",
      "attr": "8004",
      "strat": "0000",
      "intr": "0000",
      "name": "NUL"
    },
    {
      "header": "00F9:0000",
      "attr": "8013",
      "strat": "FFFF",
      "intr": "FFFF",
      "name": "CON"
    }
  ],
  "kern": [
    {
      "seg": "0070",
      "size_bytes": 16,
      "what": "DOS_IHSEG"
    },
    {
      "seg": "0071",
      "size_bytes": 800,
      "what": "DOS_INFOBLOCK_SEG"
    },
    {
      "seg": "00a3",
      "size_bytes": 1376,
      "what": "DOS_SDA_SEG"
    },
    {
      "seg": "00f9",
      "size_bytes": 64,
      "what": "DOS_CONDRV_SEG"
    },
    {
      "seg": "00fd",
      "size_bytes": 256,
      "what": "DOS_CDA_SEG"
    },
    {
      "seg": "010d",
      "size_bytes": 64,
      "what": "dos.tables.tempdta"
    },
    "... 14 more"
  ],
  "xms": [],
  "ems": [
    {
      "handle": 0,
      "addr": "0x00110000",
      "size_bytes": 393216,
      "name": ""
    }
  ],
  "ems_pages": [
    {
      "handle": "--",
      "page": "0/",
      "start": "000e0000",
      "end": "000e3fff"
    },
    {
      "handle": "--",
      "page": "1/",
      "start": "000e4000",
      "end": "000e7fff"
    },
    {
      "handle": "--",
      "page": "2/",
      "start": "000e8000",
      "end": "000ebfff"
    },
    {
      "handle": "--",
      "page": "3/",
      "start": "000ec000",
      "end": "000effff"
    }
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
    "gdtr": {
      "base": "00000000",
      "limit": "0000FFFF"
    },
    "idt": {
      "base": "00000000",
      "limit": "000003FF"
    },
    "tr": {
      "selector": "0000",
      "base": "000EF000",
      "limit": "0000CA60*1"
    },
    "ldtr": {
      "selector": "0000",
      "base": "000EF000",
      "limit": "0000CA60*1"
    }
  },
  "counts": {
    "mcbs": 7,
    "devs": 2,
    "kern": 20,
    "xms": 0,
    "ems": 1,
    "ems_pages": 4
  },
  "sources": {
    "mcbs": [
      "DOS MCBS"
    ],
    "devs": [
      "DOS DEVS"
    ],
    "kern": [
      "DOS KERN"
    ],
    "xms": [
      "DOS XMS"
    ],
    "ems": [
      "DOS EMS"
    ],
    "ems_pages": [
      "DOS EMS"
    ],
    "emu_mem": [
      "EMU MEM"
    ],
    "machine": [
      "EMU MACHINE"
    ],
    "control": [
      "CPU"
    ]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": [
    "bios_mem",
    "callbacks",
    "vga"
  ],
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

Each listing costs one round trip. `cpu_mode` is `real`, `protected` or `paged`, unavailable when the `CPU` listing is unreadable. `gdt` and `ldt` exist in protected mode. Row fields per section: `mcbs` (`memory`, `mcb_seg`, `size_bytes`, `psp_seg`, `notes`, `filename`), `devs` (`header`, `attr`, `strat`, `intr`, `name`), `kern` (`seg`, `size_bytes`, `what`), `xms` (`handle`, `status`, `location`, `size_bytes`), `ems` (`handle`, `addr`, `size_bytes`, `name`), `ems_pages` (`handle`, `page`, `start`, `end`), `bios_mem` (`start`, `end`, `status`, `what`), `callbacks` (`number`, `desc`), `control` (control registers, flags, `gdtr`, `idt`, `tr`, `ldtr`), `gdt`/`ldt` (`selector`, `base`, `limit`, `type`, `dpl`, `p`, `a`, `r`, `b`, `g`), `paging` runs (`start`, `end`, `phy`, `flags`, `d`, `a`), `vga` (`mode`, `crtc`, `seq`, `gc`, `ac`, `dac`, `draw`). `omitted` and `how` name the sections of this mode that were not read. A section the debugger refused or printed in no known shape is absent rather than partial.

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
      "bios_mem": {
        "start": "000fca00",
        "end": "000fdfff",
        "status": "ALLOC DYN",
        "what": "DOSBox callback area"
      }
    }
  ],
  "counts": {
    "vectors": 256,
    "held": 113,
    "named": 0
  },
  "sources": {
    "vectors": [
      "INTVEC"
    ],
    "mcbs": [
      "DOS MCBS"
    ],
    "kern": [
      "DOS KERN"
    ],
    "bios_mem": [
      "BIOS MEM"
    ],
    "control": [
      "CPU"
    ]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off"
}
```
<!-- scry-reference:end interrupt_vectors -->

The holder row says which program
hooked a vector without comparing against an earlier table; a table taken at `start` is all zeros,
since the park comes before DOS fills it.

The debugger writes `MCPIVT.TXT` into the emulator's working directory, which this reads and removes; it then reads the listings `machine_map` reads, a round trip each. The whole table is read either way. The holder is the first match in the order mcbs, kern, bios_mem; `symbol` is given only between the table's lowest and highest symbol, as `symbols_find(linear=)` answers it. Before DOS fills the table every vector is 0000:0000, as read. `cpu_mode` has `VM86` among its words.

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
  "colors": [
    "#000000",
    "#0000aa"
  ],
  "rgb": [
    "000000",
    "00002a"
  ],
  "bits": 6,
  "pel_mask": "ffh",
  "image": {
    "path": "$TMPDIR/dosbox-x-session-acy0tq47/gfx/palette-1.png",
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
screen_view(crop=null, scale=0, dest="", attach=true)
```

What the screen shows at this stop, read from video memory: text as text, a graphics mode
as a PNG (256 colours chained or not, 16-colour planar, 8-, 15-, 16- or 32-bit linear; all
but chained through `VGAMEMDUMP`). `crop` is `[x, y, width, height]` in characters or pixels.
`scale` 0 fits the largest up to 8x; `dest` a new path (else a scratch); `attach` false
leaves it unattached.

Reply: `vga_mode`, `kind`, `width`, `height`, `crop`, `display_start`; in text `text`,
`cursor`; in graphics `image`.

Refused: a relative or existing `dest`, a bad `scale` or `crop`, `dest`/`scale`/`attach` in
text (`bad_argument`); another mode or a build without `VGAMEMDUMP` (naming
`capture_frame`), or an undecodable layout (`no_channel`); a running guest
(`not_stopped`); a DAC not six-bit (`unexpected_answer`).

Reference: REFERENCE.md, Media files.

| argument | type | default |
|---|---|---|
| `crop` | array of integer or null | `null` |
| `scale` | integer | `0` |
| `dest` | string | `""` |
| `attach` | boolean | `true` |

| reply field | type |
|---|---|
| `crop` | array |
| `cursor` | array or object |
| `display_start` | string |
| `height` | integer |
| `image` | object |
| `kind` | string |
| `text` | array |
| `vga_mode` | string |
| `width` | integer |

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
  "crop": [
    0,
    0,
    80,
    25
  ],
  "text": [
    "Z:\\>mount c \".\"",
    "Drive C is mounted as local directory ./",
    "Z:\\>c:",
    "C:\\>PROBE.COM",
    "",
    "",
    "... 19 more"
  ],
  "cursor": [
    0,
    4
  ],
  "display_start": "0h"
}
```
<!-- scry-reference:end screen_view -->

**Every VGA mode is read, and none is read by touching the card.** Text and 13h's chained bytes come through the CPU's window; a planar 16-colour mode, an unchained 256-colour one (mode X) and an 8-, 15-, 16- or 32-bit linear mode come from the video RAM itself through the debugger's `VGAMEMDUMP`, since the window answers one plane per read in the first two and is smaller than the frame in the others. A build without that command refuses those modes naming it. A 16-colour pixel goes through the Attribute Controller to its DAC entry; a 15- or 16-bit one is widened to eight bits a channel by repeating its high bits. The 256-colour PNG's pixels are the bytes the guest wrote and its PLTE the DAC, so each pixel, doubled each way as the emulator renders 13h, equals the emulator's own capture.

**In protected mode the screen is read through a data segment that covers it** (the lowest present one of the GDT, then of the LDT), with paging on only when every page maps to the same physical address; none qualifying is `no_channel`.

Protected mode reads through a covering GDT or LDT segment. `text` is one string a row of the crop as code page 437 draws it, trailing spaces dropped; `cursor` is `[column, row]` in the crop, unavailable when hidden or outside it. The PNG's PLTE is the DAC and its pixels the indices the guest wrote. It is attached after the JSON when within the inline ceiling (1568 px a side, 1568 tiles of 28 px); `image` names it either way (`path`, `bytes`, `sha256`, `width`, `height`, `scale`, `indexed`, `border`, `inline`, `not_inlined`). A dump file left in the emulator's working directory, a screen past its window, one no segment or page reaches, a layout with split or panning is refused, and a picture the disk could not take whole is `host_failed`.

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
  "crop": [
    0,
    0,
    80,
    25
  ]
}
```
<!-- scry-reference:end screen_signature -->



<!-- scry-reference:begin map_find -->
## `map_find`

*Which mapped screen is this*

```text
map_find()
```

Which mapped screen the machine shows. Reply: `matched`; matched, `screen`, `layer`, `kind`,
`size`, `controls` (`name`, `rect`, `centre`); else `screens_mapped`, `screens_tried`. None
mapped: `needs_call`.

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
| `size` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "map_find: probe_stopped (session), 0 controls",
  "status": "ok",
  "matched": true,
  "screen": "probe_stopped",
  "layer": "session",
  "kind": "text",
  "size": [
    80,
    25
  ],
  "controls": []
}
```
<!-- scry-reference:end map_find -->

Session layer first, then the file's; a screen matches when its kind and size are the screen's and every region's signature is. Matched controls are what `send_mouse(target=)` acts on. The modes `screen_view` refuses are refused.

<!-- scry-reference:begin map_write -->
## `map_write`

*Write the screen map*

```text
map_write(method, screen="", match=null, controls=null, path="", dest="", overwrite=null)
```

The screen map: an application's screens, each known by the signatures of its stable
regions, and their controls, in a session layer and a file layer.

`add`: the screen shown now as `screen` in the session layer, one read signing each `match`
crop ([x, y, width, height], 1..16), `controls` ([{"name", "rect"}]) in the screen's own
units. Reply: `screen`, `kind`, `size`, `match`, `controls`, `replaced`,
`shadows_file`.

`load`: `path` (`<application>.scry-map.json`, absolute or `~`-led) as the file layer. Reply:
`path`, `application`, `screens`, `controls`.

`save`: both layers as one map to `dest`, refused there without `overwrite`, made the file
layer. Reply: `path`, `application`, `screens`, `controls`, `promoted`.

Refused: an argument the method does not take; a misshapen name, crop, control or file
(`bad_argument`); nothing mapped to save (`needs_call`); the modes `screen_view` refuses.

Reference: REFERENCE.md, Screen maps.

| argument | type | default |
|---|---|---|
| `method` | one of `"add"`, `"load"`, `"save"` | required |
| `screen` | string | `""` |
| `match` | array of array of integer or null | `null` |
| `controls` | array of object or null | `null` |
| `path` | string | `""` |
| `dest` | string | `""` |
| `overwrite` | boolean or null | `null` |

| reply field | type |
|---|---|
| `application` | string |
| `controls` | integer |
| `kind` | string |
| `match` | array |
| `path` | string |
| `promoted` | array |
| `replaced` | boolean |
| `screen` | string |
| `screens` | integer |
| `shadows_file` | boolean |
| `size` | array |

Example, from a live run:

```json
{
  "method": "add",
  "screen": "probe_stopped",
  "match": [
    [
      0,
      0,
      8,
      1
    ]
  ]
}
```

```json
{
  "summary": "map_write add: probe_stopped (text 80x25), 1 region, 0 controls",
  "status": "ok",
  "screen": "probe_stopped",
  "kind": "text",
  "size": [
    80,
    25
  ],
  "match": [
    {
      "crop": [
        0,
        0,
        8,
        1
      ],
      "signature": "ed0b26b4f25ef236"
    }
  ],
  "controls": 0,
  "replaced": false,
  "shadows_file": false
}
```
<!-- scry-reference:end map_write -->

Units are cells in a text mode and pixels in 256 colours.

<!-- scry-reference:begin debug -->
## `debug`

*Raw debugger command*

```text
debug(command)
```

One raw `command` to the debugger; the last resort. For a value use `registers`,
`read_memory` or `memdump`; for the log `log`.

Reply: `output` (the last 4000 characters of what the debugger printed),
`output_chars`, `clipped`, `command`, `note` (when the debugger did not take the command).

Refused `bad_argument`: a command that lets the guest run (`RUN`, `VRT`, `RUNWATCH`, `INT`,
`STEPIN`, the `LOG` family) and a control character.

| argument | type | default |
|---|---|---|
| `command` | string | required |

| reply field | type |
|---|---|
| `clipped` | boolean |
| `command` | string |
| `note` | string |
| `output` | string |
| `output_chars` | integer |

Example, from a live run:

```json
{
  "command": "BPLIST"
}
```

```json
{
  "summary": "debug 'BPLIST': 90 chars",
  "status": "ok",
  "command": "BPLIST",
  "output": "Breakpoint list:\n-------------------------------------------------------------------------",
  "output_chars": 90,
  "clipped": false
}
```
<!-- scry-reference:end debug -->

**A command that lets the guest run is refused before it is sent**, because it leaves the debugger without the session knowing and `last_stop` and `status` would go on naming the stop before it. A control character is refused: a line break would carry a second command past that check.

**A command the debugger does not take says so**: its printed reason comes back in `output` and `note` says it was not taken.

The refusal names the tool that does what the command would.
