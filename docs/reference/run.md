# The Run tools

These tools let the program run and stop it again: to an address, for a number of frames, one instruction at a time, or with no deadline. Most other tools read the machine only while it is stopped, and [REFERENCE.md](../../REFERENCE.md#running-and-stopping) says which ones answer while it runs.

A frame is counted here at the vertical retrace: the moment the display finishes drawing a frame and goes back to the top of the screen. DOS programs wait for it before they draw. The debugger's `VRT` command runs to the next one.

## What every stop returns

A reply that ends at a stop carries the same readings whatever the call was about: `stop_seq`, `pc`, `cpu_mode`, `frame`, `instruction`, `regs`, `watches`, `cause` and `e9`. [REFERENCE.md](../../REFERENCE.md#what-a-stop-returns) describes each.

`frame` counts the frames the emulator's vertical timer has started since power-on, so a frame number names one instant of a run, and `perform(until_frame=F)` relies on it. It belongs to this run, not to a saved state: after a load it goes on counting.

The count is read from `RUNSTATE`, the debugger command that says whether the machine is stopped. A build whose `RUNSTATE` prints no `frames=` leaves `frame` unavailable, saying so.

When the machine stopped and the stop could not be read, the reply keeps the tool's own fields. In place of the stop's readings it carries `enrichment`, as `available: false` with `why`.

A stop inside the BIOS ROM is where the machine stood, not where your program is: a program that called the BIOS is inside a handler there. The `note` gives the address and the calls that leave it, because `step` there stays inside the handler, one instruction at a time.

<!-- scry-reference:begin run_to -->
## `run_to`

Run until the program reaches an address, or a screen of the screen map, and stop there.

```text
run_to(ref="", control="", screen="", seconds=30.0, disarm_watches=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped on its play screen with its symbols loaded.

Ask:

> Run until the ball hits a brick, and check that the game's retrace wait keeps running meanwhile.

Call:

```text
run_to(ref="brick_hit", control="retrace", seconds=60)
```

Reply, 5 of 18 fields:

```json
{
  "summary": "run_to brick_hit: TARGET at 08DF:000002A5, control counted 34",
  "verdict": "TARGET",
  "target_disarmed": true,
  "control_hits": 34,
  "controls": [
    {"ref": "retrace", "at": "08DF:0536", "hits_in_run": 34, "removed": true}
  ]
}
```

The run reached `brick_hit`, which is what `TARGET` says. The control `retrace` ran 34 times on the way, so breakpoints were firing, and both breakpoints of the run are removed.

<details><summary>The whole reply</summary>

```json
{
  "summary": "run_to brick_hit: TARGET at 08DF:000002A5, control counted 34",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:02A5",
  "ref": "brick_hit",
  "pc": "08DF:000002A5",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 34,
  "controls": [
    {"ref": "retrace", "at": "08DF:0536", "hits_in_run": 34, "removed": true}
  ],
  "frame": 36,
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002a5",
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
    }
  ],
  "cause": "run_to's target brick_hit at 08DF:000002A5",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DF:000002A5",
    "bytes": "88DF",
    "text": "mov bh, bl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "comment": "AL = row, BL = column of the brick that falls",
    "symbol": "brick_hit",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00009095", "kind": "symbol", "name": "brick_hit"}
  ]
}
```

</details>

### Arguments

- `ref` (string, default `""`): The address to stop at: a loaded symbol or a hex `SEG:OFF`. Give this or `screen`, never both.
- `control` (string, default `""`): An address known to run often, counted beside the target, so that "the target never ran" can be told from "nothing ran". Required with `ref` or an anchored `screen`.
- `screen` (string, default `""`): A screen of the loaded screen map, the file naming a program's screens. With an `anchor`, an address the map gives it, the run goes there; without, frame by frame.
- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to wait for the stop, in real seconds, before the server interrupts the machine. Left out, 30.
- `disarm_watches` (boolean, default `false`): `true` takes your watches off for this run, so none of them stops it, and sets them again at the end.

### What comes back

- `verdict`: How the run ended: `TARGET`, the target was reached; `TIMEOUT`, the wait gave up; `OTHER_STOP`, a breakpoint or a watch nobody targeted stopped it first.
- `control_hits`: How many times the controls ran during the run. A `TARGET` is `ok` even with none.
- `controls`: One row per control counted: its `ref`, `at` (where the debugger set it), `hits_in_run` and `removed`. It comes with a run to a `ref` or an anchor.
- `target_disarmed`: Whether the run's own breakpoint at the target was removed.
- `frames`: How many frames a run to a screen with no `anchor` took.
- `screen`: After a run to a screen: its `screen`, `layer` and `mode`, and `judged`, whether the map checked the screen there.

<details><summary>All 21 reply fields</summary>

- `disarmed_watches` (array)
- `not_rearmed` (array)
- `cause` (string)
- `regpoint_hit` (object)
- `control_hits` (integer)
- `controls` (array)
- `cpu_mode` (string or object)
- `e9` (object)
- `enrichment` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string)
- `ref` (string)
- `regs` (object)
- `screen` (object)
- `frames` (integer)
- `stop_seq` (integer)
- `target` (string)
- `target_disarmed` (boolean)
- `verdict` (string)
- `watches` (array)

</details>

### What it refuses

- A `ref` or a `control` that no loaded symbol table holds, or a `screen` the map does not name (`unknown_ref`).
- A name that several symbols share (`ambiguous_ref`).
- No `control` with a `ref` or an anchored screen, or a `control` or `disarm_watches` with a screen that has no anchor (`bad_argument`).
- A control at the target's address (`bad_argument`).
- A breakpoint the debugger does not list after being told to set it, found before the machine moves (`readback_refused`).
- A `TIMEOUT` during which no control ran: nothing was learned about the target (`control_silent`).
- Another stop before any control ran (`cut_by_other_stop`).
- A machine that did not report stopped after the interrupt at the time limit (`not_settled`).
- A screen map that no longer matches the screen at its anchor (`stale_map`).
- A machine that is running (`not_stopped`).

### Why it works this way

A breakpoint can stay silent for reasons that have nothing to do with the program, as one set in ROM does. That looks exactly like "that routine is never called". The control counting beside the target tells them apart, so a `TIMEOUT` with no control hit is refused: it proves nothing about the target.

The target is a temporary breakpoint of the run's own, removed however the run ends. The debugger's breakpoints are persistent, so one left behind would stop the next `resume` at an address none of your breakpoints names. `target` is that breakpoint as the debugger lists it.

`disarm_watches` is for a watch on a byte written every frame, which would otherwise stop every later run.

<details><summary>More on why</summary>

A dynamic cpu core runs its recompiled blocks past a code breakpoint without checking it, so a run there could miss its target and read as "never reached". `start`, `run_to` and `breakpoint_at` say so in `note` when the conf's `[cpu] core=` or a `-set "cpu core=..."` flag selects it.

That `note` names the way out, `start(flags=["-set", "cpu core=normal"])`. `auto` is noted by `run_to` and `breakpoint_at` too, because its protected-mode code runs on the dynamic core. `normal` is not noted.

A control stops the machine at each hit, and the server counts it and resumes. Pick a control that runs a few times during the run: each hit costs a stop and a resume. `control_silent` and `cut_by_other_stop` still carry the stop's readings.

With `disarm_watches` the watches are removed from the debugger for the run and set again at its stop. Their addresses are worked out afresh, so a watch on a pointer that moved follows it. One that cannot be set there waits for the next stop, and `not_rearmed` names it with `why`.

- `disarmed_watches` lists, by `ref`, the watches taken off for the run.
- If the call fails with no reply, what it took off is set again or left waiting. The next stop's `applied_on_stop` says when.
- A watch the debugger kept in spite of the removal is named in `note`, since it could still stop the run.

</details>

### Related tools

- [`breakpoint_at`](breakpoints.md#breakpoint_at)
- [`run_for`](#run_for)
- [`stop`](#stop)
- [`screen_map_write`](read.md#screen_map_write)
- [`screen_wait`](#screen_wait)
- [`declaration_clear`](breakpoints.md#declaration_clear)

<details><summary>The contract your client receives</summary>

```text
Run until a symbol or a `SEG:OFF` and say where it stopped.

