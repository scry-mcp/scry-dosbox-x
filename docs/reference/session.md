# The Session tools

A session is one DOSBox-X running under its debugger. `start` opens it from your conf and leaves the machine stopped at the debugger; `close` ends it. One session is open at a time.

`build_check` answers only while no session is open. `status`, `window` and `close` answer at any time, while the program runs too.

A repository can keep how its program starts in its own `.scry/` folder, as a start profile: a file of `start` arguments. What every session shares, such as how a path is written and which DOSBox-X binary runs, is in [REFERENCE.md, The session](../../REFERENCE.md#the-session).

<!-- scry-reference:begin build_check -->
## `build_check`

Check which DOSBox-X would run and whether it has the debugger a session needs, before starting one.

```text
build_check(binary="")
```

### Try it

On any host where DOSBox-X is installed, before a session is open. It needs no program.

Ask:

> Which DOSBox-X would you run, and does it have the debugger?

Call:

```text
build_check()
```

Reply, 3 of 9 fields:

```json
{
  "status": "ok",
  "debugger": true,
  "heavy_debug": true
}
```

The build has the debugger, and it has heavy debugging, the option `trace` needs.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger": true,
  "heavy_debug": true,
  "debugger_commands": ["RUNSTATE", "STEPIN", "SAVESTATE", "LOADSTATE", "PRESENCE", "VGAMEMDUMP", "... 8 more"],
  "tools": ["a20", "audio_compare", "audio_record", "breakpoint_at", "breakpoint_interrupt", "build_check", "... 56 more"]
}
```

</details>

### Arguments

- `binary` (string, default `""`): The DOSBox-X to check, as an absolute path. Left empty, `DOSBOX_X_BINARY`, else the `dosbox-x` on the PATH.

### What comes back

- `binary`: The executable that was found.
- `binary_origin`: Where its path came from: `argument`, `DOSBOX_X_BINARY` or `PATH`.
- `version`: The build's own version line, or `available: false` with a `why`: a version that cannot be read never fails the call.
- `heavy_debug`: Whether the build has heavy debugging, which `trace` and a `freeze` watch, one that holds bytes at their value, need. `false` is an answer, not a failure.
- `debugger_commands`: The optional debugger commands the build has; several tools need one. Left out when it has none.
- `debugger_commands_missing`: Each command the build lacks (`command`) with the tools that stop working without it (`disables`). Left out when none is missing.

<details><summary>All 9 reply fields</summary>

- `binary` (string)
- `binary_origin` (string)
- `debugger` (boolean)
- `debugger_commands` (array)
- `debugger_commands_missing` (array)
- `heavy_debug` (boolean)
- `presence_layers` (array of string)
- `tools` (array)
- `version` (string or object)

</details>

### What it refuses

- A session is open: answering would start a second emulator (`session_live`).
- A `binary` that is not an absolute path or names no executable (`bad_argument`).
- `DOSBOX_X_BINARY` or the PATH naming no executable, or a build without the debugger (`host_failed`).

### Why it works this way

A DOSBox-X built without the debugger starts fine and then leaves `start` waiting until it gives up, so this check comes first. It reads the binary's own bytes and never asks it: `-helpdebug` lists `-break-start` on a build without the debugger too, and on Windows it prints nowhere and never exits.

It is refused while a session is open: reading the version starts a second emulator, which a build that does not know the option runs until the check gives up. The answer is about the build, never about a reading, and `debugger` is always `true`: a build without one is refused.

<details><summary>More on why</summary>

`tools` lists this server's tools by name.

`presence_layers` lists the layers of `start`'s `overlay` the build draws: all six, five before the record mark, or the border and the pointer from an older build. It is left out without the `PRESENCE` command.

</details>

### Related tools

- [`start`](#start)
- [`status`](#status)
- [`trace`](run.md#trace)
- [`watch_add`](breakpoints.md#watch_add)

<details><summary>The contract your client receives</summary>

```text
Whether a DOSBox-X binary resolves and carries the debugger. Run before `start`; it
refuses `session_live` while a session is live. `binary`: omitted, `DOSBOX_X_BINARY`, else
the PATH's `dosbox-x`; a named build that fails is refused.

