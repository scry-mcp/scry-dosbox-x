# The Session tools

A session is one DOSBox-X process, parked at the debugger by `start` and ended by `close`. The path rule, the binary ladder and the presence indicator are in [REFERENCE.md, The session](../../REFERENCE.md#the-session).

<!-- scry-reference:begin build_check -->
## `build_check`

*Check the build*

```text
build_check(binary="")
```

Whether a DOSBox-X binary resolves and carries the debugger. Run before `start`; it
refuses while a session is live. `binary`: omitted, `DOSBOX_X_BINARY`, else the PATH's
`dosbox-x`; a named build that fails is refused.

Reply: `binary`, `binary_origin`, `version`, `debugger`, `heavy_debug` (`trace` and a freeze
watch need it), `debugger_commands` (which of `RUNSTATE`, `STEPIN`, `SAVESTATE`, `LOADSTATE`, `PRESENCE`, `VGAMEMDUMP`, `BPIF`, `CAPTURE`, `TAP`, `PORTINFO`, `DOSTRACE` the build's debugger has;
omitted when none).

| argument | type | default |
|---|---|---|
| `binary` | string | `""` |

| reply field | type |
|---|---|
| `binary` | string |
| `binary_origin` | string |
| `debugger` | boolean |
| `debugger_commands` | array |
| `heavy_debug` | boolean |
| `tools` | array |
| `version` | string or object |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "build_check: ~/.local/state/dosbox-x-builds/scry/dosbox-x (DOSBOX_X_BINARY), debugger True, heavy_debug True",
  "status": "ok",
  "binary": "~/.local/state/dosbox-x-builds/scry/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
  "debugger": true,
  "heavy_debug": true,
  "debugger_commands": [
    "RUNSTATE",
    "STEPIN",
    "SAVESTATE",
    "LOADSTATE",
    "PRESENCE",
    "VGAMEMDUMP",
    "... 5 more"
  ],
  "tools": [
    "a20",
    "audio_compare",
    "audio_record",
    "breakpoint_at",
    "breakpoint_interrupt",
    "build_check",
    "... 53 more"
  ]
}
```
<!-- scry-reference:end build_check -->

A build without the debugger starts fine and then hangs `start` until its timeout. The debugger and its optional commands (`debugger_commands`) are read off the binary itself, never asked of it: `-helpdebug` lists `-break-start` in a build configured without the debugger too, and on Windows it prints to no stream and never exits. It refuses while a session is live because its version probe starts the emulator, which a build that does not know the option runs until the probe's bound.

**`heavy_debug: false` is an answer, not a failure**: it is `trace` and a freeze watch that refuse such a build. The tool is about the build, never about a reading. `binary_origin` is `argument`, `DOSBOX_X_BINARY` or `PATH`; `version` is the build's first line, or `{available: false, why}`.

<!-- scry-reference:begin start -->
## `start`

*Start a DOSBox-X session*

```text
start(conf, cwd, session_seconds, shared=false, flags=null, break_on_int3=false, program="", logfile="", capture_video=false, captures_dir="", plan=null, settle_seconds=null, input_port=0, state_dir="", binary="", background=null, presence=true, dos_calls=false, log_categories=null, guest_files=null, symbols="", base_from="program")
```

Open one live DOSBox-X session from your conf, parked at the debugger.

Paths are absolute or `~`-led. `session_seconds`: the lifetime. `shared`: watched, in a
window; false, headless. `flags`: argv tokens, a `-set` value one token. `logfile`: the
guest's E9 channel, for `log`, `log_wait`, `drive`. `program` runs after autoexec;
`capture_video` records it. `plan` runs as `perform` does, each wait bounded by
`settle_seconds` (default 30). `input_port`: COM1's TCP port, 0 a free one.
`state_dir`: where `state_write` saves; empty, under `cwd`. `dos_calls`: record every
INT 21h for `log(channel="dos")`. `log_categories`: `[log]` category to level, into
`logfile`. `guest_files`: host files the guest should leave, read by `guest_file` and
`close`. `symbols`: a table `symbols_load` reads, judged here and placed at the first stop
where DOS holds the program its stem names (`<stem>.exe`); `base_from` `program` (its load
segment) or a register, as `symbols_load` measures one, at a protected-mode stop. That stop's
reply says `symbols_placed` once (`placed`, `path`, `load_segment`, `base`, `loaded`; a
placement refused: `placed: false`, `code`, `why`); a later `symbols_load` replaces it.

Refused: a live session, a bad path or `symbols` table, `session_seconds` out of range,
`capture_video` without `program`, an `input_port` other than 0 outside
1024-65535, `log_categories` without `logfile`, `dos_calls` on a build
with no `DOSTRACE`, `guest_files` naming a directory, one file twice or more than
16, or busy.

Reply: `pid`, `stub`, `input_port`, `declarations` (`rearm`), `dos_calls`, `log_categories`,
`guest_files` (each when asked for: the trace's path, the categories set, each file as it was
before the boot), `symbols` (`held`, `base_from`); with `plan`, these facts sit under `start`
beside the plan's account. `note` when the conf or `flags` select a dynamic cpu core, which
can pass over code breakpoints: start on `flags=["-set", "cpu core=normal"]`.

Reference: REFERENCE.md, The session.

| argument | type | default |
|---|---|---|
| `conf` | string | required |
| `cwd` | string | required |
| `session_seconds` | integer (>= 1, <= 14400) | required |
| `shared` | boolean | `false` |
| `flags` | array of string or null | `null` |
| `break_on_int3` | boolean | `false` |
| `program` | string | `""` |
| `logfile` | string | `""` |
| `capture_video` | boolean | `false` |
| `captures_dir` | string | `""` |
| `plan` | array of object or null | `null` |
| `settle_seconds` | number (>= 0, <= 600.0) or null | `null` |
| `input_port` | integer (>= 0, <= 65535) | `0` |
| `state_dir` | string | `""` |
| `binary` | string | `""` |
| `background` | boolean or null | `null` |
| `presence` | boolean | `true` |
| `dos_calls` | boolean | `false` |
| `log_categories` | object or null | `null` |
| `guest_files` | array of string or null | `null` |
| `symbols` | string | `""` |
| `base_from` | string (matching `^([pP][rR][oO][gG][rR][aA][mM]\|[cC][sS]\|[dD][sS]\|[eE][sS]\|[sS][sS]\|[fF][sS]\|[gG][sS])$`) | `"program"` |

- `presence`: Draw an edge around the emulator's window while this session is open: dim while idle, bright while a call runs the machine. No capture of this server carries it.

| reply field | type |
|---|---|
| `errors` | array |
| `failed` | object |
| `field` | string |
| `got` | any |
| `ran_path` | string or object |
| `recorded` | any |
| `replies_path` | string or object |
| `steps_total` | integer |
| `still_running` | boolean |
| `stopped` | object |
| `stops` | object |
| `truncated` | boolean |
| `verdict` | string |
| `failed_at` | integer or object |
| `held` | integer |
| `ran` | array |
| `steps_completed` | integer |
| `argv` | array |
| `background` | boolean |
| `binary` | string |
| `binary_origin` | string |
| `bound_s` | number |
| `captures` | string |
| `conf` | string |
| `conf_changed_on_disk` | boolean or object |
| `conf_digest` | string |
| `debugger_commands` | array |
| `declarations` | object |
| `dos_calls` | string |
| `elapsed_s` | number |
| `guest_files` | array |
| `input_port` | integer or object |
| `log_categories` | object |
| `operations` | array |
| `pid` | integer |
| `presence` | boolean or object |
| `ready_after_s` | number |
| `rearm_refused` | string |
| `shared` | boolean |
| `start` | object |
| `state_dir` | string |
| `stub` | string |
| `output_bytes_dropped` | integer |
| `symbols` | object |
| `version` | string or object |
| `watched` | boolean |

Example, from a live run:

```json
{
  "conf": "$TMPDIR/dosbox-x-live-job-vri600ji/A/tests/guest/probe.conf",
  "cwd": "$TMPDIR/dosbox-x-live-job-vri600ji/A/tests/guest",
  "session_seconds": 1200,
  "logfile": "$TMPDIR/dosbox-x-live-matrix-c7eda17a48fc/jobs-scratch/A/n985.log",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-c7eda17a48fc/jobs-scratch/A/n986-save"
}
```

```json
{
  "summary": "start probe.conf: headless on ~/.local/state/dosbox-x-builds/scry/dosbox-x (DOSBOX_X_BINARY), debugger answered after 0.108s",
  "status": "ok",
  "pid": 6399,
  "conf": "$TMPDIR/dosbox-x-live-job-vri600ji/A/tests/guest/probe.conf",
  "conf_digest": "78bdc38f360b9b4a",
  "bound_s": 1200,
  "elapsed_s": 0.3,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-c7eda17a48fc/jobs-scratch/A/n986-save",
  "ready_after_s": 0.108,
  "argv": [
    "~/.local/state/dosbox-x-builds/scry/dosbox-x",
    "-conf",
    "$TMPDIR/dosbox-x-live-job-vri600ji/A/tests/guest/probe.conf",
    "-time-limit",
    "1200",
    "-break-start",
    "... 20 more"
  ],
  "binary": "~/.local/state/dosbox-x-builds/scry/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
  "debugger_commands": [
    "BPIF",
    "CAPTURE",
    "DOSTRACE",
    "LOADSTATE",
    "PORTINFO",
    "PRESENCE",
    "... 5 more"
  ],
  "stub": "/path/to/scry-dosbox-x/guest/SCRY.COM",
  "input_port": 58293,
  "background": true,
  "presence": {
    "available": false,
    "why": "a session started without `shared` has no window to draw on"
  },
  "declarations": {
    "rearm": {
      "rearmed": [],
      "stale": [],
      "unresolved": [],
      "ambiguous": [],
      "unarmable": []
    }
  }
}
```
<!-- scry-reference:end start -->

**`shared` is explicit, with no detection behind it.** Headless uses `videodriver=dummy`, not `SDL_VIDEODRIVER` and not `-silent`, which exits after `AUTOEXEC.BAT` and cannot host a session.

**`session_seconds` is a hard bound** because a DOSBox-X held at its debugger never reaches its own time limit. The emulator's `-time-limit` counts emulated time, which a machine held at the debugger never advances, so a guardian (`scry-dosbox-x-guardian` in the process list) also keeps the host's clock, ending the emulator a few seconds past the bound or within one poll of this server dying.

**The window, and the host's own arguments.** A watched start opens DOSBox-X's window as the conf sizes it (`windowresolution`, with `output=opengl` to scale it), on any host and with nothing to set. `SCRY_EMULATOR_ARGS` in the server's environment holds the host's own DOSBox-X arguments, one token a line so a `-set` value keeps its space (`-set`, then `sdl display=1`). They go after this server's own on every watched start, so which display the window opens on is the host's to say; only the caller's `flags`, which come last, could override them. A headless start opens no window and takes none of them (MAME's window opens either way, so MAME takes them on every start). A glued or shredded `-set` there refuses the start `host_failed` before anything else happens, for the same reasons as in `flags`.

**`flags` come after this server's defaults**, so a `-set` for the same key wins, except the ones a named argument sets (`-time-limit`, `sdl videodriver`, `log logfile`, the conf, the program...): refused naming the argument, because after ours the flag would quietly undo it.

**`break_on_int3`** has two limits that are the debugger's: at the reset vector there is no row, so a trap faults; and the first instruction after a `resume` runs unchecked, so a trap written at the stop itself is stepped over.

**`binary` and `background`**: `binary` omitted is `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`, as `build_check` resolves it. `background` `true` starts behind, `false` in front, omitted by `shared`.

**`flags` are argv tokens, so a `-set` value with spaces is one token**; a glued `-set` is refused because DOSBox-X hangs on it, a shredded one because DOSBox-X ignores it at rc 0 and the setting would silently not apply.

**`program` loads the stub itself when the conf's autoexec does not run it**, which is why the autoexec must not `exit` before `program` runs.

**`state_dir`** is what `state_write(method="save")` writes to; empty, `save` under `cwd`.

**Also refused before anything starts**: a missing conf, `cwd` or `logfile` directory, an unresolved binary, a glued or shredded `-set`, and no drive free for the stub. `captures_dir` and `state_dir` are created with their parents. The reply also carries `shared`, `ready_after_s`, `argv`, `binary`, `binary_origin`, `version`, `background`, `presence` and `rearm_refused` (why, when stored raw breakpoints could not re-arm).

<!-- scry-reference:begin status -->
## `status`

*Session status*

```text
status()
```

What the session is right now. It records a stop no tool has reported
(`stopped_on_its_own`) and applies what was queued while the guest ran
(`applied_on_stop`).

Reply: `last_stop` (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`), `pending` (`arm` refs, a
`disarm` count, `symbols_load`, `base_remeasure`) and `presence`; with a session also `pid`,
`conf`, `conf_digest`, `conf_changed_on_disk`, `watched`, `bound_s`, `elapsed_s`,
`output_bytes_dropped`, `captures`, `state_dir`, `declarations`, `pc` and `cpu_mode`.
`session` carries `alive`, `running`, `altered` and each alarm while it holds.

