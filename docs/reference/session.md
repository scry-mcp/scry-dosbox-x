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

Reply: `binary`, `binary_origin`, `version`, `debugger`, `heavy_debug` (`trace` needs it),
`debugger_commands` (which of `RUNSTATE`, `STEPIN`, `SAVESTATE`, `LOADSTATE`, `PRESENCE` the build's debugger has; omitted when none).

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
  "summary": "build_check: ~/.local/state/dosbox-x-builds/scry-92d913050/dosbox-x (DOSBOX_X_BINARY), debugger True, heavy_debug True",
  "status": "ok",
  "binary": "~/.local/state/dosbox-x-builds/scry-92d913050/dosbox-x",
  "binary_origin": "DOSBOX_X_BINARY",
  "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
  "debugger": true,
  "heavy_debug": true,
  "debugger_commands": [
    "RUNSTATE",
    "STEPIN",
    "SAVESTATE",
    "LOADSTATE",
    "PRESENCE"
  ],
  "tools": [
    "breakpoint_at",
    "breakpoint_interrupt",
    "build_check",
    "call_stack",
    "capture_frame",
    "captures",
    "... 45 more"
  ]
}
```
<!-- scry-reference:end build_check -->

A build without the debugger starts fine and then hangs `start` until its timeout. The debugger and its optional commands (`debugger_commands`) are read off the binary itself, never asked of it: `-helpdebug` lists `-break-start` in a build configured without the debugger too, and on Windows it prints to no stream and never exits. It refuses while a session is live because its version probe starts the emulator, which a build that does not know the option runs until the probe's bound.

**`heavy_debug: false` is an answer, not a failure**: it is `trace` that refuses such a build. The tool is about the build, never about a reading. `binary_origin` is `argument`, `DOSBOX_X_BINARY` or `PATH`; `version` is the build's first line, or `{available: false, why}`.

<!-- scry-reference:begin start -->
## `start`

*Start a DOSBox-X session*

```text
start(conf, cwd, session_seconds, shared=false, display="", flags=null, break_on_int3=false, program="", logfile="", capture_video=false, captures_dir="", plan=null, settle_seconds=null, input_port=0, state_dir="", binary="", background=null, presence=true)
```

Open one live DOSBox-X session from your conf, parked at the debugger.

Paths are absolute or `~`-led. `session_seconds`: the lifetime. `shared`: watched on
`display`; false, headless. `flags`: argv tokens, a `-set` value one token. `logfile`: the
guest's E9 channel, for `log`, `log_wait`, `drive`. `program` runs after autoexec;
`capture_video` records it. `plan` runs as `perform` does, each wait bounded by
`settle_seconds` (default 30). `input_port`: COM1's TCP port, 0 a free one.
`state_dir`: where `state_write` saves; empty, under `cwd`.

Refused: a live session, a bad path, `session_seconds` out of range, `capture_video`
without `program`, an `input_port` other than 0 outside 1024-65535, or
busy.

Reply: `pid`, `stub`, `input_port`, `declarations` (`rearm`); with `plan`, its account.

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

- `display`: Where a watched (`shared`) window opens: `main` or `secondary`; empty, the display `WINDOW_SHARED_DISPLAY` names, else the secondary.
- `presence`: Draw an edge around the emulator's window while this session is open: dim while idle, bright while a call runs the machine. No capture of this server carries it.

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
| `debugger_commands` | array |
| `declarations` | object |
| `display` | string |
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
| `output_bytes_dropped` | integer |
| `version` | string or object |
| `watched` | boolean |

Example, from a live run:

```json
{
  "conf": "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest/probe.conf",
  "cwd": "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest",
  "session_seconds": 1200,
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/C/n11-save",
  "plan": [
    {
      "op": "status"
    },
    {
      "op": "registers"
    }
  ],
  "presence": false
}
```

```json
{
  "summary": "start probe.conf: headless on ~/.local/state/dosbox-x-builds/scry-92d913050/dosbox-x (DOSBOX_X_BINARY), debugger answered after 0.104s, then 2 of 2 steps",
  "status": "ok",
  "ran": [
    {
      "op": "status",
      "reply": {
        "summary": "status: alive, stopped",
        "status": "ok",
        "pid": 46953,
        "conf": "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest/probe.conf",
        "conf_digest": "78bdc38f360b9b4a",
        "bound_s": 1200,
        "elapsed_s": 0.6,
        "captures": "off",
        "state_dir": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/C/n11-save",
        "last_stop": {
          "stop_seq": 1,
          "pc": "F000:0000FFF0",
          "cause": "no declared code breakpoint at F000:0000FFF0: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
          "since_s": 0.0,
          "wall_at": "2026-10-26T07:36:06+00:00"
        },
        "pending": {
          "arm": [],
          "disarm": 0,
          "symbols_load": false,
          "base_remeasure": false
        },
        "cpu_mode": "real",
        "pc": "F000:0000FFF0",
        "declarations": {
          "breakpoints": 2,
          "watches": 0
        },
        "presence": false,
        "session": {
          "alive": true,
          "running": false,
          "altered": true
        }
      }
    },
    {
      "op": "registers",
      "reply": {
        "summary": "registers: 15 registers",
        "status": "ok",
        "regs": {
          "EAX": "0x00000000",
          "EBX": "0x00000000",
          "ECX": "0x00000000",
          "EDX": "0x00000000",
          "ESI": "0x00000000",
          "EDI": "0x00000000",
          "EBP": "0x00000000",
          "ESP": "0x00000000",
          "EIP": "0x0000fff0",
          "CS": "0xf000",
          "DS": "0x0000",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x0000"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": true
        }
      }
    }
  ],
  "steps_completed": 2,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "start": {
    "pid": 46953,
    "conf": "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest/probe.conf",
    "conf_digest": "78bdc38f360b9b4a",
    "conf_changed_on_disk": false,
    "watched": false,
    "bound_s": 1200,
    "elapsed_s": 0.6,
    "output_bytes_dropped": 0,
    "captures": "off",
    "state_dir": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/C/n11-save",
    "shared": false,
    "display": "",
    "ready_after_s": 0.104,
    "argv": [
      "~/.local/state/dosbox-x-builds/scry-92d913050/dosbox-x",
      "-conf",
      "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest/probe.conf",
      "-time-limit",
      "1200",
      "-break-start",
      "... 18 more"
    ],
    "binary": "~/.local/state/dosbox-x-builds/scry-92d913050/dosbox-x",
    "binary_origin": "DOSBOX_X_BINARY",
    "version": "DOSBox-X version 2026.10.01 SDL2, copyright 2011-2026 The DOSBox-X Team.",
    "debugger_commands": [
      "LOADSTATE",
      "PRESENCE",
      "RUNSTATE",
      "SAVESTATE",
      "STEPIN"
    ],
    "stub": "/path/to/scry-dosbox-x/guest/INJECT.COM",
    "input_port": 55437,
    "background": true,
    "presence": false,
    "declarations": {
      "rearm": {
        "rearmed": [
          {
            "ref": "0000:0006",
            "by": "address",
            "cpu": {
              "available": false,
              "why": "a DOS machine has one cpu, and every row acts on it"
            },
            "created_at": "2026-10-26T07:35:58+00:00",
            "origin": "2026-10-26T07:35:57+00:00#46519.2",
            "inherited": true,
            "age_s": 8
          },
          {
            "ref": "0000:0001",
            "by": "address",
            "cpu": {
              "available": false,
              "why": "a DOS machine has one cpu, and every row acts on it"
            },
            "created_at": "2026-10-26T07:36:00+00:00",
            "origin": "2026-10-26T07:35:59+00:00#46519.4",
            "inherited": true,
            "age_s": 6
          }
        ],
        "stale": [],
        "unresolved": [],
        "ambiguous": [],
        "unarmable": []
      }
    }
  }
}
```
<!-- scry-reference:end start -->

**`shared` is explicit, with no detection behind it.** Headless uses `videodriver=dummy`, not `SDL_VIDEODRIVER` and not `-silent`, which exits after `AUTOEXEC.BAT` and cannot host a session.

**`session_seconds` is a hard bound** because a DOSBox-X held at its debugger never reaches its own time limit. The emulator's `-time-limit` counts emulated time, which a machine held at the debugger never advances, so a guardian (`scry-dosbox-x-guardian` in the process list) also keeps the host's clock, ending the emulator a few seconds past the bound or within one poll of this server dying.

**The server never decides where a window goes**: no helper, or a failing one, refuses a shared `start` `host_failed` rather than invent a geometry. No flags is an answer (one display).

**`flags` come after this server's defaults**, so a `-set` for the same key wins, except the ones a named argument sets (`-time-limit`, `sdl videodriver`, `log logfile`, the conf, the program...): refused naming the argument, because after ours the flag would quietly undo it.

**`break_on_int3`** has two limits that are the debugger's: at the reset vector there is no row, so a trap faults; and the first instruction after a `resume` runs unchecked, so a trap written at the stop itself is stepped over.

**`binary` and `background`**: `binary` omitted is `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`, as `build_check` resolves it. `background` `true` starts behind, `false` in front, omitted by `shared`.

**`flags` are argv tokens, so a `-set` value with spaces is one token**; a glued or shredded `-set` is refused because the emulator would read it as something else.

**`program` loads the stub itself when the conf's autoexec does not run it**, which is why the autoexec must not `exit` before `program` runs.

**`state_dir`** is what `state_write(method="save")` writes to; empty, `save` under `cwd`. **`break_on_int3`** has two limits that are the debugger's.

**Also refused before anything starts**: a missing conf, `cwd` or `logfile` directory, an unresolved binary, `display` headless, `shared` with no window helper, a glued or shredded `-set`, and no drive free for the stub. `captures_dir` and `state_dir` are created with their parents. The reply also carries `shared`, `display`, `ready_after_s`, `argv`, `binary`, `binary_origin`, `version`, `background`, `presence` and `rearm_refused` (why, when stored raw breakpoints could not re-arm).

<!-- scry-reference:begin status -->
## `status`

*Session status*

```text
status()
```

What the session is right now. It records a stop no tool has reported
(`stopped_on_its_own`) and applies what was queued while the guest ran
(`applied_on_stop`).

Reply: `pid`, `conf`, `conf_digest`, `conf_changed_on_disk`, `watched`, `bound_s`, `elapsed_s`,
`output_bytes_dropped`, `captures`, `state_dir`, `pending` (`arm` refs, a `disarm` count,
`symbols_load`, `base_remeasure`), `presence`, `declarations`, and with a session `pc` and
`cpu_mode`. Also `last_stop` (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`). `session`
carries `alive`, `running`, `altered` and each alarm while it holds.

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
  "summary": "status: alive, stopped",
  "status": "ok",
  "pid": 47100,
  "conf": "$TMPDIR/dosbox-x-live-job-og6cg2yw/N/tests/guest/probe.conf",
  "conf_digest": "78bdc38f360b9b4a",
  "bound_s": 1200,
  "elapsed_s": 0.9,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/N/n2-save",
  "last_stop": {
    "stop_seq": 2,
    "pc": "0814:00000106",
    "cause": "no declared code breakpoint at 0814:00000106: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
    "since_s": 0.2,
    "wall_at": "2026-10-26T07:36:15+00:00"
  },
  "pending": {
    "arm": [],
    "disarm": 0,
    "symbols_load": false,
    "base_remeasure": false
  },
  "cpu_mode": "real",
  "pc": "0814:00000106",
  "declarations": {
    "breakpoints": 0,
    "watches": 0
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

Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid`, `stdout_tail` and
`errorlog_tail` when the end was not a clean `quit`, or with `detail=True`. `exit_code` is
an integer or unavailable with its `why`; `note` when the output was not read to its end.
`session` is the block before closing.

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
| `note` | string |
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
  "summary": "close: quit, exit code 0",
  "status": "ok",
  "closed": true,
  "pid": 46899,
  "conf": "$TMPDIR/dosbox-x-live-job-og6cg2yw/C/tests/guest/probe.conf",
  "conf_digest": "78bdc38f360b9b4a",
  "bound_s": 1200,
  "elapsed_s": 6.7,
  "captures": "off",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/C/n10-save",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": [
    "stdout_tail",
    "errorlog_tail"
  ],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)"
}
```
<!-- scry-reference:end close -->

**The `ended_by` values**: `quit` is the emulator leaving on the first signal, which is what a session launched here does, program loaded or not, because `start` turns the quit warning off; `killed` is a conf that puts the warning back or a wedged guest, ended by SIGKILL, and every close on Windows, which has no signal to ask with and terminates the process; `died` is already exited when called; `none` is nothing to close. **`exit_code`** is unavailable when SIGKILLed and still not reaped, since an emulator may still be on the machine.

**`note`** says how the reader of the emulator's output ended when that was not at the end of its output: it outlived the close, or a read failed, so the tails may be short. **The reply also carries** what the process was (`status`'s rows, `pid` first), read before the end, so `pid` is the process this call ended.