Reply: `binary`, `binary_origin`, `version`, `debugger`, `heavy_debug` (`trace` and a freeze
watch need it), `debugger_commands` (which of `RUNSTATE`, `STEPIN`, `SAVESTATE`, `LOADSTATE`, `PRESENCE`, `VGAMEMDUMP`, `BPIF`, `CAPTURE`, `TAP`, `PORTINFO`, `DOSTRACE`, `PIC`, `A20`, `MEMDUMPLIN` the build's debugger has;
omitted when none), `debugger_commands_missing` (each one it lacks, with the tools that
command disables; omitted when none is missing), `presence_layers` (the layers of `start`'s
`overlay` its `PRESENCE` draws; omitted without the command).
```

</details>
<!-- scry-reference:end build_check -->

<!-- scry-reference:begin start -->
## `start`

Start DOSBox-X from your conf file and leave the machine stopped at the debugger, at its first instruction.

```text
start(conf="", cwd="", session_seconds=null, shared=false, display=null, fullscreen=null, size=null,
    flags=null, break_on_int3=false, program="", logfile="", capture_video=false, captures_dir="",
    plan=null, settle_seconds=null, input_port=0, state_dir="", binary="", background=null,
    presence=true,
    overlay={"calls": true, "keys": true, "pointer": true, "pause": true, "record": true, "place": "auto"},
    names=true, dos_calls=false, log_categories=null, guest_files=null, symbols="",
    base_from="program", profile="")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds. The example session starts it for a person to watch, with a log file for what the game writes.

Ask:

> Start Bricks in a window I can watch without losing my keyboard, for at most fifteen minutes, and keep its log.

Call:

```text
start(shared=true, background=true, display="<host>", conf="./demos/bricks/bricks.conf",
    cwd="./demos/bricks", session_seconds=900, logfile="./tmp/demos/tour/files/e9.log",
    state_dir="./tmp/demos/tour/files/states", captures_dir="./tmp/demos/tour/files/captures")
```

Reply, 6 of 25 fields:

```json
{
  "status": "ok",
  "conf": "./demos/bricks/bricks.conf",
  "watched": true,
  "bound_s": 900,
  "logfile": "./tmp/demos/tour/files/e9.log",
  "kept": "1 saved for `promote`"
}
```

