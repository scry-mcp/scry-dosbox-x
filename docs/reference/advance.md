# The Advance tools

<!-- scry-reference:begin run_to -->
## `run_to`

*Run to a place, with a control*

```text
run_to(ref, control, seconds=30.0)
```

Run until a SYMBOL or a `SEG:OFF`, and say where it really stopped. Reports its
progress while it waits.

`ref` is a symbol name from the loaded table or a raw `SEG:OFF` in hex (the colon is the
tell); the server derives the debugger's address from the machine's own mode, arms a
`BP`, verifies it by reading the list back, releases the machine and waits up to
`seconds`, INTERRUPTING the run at its bound. `control` is REQUIRED, this run's own (the
session keeps no declared control): a second `ref` known to be HOT, armed
beside the target and counted every time it fires, so a bound that expires with ZERO
control hits is INVALID rather than "it did not arrive". Pick one that fires a few times a
run: each hit costs a round trip.

Refused before the machine moves: no control (the schema requires one, and an empty one is
none), an absent or ambiguous name, a machine not stopped.

Reply: `verdict` (`TARGET`; `OTHER_STOP`, another breakpoint got there first; `TIMEOUT`,
the bound ran out and the run was interrupted where it stood), `target_disarmed` (the
breakpoint it armed, removed on every outcome; false when that could not be confirmed),
`target`, `control_hits`, `controls` (`ref`, `at`, `hits_in_run`, `removed`), a `note`
explaining a non-arrival, and the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9`. INVALID
carries no `verdict`: `control_silent` (a TIMEOUT with no control hit) or
`cut_by_other_stop` (another stop before the control fired), each with the stop surveyed;
`not_settled` when the interrupt found no prompt.

Reference: REFERENCE.md, Advancing the machine.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `control` | string | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `cause` | string |
| `control_hits` | integer |
| `controls` | array |
| `cpu_mode` | string or object |
| `e9` | object |
| `enrichment` | object |
| `instruction` | object |
| `note` | string |
| `pc` | string |
| `ref` | string |
| `regs` | object |
| `stop_seq` | integer |
| `target` | string |
| `target_disarmed` | boolean |
| `verdict` | string |
| `watches` | array |

Example, from a live run:

```json
{
  "ref": "0000:0003",
  "seconds": 3,
  "control": "0814:0130"
}
```

```json
{
  "summary": "run_to 0000:0003: TIMEOUT at 0814:00000130, control counted 3",
  "status": "ok",
  "verdict": "TIMEOUT",
  "target": "0000:0003",
  "ref": "0000:0003",
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 3,
  "controls": [
    {
      "ref": "0814:0130",
      "at": "0814:0130",
      "hits_in_run": 3,
      "removed": true
    }
  ],
  "note": "it came to rest ON the control 0814:0130 (its hit number 3) when the bound ran out, and not at 0000:0003. The breakpoint at 0000:0003 was removed.",
  "regs": {
    "EAX": "0x00000000",
    "ESI": "0x00000173",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814",
    "EBX": "0x000002bc",
    "EDI": "0x0000015d",
    "CS": "0x0814",
    "EIP": "0x00000130",
    "ECX": "0x0000fffe",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fffe"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": [
      "Bochs port E9h: [+ 00000.000] PROBE . tick"
    ],
    "mark": 31673
  },
  "stop_seq": 6,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "code pane",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  }
}
```
<!-- scry-reference:end run_to -->

The breakpoint it created is removed on every outcome, because `BP` is persistent and a leftover
would silently stop the next `resume` at a place no declaration names; it looks the index up again,
because `BPDEL` renumbers.

**A control turns a silence into a measurement.** A `TIMEOUT` with zero control hits is
`control_silent`, not "it did not arrive": nothing was proved about the target, the shape of the
ROM breakpoint that never fires (`breakpoint_at`). A cold target beside a hot control fires the
control and never the target; with the roles swapped the target arrives.

<!-- scry-reference:begin run_for -->
## `run_for`

*Run for frames or emulated time*

```text
run_for(milliseconds=0, frames=0, seconds=30.0)
```

Run the machine for `frames` frames of the display, one vertical retrace each (the
debugger's `VRT`), or for `milliseconds` of its emulated time, and come back STOPPED with
the full stop reply. Reports its progress while it waits.

Arguments: exactly one of `frames` and `milliseconds` above zero. By `milliseconds` it runs
retrace by retrace until the register pane's emulated clock has risen at least that far, so
it stops at the first retrace at or past the mark, surveying every frame to read it.
`seconds`: the wall-clock bound. Needs the machine stopped. A DOS machine keeps no frame
counter, so `frames` counts retraces from where the call starts.

Reply: `verdict`, `ELAPSED` (the run ran its course: every frame, or the clock at the mark),
`OTHER_STOP` (a declared code breakpoint stopped it first, named by `cause`) or
`TIMEOUT` (the bound expired); `polls`, the `VRT`s answered by a stop; `emulated_before_s`
and `emulated_after_s`, the register pane's emulated clock; `frame_before`, `frame_after`
and `cycles`, unavailable with why; and the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9`. `retrace_pending: true`:
the debugger still holds a retrace stop, which the next release meets. `note`: what the
reply cannot prove (a declared breakpoint or watch, an unread clock). A `TIMEOUT` with a
`VRT` still out is interrupted where it stands, its retrace left pending. INVALID
`no_progress` when the clock did not move (over the run by frames, at any frame by
milliseconds); `unexpected_answer` when a timed run finds no clock to start from, before
anything runs. Advancing is not altering.

