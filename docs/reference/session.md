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
watch need it), `debugger_commands` (which of `RUNSTATE`, `STEPIN`, `SAVESTATE`, `LOADSTATE`, `PRESENCE`, `VGAMEMDUMP`, `BPIF`, `CAPTURE`, `TAP`, `PORTINFO`, `DOSTRACE`, `PIC`, `A20`, `MEMDUMPLIN` the build's debugger has;
omitted when none), `debugger_commands_missing` (each one it lacks, with the tools that
command disables; omitted when none is missing).

| argument | type | default |
|---|---|---|
| `binary` | string | `""` |

| reply field | type |
|---|---|
| `binary` | string |
| `binary_origin` | string |
| `debugger` | boolean |
| `debugger_commands` | array |
| `debugger_commands_missing` | array |
| `heavy_debug` | boolean |
| `tools` | array |
| `version` | string or object |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "build_check: /path/to/dosbox-x (DOSBOX_X_BINARY), debugger True, heavy_debug True",
  "status": "ok",
  "binary": "/path/to/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "<volatile>",
  "debugger": true,
  "heavy_debug": true,
  "debugger_commands": ["RUNSTATE", "STEPIN", "SAVESTATE", "LOADSTATE", "PRESENCE", "VGAMEMDUMP", "... 7 more"],
  "tools": ["a20", "audio_compare", "audio_record", "breakpoint_at", "breakpoint_interrupt", "build_check", "... 53 more"]
}
```
<!-- scry-reference:end build_check -->

A build without the debugger starts fine and then hangs `start` until its timeout. The debugger and its optional commands (`debugger_commands`) are read off the binary itself, never asked of it: `-helpdebug` lists `-break-start` in a build configured without the debugger too, and on Windows it prints to no stream and never exits. It refuses while a session is live because its version probe starts the emulator, which a build that does not know the option runs until the probe's bound.

**`heavy_debug: false` is an answer, not a failure**: it is `trace` and a freeze watch that refuse such a build. The tool is about the build, never about a reading. `binary_origin` is `argument`, `DOSBOX_X_BINARY` or `PATH`; `version` is the build's first line, or `{available: false, why}`.

<!-- scry-reference:begin start -->
## `start`

*Start a DOSBox-X session*

```text
start(conf, cwd, session_seconds, shared=false, display=null, fullscreen=null, size=null, flags=null, break_on_int3=false, program="", logfile="", capture_video=false, captures_dir="", plan=null, settle_seconds=null, input_port=0, state_dir="", binary="", background=null, presence=true, dos_calls=false, log_categories=null, guest_files=null, symbols="", base_from="program")
```

Open one live DOSBox-X session from your conf, parked at the debugger. Somebody watching
through a stream (Moonlight) needs `shared=true` and `fullscreen=true`: a pointer does not
map inside a window.

Paths are absolute or `~`-led. `cwd`: where the conf's relative paths resolve.
`session_seconds`: the lifetime, no default. `shared`: watched, in a window; false, headless.
`display`: the OS's display index for the window, 0 (the main display) when omitted;
`fullscreen`: the window fills it; `size`: `WIDTHxHEIGHT` of the window in the host's unit,
else the largest 4:3 window the display's usable area holds. All three need `shared=true` and
are refused otherwise; `size` is also refused beside `fullscreen`, beyond the usable area
(naming it) and under an `sdl output` that ignores it; a `display` past the host's count is
refused naming the count. The server waits for the window to be listed on that display and
answers `window`; `window` judges the size once the guest runs.
`flags`: argv tokens, a `-set` value one token. `logfile`: the guest's E9 channel, for `log`,
`log_wait`, `drive`. `program` runs after autoexec; `capture_video` records it. `plan` runs
as `perform` does, each wait bounded by `settle_seconds` (default 30). `input_port`:
COM1's TCP port, 0 a free one.
`state_dir`: where `state_write` saves; empty, the session's scratch (gone at `close`).
`dos_calls`: record every INT 21h for `log(channel="dos")`, up to the build's row cap; the
server holds the newest 50000 calls it has read, `n` staying the file's number.
`log_categories`: `[log]` category to level, into `logfile`. `guest_files`: host files the
guest should leave, read by `guest_file` and `close`. `symbols`: a table `symbols_load`
reads, judged here and placed at the first stop where DOS holds the program its stem names
(`<stem>.exe`); `base_from` `program` (its load segment) or a register, as `symbols_load`
measures one, at a protected-mode stop. That stop's reply says `symbols_placed` once
(`placed`, `path`, `load_segment`, `base`, `loaded`; a placement refused: `placed: false`,
`code`, `why`); a later `symbols_load` replaces it.

Refused: a live session, a window that never appears on the asked display
(`window_not_visible`, the session left live to `window` or `close`), `flags` setting what
`display`, `fullscreen` or `size` own, `fullscreen` on `sdl output=surface` (it switches the
display's video mode and leaves the window off screen), `fullscreen` on a display other than 0
on macOS (a halted start never reaches full screen there), a bad path or `symbols` table,
`session_seconds` out of range, `capture_video` without `program`, an `input_port` other than
0 outside 1024-65535, `log_categories` without `logfile`, `dos_calls`
on a build with no `DOSTRACE`, `guest_files` naming a directory, one file twice or more than
16, or busy.

Reply: `pid`, `stub`, `window` (`display`, `bounds`, `onscreen`, `front`, `fullscreen`, with
`shared`), `input_port`, `declarations` (`rearm`), `dos_calls`, `log_categories`,
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
| `display` | integer or null | `null` |
| `fullscreen` | boolean or null | `null` |
| `size` | string or null | `null` |
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
| `activation` | string |
| `asked_display` | integer |
| `seen` | object |
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
| `window` | object |

Example, from a live run:

```json
{
  "conf": "$TMPDIR/dosbox-x-live-job-<run>/A/tests/guest/probe.conf",
  "cwd": "$TMPDIR/dosbox-x-live-job-<run>/A/tests/guest",
  "session_seconds": 1200,
  "logfile": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n985.log",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n986-save"
}
```

```json
{
  "summary": "start probe.conf: headless on /path/to/dosbox-x (DOSBOX_X_BINARY), debugger answered after 0.187s",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "$TMPDIR/dosbox-x-live-job-<run>/A/tests/guest/probe.conf",
  "conf_digest": "78bdc38f360b9b4a",
  "bound_s": 1200,
  "elapsed_s": 0.5,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-<run>/jobs-scratch/A/n986-save",
  "ready_after_s": 0.187,
  "argv": ["/path/to/dosbox-x", "-conf", "$TMPDIR/dosbox-x-live-job-<run>/A/tests/guest/probe.conf", "-time-limit", "1200", "-break-start", "... 20 more"],
  "binary": "/path/to/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "<volatile>",
  "debugger_commands": ["A20", "BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "PIC", "... 7 more"],
  "stub": "/path/to/scry-dosbox-x/src/scry_dosbox_x/guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": true,
  "presence": {"available": false, "why": "a session started without `shared` has no window to draw on"},
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  }
}
```
<!-- scry-reference:end start -->

**`shared` is explicit, with no detection behind it.** Headless uses `videodriver=dummy`, not `SDL_VIDEODRIVER` and not `-silent`, which exits after `AUTOEXEC.BAT` and cannot host a session.

**`session_seconds` is a hard bound** because a DOSBox-X held at its debugger never reaches its own time limit. The emulator's `-time-limit` counts emulated time, which a machine held at the debugger never advances, so a guardian (`scry-dosbox-x-guardian` in the process list) also keeps the host's clock, ending the emulator a few seconds past the bound or within one poll of this server dying.

**The window.** Three situations, one combination of arguments each:

| Situation | `start` | Window |
|---|---|---|
| No window to lose focus to | `shared=false` (the default) | none; `window` refuses it as `no_channel` |
| A window nobody watches, kept behind | `shared=true`, `background=true` | placed on the display, behind the caller's application |
| A window somebody tests | `shared=true`, with `display` and `size` or `fullscreen`, `background=false` | placed on the display, in front, proved in the host's window list |

A watched start opens DOSBox-X's window on the display `display` names (the OS's index, 0 the main display and the default), placing a windowed run 40 px inside that display's corner, and `fullscreen` makes it fill that display. Its size is `size` (`WIDTHxHEIGHT` in the host's unit: points on macOS, real pixels on Windows) when stated, else the size the conf states in `windowresolution`, else the largest 4:3 window the display's usable area holds (menu bar, Dock and taskbar excluded) when the host reports one. The size reaches the emulator as `-set "sdl windowresolution=..."`: on Windows DOSBox-X stops being DPI aware from 200 %, so there the number is in logical pixels (a display at 300 % gets a third of the size asked) and below 200 % it is in real pixels, sent as asked; on macOS high DPI is off and the unit is the point. It is refused naming the usable size and the frame's share of it when it does not fit, beside `fullscreen`, and under an `sdl output` that ignores a size: every OpenGL output and Direct3D take one, `surface` does not, and an unset `output` is OpenGL on macOS and was `surface` on the Windows build this was measured on. With an ignoring output and no `size` the conf's size stays. On macOS `fullscreen` is accepted on display 0 only: a start is halted at its first instruction, and on another display the window reaches full screen only once the emulator runs, so it is refused naming `display=0`. The same halt keeps a parked window at the conf's size until the guest runs, so `start` does not judge the size: `window` does, once the guest runs, comparing the window's client area on Windows and its outer rectangle on macOS (which has no client area, so a title bar's height is allowed on the height), with the tolerance in its reply. The server waits for the window to be listed on that display and answers it as `window`; one that never appears is `window_not_visible`, with the session left live to `window` or `close`. `flags` cannot retune it: a `-set` of `sdl display`, `sdl fullscreen`, `sdl windowposition` or `sdl windowresolution`, or `-fullscreen`, is refused naming the argument that owns it. `fullscreen` on `sdl output=surface` is refused too: that output fills the display by switching its video mode, and the window ends off screen. Linux is out of scope. A headless start takes none of these arguments.

**`flags` come after this server's defaults**, so a `-set` for the same key wins, except the ones a named argument sets (`-time-limit`, `sdl videodriver`, `log logfile`, the conf, the program...): refused naming the argument, because after ours the flag would quietly undo it.

**`break_on_int3`** has two limits that are the debugger's: at the reset vector there is no row, so a trap faults; and the first instruction after a `resume` runs unchecked, so a trap written at the stop itself is stepped over.

**`binary` and `background`**: `binary` omitted is `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`, as `build_check` resolves it. `background` `true` starts behind, `false` in front, omitted by `shared`.

**`flags` are argv tokens, so a `-set` value with spaces is one token**; a glued `-set` is refused because DOSBox-X hangs on it, a shredded one because DOSBox-X ignores it at rc 0 and the setting would silently not apply.

**`program` loads the stub itself when the conf's autoexec does not run it**, which is why the autoexec must not `exit` before `program` runs.

**`state_dir`** is what `state_write(method="save")` writes to; empty, `save` under the session's scratch, gone at `close`; `start` and `status` name that folder.

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

Reply: `last_stop` (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`) and `pending` (`arm`
refs, a `disarm` count, `symbols_load`, `base_remeasure`), both unavailable or empty once a
session has ended; with a session also `presence`, `pid`,
`conf`, `conf_digest`, `conf_changed_on_disk`, `watched`, `bound_s`, `elapsed_s`,
`output_bytes_dropped`, `captures`, `state_dir`, `declarations`, `pc` and `cpu_mode`;
`symbols_held` (`path`, `base_from`, `waiting_for`) while a `start` table waits for its
program, which costs a memory-chain read at every stop. `session` carries `alive`,
`running`, `altered` and each alarm while it holds.

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
| `symbols_held` | object |
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
  "last_stop": {"available": false, "why": "this session has not stopped yet"},
  "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false}
}
```
<!-- scry-reference:end status -->

**The alarms** are `conf_changed_on_disk` (the file changed since start; `false` also if gone), `output_bytes_dropped` (the emulator's output overflowed what the server keeps) and `program` (the program the guest was running is gone). They ride in `session` only while they hold.

**`program` is read at the stops that answer a call**, not at each frame of a timed run: each reads DOS's current process (`EV PSPSEG`) and, when it changed, its owner in the debugger's `DOS MCBS` listing, so a program that ends while the guest runs shows from the next such stop on, and a session that never stops never learns it. The program is the one `start` launched by `program` (any other, when it named none), never the resident stub; only the first command interpreter counts as DOS being back at the prompt, not one the program opened. It is `state: exited` once DOS's current process is that interpreter's where it had been the program's, with `name` and `seen_by` (what was read); or `state: fault` when the text screen then holds, below the row that ran the program, the message DJGPP writes as a program dies (it never reaches the E9 log), quoted in `fault` from its first line to the prompt. A first stop that finds the prompt where none had seen the program names it from the start's `program`, but only when the log shows the program wrote a line of its own. A program started again clears it only when a stop sees it run: one relaunched and dead between two stops leaves the first exit in place. A wait that expired opens its `note` with it, or, when the guest wrote no line in the wait and the note does not already say so, with that fact; a wait in which lines kept arriving gets neither.

**`pc` is read from the debugger at a stop**, so it is unavailable while the guest runs; `cpu_mode` is `real`, `protected`, `paged` or `VM86`. `last_stop` is unavailable with no session or a cut survey. `presence` is `true` drawn, `false` off, or why not, and is left out with no session. `declarations` is this server's own count.

<!-- scry-reference:begin window -->
## `window`

*The session's window*

```text
window(front=false)
```

Where the watched window is on the host, at any time, a running guest included. `front`
brings it in front of whatever covers it and reads that back.

Reply: `window` (`display`, the OS's index; `bounds`; `onscreen`; `front`, no other
application's window covering its centre; `fullscreen`); `size` when the session was started
with a stated `size`: `asked`, `seen`, which rectangle was `compared` (`client` or
`outer`), `tolerance_px`, `height_free` and `matches`.

Refused: no session (`no_session`), a session started without `shared` (`no_channel`), a
window that never appears or, with `front`, is still covered after the activation
(`window_not_visible`, naming what was seen; on a `background=true` session it names that as
what may keep it behind). Without `front` the window is answered wherever the owner put it.

Reference: REFERENCE.md, The session.

| argument | type | default |
|---|---|---|
| `front` | boolean | `false` |

| reply field | type |
|---|---|
| `activation` | string |
| `asked_display` | integer |
| `seen` | object |
| `size` | object |
| `window` | object |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "window: display 0, on screen, covered",
  "status": "ok",
  "window": {
    "display": 0,
    "bounds": {"x": 704, "y": 359, "width": 640, "height": 432},
    "onscreen": true,
    "front": false,
    "fullscreen": false
  }
}
```
<!-- scry-reference:end window -->