The session may live 900 seconds (`bound_s`), and `watched` says it has a window. `kept` says the arguments were saved as a start profile, for `promote` to write into a repository.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/tour/files/states",
  "shared": true,
  "ready_after_s": "<volatile>",
  "argv": "<volatile>",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger_commands": ["A20", "BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "MEMDUMPLIN", "... 8 more"],
  "stub": "./src/scry_dosbox_x/guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": true,
  "presence": true,
  "window": "<volatile>",
  "logfile": "./tmp/demos/tour/files/e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "1 saved for `promote`"
}
```

</details>

### Arguments

- `conf` (string, default `""`): The DOSBox-X conf file to run, as it is. Required unless a start profile gives it.
- `cwd` (string, default `""`): The folder the conf's relative paths resolve in. Required unless a start profile gives it.
- `session_seconds` (integer (>= 1, <= 14400), optional): The session's lifetime in seconds, after which the emulator is ended. Required unless a start profile gives it.
- `shared` (boolean, default `false`): `true` when a person watches: the session opens a window. Left out, it has none.
- `display` (integer, optional): Which display the window opens on, by the operating system's index. Needs `shared=true`; left out, 0, the main display.
- `fullscreen` (boolean, optional): `true` makes the window fill the display; DOSBox-X then captures the mouse, so its pointer no longer follows yours. Needs `shared=true`.
- `size` (string, optional): The window's size as `WIDTHxHEIGHT`, in the host's unit. Needs `shared=true`; left out, the conf's own size, else the largest 4:3 window the display holds.
- `flags` (array of string, optional): More command-line tokens for DOSBox-X, one list item each: `["-set", "cpu core=normal"]`. They come after the server's own, so a `-set` of the same key wins.
- `break_on_int3` (boolean, default `false`): `true` also stops at the program's own `int 3`, where a program marks a break. The stop at the debugger's first prompt still comes first.
- `program` (string, default `""`): A program to run inside DOS once the conf's `[autoexec]` has finished. Left empty, none.
- `logfile` (string, default `""`): A file that receives what the program writes to port `0xE9`, its own debug log, which `log` and `log_wait` read. A file already there is overwritten.
- `capture_video` (boolean, default `false`): `true` records the run of `program` as video. It needs `program`.
- `captures_dir` (string, default `""`): Where the emulator writes a capture it takes itself. Left empty, `capture` under the working directory.
- `plan` (array of object, optional): A list of calls to run right after the start, each `{"op": <tool>, ...arguments}`, run as `perform` runs a list.
- `settle_seconds` (number (>= 0, <= 600.0), optional): How long each wait of the `plan` may take, in seconds. Left out, 30.
- `input_port` (integer (>= 0, <= 65535), default `0`): The TCP port the emulated COM1 dials, through which keys and mouse reach the program. Left at 0, a free one; any other is 1024 or above.
- `state_dir` (string, default `""`): The folder `state_write` saves into, which stays after `close`. Left empty, the session's temporary folder, deleted at `close`.
- `binary` (string, default `""`): The DOSBox-X to run: an executable, or on macOS a `.app` bundle holding one. Left empty, `DOSBOX_X_BINARY`, else the `dosbox-x` on the PATH.
- `background` (boolean, optional): `true` opens the window behind your other windows and leaves the keyboard focus where it is; `false` opens it in front. Left out, behind unless `shared`.
- `presence` (boolean, default `true`): Draws a border around the emulator's window while the session is open, brighter while a call runs the machine. `false` leaves it off.
- `overlay` (any, default `{"calls": true, "keys": true, "pointer": true, "pause": true, "record": true, "place": "auto"}`): Layers over the border, each on unless `false`: `calls` names each call, `keys` keys held, `pointer` the pointer, `pause` a stopped machine, `record` a recording. `place`: `top`, `bottom`, `auto`.
- `names` (boolean, default `true`): `false` leaves a reply's numbers bare, with no `names` field, no name in its summary and no note on a disassembled line; the window's captions still name them.
- `dos_calls` (boolean, default `false`): `true` records every DOS call (INT 21h) the program makes, for `log(channel="dos")`. It needs a build whose debugger has `DOSTRACE`.
- `log_categories` (object, optional): DOSBox-X's own `[log]` categories, each with its level, written into `logfile`. It needs `logfile`.
- `guest_files` (array of string, optional): Up to 16 files on the host that the program is expected to leave. `guest_file` and `close` say what became of each.
- `symbols` (string, default `""`): A symbol table, checked now and loaded at the first stop where DOS holds the program it is named after. `symbols_load` loads one later.
- `base_from` (one of `"program"`, `"cs"`, `"ds"`, `"es"`, `"ss"`, `"fs"`, `"gs"` (in any case), default `"program"`): Where the table's addresses start: `program`, the program's own load address, or a segment register read at a protected-mode stop. Left out, `program`.
- `profile` (string, default `""`): A start profile: a saved set of `start` arguments, by its name under `.scry/start/` or by a path. It fills only the arguments the call leaves out.

### What comes back

- `window`: With `shared`, where the window is. Its `front` is `true` when no other application's window covers its centre; it does not mean the window has the keyboard focus.
- `input_port`: The TCP port the emulated COM1 dialled, or why no input connection was opened.
- `symbols`: With `symbols`: `held`, the table's path; `base_from`; and `checked`, what comparing it with the executable beside it found.
- `profile`: With a start profile: its `name`, its `file`, and `supplied`, the arguments it filled.
- `kept`: Says that this start's arguments were saved as a start profile for `promote`, the tool that writes one into your repository's `.scry/` folder.
- `start`: With `plan`: the start's own fields sit here, beside the plan's account of its steps.

<details><summary>All 57 reply fields</summary>

- `activation` (string)
- `asked_display` (integer)
- `seen` (object)
- `errors` (array)
- `failed` (object)
- `field` (string)
- `got` (any)
- `ran_path` (string or object)
- `recorded` (any)
- `replies_path` (string or object)
- `steps_total` (integer)
- `still_running` (boolean)
- `stopped` (object)
- `stops` (object)
- `truncated` (boolean)
- `verdict` (string)
- `searched` (array)
- `kept` (string)
- `failed_at` (integer or object)
- `held` (integer)
- `ran` (array)
- `steps_completed` (integer)
- `argv` (array)
- `background` (boolean)
- `binary` (string)
- `binary_origin` (string)
- `bound_s` (number)
- `bundle` (string)
- `captures` (string)
- `conf` (string)
- `conf_changed_on_disk` (boolean or object)
- `image_changed_on_disk` (boolean or object)
- `conf_digest` (string)
- `debugger_commands` (array)
- `declarations` (object)
- `dos_calls` (string)
- `elapsed_s` (number)
- `guest_files` (array)
- `input_port` (integer or object)
- `log_categories` (object)
- `logfile` (string)
- `operations` (array)
- `overlay` (OverlayReply)
- `pid` (integer)
- `presence` (boolean or object)
- `ready_after_s` (number)
- `rearm_refused` (string)
- `shared` (boolean)
- `start` (object)
- `state_dir` (string)
- `stub` (string)
- `profile` (object)
- `output_bytes_dropped` (integer)
- `symbols` (object)
- `version` (string or object)
- `watched` (boolean)
- `window` (object)

</details>

### What it refuses

- A session is already open (`session_live`).
- `conf`, `cwd` or `session_seconds` given neither by the call nor by a start profile, or a path that is not absolute (`bad_argument`).
- A conf, a `cwd` or a `logfile` folder that does not exist, or a `symbols` table the executable beside it contradicts (`bad_argument`).
- `display`, `fullscreen` or `size` without `shared=true`, or a `display` the host does not have (`bad_argument`).
- A `size` that does not fit the display, comes with `fullscreen`, or is ignored by the conf's `sdl output` (`bad_argument`).
- `fullscreen` under `sdl output=surface`, or on macOS on a display other than 0 (`bad_argument`).
- `flags` that set what a named argument owns, or a `-set` glued to its value or without `=` (`bad_argument`).
- `capture_video` without `program`, `log_categories` without `logfile`, an `input_port` from 1 to 1023, or `guest_files` naming a folder, a file twice or more than 16 (`bad_argument`).
- A `profile` that no `.scry/` folder searched holds; `searched` lists them (`bad_argument`).
- `dos_calls` on a build whose debugger has no `DOSTRACE` command (`no_channel`).
- A window that never appears on the display asked for. The session stays open for `window` or `close` (`window_not_visible`).
- A DOSBox-X that exits or never reaches its debugger (`session_broken`).

### Why it works this way

`shared` says whether a person watches. Without it the session has no window at all, and `window` cannot report one. With it the window opens on `display`, in front; add `background=true` to watch without losing the keyboard focus.

A start profile is a file of `start` arguments, `.scry/start/<name>.json` in a repository, so a session starts with `start(profile="<name>")`. The call's own arguments win and the profile fills the rest. The `.scry/` folder is looked for upwards from the server's working directory, then from `cwd`.

The server runs the conf you name as it is and writes none of its own. It mounts its own folder on a drive letter the conf's `[autoexec]` leaves free and runs `SCRY.COM` from it, the helper that delivers keys and mouse inside DOS. So the conf must not `exit` before `program` runs.

<details><summary>More on why</summary>

| you want | arguments | the window |
|---|---|---|
| Nobody watching | `shared=false`, the default | None. `window` refuses it as `no_channel`. |
| Somebody watching | `shared=true`, with `display` and `size` or `fullscreen` if wanted | On the display, in front, confirmed in the host's window list. |
| Watching and keeping the keyboard focus | `shared=true`, `background=true` | The same, opened behind your other windows. |

**The window's size.**

A windowed session opens 40 px inside the display's corner. Its size is `size` when given, else the conf's `windowresolution`, else the largest 4:3 window the display's usable area holds. The menu bar, Dock and taskbar do not count as usable.

`size` is in the host's unit: points on macOS, real pixels on Windows. Every OpenGL output and Direct3D take a size, and so does an unset `output` on macOS and Windows; `surface` does not. Under an output that ignores it, `size` is refused, and without `size` the conf's size stays.

`fullscreen` under `sdl output=surface` is refused because that output fills the display by switching its video mode, and the window ends off screen. On macOS it is accepted on display 0 only: a start stopped at its first instruction reaches full screen on another display only once the program runs.

`start` waits until the host lists the window on that display. It does not check the size, since a stopped window keeps the conf's size until the program runs; `window` does.

`background` only chooses where the window opens. How the focus stays with you is the host's: on macOS the emulator starts as a background application, and on Windows no program may take the foreground while `start` launches. A click or ALT moves the focus as always.

On Windows a start in front brings its window forward once it is up, and `window.front` says whether Windows allowed it.

**The lifetime.**

`session_seconds` is a hard limit because DOSBox-X's own time limit counts emulated time, which a machine stopped at the debugger never spends. A watchdog process, `scry-dosbox-x-guardian` in the process list, keeps the host's clock instead. It ends the emulator a few seconds past the limit, or soon after this server dies.

**Flags.**

- A flag that sets what a named argument sets (`-time-limit`, `sdl videodriver`, `log logfile`, the conf, the program) is refused, naming the argument: coming after the server's, it would undo it.
- So is a `-set` of `sdl display`, `sdl fullscreen`, `sdl windowposition` or `sdl windowresolution`, and `-fullscreen`.
- A `-set` value with spaces is one token. A `-set` glued to its value is refused because DOSBox-X hangs on it.
- A `-set` without `=` is refused because DOSBox-X ignores it with no error, and the setting would not apply.
- `key=value` with no section is accepted, and a key the server owns is refused in that spelling too.
- Without a window the server passes `videodriver=dummy`. It never passes `-silent`, which exits after `AUTOEXEC.BAT` and cannot keep a session open.

**The program and its symbols.**

- `program` loads the input helper itself when the conf's autoexec does not run it. A copy of `SCRY.COM` in the conf that speaks another protocol is reported in the `note`.
- A `symbols` table is compared with the executable beside it before anything starts. `symbols.checked` says how many global code symbols agreed, or why nothing could be compared.
- It is compared again at the first stop that holds the program, since the executable can be rebuilt meanwhile. That stop's reply carries `symbols_placed`, once.
- `symbols_placed` holds `placed`, `path`, `load_segment` in real mode, `base` and `loaded`; a refusal is `placed: false` with `code` and `why`.
- `base_from=program` is the DOS load segment of a real-mode program. For a DJGPP COFF executable it is the selector `CS` holds at a protected-mode stop, where the code runs.
- `break_on_int3` has two limits that are the debugger's: an `int 3` at the reset vector faults, and one at the address of a stop is stepped over by `resume`.
- `guest_files` answers each file as `path` and `before`, what it was before the boot.

**Speed.**

`[cpu] use dynamic core with fpu` decides whether FPU code runs recompiled. Its `auto` takes FPU and MMX instructions off the dynamic core. A single-tasking DOS program that leans on the FPU then runs below real time with nothing in the session saying so, and a conf for it states `true`.

**What else the reply says.**

- `captures_dir` and `state_dir` are created with their parents. `state_dir` in the reply is the folder in use.
- `shared`, `ready_after_s`, `argv`, `binary`, `binary_origin`, `version`, `background` and `presence` say what the launch used.
- A `version` the build would not give is `available: false` with a `why`, and never fails the start.
- `rearm_refused` says why saved raw breakpoints could not be set again.
- No free drive letter for the input helper is refused before anything starts.

**Files, the emulator's log and the border.**

- A file a tool reads must be a regular file, never a folder. A tool never writes over a file unless its entry says it replaces one, as `logfile` does.
- `logfile` is written under a name of lowercase words joined by hyphens, as every file the server writes, so a capital or a `%` in it is replaced.
- At `debug` a `log_categories` category can write a line per event: `files` writes one per read once the `[log]` setting `fileio` is on. Turn on only what the question needs.
- The border never changes another reply: a failure to draw it shows only in `presence`, in `start` and `status`; `overlay` says which of its layers are drawn.
- While the debugger does not answer, the border is not redrawn. It catches up once a call is answered.

</details>

### Related tools

- [`build_check`](#build_check)
- [`status`](#status)
- [`window`](#window)
- [`close`](#close)
- [`symbols_load`](names.md#symbols_load)
- [`promote`](project.md#promote)

<details><summary>The contract your client receives</summary>

```text
Open one live DOSBox-X session from your conf, parked at the debugger.