`ref`: a loaded symbol or hex `SEG:OFF`. `control` is required with a `ref` or an anchored
screen: a place the program runs often while the target is awaited, counted each time it
does, so a bound that expires with no control hit is INVALID, not "it did not arrive"; each
control `breakpoint_at(role="control")` declared counts too. `disarm_watches=true` disarms the watches for this pass, so none of them cuts it. Needs a
stopped machine. Refused: an absent or ambiguous name. On a dynamic cpu core, or `auto`
(protected-mode code runs dynamic), which can pass over a breakpoint inside a compiled block,
`note` says so.

`screen`: a mapped screen's name instead of `ref` (exactly one). If the screen names an `anchor` (set by `screen_map_write`), run to it (`control`
required): a `verified` map judges it there (`stale_map` when it no longer holds), a
`consolidated` one takes it as shown. If it names none, a frame at a time until the map names it,
within `seconds`; a `control` or `disarm_watches` is refused there (`bad_argument`). Reply: `screen` (`screen`, `layer`,
`mode`, `judged`), `frames` run. Refused: an unmapped screen (`unknown_ref`).

Reply: `verdict` (`TARGET`, `OTHER_STOP`, `TIMEOUT`), `target_disarmed`, `control_hits`,
`controls` (`ref`, `at`, `hits_in_run`; a run to a ref or an anchor), `frames` (a screen with
no anchor), `note`, the stop (`pc`, `frame`, `regs`, `cause`). INVALID: `control_silent`,
`cut_by_other_stop`, `not_settled`, `stale_map`.

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end run_to -->

<!-- scry-reference:begin run_for -->
## `run_for`

Run for a number of frames or milliseconds of emulated time and come back stopped.

```text
run_for(milliseconds=0, frames=0, seconds=30.0, disarm_watches=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at `brick_hit` in the middle of a game.

Ask:

> Run three frames, then stop.

Call:

```text
run_for(frames=3)
```

Reply, 5 of 18 fields:

```json
{
  "verdict": "ELAPSED",
  "polls": 3,
  "frame_before": 244,
  "frame_after": 247,
  "cycles": 68493
}
```

`ELAPSED` says the three frames ran out as asked. The frame counter went from 244 to 247 in three stops at the retrace, and the cpu spent 68493 cycles.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 3,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 247,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 0"], "mark": "<volatile>"},
  "stop_seq": 11,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 244,
  "frame_after": 247,
  "cycles": 68493
}
```

</details>

### Arguments

- `milliseconds` (integer, default `0`): How much emulated time to run, in milliseconds. Give this or `frames`, never both.
- `frames` (integer, default `0`): How many frames to run, each counted at the screen's vertical retrace. Give this or `milliseconds`, never both.
- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to wait for the run to end, in real seconds. Left out, 30.
- `disarm_watches` (boolean, default `false`): `true` takes your watches off for this run, so none of them stops it, and sets them again at the end.

### What comes back

- `verdict`: How the run ended: `ELAPSED`, the frames or time asked for ran out, as asked; `TIMEOUT`, the wait gave up; `OTHER_STOP`, a breakpoint or a watch stopped it first.
- `frame_after`: The frame counter after the run; `frame_before` is the one before. Unavailable, with why, when `RUNSTATE` prints no frame count.
- `emulated_after_s`: The emulated clock after the run, in seconds; `emulated_before_s` is the one before.
- `cycles`: The cpu cycles the run took. A count only on a session started on the `normal` cpu core; otherwise unavailable, with why.
- `polls`: How many retraces the run stopped at.
- `retrace_pending`: `true` when a stop at the next retrace is still armed in the debugger, so the next resume stops there.

