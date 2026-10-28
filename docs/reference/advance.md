# The Advance tools

<!-- scry-reference:begin run_to -->
## `run_to`

*Run to a place, with a control*

```text
run_to(ref="", control, screen="", seconds=30.0)
```

Run until a symbol or a `SEG:OFF` and say where it stopped.

`ref`: a loaded symbol or hex `SEG:OFF`. `control` is required: a second ref known to be
hot, counted when it fires, so a bound that expires with no control hit is INVALID, not "it
did not arrive". Needs a stopped machine. Refused: an absent or ambiguous name. On a dynamic
cpu core, which can pass over a breakpoint inside a compiled block, `note` says so.

`screen`: a mapped screen's name instead of `ref` (exactly one), run to its `anchor`, the
`control` still required; a `verified` map judges it there (`stale_map` when it no longer
holds), a `consolidated` one takes it as shown. Reply: `screen` (`screen`, `layer`, `mode`,
`judged`). Refused: an unmapped screen (`unknown_ref`), one with no `anchor` (`needs_call`).

Reply: `verdict` (`TARGET`, `OTHER_STOP`, `TIMEOUT`), `target_disarmed`, `control_hits`,
`controls` (`ref`, `at`, `hits_in_run`), `note`, the stop (`pc`, `frame`, `regs`, `cause`).
INVALID: `control_silent`, `cut_by_other_stop`, `not_settled`, `stale_map`.

Reference: REFERENCE.md, Advancing the machine.

| argument | type | default |
|---|---|---|
| `ref` | string | `""` |
| `control` | string | required |
| `screen` | string | `""` |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `cause` | string |
| `control_hits` | integer |
| `controls` | array |
| `cpu_mode` | string or object |
| `e9` | object |
| `enrichment` | object |
| `frame` | integer or object |
| `instruction` | object |
| `note` | string |
| `pc` | string |
| `ref` | string |
| `regs` | object |
| `screen` | object |
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
  "summary": "run_to 0000:0003: TIMEOUT at 0814:00000130, control counted 85",
  "status": "ok",
  "verdict": "TIMEOUT",
  "target": "0000:0003",
  "ref": "0000:0003",
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 85,
  "controls": [
    {
      "ref": "0814:0130",
      "at": "0814:0130",
      "hits_in_run": 85,
      "removed": true
    }
  ],
  "note": "it came to rest ON the control 0814:0130 (its hit number 85) when the bound ran out, and not at 0000:0003. The breakpoint at 0000:0003 was removed.",
  "frame": 138,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000002bc",
    "ECX": "0x0000ffac",
    "EDX": "0x00000814",
    "ESI": "0x00000173",
    "EDI": "0x0000015d",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000130",
    "CS": "0x0814",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": [
      "Bochs port E9h: [+ 00000.000] PROBE . tick"
    ],
    "mark": 32026
  },
  "stop_seq": 6,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
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

**A dynamic core is refused, not waited out.** Its recompiled blocks run past a code breakpoint without checking it, so a `run_to` there would arrive at nothing and read as "never reached". `start` says so in its `note` when the conf's `[cpu] core=` or a `-set "cpu core=..."` flag selects it, and `run_to` and `breakpoint_at` refuse with `no_channel` naming `start(flags=["-set", "cpu core=normal"])`. `auto` and `normal` are not refused.

**A control turns a silence into a measurement.** A `TIMEOUT` with zero control hits is
`control_silent`, not "it did not arrive": nothing was proved about the target, the shape of the
ROM breakpoint that never fires (`breakpoint_at`). A cold target beside a hot control fires the
control and never the target; with the roles swapped the target arrives.

The server derives the debugger's address from the machine's own mode, arms a `BP`, verifies it by reading the list back, and interrupts at the bound. Pick a control that fires a few times a run: each hit costs a round trip. `OTHER_STOP` means another breakpoint got there first. The `target_disarmed` breakpoint is removed on every outcome (false when that could not be confirmed). `control_silent` is a TIMEOUT with no control hit and `cut_by_other_stop` another stop before the control fired, each with the stop surveyed; `not_settled` is an interrupt after which `RUNSTATE` did not say stopped.

