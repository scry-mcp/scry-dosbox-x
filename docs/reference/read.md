# The Read tools

The typed tools parse what the debugger console paints, read its lists back and refuse a shape they were not captured answering; `debug` is the raw command for the rest.

### The picture attached

A view's PNG goes to the session's scratch (`close` deletes it; `dest` keeps one) and is attached after the JSON. Past 1568 px a side, or 1568 tiles of 28 px, the API resamples, and a resampled picture of pixel art is a plausible wrong one: it is written and not attached, `not_inlined` says why, and the caller asks for a `crop` or a smaller `scale`. A picture inside a sequence's step is never attached, since only a reply's own picture crosses. The default `scale` is the largest integer factor that fits, so each pixel stays a square of one colour.

<!-- scry-reference:begin registers -->
## `registers`

*Read the registers*

```text
registers(from_last_stop=false)
```

The register pane as a mapping. Needs the machine stopped at the debugger; INVALID
when no pane came back, and that refusal carries `last_stop` and the tools that do answer
while the guest runs. `from_last_stop=True` hands back the registers AS THEY WERE at the
last stop, never as the current value; INVALID before any stop.

Reply: `regs` (`EAX`, `EIP`, `CS`, `DS`, ... as hex strings), and from the last stop
`superseded` (true) with `last_stop`. The control registers (CR0, CR3) and the descriptor
tables' registers are not in the pane: `machine_map(sections=["control"])` reads them.

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
    "ESI": "0x00000100",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814",
    "EBX": "0x00000124",
    "EDI": "0x0000fffe",
    "CS": "0xf000",
    "EIP": "0x0000fea5",
    "ECX": "0x0000a97e",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fff8"
  }
}
```
<!-- scry-reference:end registers -->

<!-- scry-reference:begin read_memory -->
## `read_memory`

*Read memory*

```text
read_memory(ref, length=16)
```

`length` bytes at `ref`, a symbol or a `SEG:OFF` (the colon is the tell: a bare
number is read as a symbol name), as `hex`;
beside them the data-view ROWS the debugger's `D` printed, which is where the bytes come
from. Needs the machine stopped.

Reply: `hex` (`length` bytes from the address), `length`, `rows` (the data view's rows
of sixteen bytes, as many as the debugger's window showed), and `seg_off`, where the
ref resolved to. `length` is 1 to 128, and the rows have to hold it from the
address: a view that showed fewer bytes than asked is refused (`readback_refused`)
naming what it held, and above the view the answer is `memdump`. INVALID unless the
address asked for is among the rows returned, so a cut repaint is refused rather than
handed back shifted. An absent or ambiguous symbol is refused.

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
  "summary": "read_memory 0000:0020: 8 rows at 0000:00000020",
  "status": "ok",
  "ref": "0000:0020",
  "seg_off": "0000:00000020",
  "length": 4,
  "hex": "a5fe00f0",
  "rows": [
    "0000:00000020 A5 FE 00 F0 87 E9 00 F0 55 FF 00 F0 80 CE 00 F0  ........U.......",
    "0000:00000030 80 CE 00 F0 80 CE 00 F0 E0 CC 00 F0 0E 00 70 00  ..............p.",
    "0000:00000040 EE 00 00 C0 20 CB 00 F0 40 CB 00 F0 60 CF 00 F0  .... ...@...`...",
    "0000:00000050 80 CB 00 F0 A0 CB 00 F0 C0 CF 00 F0 C0 CB 00 F0  ................",
    "0000:00000060 00 CD 00 F0 60 CC 00 F0 E0 CB 00 F0 C0 D1 00 F0  ....`...........",
    "0000:00000070 00 CC 00 F0 58 C9 00 F0 02 00 94 FC E9 05 00 C0  ....X...........",
    "... 2 more"
  ]
}
```
<!-- scry-reference:end read_memory -->

It hands back ROWS rather than a screen: the debugger paints its Output log BELOW its Data view, so
a positional cut of the terminal's tail can return a read beginning at another address with the
reply saying `ok`. It reduces by MEANING. An escape sequence can straddle two reads, so its head is
held and prepended to the next (at offset zero too), or a fragment stripped alone injects its final
byte into a row's hex; the hold is bounded by length, or an unterminated OSC would swallow the
stream and go blind while reporting nothing wrong.

<!-- scry-reference:begin disassemble -->
## `disassemble`

*Disassemble code*

```text
disassemble(ref, length=16)
```

Decode `length` bytes from `ref`, a symbol or a `SEG:OFF`, one x86
instruction a line, on the host (capstone): the debugger has no disassembly command. The
listing completes the instruction that straddles the end, so it may run a little past
`length`, unless the segment ends first. Needs the machine stopped.

The width is the segment's own D bit: real mode 16-bit; in protected mode the pane's
`Pr32`/`Pr16` for CS, `SELINFO` for a selector another segment register holds, the
descriptor listings (which need `logfile`) for one no register holds.

Reply: `seg_off`, `length`, `code_bits` (16 or 32) and `code_bits_from` (where
the width was read), `lines` (`SSSS:OOOOOOOO BYTES TEXT`; a byte no instruction starts
with is `.byte 0x..`), `flow` (per line: `call`, an interrupt included; `branch`; `return`;
`sequential`; `unknown` for such a byte), `flow_source` (`capstone`), and with a symbol
table loaded `resolved`: every direct call or branch target (`kind` `target`, its segment
the line's own or the far pointer's) and direct memory operand (`kind` `memory`,
`register` the segment register it is read through, at its value at this stop), each with
`line`, `operand`, `seg_off`, `addr` (the linear address), and the nearest `symbol` with
`delta`, unavailable outside the table's span; a row that could not be placed has `addr`
unavailable too. A register-relative operand is not resolved.

Refused: `length` out of range, and one that runs past the end of a 16-bit segment
(IP wraps there), naming the most bytes from there; `memdump`'s refusals apply to the
bytes read (a leftover dump file, a protected-mode range past offset 0xFFFF without
`logfile`).

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

<!-- scry-reference:begin call_stack -->
## `call_stack`

*Guess the call stack*

```text
call_stack()
```

A heuristic chain of the callers of the routine the stop is in, never a verdict: the
frame pointers walked (C's `push bp`/`mov bp, sp` and the `enter` frame), each return
address kept only when a call instruction ends exactly there. Needs the machine stopped.

Row 0 is the stop. Outside its routine's frame (a `push bp` or `enter` at the routine's own
address, the `mov bp, sp` right after the push, the `ret` that leaves it) the caller is read
off the stack pointer (`via` `entry`); then the chain from BP (`bp_chain`): the return
beside each frame, near or far as the call before it says. A return is named by the
routine its call is in. The walk ends at a zero
or non-rising saved frame pointer, a frame past the stack segment's end, a return no call
precedes (not listed), a return outside the loaded table (listed), or its bound.

Reply: `heuristic` (always true), `code_bits`, `calls` (innermost first: `seg_off`,
`addr` (linear), `symbol` and `delta`, unavailable outside the table's span,
`via`, `call` (the call instruction at the call site, unavailable on row 0), `bp` (the
frame it was read beside, unavailable on rows 0 and `entry`)), `truncated` (the bound was
reached), `ended_why` (a read that failed says so here). Refused when the register pane
shows no SS, ESP or EBP. A routine that keeps no frame pointer is invisible to it: its
caller's caller is listed in its place, or nothing.

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

<!-- scry-reference:begin memdump -->
## `memdump`

*Dump memory to a file*

```text
memdump(ref, length, dest)
```

`length` bytes of memory to a FILE at `dest`.

Reply: `ref`, `seg_off`, `length`, `path` and `bytes` (the size written).

`ref` is a symbol or a `SEG:OFF` (colon required); `dest` is an absolute path, its
directory there. Needs the machine stopped. The size
handed back is checked for EQUALITY against `length`. Refused rather than overwriting: a
dump file already sitting where the debugger writes (the emulator's working directory),
a dangling link there included, or at `dest`, and a `dest` directly in that directory (a
subdirectory of it is fine). An absent or ambiguous symbol is refused.

Past offset 0xFFFF the debugger would wrap a 16-bit segment or read zeros past a limit: in
real mode the range is read in 64 KiB windows, so it holds the bytes really there, up to
`FFFF:FFFF`; in protected mode the selector's descriptor is read (which needs `logfile`)
and a 16-bit segment, a range past its limit, or a selector with no descriptor is refused.
Inside 0 to 0xFFFF the limit is not judged and the debugger reads zeros past it.

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n733.bin"
}
```

