# The Session tools

A session is one DOSBox-X process, parked at the debugger by `start` and ended by `close`. The path rule, the binary ladder and the presence indicator are in [REFERENCE.md, The session](../../REFERENCE.md#the-session).

<!-- scry-reference:begin build_check -->
## `build_check`

*Check the build*

```text
build_check(binary="")
```

Whether this server's PRECONDITIONS hold: a DOSBox-X binary resolves and that build
carries the DEBUGGER. Run it BEFORE `start`; it REFUSES while a session is live
(answering means starting a second emulator). `binary`: the absolute path of the build to
ask about; omitted, the `DOSBOX_X_BINARY` variable, else the PATH's `dosbox-x`, as `start`
resolves it; a named build that does not resolve is refused, never replaced. Reply:
`binary` (the absolute path), `binary_origin` (`argument`, `DOSBOX_X_BINARY` or `PATH`),
`version` (the build's first line, or `{available: false, why}`), `debugger`,
`heavy_debug` (the build carries the debugger's CPU log, which `trace` needs), and INVALID
naming the precondition that fails; `heavy_debug: false` is an answer, and it is `trace`
that refuses such a build. It is about the build, never about a reading.

| argument | type | default |
|---|---|---|
| `binary` | string | `""` |

| reply field | type |
|---|---|
| `binary` | string |
| `binary_origin` | string |
| `debugger` | boolean |
| `heavy_debug` | boolean |
| `tools` | array |
| `version` | string or object |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "build_check: /path/to/dosbox-x-builds/scry-f06aa5d26/dosbox-x (DOSBOX_X_BINARY), debugger True, heavy_debug True",
  "status": "ok",
  "binary": "/path/to/dosbox-x-builds/scry-f06aa5d26/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
  "debugger": true,
  "heavy_debug": true,
  "tools": [
    "breakpoint_at",
    "breakpoint_clear",
    "breakpoint_interrupt",
    "breakpoint_list",
    "build_check",
    "call_stack",
    "... 58 more"
  ]
}
```
<!-- scry-reference:end build_check -->

A build without the debugger starts fine and then hangs `start` until its timeout. The debugger is read off the binary itself, since `-helpdebug` listing `-break-start` also happens in a build configured without the debugger. It refuses while a session is live because `-helpdebug` starts the emulator, which a build that does not know the option runs for the whole bound.

<!-- scry-reference:begin start -->
## `start`

*Start a DOSBox-X session*

```text
start(conf, cwd, session_seconds, shared=false, display="", flags=null, break_on_int3=false, program="", logfile="", capture_video=false, captures_dir="", plan=null, settle_seconds=null, input_port=0, state_dir="", binary="", background=null, presence=true)
```

Open ONE live DOSBox-X session from your conf, parked at the debugger.
Refuses while a session is live.

Every path is absolute or `~`-led: `cwd`, the emulator's working directory, there; `conf`;
`logfile`, its directory there; `captures_dir` and `state_dir`, created with their parents.
`session_seconds`: the session's REQUIRED lifetime; `close` is
the act. `shared`: watched, in a window the host's helper places on `display`; false,
headless. `flags` (the emulator's own, after this server's defaults) are argv
tokens, a `-set` value ONE token with its spaces.
`break_on_int3`: the guest's `int 3` stops at the debugger. `logfile`: the guest's E9
channel, without which `log`, `log_wait`, `expect` and `drive` have none. `program` runs
with `-c` AFTER the conf's autoexec (which must not `exit`); `capture_video` records it.
`plan`: operations run on the fresh session with `perform`'s rules, `settle_seconds`
(default 30, and only with a plan) bounding each wait. `input_port`: COM1's TCP port
for the input (`0`: a free one); the conf's autoexec runs the reply's `stub` first, or
`program` loads it. `state_dir`: what `state_save` writes to (`save` under `cwd`). `binary`:
the build to run; omitted, `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`. `background`:
`true` behind; `false` in front; omitted, by `shared`.

Reply: the process (`status`'s rows), `shared`, `display`, `ready_after_s`, `argv`,
`binary`, `binary_origin`, `version`, `stub`, `input_port`, `background`, `presence`,
`declarations.rearm`, and `rearm_refused` (why) when stored raw breakpoints could not
re-arm; with `plan`, the sequence account, the start facts under `start`.

Refused before anything starts: a path not absolute, an unresolved binary, a missing
conf, `cwd` or `logfile` directory, `session_seconds` out of range, `display` headless,
`shared` with no window helper, a glued or shredded `-set`, `capture_video`
without `program`, an `input_port` outside 1024-65535 or busy, no
drive free for the stub.

Reference: REFERENCE.md, The session.

| argument | type | default |
|---|---|---|
| `conf` | string | required |
| `cwd` | string | required |
| `session_seconds` | integer (>= 1, <= 14400) | required |
| `shared` | boolean | `false` |
| `display` | one of `""`, `"main"`, `"secondary"` | `""` |
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

- `display`: Where a watched (`shared`) window opens: `main` or `secondary`; empty, the display `WINDOW_SHARED_DISPLAY` names, else the secondary. The host's placement helper (`WINDOW_APP`) places it; a run nobody watches takes none.
- `presence`: Draw an edge around the emulator's window while this session is open: dim while idle, bright while a call runs the machine. No capture, recording or screen reader of this server carries it; a recording of the window made from outside does.

| reply field | type |
|---|---|
| `errors` | array |
| `failed` | object |
| `failed_at` | integer or object |
| `field` | string |
| `got` | any |
| `held` | integer |
| `note` | string |
| `ran` | array |
| `ran_path` | string or object |
| `recorded` | any |
| `replies_path` | string or object |
| `steps_completed` | integer |
| `steps_total` | integer |
| `still_running` | boolean |
| `stopped` | object |
| `stops` | object |
| `truncated` | boolean |
| `verdict` | string |
| `argv` | array |
| `background` | boolean |
| `binary` | string |
| `binary_origin` | string |
| `bound_s` | number |
| `captures` | string |
| `conf` | string |
| `conf_changed_on_disk` | boolean or object |
| `conf_digest` | string |
| `declarations` | object |
| `display` | string |
| `drain_alive` | boolean |
| `drain_ended` | string |
| `elapsed_s` | number |
| `input_port` | integer or object |
| `operations` | array |
| `pid` | integer |
| `presence` | boolean or object |
| `ready_after_s` | number |
| `rearm_refused` | string |
| `shared` | boolean |
| `start` | object |
| `state_dir` | string |
| `stub` | string |
| `terminal_bytes_dropped` | integer |
| `version` | string or object |
| `watched` | boolean |

Example, from a live run:

```json
{
  "conf": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n2.conf",
  "cwd": "/path/to/scry-dosbox-x/tests/guest",
  "session_seconds": 1200,
  "shared": true,
  "program": "PROBE.COM",
  "background": false,
  "logfile": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n3.log",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n4-save",
  "presence": false
}
```

```json
{
  "summary": "start n2.conf: shared on /path/to/dosbox-x-builds/scry-f06aa5d26/dosbox-x (DOSBOX_X_BINARY), debugger answered after 0.209s",
  "status": "ok",
  "pid": 42512,
  "conf": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n2.conf",
  "conf_digest": "33a4a905f64a2a65",
  "conf_changed_on_disk": false,
  "watched": true,
  "bound_s": 1200,
  "elapsed_s": 0.9,
  "terminal_bytes_dropped": 0,
  "drain_alive": true,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n4-save",
  "shared": true,
  "display": "secondary",
  "ready_after_s": 0.209,
  "argv": [
    "/path/to/dosbox-x-builds/scry-f06aa5d26/dosbox-x",
    "-conf",
    "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n2.conf",
    "-time-limit",
    "1200",
    "-break-start",
    "... 25 more"
  ],
  "binary": "/path/to/dosbox-x-builds/scry-f06aa5d26/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
  "stub": "/path/to/scry-dosbox-x/guest/INJECT.COM",
  "input_port": 63016,
  "background": false,
  "presence": false,
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

**`session_seconds` is a hard bound** because a DOSBox-X nobody reads freezes under its terminal. The emulator's `-time-limit` counts emulated time, which a machine held at the debugger never advances, so a guardian (`scry-dosbox-x-guardian` in the process list) also keeps the host's clock, ending the emulator a few seconds past the bound or within one poll of this server dying.

**The server never decides where a window goes**: no helper, or a failing one, refuses a shared `start` `host_failed` rather than invent a geometry. No flags is an answer (one display).

**`flags` come after this server's defaults**, so a `-set` for the same key wins, except the ones a named argument sets (`-time-limit`, `sdl videodriver`, `log logfile`, the conf, the program...): refused naming the argument, because after ours the flag would quietly undo it.

**`break_on_int3`** has two limits that are the debugger's: at the reset vector there is no row, so a trap faults; and the first instruction after a `resume` runs unchecked, so a trap written at the stop itself is stepped over.

<!-- scry-reference:begin status -->
## `status`

*Session status*

```text
status()
```

What the session is right now. It records a stop no tool has
reported (`stopped_on_its_own`) and applies what was queued while the guest ran
(`applied_on_stop`).

Reply, at the top here, on `start` and on `close`: the rows below but `alive`, `running`
and `altered` (none with no session). `session`, on every reply, carries those three
(`alive` false with no session: nothing running is an answer) and each alarm (!) while it
holds:

  pid                     the emulator process's pid.
  alive                   the emulator process is up.
  running                 the guest runs; false parked at the debugger.
  altered                 something here WROTE to the guest: later readings are forced.
  conf                    the config the session was started from.
  conf_digest             a digest of that file's content AT START.
  conf_changed_on_disk !  the file changed since (`false` also if gone).
  watched                 a window was placed to be watched.
  bound_s                 the ceiling the session was given.
  elapsed_s               how much of that is spent.
  terminal_bytes_dropped ! nonzero: a screen delta had a hole in it.
  drain_alive !           the terminal reader runs.
  drain_ended !           why that reader stopped, present once it has.
  captures                `off`, or where a `capture_video` session records.
  state_dir               where `state_save` writes and `state_list` reads.

Also at the top: `last_stop` (`stop_seq`,
`pc`, `cause`, `since_s`, `wall_at`; the park after `start` is stop 1; unavailable with no
session or a cut survey), `pending` (asked while the guest ran: `arm` refs, a `disarm` count,
`symbols_load`; `base_remeasure` after a `state_load`), `presence` (the window's edge:
`true` drawn, `false` off or no session, or why not), and with a
session `pc` (where it is now, read off the pane; unavailable while it runs) and `cpu_mode`
(`real`, `protected`, `paged`, `VM86`), and `declarations`, this server's own counted.

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
| `drain_alive` | boolean |
| `drain_ended` | string |
| `elapsed_s` | number |
| `pc` | string or object |
| `pending` | object |
| `pid` | integer |
| `presence` | boolean or object |
| `state_dir` | string |
| `terminal_bytes_dropped` | integer |
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

<!-- scry-reference:begin close -->
## `close`

*Close the session*

```text
close(detail=false)
```

End the session deliberately rather than waiting for its bound. Reports its progress
while the emulator takes its time to leave.

Reply: `closed`, `ended_by` (`quit`: the emulator left on the first signal, which is what
a session launched here does, program loaded or not, because `start` turns the quit
warning off; `killed`: it ignored the signal, a conf that puts the warning back or a
guest wedged, and SIGKILL ended it; `died`: it had already exited when this was called;
`none`: nothing to close), `exit_code` (an integer, or unavailable with its `why`:
SIGKILLed and still not reaped, an emulator may still be on the machine, or not read).
`stdout_tail` and `errorlog_tail` (the last words of the console and of the logfile, read
after the exit) when the end was not a clean `quit` with exit code 0, or with
`detail=True`, else `omitted` names them with `how`. What the process was (`status`'s
rows, `pid` first) rides at the top, read before the end, so `pid` is the process this call
ended; `session` is the block as it stood BEFORE closing.

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
| `drain_alive` | boolean |
| `drain_ended` | string |
| `elapsed_s` | number |
| `ended_by` | string |
| `errorlog_tail` | string or object |
| `note` | string |
| `pid` | integer |
| `state_dir` | string |
| `stdout_tail` | string |
| `terminal_bytes_dropped` | integer |
| `watched` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "close: quit, exit code 0",
  "status": "ok",
  "closed": true,
  "pid": 42512,
  "conf": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n2.conf",
  "conf_digest": "33a4a905f64a2a65",
  "conf_changed_on_disk": false,
  "watched": true,
  "bound_s": 1200,
  "elapsed_s": 6.0,
  "terminal_bytes_dropped": 0,
  "drain_alive": true,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/n4-save",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": [
    "stdout_tail",
    "errorlog_tail"
  ],
  "how": "close(detail=True) keeps the channels' last words on a clean quit too; once a close has answered the console's are gone (the logfile stays at its path)"
}
```
<!-- scry-reference:end close -->