Reference: REFERENCE.md, Advancing the machine.

| argument | type | default |
|---|---|---|
| `milliseconds` | integer | `0` |
| `frames` | integer | `0` |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `cycles` | object |
| `e9` | object |
| `emulated_after_s` | number or object |
| `emulated_before_s` | number |
| `enrichment` | object |
| `frame_after` | object |
| `frame_before` | object |
| `instruction` | object |
| `note` | string |
| `pc` | string or object |
| `polls` | integer |
| `regs` | object |
| `retrace_pending` | boolean |
| `stop_seq` | integer |
| `verdict` | string |
| `watches` | array |

Example, from a live run:

```json
{
  "frames": 1
}
```

```json
{
  "summary": "run_for 1 frame: ELAPSED, 1 poll, at 0814:00000130",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 1,
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "regs": {
    "EAX": "0x00000000",
    "ESI": "0x00000173",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814",
    "EBX": "0x000002bc",
    "EDI": "0x0000015d",
    "CS": "0x0814",
    "EIP": "0x00000130",
    "ECX": "0x0000c12e",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fffe"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 32972
  },
  "stop_seq": 7,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "code pane",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "emulated_before_s": 1.9730911,
  "emulated_after_s": 1.9747000000000001,
  "frame_before": {
    "available": false,
    "why": "a DOS machine keeps no frame counter a server could read: `polls` counts the retraces"
  },
  "frame_after": {
    "available": false,
    "why": "a DOS machine keeps no frame counter a server could read: `polls` counts the retraces"
  },
  "cycles": {
    "available": false,
    "why": "the pane's `cc=` counts cycles only on the normal core, and which core runs is not something this server can read, so no count is given"
  }
}
```
<!-- scry-reference:end run_for -->

**A `VRT` a breakpoint cuts stays armed**, so the next release stops at the next retrace: an
`OTHER_STOP` says `retrace_pending: true`, and the first later stop no declaration explains names
that retrace as the likeliest cause. Two limits the `note` states: on a dynamic core a code
breakpoint armed after its code already ran can fail to cut the frames after it, so an `ELAPSED`
does not prove its address was not reached; and a change-watch or interrupt breakpoint cannot be
told from a retrace, so its stop counts as a frame.

<!-- scry-reference:begin trace -->
## `trace`

*Trace what a run executes*

```text
trace(instructions, shape="normal", dest="", seconds=60.0)
```

Run the machine `instructions` instructions with the debugger's CPU log on (its `LOG`
family), come back STOPPED with the log in a file and the full stop reply, and say which
loaded symbols the executed addresses fall in.

Arguments: `instructions`, how many to EXECUTE, 1 to 3000000. `shape`: `normal`
(`LOG`: disassembly and registers), `short` (`LOGS`), `long` (`LOGL`: adds emulated time, VM and
CR0) or `cs_ip` (`LOGC`: the address alone). `dest`: absolute, its directory there, the
file not, not directly in the emulator's working directory; empty,
the next free `trace-<n>.trace` in the session's captures directory. `seconds`: the
wall-clock bound. Needs the machine stopped, a writable working directory and
`build_check`'s `heavy_debug`.