<!-- scry-reference:begin run_for -->
## `run_for`

*Run for frames or emulated time*

```text
run_for(milliseconds=0, frames=0, seconds=30.0)
```

Run for `frames` display frames (one `VRT` each) or `milliseconds` of emulated time (exactly
one) and come back STOPPED. `milliseconds` runs whole frames, so it ends at the first
retrace at or past the time asked, up to one frame later. Reports progress while it waits.
Needs the machine stopped.

Reply: `verdict` (`ELAPSED`, `OTHER_STOP`, `TIMEOUT`), `polls`, `emulated_before_s`,
`emulated_after_s`, `frame_before`, `frame_after`, `cycles` (unavailable with why),
`retrace_pending`, `note`, the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause` and `e9`. INVALID: `no_progress`, `unexpected_answer`.

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
| `frame` | integer or object |
| `frame_after` | integer or object |
| `frame_before` | integer or object |
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
  "frame": 139,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000002bc",
    "ECX": "0x0000c1d1",
    "EDX": "0x00000814",
    "ESI": "0x00000173",
    "EDI": "0x0000015d",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000130",
    "CS": "0x0814",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0814:00000130",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 88798
  },
  "stop_seq": 7,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "emulated_before_s": 1.9731157000000001,
  "emulated_after_s": 1.9747000000000001,
  "frame_before": 138,
  "frame_after": 139,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and which core runs is not something this server can read, so no count is given"
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

**Every stop says which display frame it is in** (`frame`): the frames the emulator's vertical timer has started since power-on, read off `RUNSTATE` at the stop, so a `run_for(frames=N)` that ends `ELAPSED` with nothing else able to stop the machine moves it by exactly N (a change-watch's stop counted as a frame moves it less), and a frame number names one instant of a run. `perform(until_frame=F)` stands on it. It belongs to this run, not to a saved state: after a load it goes on counting. A build whose `RUNSTATE` prints no `frames=` leaves it unavailable, saying so.

By milliseconds it reads the emulated clock off each retrace stop's `RUNSTATE` and stops at the first retrace at or past the time asked, since a stop between retraces is not one a replay can reach again: it runs over by up to one frame. A `TIMEOUT` with a `VRT` still out is interrupted where it stands, its retrace left pending. `retrace_pending: true` means the debugger still holds a retrace stop, which the next release meets. The `note` states what the reply cannot prove (a declared breakpoint or watch, an unread clock). Advancing is not altering.

<!-- scry-reference:begin trace -->
## `trace`

*Trace what a run executes*

```text
trace(instructions, shape="normal", dest="", seconds=60.0)
```

Run `instructions` (1 to 3000000) with the debugger's CPU log on and come back
STOPPED with the log in a file, joined to symbols.

`shape`: `normal` (`LOG`), `short` (`LOGS`), `long` (`LOGL`) or `cs_ip` (`LOGC`). `dest`:
absolute, its directory there, the file not; empty is the next `trace-<n>.trace` in
captures. Needs a stopped machine, a writable working directory and `build_check`'s
`heavy_debug`; a dynamic core needs `start(flags=["-set", "cpu core=normal"])`.

Reply: `verdict`, the stop reply of `run_to`, `trace` (`path`, `instructions`, `addresses`,
`unplaced`, `set_path`, `symbols` (first 64)). Refused: `no_channel`,
`readback_refused`, `host_failed`.

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
| `frame` | integer or object |
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
  "dest": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n1372.trace",
  "seconds": 30
}
```