```json
{
  "summary": "memdump 0000:0400: 16 bytes to $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n733.bin",
  "status": "ok",
  "ref": "0000:0400",
  "seg_off": "0000:00000400",
  "length": 16,
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n733.bin",
  "bytes": 16
}
```
<!-- scry-reference:end memdump -->

**`memdump` names the debugger's file itself**, `MCPDUMP.BIN` in the emulator's working directory, so `captures_dir` is not where a dump lands. A build whose `MEMDUMPBIN` is given no name reads one from past the end of the line; a build that takes no name writes `MEMDUMP.BIN`, collected from the working directory and the captures directory alike, because where that lands is one build's behaviour.

A `dest` that is, or lives under, one of the debugger's file names is refused too, compared on the filesystem rather than the spelling: a dump collected into the directory it is collected FROM cannot be told from the leftover, and would poison every later dump.

<!-- scry-reference:begin find -->
## `find`

*Find bytes in memory*

```text
find(data_hex, ref, length)
```

Every address holding the bytes `data_hex` (whole hex bytes, two digits each) in
`length` bytes from `ref`. `ref` and `length` are required: there is no default range.

The debugger has no pattern search of its own, so the range is dumped (the `memdump`
route, its windows past offset 0xFFFF included, into a scratch file of this call's own
that is gone before the reply) and searched exactly. Needs the machine
stopped; `memdump`'s refusals apply (a leftover dump file where the debugger writes). In
real mode a hit past offset 0xFFFF is named from its own paragraph. For a VALUE narrowed
by what it does over time, the debugger's own scanner is `scan_start` / `scan_filter` /
`scan_clear`.