Paths are absolute or `~`-led. `cwd`: where the conf's relative paths resolve. `binary`:
an executable or a `.app` carrying one, which `open` launches (macOS alone): that route
keeps `cwd` through DOSBox-X's own `working directory` setting, names the bundle in
`bundle`, and leaves the exit status to launchd, so `close` answers `unavailable` for it.
`session_seconds`: the lifetime.
`shared`: watched, in a window; false, headless.
`profile`: a repository's run recipe (`.scry/start/<name>.json`) or a path to one. Its keys
are this tool's arguments and fill only what the call does not give; the reply's `profile`
block names it and what it filled. The store is looked for from the server's directory, then
`cwd`.
`display`: the OS's display index for the window, 0 (the main display) when omitted;
`fullscreen`: the window fills it and DOSBox-X captures the mouse, so the guest pointer no
longer follows the host cursor; `size`: `WIDTHxHEIGHT` of the window in the host's unit,
else the largest 4:3 window the display's usable area holds. All three need `shared=true` and
are refused otherwise; `size` is also refused beside `fullscreen`, beyond the usable area
(naming it) and under an `sdl output` that ignores it; a `display` past the host's count is
refused naming the count. The server waits for the window to be listed on that display and
answers `window`; `window` judges the size once the guest runs.
`flags`: argv tokens, a `-set` value one token. `logfile`: the guest's E9 channel, for `log`,
`log_wait`, `drive`. `program` runs after autoexec; `capture_video` records it. `plan` runs
as `perform` does, a step `{"op": <tool>, ...arguments}`, each wait bounded by
`settle_seconds` (default 30). `input_port`: COM1's TCP port, 0 a free one.
`state_dir`: where `state_write` saves; empty, the session's scratch (gone at `close`).
`dos_calls`: record every INT 21h for `log(channel="dos")`, up to the build's row cap; the
server holds the newest 50000 calls it has read, `n` staying the file's number.
`log_categories`: `[log]` category to level, into `logfile`. `guest_files`: host files the
guest should leave, read by `guest_file` and `close`. `symbols`: a table `symbols_load`
reads, judged here and placed at the first stop where DOS holds the program its stem names
(`<stem>.exe`); `base_from` `program` (its own base) or a register, as `symbols_load`
measures one, at a protected-mode stop. That stop's reply says `symbols_placed` once
(`placed`, `path`, `load_segment` in real mode, `base`, `loaded`; refused: `placed:
false`, `code`, `why`); a later `symbols_load` replaces it.