```json
{
  "summary": "trace 16 cs_ip: ELAPSED, 16 executed at 1 address, at 0814:00000130, to $TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n1372.trace",
  "status": "ok",
  "pc": "0814:00000130",
  "cpu_mode": "real",
  "frame": 139,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000002bc",
    "ECX": "0x0000c1c1",
    "EDX": "0x00000814",
    "ESI": "0x00000173",
    "EDI": "0x0000015d",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000130",
    "CS": "0x0814",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 89341
  },
  "stop_seq": 8,
  "instruction": {
    "seg_off": "0814:00000130",
    "bytes": "E2FE",
    "text": "loop 0x130",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
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
    "path": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n1372.trace",
    "bytes": 238,
    "shape": "cs_ip",
    "instructions": 16,
    "addresses": 1,
    "unplaced": 1,
    "set_path": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n1372.trace.set.jsonl",
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
so the cycle count `RUNSTATE` gives must have moved by the entries the file holds. An interrupt breakpoint stops
inside its INT, after the counter took it and before it ran, so a cut run may count one more than
it executed; and the log writes each line before breakpoints are checked, so a trace started on a
breakpoint's address stops there again with nothing executed. The machine can close the log itself
(the BIOS's power-on self test does, so a trace from the reset park meets it).

`verdict`: `ELAPSED` means all ran and the file holds one line more, the stop; `OTHER_STOP` a declared stopper or pending retrace first (`cause`); `TIMEOUT` the run was interrupted where it stood and what ran up to there collected. `instructions` is executed, `addresses` distinct, `unplaced` those no symbol places; `set_path` is a JSON line per address, unavailable when it could not be written (said in `note`). `no_channel`: the count is proved against `RUNSTATE`'s cycle count, which moves one per instruction on the normal core only. `readback_refused`: the log closed early (the machine closed it before the trace stopped, so its lines are not what ran), is empty, or would not close. `host_failed`: the debugger was refused its file, and nothing ran.

<!-- scry-reference:begin screen_wait -->
## `screen_wait`

*Run until text is on screen*

```text
screen_wait(text, seconds=30.0)
```

Run the machine retrace by retrace until `text` is on the TEXT screen, and stop there.
`text` (1 to 132 code page 437 characters) is matched literally,
case-sensitive, inside one row as `screen_view` reads it. Needs a stopped machine and
`RUNSTATE`. Already on screen: answered at once. Each retrace costs a stop and a reading of the
screen, so `run_for` first for a distant string.

Reply: `verdict` `TARGET` (`already`, `waited_s`, `polls`, `point` `[column, row]`, `line`)
or `TIMEOUT` (`waited_s`, `polls`, `text`, `retrace_pending`), `note`, the stop reply of
`run_to` with its `frame`. Refused: `bad_argument`, `wait_stopped` (a declared breakpoint
stopped it), `no_channel` (a screen it cannot read, or a build with no `RUNSTATE`).

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
| `frame` | integer or object |
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

`seconds` is counted from after the first read so that a short one still reaches the first frame; a frame read under way when it passes is finished. A frame not in a text mode is no match. `note` on a TARGET appears when a declared watch or interrupt breakpoint could have made a stop it took for a retrace. On a TIMEOUT `text` holds the rows of the last text page read, absent when none was, and a `VRT` still out is interrupted where it stands. Refusals that ran a retrace carry `polls` and `stop_seq`; `wait_stopped` also carries `stop_seq`, `polls`, `retrace_pending` and `text`. Where `stop_seq` is due and the stop's survey came back cut, `enrichment` is unavailable instead.

<!-- scry-reference:begin step -->
## `step`

*Step instructions*

```text
step(count=1, mode="into")
```

`count` instructions, each read back; `mode` `into` (the debugger's `STEPIN`) or `over` (a
CALL, INT, LOOP or REP run to the next instruction, which needs `RUNSTATE`). Needs the machine
stopped.

Reply: `mode`, `asked`, `before`, `after`, `instructions_completed`, `moved`, `stalled`
(CS:EIP unchanged after a step), `note` (a step over's own breakpoint not confirmed removed),
and the stop reply; an `over` that does not come back within its bound is stopped where it
stands, and no later step is sent. For longer runs `run_to`.

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
| `frame` | integer or object |
| `instruction` | object |
| `instructions_completed` | integer |
| `mode` | string |
| `moved` | boolean |
| `note` | string |
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
  "frame": 4,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000124",
    "ECX": "0x0000a97e",
    "EDX": "0x00000814",
    "ESI": "0x00000100",
    "EDI": "0x0000fffe",
    "EBP": "0x0000091c",
    "ESP": "0x0000fff8",
    "EIP": "0x0000fea6",
    "CS": "0xf000",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814"
  },
  "watches": [],
  "cause": "no declared code breakpoint at F000:0000FEA6: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": 6109
  },
  "stop_seq": 5,
  "instruction": {
    "available": false,
    "why": "the bytes at F000:0000FEA6 (FE...) start no instruction"
  }
}
```
<!-- scry-reference:end step -->