<details><summary>All 21 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `cycles` (integer or object)
- `e9` (object)
- `emulated_after_s` (number or object)
- `emulated_before_s` (number)
- `enrichment` (object)
- `frame` (integer or object)
- `frame_after` (integer or object)
- `frame_before` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string or object)
- `polls` (integer)
- `regs` (object)
- `retrace_pending` (boolean)
- `stop_seq` (integer)
- `verdict` (string)
- `watches` (array)
- `disarmed_watches` (array)
- `not_rearmed` (array)

</details>

### What it refuses

- Both `milliseconds` and `frames` above zero, or neither, or a negative one (`bad_argument`).
- A run during which the emulated clock did not move (`no_progress`).
- `milliseconds` when `RUNSTATE` gave no clock to count from; nothing ran (`unexpected_answer`).
- A DOSBox-X whose debugger has no `RUNSTATE` command (`no_channel`).
- A machine that is running (`not_stopped`).

### Why it works this way

The run is the debugger's `VRT` command, once per frame. By `milliseconds` it still ends on a retrace, the first at or past the time asked, so it can run over by up to one frame. A stop between two retraces is not one a replay could reach again.

A breakpoint that stops the run in the middle of a frame leaves that frame's retrace stop armed in the debugger. The reply is `OTHER_STOP` with `retrace_pending: true`, and the next resume stops at the next retrace. The first later stop that none of your breakpoints explains names that retrace as the likeliest cause.

An `ELAPSED` run of N frames, with nothing else able to stop the machine, moves `frame` by exactly N. On a dynamic cpu core a code breakpoint set after its code already ran can fail to stop the frames after it. So `ELAPSED` there does not prove its address was not reached, which `note` says.

<details><summary>More on why</summary>

- The stop of a change watch or an interrupt breakpoint cannot be told from a retrace, so it counts as a frame. `note` says when one is set.
- A `TIMEOUT` whose `VRT` is still running is interrupted where it stands, with its retrace left pending.
- `note` states what the reply cannot prove: a breakpoint or a watch that is set, a clock that could not be read.
- A run does not mark the session `altered`.
- The call reports progress to the client while it waits.

</details>

### Related tools