The count is proved against the pane's `cc=` counter, which on the normal core moves one
per instruction: a mismatch is `no_channel`, the file kept (a dynamic core logs once per
block: `start(flags=["-set", "cpu core=normal"])` to trace).

Reply: `verdict`, `ELAPSED` (all ran; the file holds one line more, the stop), `OTHER_STOP`
(a declared stopper or pending retrace first, `cause`) or `TIMEOUT` (the bound ran
out: the run interrupted where it stood, and what ran up to there collected);
the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9`; `trace`: `path`, `bytes`, `shape`, `instructions` (executed), `addresses`
(distinct), `unplaced` (no symbol places them), `set_path` (a JSON line per address;
unavailable when it could not be written, said in `note`), `symbols` (per routine, the first
64), `symbols_total`, `truncated`, `note` for what it cannot prove.
`readback_refused`: the log closed early (the machine closed it before the trace stopped, so
its lines are not what ran), is empty, or would not close; `host_failed`: the debugger was
refused its file, nothing ran and the line it left is emptied. Advancing is not altering.

Reference: REFERENCE.md, Advancing the machine.

| argument | type | default |
|---|---|---|
| `instructions` | integer (>= 1, <= 3000000) | required |
| `shape` | one of `"normal"`, `"short"`, `"long"`, `"cs_ip"` | `"normal"` |
| `dest` | string | `""` |
| `seconds` | number (> 0, <= 600.0) | `60.0` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `instruction` | object |
| `pc` | string |
| `regs` | object |
| `stop_seq` | integer |
| `trace` | object |
| `verdict` | string |
| `watches` | array |

Example, from a live run:

```json
{
  "instructions": 16,
  "shape": "cs_ip",
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n954.trace",
  "seconds": 30
}
```

```json
{
  "summary": "trace 16 cs_ip: ELAPSED, 16 executed at 1 address, at 0814:00000130, to $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n954.trace",
  "status": "ok",
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "regs": {
    "EAX": "0x00000000",
    "ESI": "0x00000173",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814",
    "EBX": "0x000002bc",
    "EDI": "0x0000015d",
    "CS": "0x0814",
    "EIP": "0x00000130",
    "ECX": "0x0000c11e",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fffe"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 33154
  },
  "stop_seq": 8,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "code pane",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "verdict": "ELAPSED",
  "trace": {
    "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n954.trace",
    "bytes": 238,
    "shape": "cs_ip",
    "instructions": 16,
    "addresses": 1,
    "unplaced": 1,
    "set_path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n954.trace.set.jsonl",
    "symbols": [],
    "symbols_total": 0,
    "truncated": false,
    "note": "no symbol table is loaded: `symbols_load` names the routines"
  }
}
```
<!-- scry-reference:end trace -->

**The log is the instrument.** The debugger writes as its last line the instruction it stops at,
logged and not executed, so the call sends `N + 1` in hex and an `ELAPSED` file holds `N + 1`
lines. What ran before a stop is not read back: `HEAVYLOG` writes its ring only when the emulator
exits, so that question is answered by a trace forward from an earlier stop.

The working directory is only the file's passing place, because the debugger writes nowhere else.

**A trace proves its own count**: the line count is an instruction count only on the normal core,
so the pane's `cc=` must have moved by the entries the file holds. An interrupt breakpoint stops
inside its INT, after the counter took it and before it ran, so a cut run may count one more than
it executed; and the log writes each line before breakpoints are checked, so a trace started on a
breakpoint's address stops there again with nothing executed. The machine can close the log itself
(the BIOS's power-on self test does, so a trace from the reset park meets it).

<!-- scry-reference:begin screen_wait -->
## `screen_wait`

*Run until text is on screen*

```text
screen_wait(text, seconds=30.0)
```

Run the machine retrace by retrace until `text` is on the TEXT screen, and stop there.
`text` (1 to 132 characters code page 437 draws, not ending in a blank) is matched
literally, case-sensitive, inside ONE row of the screen as `screen_view` reads it, trailing
blanks dropped: a string that wraps across rows is not found. `seconds`, the wall-clock
bound, counted from after the first read of the screen, so a short one still
reaches the first frame; a frame's read under way when it passes is finished. Needs the
machine stopped and a session started with `logfile`; reports its progress while it waits.

Already on screen at the call: answered at once, the machine not moved. Otherwise each
retrace costs a stop and five console round trips, so for a string far ahead `run_for`
first. A frame not in a text mode is no match.

Reply: `verdict` `TARGET` with `already`, `waited_s`, `polls` (the retraces run), `point`
(`[column, row]` where the text begins), `line` (that row), and a `note` when a declared watch
or interrupt breakpoint could have made a stop it took for a retrace. The bound: `verdict`
`TIMEOUT` with `waited_s`, `polls`, `text` (the rows of the last text page read, absent when
none was), `retrace_pending` and a `note` (a `VRT` still out is interrupted where it stands).
Either, when it ran: the stop it ended at, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9` (or `enrichment` unavailable, its
survey cut).