Reference: REFERENCE.md, What every reply carries.

Takes no argument.

| reply field | type |
|---|---|
| `bound_s` | number |
| `captures` | string |
| `conf` | string |
| `conf_changed_on_disk` | boolean or object |
| `conf_digest` | string |
| `cpu_mode` | string or object |
| `declarations` | object |
| `elapsed_s` | number |
| `pc` | string or object |
| `pending` | object |
| `pid` | integer |
| `presence` | boolean or object |
| `state_dir` | string |
| `output_bytes_dropped` | integer |
| `watched` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "status: no session",
  "status": "ok",
  "last_stop": {
    "available": false,
    "why": "this session has not stopped yet"
  },
  "pending": {
    "arm": [],
    "disarm": 0,
    "symbols_load": false,
    "base_remeasure": false
  },
  "presence": false
}
```
<!-- scry-reference:end status -->

**The alarms** are `conf_changed_on_disk` (the file changed since start; `false` also if gone), and `output_bytes_dropped` (the emulator's output overflowed what the server keeps). They ride in `session` only while they hold.

**`pc` is read from the debugger at a stop**, so it is unavailable while the guest runs; `cpu_mode` is `real`, `protected`, `paged` or `VM86`. `last_stop` is unavailable with no session or a cut survey. `presence` is `true` drawn, `false` off or no session, or why not. `declarations` is this server's own count.

<!-- scry-reference:begin close -->
## `close`

*Close the session*

```text
close(detail=false)
```

End the session deliberately rather than waiting for its bound.

Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid` (with a session),
`stdout_tail` and `errorlog_tail` when the end was not a clean `quit`, or with `detail=True`.
`exit_code`, with a session, is an integer or unavailable with its `why`; `note` when the
output was not read to its end. `guest_files`: each file `start` named, with `guest_file`'s
`state`. `session` is the block as it is after the close (`alive` and `running` false).