Stepping into is the debugger's `STEPIN`. Stepping OVER a `CALL`, an `INT`, a `LOOP` or a `REP` is
composed: a breakpoint on the next instruction, `RUN`, the wait for the stop (`RUNSTATE`), the
breakpoint removed; so a call that never returns leaves the machine running and the remaining
steps are not sent. `stalled` is counted per step because comparing only the endpoints misreads a
two-instruction loop (`L: nop` / `jmp L`) as a step that went nowhere. `count` is a cost bound, not
a safety one: past it the question is `run_to`.

`instructions_completed` can be fewer than asked when the machine left the debugger (an `over` across a call that never returns, which `session.running` says), so the remaining steps were not sent. `stalled` is a `rep` iteration, a jump to itself or a halt.

<!-- scry-reference:begin resume -->
## `resume`

*Resume the machine*

```text
resume(seconds=0.0, detail=false)
```

Let the machine run. `seconds` 0 (the default) returns at once with no deadline; a bound
up to 600 waits for a stop and, if none comes, leaves it running. Needs a stopped
machine.

Reply: with a bound, `verdict` (`OTHER_STOP` with the stop reply of `run_to`; `TIMEOUT`,
`waited_s`, `note`). `output` (with `detail=True`: the last 2000 characters
the debugger printed for `RUN`; else `omitted`).

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
| `frame` | integer or object |
| `instruction` | object |
| `note` | string |
| `pc` | string |
| `regs` | object |
| `output` | string |
| `output_chars` | integer |
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
    "output",
    "output_chars",
    "clipped"
  ],
  "how": "detail=True adds what the debugger printed for this command"
}
```
<!-- scry-reference:end resume -->

It asks `RUNSTATE` as `run_to` does and reports progress. A running guest is refused because a `RUN` there does nothing and an `ok` would read like a release. Nothing has to be declared first: `stop` brings a running guest back, headless or windowed. A release that stopped at once is a stop too, but only for a call with a bound: `seconds` 0 returns straight after the release with no look for a stop, and a stop after it is what the next call finds.

<!-- scry-reference:begin stop -->
## `stop`

*Stop a running machine*

```text
stop()
```

Bring a running guest back to the debugger and survey the stop, headless or windowed.

Reply: `interrupted` (`true` with the stop reply and `via: "break"`; `false` when already
stopped, with a `note`). INVALID `not_settled`: after the `BREAK`, `RUNSTATE` did not say
stopped; ask again.

Reference: REFERENCE.md, Advancing the machine.

Takes no argument.

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `frame` | integer or object |
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
    "since_s": 0.1,
    "wall_at": "2026-10-27T11:18:22+00:00"
  },
  "note": "the machine was already stopped"
}
```
<!-- scry-reference:end stop -->

The session sends `BREAK` down the emulator's own debugger channel (upstream's `mcp_server`), so it needs no window, no menu and nothing taken from whoever is using the screen. The machine stops wherever it is, often outside the program: a DJGPP guest spends part of every frame in real-mode BIOS handlers (`F000:xxxx`), where no protected-mode selector can place a symbol, so every symbol of a protected-mode table answers that the machine stopped outside the program. A breakpoint on the program, armed at a stop inside it before the release, brings the machine back into its code. `unarmable` means the symbol is in the table and its address cannot be worked out at this instant; `unresolved` means the table does not carry the name, a fact about the table and not the stop, since `symbols_load` accumulates its batches. If `stop` fails as well, `close` then `start`. Last stop is reported as `last_stop`.