Refused: a live session, a window that never appears on the asked display
(`window_not_visible`, the session left live to `window` or `close`), `flags` setting what
`display`, `fullscreen` or `size` own, `fullscreen` on `sdl output=surface` or, on macOS, on
a display other than 0, a bad path or `symbols` table,
`session_seconds` out of range, `capture_video` without `program`, an `input_port` other than
0 outside 1024-65535, `log_categories` without `logfile`, `dos_calls`
on a build with no `DOSTRACE`, `guest_files` naming a directory, one file twice or more than
16, or a session already live (`session_live`).

Reply: `pid`, `stub`, `window` (`display`, `bounds`, `onscreen`, `front`, `fullscreen`, with
`shared`; `front` says no other application's window covers its centre, not that it has the keyboard focus), `input_port`, `declarations` (`rearm`), `logfile`, `dos_calls`,
`log_categories`, `guest_files` (each when asked for: the log's path as written, the trace's
path, the categories set, each file as it was before the boot), `symbols` (`held`, `base_from`,
`checked`), and with a profile `profile` (`name`, `file`, `supplied`); with `plan`, these
facts sit under `start` beside the plan's account. `note` when the conf or `flags` select a
dynamic cpu core, which can pass over code breakpoints: start on
`flags=["-set", "cpu core=normal"]`.

Reference: REFERENCE.md, The session.

break_on_int3: Also stop at the guest's own `int 3`, where a program marks a break; the debugger's first prompt still comes first.

captures_dir: Where the emulator writes a capture it takes itself; empty, `capture` under the working directory.

background: Launch behind, keeping the caller's focus, or in front; omitted it is behind unless `shared`.

presence: Draw an edge around the emulator's window while this session is open: dim while idle, bright while a call runs the machine. No capture of this server carries it.

overlay: Layers drawn over the presence edge, each on by default: `calls` a caption naming each call and its arguments, abbreviated (paths by their last name); `keys` the keys or fields held down; `pointer` the guest's mouse pointer; `pause` a mark while the session holds the machine stopped; `record` a blinking mark while it records video or audio. `place`: where the captions go, `top`, `bottom`, or `auto`, the band of the picture that shows less. Ignored with `presence=false`.

names: Name the numbers a reply shows: a port, interrupt, address or key gets its name in the reply's `names`, its summary and a disassembled line's note. `false` leaves replies bare; the window's captions keep their names.
```

</details>
<!-- scry-reference:end start -->

<!-- scry-reference:begin status -->
## `status`

Ask whether a session is open and what the machine is doing, without moving it.

```text
status()
```

### Try it

On [Bricks](../../demos/bricks/README.md), right after that start: the machine is stopped at its first instruction.

Ask:

> Is the emulator still up, and where is it stopped?

Call:

```text
status()
```

Reply, 6 of 16 fields:

```json
{
  "summary": "status: alive, stopped",
  "status": "ok",
  "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false},
  "cpu_mode": "real",
  "pc": "F000:0000FFF0",
  "declarations": {"breakpoints": 0, "watches": 0, "regpoints": 0}
}
```

The machine is stopped in real mode at `F000:0000FFF0`, the reset vector. `pending` is empty, so nothing waits for the next stop, and `declarations` counts no saved breakpoint or watch.

<details><summary>The whole reply</summary>

```json
{
  "summary": "status: alive, stopped",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/tour/files/states",
  "last_stop": {
    "stop_seq": 1,
    "pc": "F000:0000FFF0",
    "cause": "no declared code breakpoint at F000:0000FFF0, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
    "since_s": "<volatile>",
    "wall_at": "<volatile>"
  },
  "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false},
  "cpu_mode": "real",
  "pc": "F000:0000FFF0",
  "declarations": {"breakpoints": 0, "watches": 0, "regpoints": 0},
  "presence": true
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `last_stop`: Where the machine last stopped: its `pc` and `cause`, and `since_s`, how long ago. Unavailable, with why, when there is no stop to report.
- `pc`: Where the machine stands now (`SSSS:OOOOOOOO`), read from the registers, so a `set_register` on `CS:IP` shows here; `cpu_mode` is beside it. Unavailable while running.
- `stopped_on_its_own`: Present when the machine had stopped and no call had reported it yet. `status` records that stop as the last one.
- `pending`: What waits for the next stop: `arm`, the breakpoints declared while the program ran; a `disarm` count; and whether a `symbols_load` or a `base_remeasure` is queued.
- `symbols_held`: Present while a `start` symbol table waits for its program: its `path`, its `base_from` and `waiting_for`, the program's file name.
- `knowledge`: How many entries the base serves (`served`) and holds back as not confirmed (`held_back`).

<details><summary>All 21 reply fields</summary>

- `bound_s` (number)
- `bundle` (string)
- `captures` (string)
- `conf` (string)
- `conf_changed_on_disk` (boolean or object)
- `image_changed_on_disk` (boolean or object)
- `conf_digest` (string)
- `cpu_mode` (string or object)
- `declarations` (object)
- `elapsed_s` (number)
- `knowledge` (Counts)
- `names_failed` (object)
- `overlay` (OverlayReply)
- `pc` (string or object)
- `pending` (object)
- `pid` (integer)
- `presence` (boolean or object)
- `state_dir` (string)
- `symbols_held` (object)
- `output_bytes_dropped` (integer)
- `watched` (boolean)

</details>

### Why it works this way

`status` answers in every state: with no session, while the machine runs and once the session is broken. It is where you learn why another tool does not answer.

At a stop it also sets the breakpoints that were declared while the program ran, and says so in `applied_on_stop`.

`session` carries five warnings, each only while it is true: `program`, `range_widened`, `conf_changed_on_disk`, `image_changed_on_disk` and `output_bytes_dropped`.

<details><summary>More on why</summary>

- `conf_changed_on_disk`: the conf file changed since `start`. It is `false` too when the file is gone.
- `image_changed_on_disk`: the executable the loaded symbol table was checked against was written since, as a rebuild under an open session does.
- `output_bytes_dropped`: the emulator printed more than the server keeps.
- `program`: the program that ran inside DOS is gone. It is `state: exited` with `name` and `seen_by`, or `state: fault` with `fault`, the message DJGPP writes as a program dies.
- `program` is read at the stops that answer a call, never while the program runs, so a session that never stops never learns it.

- `presence` is `true` when the border is drawn, `false` when it was asked off, or the reason it is not drawn.
- `overlay` comes with a drawn border: the `layers` drawn, the `place` of the captions and, per layer the build cannot draw, `lacking` with the reason.
- `declarations` counts the server's own saved `breakpoints`, `watches` and `regpoints` (stops on a register condition).
- `last_stop` also carries `stop_seq` and `wall_at`.
- `pid`, `conf`, `conf_digest`, `watched`, `bound_s`, `elapsed_s`, `captures`, `state_dir` and `bundle` describe the process, as `start` set it up.

</details>

### Related tools

- [`start`](#start)
- [`close`](#close)
- [`stop`](run.md#stop)
- [`declaration_list`](breakpoints.md#declaration_list)
- [`symbols_load`](names.md#symbols_load)

<details><summary>The contract your client receives</summary>

```text
What the session is right now. It records a stop no tool has reported
(`stopped_on_its_own`) and applies what was queued while the guest ran
(`applied_on_stop`).

Reply: `last_stop` (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`) and `pending` (`arm`
refs, a `disarm` count, `symbols_load`, `base_remeasure`), both unavailable or empty once a
session has ended; with a session also `presence`, `pid`,
`conf`, `conf_digest`, `conf_changed_on_disk`, `image_changed_on_disk`, `watched`, `bound_s`,
`elapsed_s`, `output_bytes_dropped`, `captures`, `state_dir`, `declarations`, `pc` and
`cpu_mode`;
`symbols_held` (`path`, `base_from`, `waiting_for`) while a `start` table waits for its
program, which costs a memory-chain read at every stop. `session` carries `alive`,
`running`, `altered` and each alarm while it holds.

Reference: REFERENCE.md, What every reply carries.
```

</details>
<!-- scry-reference:end status -->

<!-- scry-reference:begin window -->
## `window`

Find where the session's window is on your displays and whether another window covers it, or bring it in front.

```text
window(front=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), started with `shared=true` so that it has a window to report.

Ask:

> Where is the emulator's window, and can I see it?

Call:

```text
window()
```

Reply, 1 of 3 fields:

```json
{
  "status": "ok"
}
```

The run hides the `window` block and the summary here, because where the window is differs on every host. `status` is `ok`: the host listed the window.

<details><summary>The whole reply</summary>

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "window": "<volatile>"
}
```

</details>

### Arguments

- `front` (boolean, default `false`): `true` brings the window in front of whatever covers it and reads the result back. Left out, the window is reported where it is and nothing moves.

### What comes back

- `window`: Where it is: `display`, `bounds`, `onscreen`, `fullscreen` and `front`. `front` is `true` when no other application's window covers its centre; it does not mean the window has the keyboard focus.
- `size`: Only when `start` named a `size`: what was `asked`, what is `seen`, and whether it `matches` within `tolerance_px`.

<details><summary>All 5 reply fields</summary>

- `activation` (string)
- `asked_display` (integer)
- `seen` (object)
- `size` (object)
- `window` (object)

</details>

### What it refuses

- No session is open (`no_session`).
- The session's emulator died (`session_broken`).
- The session was started without `shared`, so there is no watched window to report (`no_channel`).
- The window never appears, or with `front` is still covered after it was activated. `seen` says what the host listed (`window_not_visible`).

### Why it works this way

`front` answers one question: can a person see the picture? It is `true` when the window is on screen and no other application's window covers its centre. It is not the keyboard focus, which a window nothing covers can be without.

`window` answers at any time, a running program included. Without `front` it moves nothing and reports the window wherever you put it. With `front`, a session started with `background=true` may stay behind, and the refusal names that as the likely cause.

A `size` given to `start` is checked here and not there, because the window takes that size at the program's first video mode. Until the program has run it reads the emulator's own size, and the `note` says to `resume` and ask again. The size the server chose by itself is never checked.

<details><summary>More on why</summary>

- `compared` says which rectangle was measured: `client`, the area inside the frame, on Windows; `outer` on macOS, which has no client area, so a title bar's height is allowed.
- `height_free` is `true` when the emulator fits the height to the picture's aspect by itself, so only the width is checked.
- `display` is the operating system's index, and `fullscreen` is `true` when the window's bounds are the display's.
- On a `window_not_visible` refusal, `asked_display` is the display `start` asked for and `activation` what bringing it forward answered.

</details>

### Related tools

- [`start`](#start)
- [`status`](#status)
- [`snapshot`](captures.md#snapshot)

<details><summary>The contract your client receives</summary>

```text
Where the watched window is on the host, at any time, a running guest included. `front`
brings it in front of whatever covers it and reads that back.

Reply: `window` (`display`, the OS's index; `bounds`; `onscreen`; `front`, on screen with no other application's window covering its centre; `fullscreen`); `size` when the session was started with a stated `size`: `asked`, `seen`, which rectangle was `compared` (`client` or `outer`), `tolerance_px`, `height_free` and `matches`.

Refused: no session (`no_session`), one that died (`session_broken`), a session started without `shared` (`no_channel`), a window that never appears or, with `front`, is still covered after the activation (`window_not_visible`, naming what was seen; on a `background=true` session it names that as what may keep it behind). Without `front` the window is answered wherever the owner put it.

Reference: REFERENCE.md, The session.
```

</details>
<!-- scry-reference:end window -->

<!-- scry-reference:begin close -->
## `close`

End the session and the emulator with it, and learn how it ended.

```text
close(detail=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), at the end of the example session's session.

Ask:

> We are done: close the emulator and tell me how it ended.

Call:

```text
close()
```

Reply, 6 of 16 fields:

```json
{
  "summary": "close: quit, exit code 0",
  "status": "ok",
  "closed": true,
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"]
}
```

DOSBox-X quit when asked, with exit code 0. `omitted` names the last lines it printed, which a clean quit leaves out.

<details><summary>The whole reply</summary>

```json
{
  "summary": "close: quit, exit code 0",
  "status": "ok",
  "closed": true,
  "pid": "<volatile>",
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/tour/files/states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>"
}
```

</details>

### Arguments

- `detail` (boolean, default `false`): `true` returns the last lines the emulator printed (`stdout_tail`, `errorlog_tail`) after a clean quit too. Left out, they come only when the end was not clean.

### What comes back

- `closed`: `true` when a session was ended; `false` when there was none to close.
- `ended_by`: How it ended: `quit`, `killed`, `died` or `none`.
- `exit_code`: The emulator's exit code. It is `available: false` with a `why` when no session was running or the killed process could not be collected.
- `pid`: The process this call ended, or `available: false` with a `why` when no session was running.
- `guest_files`: Each file `start` named in `guest_files`, with the `state` that `guest_file` reports for it.
- `draft`: The names of what the session saved and `promote` has not yet written into your repository's `.scry/` folder.

<details><summary>All 18 reply fields</summary>

- `draft` (array of string)
- `bound_s` (number)
- `bundle` (string)
- `captures` (string)
- `closed` (boolean)
- `conf` (string)
- `conf_changed_on_disk` (boolean or object)
- `image_changed_on_disk` (boolean or object)
- `conf_digest` (string)
- `elapsed_s` (number)
- `ended_by` (string)
- `errorlog_tail` (string or object)
- `guest_files` (array)
- `pid` (integer or object)
- `state_dir` (string)
- `stdout_tail` (string)
- `output_bytes_dropped` (integer)
- `watched` (boolean)

</details>

### Why it works this way

`close` ends the session now instead of leaving it to `session_seconds`. It asks DOSBox-X to quit and kills it only when the request is ignored; `ended_by` says which happened.

`session` describes the state after the close: `alive`, `running` and `altered` are `false`, as with no session.

The reply also says what the process was, in `status`'s fields, read before the end. So `pid` is the process this call ended.

<details><summary>More on why</summary>

- `quit`: DOSBox-X left when asked. A session started here does, with or without a program loaded, because `start` turns its quit warning off.
- `killed`: a conf that turns the warning back on, or a program that ignored the request. `exit_code` is unavailable if the process is still not collected.
- `died`: it had already exited.
- `none`: there was no session.

- The request is SIGTERM on macOS and the debugger's `QUIT` on Windows, which has no signal to ask with; the kill is SIGKILL, or a terminate on Windows.
- A `note` says the emulator's output was not read to its end, so the last lines may be short.

</details>

### Related tools

- [`start`](#start)
- [`status`](#status)
- [`promote`](project.md#promote)
- [`guest_file`](files.md#guest_file)

<details><summary>The contract your client receives</summary>

```text
End the session deliberately rather than waiting for its bound.

Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid` and
`exit_code`, each an integer, or unavailable with its `why` when no session was running;
`stdout_tail` and `errorlog_tail` when the end was not a clean `quit`, or with `detail=True`;
`note` when the output was not read to its end. `guest_files`: each file `start` named, with
`guest_file`'s `state`. `session` is the block as it is after the close (`alive` and
`running` false), and `draft` names the candidates the session left waiting for `promote`.
```

</details>
<!-- scry-reference:end close -->