- [`run_to`](#run_to)
- [`resume`](#resume)
- [`stop`](#stop)
- [`trace`](#trace)
- [`screen_wait`](#screen_wait)
- [`perform`](sequences.md#perform)

<details><summary>The contract your client receives</summary>

```text
Run for `frames` display frames (one `VRT` each) or `milliseconds` of emulated time (exactly
one) and come back STOPPED. `milliseconds` runs whole frames, so it ends at the first
retrace at or past the time asked, up to one frame later. Reports progress while it waits.
`disarm_watches=true` disarms the watches for this pass, so none of them cuts it. Needs the machine stopped.

Reply: `verdict` (`ELAPSED`, `OTHER_STOP`, `TIMEOUT`), `polls`, `emulated_before_s`,
`emulated_after_s`, `frame_before`, `frame_after`, `cycles` (a count on the normal core, else
unavailable with why), `retrace_pending` (a retrace stop is left armed), `note`,
the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause`, `regpoint_hit` (a registerpoint stopped it) and `e9`. INVALID: `no_progress`, `unexpected_answer`.

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end run_for -->

<!-- scry-reference:begin trace -->
## `trace`

Run a number of instructions with the debugger's CPU log on and get every address executed, grouped by symbol.

```text
trace(instructions, shape="normal", dest="", seconds=60.0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped inside `brick_hit`. It needs a DOSBox-X built with heavy debugging, started on the `normal` cpu core.

Ask:

> Trace the next 40 instructions and tell me which routines they run through.

Call:

```text
trace(instructions=40)
```

Reply, 4 of 13 fields:

```json
{
  "summary": "trace 40 normal: ELAPSED, 40 executed at 34 addresses, at 08 ... (121 characters)",
  "verdict": "ELAPSED",
  "pc": "08DF:000001FE",
  "frame": 36
}
```

All 40 instructions ran, which is what `ELAPSED` says, at 34 distinct addresses. `trace`, in the whole reply, lists the routines they ran through.

<details><summary>The whole reply</summary>

```json
{
  "summary": "trace 40 normal: ELAPSED, 40 executed at 34 addresses, at 08DF:000001FE, to ./tmp/demos/tour/files/captures/trace-1.trace",
  "status": "ok",
  "pc": "08DF:000001FE",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000700",
    "ECX": "0x005b0002",
    "EDX": "0x00000008",
    "ESI": "0x00000007",
    "EDI": "0x00001efd",
    "EBP": "0x0000091c",
    "ESP": "0x0000fff0",
    "EIP": "0x000001fe",
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
    }
  ],
  "cause": "the end of the trace's count, at 08DF:000001FE",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 5,
  "instruction": {
    "address": "08DF:000001FE",
    "bytes": "F3AA",
    "text": "rep stosb byte ptr es:[di], al",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "fill_rect",
    "delta": 3
  },
  "verdict": "ELAPSED",
  "trace": {
    "path": "./tmp/demos/tour/files/captures/trace-1.trace",
    "bytes": 10209,
    "shape": "normal",
    "instructions": 40,
    "addresses": 34,
    "unplaced": 0,
    "set_path": "./tmp/demos/tour/files/captures/trace-1-trace-set.jsonl",
    "symbols": [
      {
        "symbol": "brick_index",
        "addr": "0x00008fbb",
        "addresses": 6,
        "instructions": 6,
        "first": "0x00008fbb",
        "last": "0x00008fc5"
      },
      {
        "symbol": "brick_rect",
        "addr": "0x00008fc6",
        "addresses": 18,
        "instructions": 18,
        "first": "0x00008fc6",
        "last": "0x00008fe9"
      },
      {
        "symbol": "fill_rect",
        "addr": "0x00008feb",
        "addresses": 4,
        "instructions": 10,
        "first": "0x00008feb",
        "last": "0x00008fee"
      },
      {
        "symbol": "brick_hit",
        "addr": "0x00009095",
        "addresses": 6,
        "instructions": 6,
        "first": "0x00009099",
        "last": "0x000090a8"
      }
    ],
    "symbols_total": 4,
    "truncated": false
  }
}
```

</details>

### The four shapes

| shape | the debugger command it uses |
|---|---|
| `normal` | `LOG` |
| `short` | `LOGS` |
| `long` | `LOGL`, whose lines say their own cpu mode. |
| `cs_ip` | `LOGC` |

### Arguments

- `instructions` (integer (>= 1, <= 3000000), required): How many instructions to run and log.
- `shape` (one of `"normal"`, `"short"`, `"long"`, `"cs_ip"`, default `"normal"`): Which of the debugger's log formats to write, as above. Left out, `normal`.
- `dest` (string, default `""`): Where the log ends up: an absolute or `~` path to a new file in a folder that exists. Left empty, the next `trace-<n>.trace` among the captures.
- `seconds` (number (> 0, <= 600.0), default `60.0`): How long to wait for the log to finish, in real seconds. Left out, 60.

### What comes back

- `verdict`: `ELAPSED`, every instruction ran; `OTHER_STOP`, a breakpoint or a pending retrace stopped it first; `TIMEOUT`, the wait gave up and the run was interrupted where it stood.
- `trace`: The result: `path` to the log, `set_path` to the list of addresses, `instructions` executed, distinct `addresses`, `unplaced` (addresses no symbol covers) and `symbols`.

<details><summary>All 12 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `e9` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string)
- `regs` (object)
- `stop_seq` (integer)
- `trace` (object)
- `verdict` (string)
- `watches` (array)

</details>

### What it refuses

- A DOSBox-X built without heavy debugging, which `build_check` reports as `heavy_debug` (`no_channel`).
- A working directory the emulator cannot write, since the debugger opens its log there (`no_channel`).
- A `LOGCPU.TXT` already in the emulator's working directory: it is somebody's, so move it aside; it is never deleted (`bad_argument`).
- A cpu core whose cycle count does not move one per instruction: `start(flags=["-set", "cpu core=normal"])` (`no_channel`).
- A log the machine closed before the trace stopped, an empty log, or one that would not close (`readback_refused`).
- A log file the debugger could not create; nothing ran (`host_failed`).
- A machine that is running (`not_stopped`).

### Why it works this way

The debugger's log ends with the instruction it stops at, logged and not executed, so a complete file holds one line more than `instructions`. A trace runs forward only. The debugger writes its history of what ran before a stop only when the emulator exits, so that question is a trace from an earlier stop.

A trace checks its own count. A line is one executed instruction only on the `normal` cpu core, so the cycle count `RUNSTATE` gives must have moved by the lines the file holds. That is why any other core is refused.

The debugger writes its log only in the emulator's working directory, so the file passes through there on its way to `dest`.

<details><summary>More on why</summary>

| in `trace` | what it holds |
|---|---|
| `path`, `bytes`, `shape` | the log, its size and its format |
| `set_path` | a file with one JSON line per executed address: `seg_off`, `addr` and `symbol` with `delta` where they can be worked out, `count`. Unavailable when it could not be written, which `note` says |
| `instructions`, `addresses`, `unplaced` | instructions executed, distinct addresses, addresses no symbol covers |
| `symbols` | the first rows, by address: `symbol`, `addr`, `addresses`, `instructions`, `first`, `last` |
| `symbols_total`, `truncated` | how many symbols ran, and whether `symbols` leaves some out |
| `closed` | on a refusal: whether the log was closed |

An interrupt breakpoint stops inside its `INT`, after the counter took it and before it ran, so a run it stops may count one more than it executed. The log writes each line before breakpoints are checked, so a trace started on a breakpoint's address stops there again with nothing executed.

The machine can close the log itself: the BIOS's power-on self test does, so a trace started right after a reset meets it. How each address gets its symbol is in [REFERENCE.md](../../REFERENCE.md#a-trace-says-which-routines-ran).

How a logged address becomes a linear one, and so gets its symbol:

- In real or virtual-8086 mode it is `CS` times 16 plus `EIP`. Otherwise it is the base of the selector in `CS` plus `EIP`.
- That selector counts only as a present code descriptor whose privilege is the one it requests, read from one `GDT` and `LDT` listing at the stop.
- A trace that starts and stops in real mode is read the real-mode way, even where it passed through protected mode.
- An address with no linear form gets no symbol, and counts in `unplaced`.

</details>

### Related tools

- [`run_for`](#run_for)
- [`symbols_load`](symbols.md#symbols_load)
- [`symbols_find`](symbols.md#symbols_find)
- [`build_check`](session.md#build_check)
- [`captures`](captures.md#captures)
- [`disassemble`](read.md#disassemble)

<details><summary>The contract your client receives</summary>

```text
Run `instructions` (1 to 3000000) with the debugger's CPU log on and come back
STOPPED with the log in a file, joined to symbols.

`shape`: `normal` (`LOG`), `short` (`LOGS`), `long` (`LOGL`) or `cs_ip` (`LOGC`). `dest`:
absolute or `~`-led, its directory there, the file not; empty is the next `trace-<n>.trace` in
captures. `seconds` bounds the wait for the log. Needs a stopped machine, a writable working
directory and `build_check`'s
`heavy_debug`; a dynamic core needs `start(flags=["-set", "cpu core=normal"])`.

Reply: `verdict`, the stop reply of `run_to`, `trace` (`path`, `instructions`, `addresses`,
`unplaced`, `set_path`, `symbols` (first 64)). Refused: `no_channel`,
`readback_refused`, `host_failed`.

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end trace -->

<!-- scry-reference:begin screen_wait -->
## `screen_wait`

Run until the screen shows a text, a mapped screen, a black palette or a change of screen, and stop there.

```text
screen_wait(text="", screen="", palette="", changed=false, every=0, on_breakpoint="", on_watch="",
    condition="", seconds=30.0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, right after `start`, with the game's screen map loaded.

Ask:

> Run until the game's play screen is up.

Call:

```text
screen_wait(screen="play", seconds=60)
```

Reply, 6 of 18 fields:

```json
{
  "summary": "screen_wait screen 'play': found after 2 frames",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "polls": 2,
  "screen": {"name": "play", "layer": "file"}
}
```

The map's `play` screen was not up at the call, which is `already: false`. It came up 2 frames later, and the machine stopped there.

<details><summary>The whole reply</summary>

```json
{
  "summary": "screen_wait screen 'play': found after 2 frames",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": 2,
  "sampled_every": 0,
  "screen": {"name": "play", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 2,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {
    "lines_total": 2,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1", "Bochs port E9h: BRICKS ready"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": "<volatile>"
}
```

</details>

### Arguments

- `text` (string, default `""`): Wait until this text is on the text screen: 1 to 132 characters of code page 437, matched exactly, case included, inside one row.
- `screen` (string, default `""`): Wait until this screen of the loaded screen map, the file naming a program's screens, is the one shown.
- `palette` (one of `""`, `"black"`, default `""`): `black` waits until every palette entry is black, which is how a fade ends.
- `changed` (boolean, default `false`): `true` waits until the screen map names a different screen from the one it named at the start. A frame it cannot name counts as in between.
- `every` (integer (>= 0, <= 600), default `0`): How many frames to run between two looks at the screen. Left at 0, every frame; a screen shown for fewer frames than this can be missed.
- `on_breakpoint` (string, default `""`): Look at the screen only at the end of a frame in which this breakpoint fired: its `ref`, as `declaration_list` lists it.
- `on_watch` (string, default `""`): The same for a watch: the `ref` of a `change` watch you set.
- `condition` (string, default `""`): Counts only the firings where this holds. Up to four terms joined by `&&`, each a register or a memory read (`b@ref`, `w@ref`, `d@ref`) compared with a hex value.
- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to keep looking, in real seconds, counted from the first look. Left out, 30.

### What comes back

- `verdict`: `TARGET` when what you waited for is on screen. `TIMEOUT` when the wait gave up, with a `note` and the machine stopped.
- `already`: `true` when it was on screen at the call, so the machine did not move.
- `predicate`: Which of `text`, `screen`, `palette` or `changed` was waited on.
- `polls`: How many frames ran; `sampled_every` repeats `every`.
- `point`: With `text`: where it was found, as `[column, row]`. `line` is that row's whole text.
- `screen`: The screen found, as `name` and `layer`. With `changed`, `started_on` is the screen it replaced.

<details><summary>All 29 reply fields</summary>

- `waited_on` (object)
- `firings` (integer)
- `frames_examined` (integer)
- `fired_line` (integer or object)
- `already` (boolean)
- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string)
- `e9` (object)
- `enrichment` (object)
- `entries` (integer)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `line` (string)
- `palette` (string)
- `pc` (string)
- `point` (array)
- `polls` (integer)
- `predicate` (string)
- `regs` (object)
- `retrace_pending` (boolean)
- `sampled_every` (integer)
- `screen` (object)
- `started_on` (string or object)
- `stop_seq` (integer)
- `text` (array)
- `verdict` (string)
- `waited_s` (number)
- `watches` (array)

</details>

### What it refuses

- None or several of `text`, `screen`, `palette` and `changed` (`bad_argument`).
- A screen the map does not name, or a breakpoint or watch you did not set (`unknown_ref`).
- `changed` with no screen map loaded (`needs_call`).
- A breakpoint or watch that never fired within `seconds`: no screen was looked at (`never_fired`).
- A stop nobody asked for that ends the wait early; its `cause` comes with it (`wait_stopped`).
- A screen that cannot be read, or a DOSBox-X whose debugger has no `RUNSTATE` command (`no_channel`).
- A machine that is running (`not_stopped`).

### Why it works this way

The wait runs the machine one frame at a time, to each vertical retrace, and looks at the screen there. Each look costs a stop and a read, so for a screen that is far away use `run_for` first.

`seconds` is counted from after the first read so that a short one still reaches the first frame; a frame read under way when it passes is finished. A wait that gives up never leaves the machine running: a `VRT` still running is interrupted where it stands.

If what you wait for is already on screen the reply comes at once and the machine does not move. Under `on_breakpoint` or `on_watch` the first firing is awaited even so. With `text`, a frame that is not in a text mode is no match.

<details><summary>More on why</summary>

- `waited_on` repeats what was waited on: its `kind`, its `ref`, and the `condition` if any.
- Under `on_breakpoint` or `on_watch`, `firings` and `frames_examined` (the frames looked at after a firing) replace `polls` and `sampled_every`, in refusals too.
- `fired_line` is unavailable here, with why: the debugger reports no screen line at a stop.
- `palette` and `entries` come with a black palette: the value asked for, and how many palette entries were read.
- On a `TIMEOUT`, `text` holds the rows of the last text screen read, and `retrace_pending` says whether a retrace stop is still armed.
- A `note` on a `TARGET` means a watch or an interrupt breakpoint is set whose stop the wait could have taken for a retrace.
- A refusal after the machine ran carries `polls` and `stop_seq`. `wait_stopped` adds `retrace_pending` and `text`.
- `enrichment` comes where `stop_seq` was due and the stop could not be read.

</details>

### Related tools

- [`screen_map_write`](read.md#screen_map_write)
- [`screen_view`](screen.md#screen_view)
- [`run_to`](#run_to)
- [`run_for`](#run_for)
- [`palette`](screen.md#palette)
- [`breakpoint_at`](breakpoints.md#breakpoint_at)

<details><summary>The contract your client receives</summary>

```text
Run the machine retrace by retrace until ONE predicate holds, and stop there.

Exactly one of: `text` (1 to 132 code page 437 characters, matched literally and
case-sensitive inside one row as `screen_view` reads it), `screen` (a name of the loaded
screen map, `screen_map_write`; the frame it names), `palette` (`black`: every DAC entry
black, which is how a fade ends), `changed` (the map names a screen other than the one it
named at the start; a frame it names nothing is a transition). None or several is
`bad_argument`.

`on_breakpoint` / `on_watch`: judge only at the retrace after a firing of that declared
breakpoint or `change` watch (its `ref` as `declaration_list` lists it), never sampling;
`condition` (up to 4 terms joined by `&&`, each a register of the stopped cpu or a memory read (`b@ref`, `w@ref`, `d@ref`), a comparison (`==`, `!=`, `<`, `<=`, `>`, `>=`) and a hex value (`0x` allowed)) filters the firings first. The first firing is awaited even
when the predicate already holds.

`every`: 0 judges every retrace; N judges every Nth, for a predicate whose read is a full
frame, and a screen that lasts fewer than N retraces is passed over. `seconds` bounds the
polls, counted from the opening read; the stop at the bound comes after it. Needs a stopped
machine and `RUNSTATE`. Already true: answered at once, the machine not moved. Each poll
costs a stop and a read, so `run_for` first for a distant screen.

Reply: `verdict` `TARGET` (`predicate`, `already`, `waited_s`, `polls`, `sampled_every`;
text adds `point` `[column, row]` and `line`, screen adds `screen`, palette adds `entries`) or
`TIMEOUT` (the same, with `retrace_pending`), `note`, the stop reply of `run_to` with its
`frame` (unless the predicate was already true); under `on_*`, `waited_on`, `firings`, `frames_examined` (the frames looked at after a firing) and `fired_line` in place of `polls` and `sampled_every`, and `changed` adds `screen` and
`started_on`. Refused: `bad_argument`,
`unknown_ref` (no such mapped screen or declared row), `needs_call` (`changed` with no map
loaded), `wait_stopped` (another declared breakpoint stopped it), `never_fired` (the row
never fired within `seconds`), `no_channel` (a screen it cannot read, or a build with no
`RUNSTATE`).

Reference: REFERENCE.md, Input and the screen.
```

</details>
<!-- scry-reference:end screen_wait -->

<!-- scry-reference:begin step -->
## `step`

Execute a few instructions, going into calls or over them.

```text
step(count=1, mode="into")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at `brick_hit`, where the `run_to` example above ends.

Ask:

> Execute two instructions and show me where the program is now.

Call:

```text
step(count=2)
```

Reply, 7 of 18 fields:

```json
{
  "summary": "step 2: 2 done, at 08DF:000002A9",
  "mode": "into",
  "instructions_completed": 2,
  "before": "08DF:000002A5",
  "after": "08DF:000002A9",
  "moved": true,
  "stalled": 0
}
```

Both instructions ran, from `08DF:000002A5` to `08DF:000002A9`. `stalled: 0` says neither of them left the address unchanged.

<details><summary>The whole reply</summary>

```json
{
  "summary": "step 2: 2 done, at 08DF:000002A9",
  "status": "ok",
  "mode": "into",
  "asked": 2,
  "moved": true,
  "stalled": 0,
  "before": "08DF:000002A5",
  "after": "08DF:000002A9",
  "instructions_completed": 2,
  "pc": "08DF:000002A9",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000700",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002a9",
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
    }
  ],
  "cause": "the stop `step` made after 2 steps, at 08DF:000002A9",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 4,
  "instruction": {
    "address": "08DF:000002A9",
    "bytes": "E81FFF",
    "text": "call 0x1cb",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 4
  }
}
```

</details>

### The two modes

| mode | what it does |
|---|---|
| `into` | Executes one instruction, and enters a call. |
| `over` | Runs a `CALL`, an `INT`, a `LOOP` or a `REP` to the next instruction as one step. |

### Arguments

- `count` (integer (>= 1, <= 64), default `1`): How many instructions to execute. Left out, one.
- `mode` (one of `"over"`, `"into"`, default `"into"`): `into` or `over`, as above.

### What comes back

- `instructions_completed`: How many instructions ran. Fewer than `asked` when an `over` did not come back and the remaining steps were not sent.
- `mode`: The `mode` the steps ran in.
- `before`: Where the machine was before the steps, as `SEG:OFF`; `after` is where it is now.
- `moved`: `false` when no step changed the address.
- `stalled`: How many steps left the address unchanged: an iteration of a `rep`, a jump to itself or a halt.

<details><summary>All 18 reply fields</summary>

- `after` (string)
- `asked` (integer)
- `cause` (string)
- `regpoint_hit` (object)
- `before` (string)
- `cpu_mode` (string or object)
- `e9` (object)
- `enrichment` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `instructions_completed` (integer)
- `mode` (string)
- `moved` (boolean)
- `pc` (string)
- `regs` (object)
- `stalled` (integer)
- `stop_seq` (integer)
- `watches` (array)

</details>

### What it refuses

- `over` on a DOSBox-X whose debugger has no `RUNSTATE` command (`no_channel`).
- A machine that is running (`not_stopped`).

### Why it works this way

`into` is the debugger's own `STEPIN`. `over` is built from several commands: a breakpoint on the next instruction, a run, a wait for the stop, and the breakpoint removed. That wait is why `over` needs `RUNSTATE`.

An `over` that has not come back within its time limit is interrupted where it stands, and the remaining steps are not sent. A machine that could not be stopped is left running, which `session.running` says. `note` appears when the step's own breakpoint could not be confirmed removed.

`stalled` is counted step by step, because comparing only the two ends would read a two-instruction loop as a step that went nowhere. The largest `count` limits cost, not risk: past it the tool to use is `run_to`.

### Related tools

- [`run_to`](#run_to)
- [`run_for`](#run_for)
- [`stop`](#stop)
- [`disassemble`](read.md#disassemble)
- [`registers`](read.md#registers)

<details><summary>The contract your client receives</summary>

```text
`count` instructions, each read back; `mode` `into` (the debugger's `STEPIN`) or `over` (a
CALL, INT, LOOP or REP run to the next instruction, which needs `RUNSTATE`). Needs the machine
stopped.

Reply: `mode`, `asked`, `before`, `after`, `instructions_completed`, `moved`, `stalled`
(CS:EIP unchanged after a step), `note` (a step over's own breakpoint not confirmed removed),
and the stop reply; an `over` that does not come back within its bound is stopped where it
stands, and no later step is sent. For longer runs `run_to`.
```

</details>
<!-- scry-reference:end step -->

<!-- scry-reference:begin resume -->
## `resume`

Let the machine run, either with no deadline or waiting a while for it to stop.

```text
resume(seconds=0.0, detail=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped inside `brick_hit`, with a `change` watch set on `score`.

Ask:

> Let the game run until the score changes, for a minute at most.

Call:

```text
resume(seconds=60)
```

Reply, 5 of 15 fields:

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002C8",
  "verdict": "OTHER_STOP",
  "pc": "08DF:000002C8",
  "cpu_mode": "real",
  "frame": 36
}
```

`OTHER_STOP` says something stopped the machine before the minute ran out: here at `08DF:000002C8`, where `cause` says no declared breakpoint is there and the debugger does not name the row that stopped it.

<details><summary>The whole reply</summary>

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
    "EIP": "0x000002c8",
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
  "cause": "no declared code breakpoint at 08DF:000002C8, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 6,
  "instruction": {
    "address": "08DF:000002C8",
    "bytes": "F71EDB05",
    "text": "neg word ptr [0x5db]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 35
  }
}
```

</details>

### Arguments

- `seconds` (number (>= 0, <= 600.0), default `0.0`): How long to wait for a stop, in real seconds. Left at 0, the call returns at once and the machine keeps running.
- `detail` (boolean, default `false`): `true` adds `output`, the end of what the debugger printed for its `RUN` command. Left out, `omitted` names the fields not sent.

### What comes back

- `verdict`: With `seconds`: `OTHER_STOP`, a breakpoint or a watch stopped the machine, and the stop's readings follow; `TIMEOUT`, nothing did, and it is left running with a `note`.
- `waited_s`: With `seconds`: how long the call waited.
- `output`: With `detail`: the end of the debugger's own text. `output_chars` is its whole length and `clipped` says whether it was cut.
- `e9`: With a stop: the lines the program wrote to port E9, the emulator's debug output port, since the previous stop. They come with or without `detail`.

<details><summary>All 16 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `clipped` (boolean)
- `cpu_mode` (string or object)
- `e9` (object)
- `enrichment` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string)
- `regs` (object)
- `output` (string)
- `output_chars` (integer)
- `stop_seq` (integer)
- `verdict` (string)
- `waited_s` (number)
- `watches` (array)

</details>

### What it refuses

- A machine that is already running (`not_stopped`).
- `seconds` above 0 on a DOSBox-X whose debugger has no `RUNSTATE` command (`no_channel`).

### Why it works this way

A machine that is already running is refused, because the debugger's `RUN` does nothing there and an `ok` would read as if it had been resumed. No breakpoint has to be set first: `stop` brings a running machine back.

With `seconds` at 0 the call returns straight after resuming and does not look for a stop, so a machine that stops at once is found by the next call. With `seconds`, such a stop is this call's `OTHER_STOP`, and the call reports progress while it waits.

A conf whose autoexec runs `boot` stops once more on its own. `boot` restarts the machine at the boot sector, `0000:7C00`, and the break at every start that `start` asks the debugger for fires there too. `cause` names it, and a second `resume` lets the operating system run.

<details><summary>More on why</summary>

On a DOSBox-X whose debugger has no `RUNSTATE` command no reply can see that stop at the boot sector. `stop` brings the machine back from wherever it is, and its position shows it is still there.

</details>

### Related tools

- [`stop`](#stop)
- [`wait`](#wait)
- [`run_to`](#run_to)
- [`run_for`](#run_for)
- [`breakpoint_at`](breakpoints.md#breakpoint_at)
- [`status`](session.md#status)

<details><summary>The contract your client receives</summary>

```text
Let the machine run. `seconds` 0 (the default) returns at once with no deadline; a bound
up to 600 waits for a stop and, if none comes, leaves it running. Needs a stopped
machine. The guest's E9 lines come with the stop it waited for, with or without `detail`.

Reply: with a bound, `waited_s` and `verdict` (`OTHER_STOP` with the stop reply of `run_to`;
`TIMEOUT`, left running, with a `note`). `output` (with `detail=True`: the last
2000 characters the debugger itself printed for `RUN`; else `omitted`).

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end resume -->

<!-- scry-reference:begin wait -->
## `wait`

Let a running program play for a while and see where it is after, without stopping it.

```text
wait(seconds=30.0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, running after a `resume`.

Ask:

> Let the game play for one more second without stopping it.

Call:

```text
wait(seconds=1)
```

Reply, 2 of 4 fields:

```json
{
  "status": "ok",
  "note": "the machine is still running after 1 s; a deliberate wait th ... (100 characters)"
}
```

The second ran out with the game still running. That is the answer a wait is for, so `status` is `ok`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "waited_s": "<volatile>",
  "note": "the machine is still running after 1 s; a deliberate wait that expires is this answer, not a failure"
}
```

</details>

### Arguments

- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to let it run, in real seconds. Left out, 30.

### What comes back

- `waited_s`: How long the call waited.
- `verdict`: Only when the machine stopped during the wait: `OTHER_STOP`, a breakpoint or a watch stopped it, and the stop's readings follow.

<details><summary>All 13 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `e9` (object)
- `enrichment` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `pc` (string or object)
- `regs` (object)
- `stop_seq` (integer)
- `verdict` (string)
- `waited_s` (number)
- `watches` (array)

</details>

### What it refuses

- A machine that is stopped: `resume` it first (`not_running`).
- A DOSBox-X whose debugger has no `RUNSTATE` command (`no_channel`).

### Why it works this way

The wait is deliberate, so running out of `seconds` is the answer and not a failure: the reply is `ok`, with a `note` that the machine is still running. `wait` neither resumes nor stops. `resume` lets a stopped machine run, and `stop` brings a running one back.

### Related tools

- [`resume`](#resume)
- [`stop`](#stop)
- [`log_wait`](machine.md#log_wait)
- [`screen_wait`](#screen_wait)
- [`status`](session.md#status)

<details><summary>The contract your client receives</summary>

```text
Let a running guest play for `seconds` and answer where it is after, without releasing or
stopping it. The wait is deliberate, so its expiry is the answer, never a failure; if the
machine stops on its own during the wait (a breakpoint), the stop reply comes back.

Reply: `waited_s`, and with a stop during the wait `verdict` `OTHER_STOP` with the stop reply
of `run_to`; else a `note` that the machine is still running. Refused (`not_running`) when the
machine is stopped: `wait` lets a running guest play, `resume` releases a stopped one.

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end wait -->

<!-- scry-reference:begin stop -->
## `stop`

Stop a running machine where it is and read where it stopped.

```text
stop(until="")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, running after a `resume`.

Ask:

> Stop the game where it is.

Call:

```text
stop()
```

Reply, 3 of 13 fields:

```json
{
  "interrupted": true,
  "via": "break",
  "cpu_mode": "real"
}
```

`interrupted: true` means this call stopped the machine, through the debugger's own interrupt, which is `via: break`. It landed in real mode; where exactly differs from run to run.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "interrupted": true,
  "via": "break",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": "<volatile>",
  "instruction": "<volatile>"
}
```

</details>

### Arguments

- `until` (one of `""`, `"protected"`, default `""`): `protected` goes on resuming and interrupting, in short runs, until the machine stops in protected mode. Left empty, it stops where it is.

### What comes back

- `interrupted`: `true` when this call stopped the machine, with the stop's readings. `false` when it was already stopped, with a `note`.
- `via`: `break` when the stop came from this call's own interrupt.
- `runs_to_protected`: With `until`: how many short runs it took. A `note` says so when none ended in protected mode.
- `cpu_mode`: The cpu mode the machine stopped in: `real`, `protected`, `paged` or `VM86`.

<details><summary>All 13 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `e9` (object)
- `frame` (integer or object)
- `instruction` (StopInstruction)
- `interrupted` (boolean)
- `pc` (string)
- `regs` (object)
- `runs_to_protected` (integer)
- `stop_seq` (integer)
- `via` (string)
- `watches` (array)

</details>

### What it refuses

- A machine that did not report stopped after the interrupt: ask again (`not_settled`).

### Why it works this way

The interrupt goes through the emulator's own debugger connection, the conf's `[dosbox] mcp_server` setting. It needs no window and no menu, and takes nothing from your screen and keyboard.

The machine stops wherever it is, often outside your program. A DJGPP program spends part of every frame in real-mode BIOS handlers, at `F000:xxxx`, where no symbol of a protected-mode table can be given an address. A breakpoint in your code, set at a stop inside it before resuming, brings the machine back into it, and so does `until="protected"`.

<details><summary>More on why</summary>

At a stop outside the program, a breakpoint on a symbol reads `unarmable` when the symbol is in the table and its address cannot be worked out at this instant. It reads `unresolved` when the table does not hold the name. That is a fact about the table, since `symbols_load` adds each table to the ones before.

A `stop` on a machine already stopped answers with that stop as `last_stop`. If `stop` fails as well, `close` then `start`.

</details>

### Related tools

- [`resume`](#resume)
- [`wait`](#wait)
- [`run_for`](#run_for)
- [`status`](session.md#status)
- [`close`](session.md#close)
- [`start`](session.md#start)

<details><summary>The contract your client receives</summary>

```text
Bring a running guest back to the debugger and survey the stop, headless or windowed.

`until="protected"` is for a stop that landed in real mode (a DPMI client's interrupt, in
the BIOS), this call's own or one already held: the guest is let run again in short runs, a
`BREAK` ending each, until one stops in protected mode, 256 runs at most;
with `start(symbols=)`'s DJGPP table held, until one stops in the program's own 32-bit code,
never the DPMI host's 16-bit code. The machine has then moved on, so what the earlier stop
read (screen, memory, registers) no longer describes it; a stop already where the runs would
end is answered as it stands. `cpu_mode` says where it ended.

Reply: `interrupted` (`true` with the stop reply and `via: "break"`; `false` when already
stopped, with a `note`), `runs_to_protected` (with `until`), a `note` if it did not arrive.
INVALID `not_settled`: after the `BREAK`, `RUNSTATE` did not say stopped; ask again.

Reference: REFERENCE.md, Running and stopping.
```

</details>
<!-- scry-reference:end stop -->