Reply: `seg_off`, `length`, `span` (what was examined:
`from`, `length`, `source`, here always `ref+length` since the range is the caller's
own), `hits` (`SEG:OFF` in address order, at most 400: when truncated, the HIGHEST
addresses are kept), `hits_total` (every hit), `truncated`.

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

<!-- scry-reference:begin log -->
## `log`

*Read the log*

```text
log(pattern, channel, limit=40, labels=false, since_mark=0)
```

The session's log, one `channel` of it, filtered in the server by a regex.

`channel` is `guest` (the program's own 0xE9 instrumentation, one line per write),
`emulator` (DOSBox-X's own lines, the categories its `log` section names) or `all` (the
file in order, each line tagged `[guest] ` or `[emulator] `); `process` names the
emulator's stdout, which here is the debugger's terminal, and is refused by name.
`pattern` is a Python regular expression; `limit` keeps the NEWEST
matching lines; `labels=True` adds `labels`, how many returned lines carry each first
word (the guest's own `BOOT`, `PERF`, `UI`...), one glance at who is talking. `since_mark`, a byte position in the channel's log (the `mark` a `state_load` or a stop's log block gives for it): only what was written after it is read; 0, the default, reads the whole log
(one file holds the three channels, so one position serves each). Needs a
session started with `logfile`. Works on a running guest (and, like every tool, applies
what was queued while the guest ran if it finds the machine stopped, saying so in
`applied_on_stop`).

Reply: `channel`, `lines` (the newest `limit` matches, in order), `lines_total` (how many
matched IN ALL, not how many came back), `truncated`, and `labels` when asked. An empty `lines`
is an answer: the channel is there and nothing matched.

INVALID, with `code` and `message` saying which: no `logfile` on this session; the log
does not exist yet; the guest channel holds no instrumentation at all; `limit` out of range
(above it, narrow the pattern); a
pattern that does not compile; a channel that is not one of the three; a `since_mark` that
names no position of the log; the session is gone. For "when did X happen, and wait if it
has not" use `log_wait`.

Reference: REFERENCE.md, The log.

| argument | type | default |
|---|---|---|
| `pattern` | string | required |
| `channel` | one of `"guest"`, `"emulator"`, `"all"` | required |
| `limit` | integer (>= 1, <= 400) | `40` |
| `labels` | boolean | `false` |
| `since_mark` | integer (>= 0) | `0` |

| reply field | type |
|---|---|
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
  "lines": [
    "00. BPINT 21 AH=4B",
    "DEBUG: Breakpoint deletion success.",
    "Breakpoint list:",
    "-------------------------------------------------------------------------",
    "Breakpoint list:",
    "-------------------------------------------------------------------------",
    "... 34 more"
  ]
}
```
<!-- scry-reference:end log -->

<!-- scry-reference:begin log_wait -->
## `log_wait`

*Wait for a log line*

```text
log_wait(pattern, channel, seconds=30.0, since_mark=0)
```

WHEN a line of `channel` matching `pattern` was logged: at once if it already was,
else wait for it. Reports its progress while it waits.

`channel` as in `log` (`guest`, `emulator`, `all`); `pattern` is a regex over that
channel; `seconds` bounds the wait. It reads what the log ALREADY holds first, so a line
that went past before you asked is still found. `since_mark` as in `log`: "already" is then
"since the mark", which is how "after the load" is asked. Works on a running guest (the usual
case: a guest writing traces is a guest that runs).

Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the FIRST match; `log` is the tool
for the newest), `already` (it was in the log before this call: history, not something you
were present for), `waited_s` (0.0 when already), `lines_before`, `lines_total`,
`arrived_during`, `lines_examined`; when the bound ran out, `verdict` `TIMEOUT` with
`pattern`, `channel`, `arrived_during`, `lines_examined`, `waited_s` and a `note` (the guest
still runs). `status: INVALID`: `wait_stopped` when the
machine is STOPPED and the log does not already hold the line (a stopped guest writes
nothing; the refusal names `pattern` and `last_stop`, and a stop that lands DURING the wait
is reported the same way after one last read of the log), `session_broken` when the emulator
went away. No `logfile`, a bad `seconds`, an unusable regex, an
unknown channel or a `since_mark` that names no position of the log is refused. A log that
does not exist YET is not refused: that is the ordinary state right after `resume`.

The moment it hands back is for choosing an address to `run_to` or `watch` on the NEXT
run: the guest is usually still running when this returns, and the console tools refuse
then. `expect` on `send_keys`/`drive` is this same wait on the guest channel, from a
mark taken before the act.

Reference: REFERENCE.md, The log.

| argument | type | default |
|---|---|---|
| `pattern` | string | required |
| `channel` | one of `"guest"`, `"emulator"`, `"all"` | required |
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

No breakpoint can be armed on a log line: the guest is usually still running and the console takes no commands then. The nearest is a change watch on the variable whose change produces the line.

<!-- scry-reference:begin machine_map -->
## `machine_map`

*Map the machine*

```text
machine_map(sections=null, dest="")
```

WHAT THE DOS MACHINE IS AT THIS STOP, one section per debugger listing, read live off the
session's logfile: it needs the machine STOPPED and a session started with `logfile`, and
costs a console round trip per listing.

`sections` names the ones to read; left out, the DOS machine and its control registers:
`mcbs`, `devs`, `kern`, `xms`, `ems`, `ems_pages`, `emu_mem`, `machine`, `control`, and in
protected mode `gdt` and `ldt`. The rest are read only when named: `bios_mem`, `callbacks`,
`vga`, `paging`.
`dest` (absolute, not there yet) writes every section read WHOLE as JSON (`path`).

Refused: an empty or unknown `sections`, or a `dest` already there (`bad_argument`, before
anything is typed); no `logfile` (`no_channel`); a running guest (`not_stopped`); no prompt
after a listing (`unexpected_answer`: `close` the session); a logfile that shrank
(`session_broken`).

Reply: `cpu_mode` (`real`, `protected`, `paged`; unavailable when the `CPU` listing is
unreadable), then each section read: `mcbs` (`memory`, `mcb_seg`, `size_bytes`, `psp_seg`,
`notes`, `filename`), `devs` (`header`, `attr`, `strat`, `intr`, `name`), `kern` (`seg`,
`size_bytes`, `what`), `xms` (`handle`, `status`, `location`, `size_bytes`), `ems`
(`handle`, `addr`, `size_bytes`, `name`), `ems_pages` (`handle`, `page`, `start`, `end`),
`bios_mem` (`start`, `end`, `status`, `what`), `callbacks` (`number`, `desc`), `emu_mem`,
`machine`, `control` (control registers, flags, `gdtr`, `idt`, `tr`, `ldtr`); `gdt`/`ldt`
(`selector`, `base`, `limit`, `type`, `dpl`, `p`, `a`, `r`, `b`, `g`); `paging` (runs:
`start`, `end`, `phy`, `flags`, `d`, `a`); `vga` (`mode`, `crtc`, `seq`, `gc`, `ac`, `dac`,
`draw`). A section the debugger refused or printed nothing known for is ABSENT and
`coverage_note` says why. `counts` (full lengths), `truncated` (a list cut at
400 rows), `sources`; `omitted` (sections this mode has that were not read) with
`how`. Writes nothing to the guest.

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
  "coverage_note": "read from the debugger's own listings at this stop, through the session's logfile. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
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

The rows come from the logfile and never from the screen, where the repaint draws columns with
cursor moves the escape strip removes, so a segment and a size run together. A listing longer than
the Output pane pages, and the pager eats every key, a command included; so the reader answers with
`Q` alone, and an input line still holding text after that is refused `unexpected_answer`, because
the next command would be appended to it.

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

<!-- scry-reference:begin interrupt_vectors -->
## `interrupt_vectors`

*Read the interrupt vectors*

```text
interrupt_vectors(number=null)
```

WHICH HANDLER EVERY INTERRUPT VECTOR POINTS AT, AND WHAT HOLDS IT: the debugger's
`INTVEC` table, each handler placed in the block of the MCB chain, the kernel's blocks or
the BIOS's that holds it, and named by the loaded symbol table where that table reaches.
`number`, an integer 0 to 255 (INT 0x21 is 33), narrows the reply to one vector; the whole
table is read either way. Needs the machine STOPPED. In protected mode the table is the IDT,
placed through the GDT or LDT and, with paging on, the page runs. The debugger writes
`MCPIVT.TXT` into the emulator's working directory, which this reads and removes; with
`logfile` it then reads the listings `machine_map` reads, a console round trip each.
Without `logfile` no vector has a holder, nor in protected mode an `addr` or a `symbol`.

Refused: `number` outside 0 to 255 (`bad_argument`, before anything is typed); a
`MCPIVT.TXT` already there (`bad_argument`: somebody else's, left in place); a running
guest (`not_stopped`); no table reported written, or a file that is not the whole table
(`unexpected_answer`); and the listings' refusals, as `machine_map` gives them.

Reply: `cpu_mode` (`VM86` among its words; without `logfile`, as `status` reports it),
`vectors` (each `number`,
`seg_off` as the table holds it, `addr` the linear address before any paging, the row that
holds the handler under its own section's name, `mcbs`, `kern` or `bios_mem`, first match in
that order, absent when none does or it was not placed, and `symbol` as
`symbols_find(linear=)` answers it, given only between the table's lowest and highest
symbol), `counts` (`vectors`, `held`, `named`, over the whole table), `sources`,
`coverage_note` (what could not be placed, and why). Before DOS has filled the table every
vector is 0000:0000, as read.

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
  "coverage_note": "read from the debugger's own listings at this stop, through the session's logfile. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off"
}
```
<!-- scry-reference:end interrupt_vectors -->

The holder row says which program
hooked a vector without comparing against an earlier table; a table taken at `start` is all zeros,
since the park comes before DOS fills it.

<!-- scry-reference:begin palette -->
## `palette`

*Read the palette*

```text
palette(first=0, count=0, scale=0, dest="")
```

THE 256 COLOURS OF THE VGA'S DAC AS THEY ARE AT THIS STOP, read off the debugger's
`VGA DAC` and `VGA DACPAL` listings in the session's logfile, with their swatch attached:
it needs the machine STOPPED and a session started with `logfile`, and costs a console
round trip per listing and one more for `VGA DACPAL`'s pager.

The DAC holds entries 0 to 255 and nothing past them: an entry past 255 does not exist.
`first` (0 to 255; an integer or a `0x` hex string) and `count` (1 to
256, 0 for every entry from `first`) choose the entries returned, `first + count` at most
256. The swatch is one square per entry, sixteen a row, an indexed PNG whose every pixel is
the entry's index into the DAC. The PNG is attached after the JSON when within the inline ceiling (1568 px a side, 1568 tiles of 28 px); `image` names it either way (`path`, `bytes`, `sha256`, `width`, `height`, `scale`, `indexed`, `border`, `inline`, `not_inlined`). `scale` 0, the largest integer enlargement up to 8 that fits; `dest` a new path, else the scratch, gone at `close`.

Reply: `entries` (256), `first`, `count` (how many came back), `colors` (`#rrggbb`, each
six-bit component widened as the emulator renders it, its two top bits repeated below),
`rgb` (each entry as `VGA DACPAL` printed it, three six-bit components in hex), `bits` (6),
`pel_mask` as `VGA DAC` printed it, and `image`.

Refused: an entry the DAC does not have (`first` 256 or more, `first + count` past 256), a
`scale` out of range or a relative `dest` (`bad_argument`, before anything is typed); a
`dest` already there or with no directory (`bad_argument`); no `logfile` (`no_channel`); a
running guest (`not_stopped`); a DAC not in its six-bit mode, or a listing in a shape this
was not written against (`unexpected_answer`); a picture the disk could not take whole
(`host_failed`, leaving no file).

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
    "path": "$TMPDIR/dosbox-x-session-rmnni3t3/gfx/palette-1.png",
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

<!-- scry-reference:begin screen_view -->
## `screen_view`

*Read the screen*

```text
screen_view(crop=null, scale=0, dest="", attach=true)
```

WHAT THE SCREEN SHOWS AT THIS STOP, read from video memory where the VGA listings say it
lies: needs the machine STOPPED and a session started with `logfile`. A text mode comes back
as text; the chained 256-colour mode (13h's) as the picture: an indexed PNG of
the indices the guest wrote, the PLTE the DAC. The PNG is attached after the JSON when within the inline ceiling (1568 px a side, 1568 tiles of 28 px); `image` names it either way (`path`, `bytes`, `sha256`, `width`, `height`, `scale`, `indexed`, `border`, `inline`, `not_inlined`).
`scale` 0, the largest integer enlargement up to 8 that fits; `dest` a new path, else the scratch, gone at `close`; `attach` false writes the file, unattached; a text mode takes none of these. `crop`
`[x, y, width, height]`,
in characters or pixels. Protected mode reads through a covering GDT or LDT segment.

Reply: `vga_mode` (`VGA MODE`'s word), `kind` (`text` or `pixel`), `width` and `height` (in
characters or pixels), `crop` (the rectangle read), `display_start` (as `VGA MODE` printed
it); in text, `text` (one string a row of the crop, as code page 437 draws it, trailing
spaces dropped) and `cursor` (`[column, row]` in the crop, unavailable when hidden or
outside it); in 256 colours, `image`.

Refused: a relative `dest`, a `scale` out of range or a misshapen `crop` (`bad_argument`,
before anything is typed); `dest`, `scale` or `attach` in a text mode, a `crop` off the
screen, a `dest` already there or with no directory, or a dump file left in the emulator's
working directory (`bad_argument`); any other mode, planar, linear-frame-buffer or none set,
naming it and `capture_frame`; a layout this does not decode (split, panning, a row wider
than the screen), a screen past its window, or one no segment or page reaches as itself; no
`logfile` (each `no_channel`); a running guest (`not_stopped`); a DAC not six-bit, or a
listing in another shape (`unexpected_answer`); a picture the disk could not take whole
(`host_failed`).

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

**Only a text mode and the chained 256-colour mode (13h's) are read.** In a planar or unchained mode the CPU window answers one plane per read and choosing the plane writes a Graphics Controller register; a linear frame buffer lies past the debugger's real-mode dump. A layout the bytes cannot be read straight from is refused rather than read wrong. The 256-colour PNG's pixels are the bytes the guest wrote and its PLTE the DAC, so each pixel, doubled each way as the emulator renders 13h, equals the emulator's own capture.

**In protected mode the screen is read through a data segment that covers it** (the lowest present one of the GDT, then of the LDT), with paging on only when every page maps to the same physical address; none qualifying is `no_channel`.

<!-- scry-reference:begin screen_signature -->
## `screen_signature`

*Signature of the screen*

```text
screen_signature(crop=null)
```

One hex string for what is on screen, or on `crop` of it, so "is it the same screen" is
answered by comparing two strings and no picture crosses the conversation. It is the
`scry-sig/1` signature a series row carries over the same crop: in a text mode each cell is
its code page 437 byte and the colours its attribute resolves to through the Attribute
Controller and the DAC; in 256 colours each pixel is its DAC colour. So a palette change is
a new signature, and the cursor is not part of it. `crop` `[x, y, width, height]`, in
characters or pixels. It reads what `screen_view` reads, in the same modes; needs the
machine STOPPED and a session started with `logfile`.

Reply: `signature` (16 hex characters), `kind` (`text` or `pixel`), `width` and `height`
(the screen's), `crop` (the rectangle hashed), `vga_mode`.

Refused as `screen_view` is, `dest` and `scale` aside: a `crop` off the screen
(`bad_argument`); another mode, naming it and `capture_frame`, or a screen it cannot place
(`no_channel`); no `logfile` (`no_channel`); a running guest (`not_stopped`); a DAC not in
its six-bit mode or a listing in another shape (`unexpected_answer`).

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

<!-- scry-reference:begin map_add -->
## `map_add`

*Map the screen in front of you*

```text
map_add(screen, match, controls=null)
```

Map the screen the machine shows NOW as `screen` in the SESSION layer: one read signs each
`match` crop (`[x, y, width, height]`, 1..16, regions that stay still on that screen, never
a cursor or a moving sprite), and `controls` (`[{"name", "rect"}]`, a `rect` shaped as a
crop) name its controls, all in the screen's own units (cells in a text mode, pixels in 256
colours, as `screen_view` counts). A screen of the same name in the file is shadowed
(`shadows_file`). Needs the machine STOPPED and a session started with `logfile`; a `start`
empties the session layer.

Reply: `screen`, `kind`, `size`, `match` (each crop with its `signature`), `controls`,
`replaced`, `shadows_file`. Refused: a misshapen name, crop or control, a rectangle off the
screen (`bad_argument`); the modes `screen_view` refuses.

Reference: REFERENCE.md, Screen maps.

| argument | type | default |
|---|---|---|
| `screen` | string | required |
| `match` | array of array of integer | required |
| `controls` | array of object or null | `null` |

| reply field | type |
|---|---|
| `controls` | integer |
| `kind` | string |
| `match` | array |
| `replaced` | boolean |
| `screen` | string |
| `shadows_file` | boolean |
| `size` | array |

Example, from a live run:

```json
{
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
  "summary": "map_add: probe_stopped (text 80x25), 1 region, 0 controls",
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
<!-- scry-reference:end map_add -->

<!-- scry-reference:begin map_find -->
## `map_find`

*Which mapped screen is this*

```text
map_find()
```

WHICH MAPPED SCREEN the machine shows, from ONE screen read and no picture: the session
layer first, then the file's; a screen matches when its kind and size are the screen's and
every region's signature is. Needs the machine STOPPED and a session with `logfile`.

Reply: `matched`; matched, `screen`, `layer` (`session` or `file`), `kind`, `size`,
`controls` (each `name`, `rect`, `centre`), and `send_mouse(target=)` then acts on them; not
matched, `kind`, `size`, `screens_mapped`, `screens_tried` (of that kind and size). Refused:
no screen mapped (`needs_call`); the modes `screen_view` refuses.

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

<!-- scry-reference:begin debug -->
## `debug`

*Debugger console command*

```text
debug(command)
```

One raw `command` to the debugger console; the LAST resort, not the first.

Needs the machine STOPPED at the debugger (a running guest's console takes nothing). Reply:
`screen_delta`, the delta the screen produced for the command, capped at its last
4000 characters with `screen_chars` (how much the screen produced) and
`clipped` (whether what came back is all of it). It is a repaint of an ncurses screen,
interleaved with the rest of the panes, not a parsed answer. For a VALUE use `registers`,
`read_memory` or `memdump`; for the log use `log`; for a breakpoint or a watch use the tools
that read the debugger's list back, which this does not. Refused `bad_argument` before
anything is typed: a command that lets the guest run (`VRT`, `RUNWATCH`, `INT`, the `LOG`
family), naming the tool that does it and reports the stop, and a command carrying a control
character. A command that writes the guest (memory, a register, a port, an interrupt or the
timer raised, a state loaded, the BIOS clock) marks the session `altered`. `note`: a line
the debugger did not take, emptied, or a listing that paged, ended (REFERENCE.md, The
console).

| argument | type | default |
|---|---|---|
| `command` | string | required |

| reply field | type |
|---|---|
| `clipped` | boolean |
| `command` | string |
| `note` | string |
| `screen_chars` | integer |
| `screen_delta` | string |

Example, from a live run:

```json
{
  "command": "BPLIST"
}
```

```json
{
  "summary": "debug 'BPLIST': 3231 chars",
  "status": "ok",
  "command": "BPLIST",
  "screen_delta": "B_P_L_I_S_T__ooooRegister OverviewoooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooEAX=00000000  ESI=00000100  DS=0814   ES=0814   FS=0000   GS=0000   SS=0814 Real\r\nEBX=00000124  ... (3231 characters)",
  "screen_chars": 3231,
  "clipped": false
}
```
<!-- scry-reference:end debug -->

**A command that lets the guest run is refused before it is typed**, because it leaves the debugger without the session knowing and `last_stop` and `status` would go on naming the stop before it. A control character is refused: a line break would type a second command past that check, and an escape is a key.

**`debug` leaves the console clean.** A command the console does not recognise stays on its input line, and the next command is typed onto it and fails too. So when the line still holds text once the prompt is back, `debug` empties it with ESC, which runs nothing whatever the line's length (a bare return would run it again). A listing that pages is answered with `Q`; `trace` empties the line the same way for a `LOG` the debugger refused.