Refused: a bad `text` or `seconds` (`bad_argument`, before anything is typed); a declared
code breakpoint stopping the machine first (`wait_stopped`, with its `cause`,
`stop_seq`, `polls`, `retrace_pending`, `text`); a screen it cannot read, as `screen_view`
refuses it, with `polls` and `stop_seq` after a retrace; where `stop_seq` is due and the
stop's survey came back cut, `enrichment` unavailable instead; no `logfile`
(`no_channel`); a running guest (`not_stopped`).

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `text` | string | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `already` | boolean |
| `cause` | string |
| `cpu_mode` | string |
| `e9` | object |
| `enrichment` | object |
| `instruction` | object |
| `line` | string |
| `note` | string |
| `pc` | string |
| `point` | array |
| `polls` | integer |
| `regs` | object |
| `retrace_pending` | boolean |
| `stop_seq` | integer |
| `text` | array |
| `verdict` | string |
| `waited_s` | number |
| `watches` | array |

Example, from a live run:

```json
{
  "text": "C:\\>PROBE.COM",
  "seconds": 10
}
```

```json
{
  "summary": "screen_wait 'C:\\\\>PROBE.COM': already on screen at 0,3",
  "status": "ok",
  "verdict": "TARGET",
  "already": true,
  "waited_s": 0.0,
  "polls": 0,
  "point": [
    0,
    3
  ],
  "line": "C:\\>PROBE.COM"
}
```
<!-- scry-reference:end screen_wait -->

<!-- scry-reference:begin step -->
## `step`

*Step instructions*

```text
step(count=1, mode="into")
```

`count` instructions, one at a time, `mode` `into` (F11, the default) or
`over` (F10), each step READ BACK. Needs the machine stopped.