<!-- scry-reference:begin close -->
## `close`

*Close the session*

```text
close(detail=false)
```

End the session deliberately rather than waiting for its bound.

Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid` and
`exit_code`, each an integer, or unavailable with its `why` when no session was running;
`stdout_tail` and `errorlog_tail` when the end was not a clean `quit`, or with `detail=True`;
`note` when the output was not read to its end. `guest_files`: each file `start` named, with
`guest_file`'s `state`. `session` is the block as it is after the close (`alive` and
`running` false).

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
| `pid` | integer or object |
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
  "pid": "<volatile>",
  "exit_code": {"available": false, "why": "no session was running"},
  "note": "there was no session to close"
}
```
<!-- scry-reference:end close -->

**The `ended_by` values**: `quit` is the emulator leaving on the first signal, which is what a session launched here does, program loaded or not, because `start` turns the quit warning off; `killed` is a conf that puts the warning back or a wedged guest, ended by SIGKILL, and every close on Windows, which has no signal to ask with and terminates the process; `died` is already exited when called; `none` is nothing to close. **`exit_code`** is unavailable when SIGKILLed and still not reaped, since an emulator may still be on the machine.

**The `session` block is the session after the close**: `alive` and `running` false and `altered` false, as with no session at all.

**`note`** says how the reader of the emulator's output ended when that was not at the end of its output: it outlived the close, or a read failed, so the tails may be short. **The reply also carries** what the process was (`status`'s rows, `pid` first), read before the end, so `pid` is the process this call ended.