| argument | type | default |
|---|---|---|
| `detail` | boolean | `false` |

| reply field | type |
|---|---|
| `bound_s` | number |
| `captures` | string |
| `closed` | boolean |
| `conf` | string |
| `conf_changed_on_disk` | boolean or object |
| `conf_digest` | string |
| `elapsed_s` | number |
| `ended_by` | string |
| `errorlog_tail` | string or object |
| `guest_files` | array |
| `pid` | integer |
| `state_dir` | string |
| `stdout_tail` | string |
| `output_bytes_dropped` | integer |
| `watched` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "close: no session",
  "status": "ok",
  "closed": false,
  "ended_by": "none",
  "note": "there was no session to close"
}
```
<!-- scry-reference:end close -->

**The `ended_by` values**: `quit` is the emulator leaving on the first signal, which is what a session launched here does, program loaded or not, because `start` turns the quit warning off; `killed` is a conf that puts the warning back or a wedged guest, ended by SIGKILL, and every close on Windows, which has no signal to ask with and terminates the process; `died` is already exited when called; `none` is nothing to close. **`exit_code`** is unavailable when SIGKILLed and still not reaped, since an emulator may still be on the machine.

**The `session` block is the session after the close**: `alive` and `running` false and `altered` false, as with no session at all.

**`note`** says how the reader of the emulator's output ended when that was not at the end of its output: it outlived the close, or a read failed, so the tails may be short. **The reply also carries** what the process was (`status`'s rows, `pid` first), read before the end, so `pid` is the process this call ended.