Reply: `mode`, `asked`, `before` and `after` (each `SSSS:OOOOOOOO`),
`instructions_completed` (how many steps actually landed, not how many were asked; fewer
when the machine left the debugger, e.g. an `over` across a call that never returns, which
`session.running` says, so the remaining steps were not sent), `moved`, `stalled` (steps
after which CS:EIP was unchanged: a swallowed keystroke, a `rep` iteration, a jump to
itself, a halt), and when it stopped the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9`. A settle per step; for a longer run use
`run_to`.

| argument | type | default |
|---|---|---|
| `count` | integer (>= 1, <= 64) | `1` |
| `mode` | one of `"over"`, `"into"` | `"into"` |

| reply field | type |
|---|---|
| `after` | string |
| `asked` | integer |
| `cause` | string |
| `before` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `enrichment` | object |
| `instruction` | object |
| `instructions_completed` | integer |
| `mode` | string |
| `moved` | boolean |
| `pc` | string |
| `regs` | object |
| `stalled` | integer |
| `stop_seq` | integer |
| `watches` | array |

Example, from a live run:

```json
{
  "count": 1
}
```

```json
{
  "summary": "step 1: 1 done, at F000:0000FEA6",
  "status": "ok",
  "mode": "into",
  "asked": 1,
  "moved": true,
  "stalled": 0,
  "before": "F000:0000FEA5",
  "after": "F000:0000FEA6",
  "instructions_completed": 1,
  "pc": "F000:0000FEA6",
  "cpu_mode": "real",
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
    "EIP": "0x0000fea6",
    "ECX": "0x0000a97e",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fff8"
  },
  "watches": [],
  "cause": "no declared code breakpoint at F000:0000FEA6: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 4820
  },
  "stop_seq": 5,
  "instruction": {
    "available": false,
    "why": "the bytes at F000:0000FEA6 (FE...) start no instruction"
  }
}
```
<!-- scry-reference:end step -->

Stepping OVER a `CALL` is run-until-it-returns, so a call that never returns leaves the machine
running and the remaining keystrokes go nowhere; the position is re-established after every key.
`stalled` is counted per step because comparing only the endpoints misreads a two-instruction loop
(`L: nop` / `jmp L`) as a swallowed key. `count` is a cost bound, not a safety one: past it the
question is `run_to`, which pays the settle once.

<!-- scry-reference:begin resume -->
## `resume`

*Resume the machine*

```text
resume(seconds=0.0, detail=false)
```

Let the machine run (F5, sent once). With `seconds` at zero (the default) it comes back
at once, no verdict; with a bound it waits up to `seconds` for a stop, listening for the
debugger's prompt as `run_to` does and reporting its progress: `verdict` `OTHER_STOP` with
the full stop when one lands, or `TIMEOUT` with `waited_s` and a `note`, LEAVING IT RUNNING
(unlike `run_to`, which interrupts at its bound); `seconds` is 0 or a bound up to
600. Needs the machine stopped: a guest already running is refused `not_stopped`,
since an F5 there does nothing and an `ok` would read like a release.

Nothing has to be declared first: `stop` brings a running guest back, headless or windowed.

Reply: a reply that stopped (an F5 that never left the debugger is a stop too) carries
the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, `cause` and `e9`. With `detail=True`, `screen_delta`: the debugger's repaint
for the F5, a POSITIONAL tail capped at its last 2000 characters (`clipped`),
never a value; without it `omitted` names it.

Reference: REFERENCE.md, Advancing the machine.

| argument | type | default |
|---|---|---|
| `seconds` | number (>= 0, <= 600.0) | `0.0` |
| `detail` | boolean | `false` |

| reply field | type |
|---|---|
| `cause` | string |
| `clipped` | boolean |
| `cpu_mode` | string or object |
| `e9` | object |
| `enrichment` | object |
| `instruction` | object |
| `note` | string |
| `pc` | string |
| `regs` | object |
| `screen_chars` | integer |
| `screen_delta` | string |
| `stop_seq` | integer |
| `verdict` | string |
| `waited_s` | number |
| `watches` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "resume: running",
  "status": "ok",
  "omitted": [
    "screen_delta",
    "screen_chars",
    "clipped"
  ],
  "how": "detail=True adds the debugger's repaint for this command"
}
```
<!-- scry-reference:end resume -->

<!-- scry-reference:begin stop -->
## `stop`

*Stop a running machine*

```text
stop()
```

Bring a RUNNING guest back to the debugger and survey the stop, headless or windowed
alike: the session sends `BREAK` down the emulator's own debugger channel (upstream's
`mcp_server`), which reaches the debugger while the guest runs, with no window, no menu and
nothing taken from whoever is using the screen.

THE MACHINE STOPS WHEREVER IT IS, and that is not always in the program: a DJGPP guest
spends part of every frame in real-mode BIOS handlers (`F000:xxxx`), and a stop landing
there has no protected-mode selector to place a symbol through, so every symbol of a
protected-mode table answers that the machine stopped outside the program, and a stop
lands there often. A breakpoint on the program, armed at a stop inside it before the
release, is what brings the machine back into its code.

`unarmable` AND `unresolved` ARE DIFFERENT ANSWERS and the difference is worth holding:
`unarmable` means the symbol IS in the table and its address cannot be worked out at
this instant, while `unresolved` means the table does not carry the name at all:
`unresolved` is a fact about the TABLE, not about the stop: `symbols_load` accumulates its
batches, so a name missing after several
loads is one none of them carried.

Reply: `interrupted` (`true` with the full stop reply and `via: "break"`; `false` when the
machine was already stopped, with `last_stop` and a `note`). A `BREAK` whose prompt never
comes is `not_settled`: asking again is allowed, and if `stop` fails as well, `close` then
`start`.

Takes no argument.

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `instruction` | object |
| `interrupted` | boolean |
| `note` | string |
| `pc` | string |
| `regs` | object |
| `stop_seq` | integer |
| `via` | string |
| `watches` | array |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "stop: already stopped",
  "status": "ok",
  "interrupted": false,
  "last_stop": {
    "stop_seq": 4,
    "pc": "F000:0000FEA5",
    "cause": "no declared code breakpoint at F000:0000FEA5: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
    "since_s": 25.0,
    "wall_at": "2026-10-24T16:10:01+00:00"
  },
  "note": "the machine was already stopped"
}
```
<!-- scry-reference:end stop -->
