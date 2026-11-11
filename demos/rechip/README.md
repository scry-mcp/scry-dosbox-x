# ReChip!: a program boots from its own recipe and says what the keys did

![ReChip!'s tracker with the demo song paused](screen.png)

*ReChip!* is a converter of music to vintage sound chips with a live tracker, a 32-bit DOS
program. This demo boots its DEV build from the run recipe its own repository declares in
`.scry/start/dev.json`: the line `make mcp-conf` prints there, the demo song opened unattended,
the conf with its boot line removed, and the E9 log the build writes. The call gives only what is
the run's own, and the reply says which keys the recipe filled.

It then reads the program's own log for the line that says the song sounds, pauses it with a key
the program logs by name, stops the machine for a picture, and leaves the program by its own
keys, the confirm's answer read off the log, before closing the session.

## The program

ReChip! is not distributed with this repository. The demo needs a checkout of it after `make mcp-conf`, which builds `RECHIPD.EXE` and derives the conf; that
checkout is what `--cwd` names.

## Run it

```sh
uv run python demos/rechip/demo.py --cwd /path/to/rechip
```

- `--cwd PATH` (absolute or `~`-led) is the program's own repository checkout.
- `--binary PATH` picks the DOSBox-X to start; left out, `DOSBOX_X_BINARY`, else the `dosbox-x`
  on your `PATH`.
- The window opens in front.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below, `TRANSCRIPT.md` and `screen.png` from a run where
  every step passed.

Each line it prints is one call and its check. Exit codes: 0 every step passed, 1 a step failed,
2 a usage error, 3 nothing was demonstrated (a checkout without its recipe or its build, a
relative path, a server that did not start).

## The prompt

Give this to an MCP client with this server connected:

> Start from the recipe `.scry/start/dev.json` in the `--cwd` checkout, with a window, and let
> it run. Wait on the guest log for `PERF  . audio play=1`, press space and show me that the
> program logged `key down SPACE`, wait for `ACT   . play=0`, stop, save a picture of the screen,
> resume, press alt+x and wait for `ask opens`, press right then enter and wait for `ask res=1`,
> and close.

## What it walks

<!-- demo-flow:begin rechip -->
<!-- demo-flow:end rechip -->

## The transcript

<!-- demo-transcript:begin -->
The run is 11 calls; these are the ones that show how it is done, and every call with its reply is in [TRANSCRIPT.md](TRANSCRIPT.md).

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

`start(profile=...)` boots from the recipe the program's own repository declares: the line `make mcp-conf` prints, the DEV build opening the demo song unattended, the conf with its boot line removed, the E9 log. The call gives only what is the run's own, and the reply says which keys the recipe filled.

<details><summary>call and reply</summary>

```json
{
  "profile": "<host>",
  "shared": true,
  "captures_dir": "<host>",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "<volatile>",
  "conf_digest": "<volatile>",
  "watched": true,
  "bound_s": 14400,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "<volatile>",
  "shared": true,
  "ready_after_s": "<volatile>",
  "argv": "<volatile>",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger_commands": ["A20", "BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "MEMDUMPLIN", "PIC", "PORTINFO", "PRESENCE", "RUNSTATE", "SAVESTATE", "STEPIN", "TAP", "VGAMEMDUMP"],
  "stub": "./src/scry_dosbox_x/guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": false,
  "presence": true,
  "window": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "note": "this session runs the dynamic core, which checks breakpoints only between compiled blocks, so a code breakpoint inside one can be passed over and a run that never reaches it proves nothing. Start on the normal core: `start(flags=[\"-set\", \"cpu core=normal\"])`",
  "kept": "kept 1 (promote to review)",
  "profile": {
    "name": "<volatile>",
    "file": "<volatile>",
    "supplied": ["conf", "logfile", "program", "session_seconds"]
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `log_wait`**: OK sounding: the app is up and the song sounds

The program's own log says when it is up and when the song sounds, two different lines: `log_wait` on the guest channel waits for the second, on a running machine.

<details><summary>call and reply</summary>

```json
{
  "pattern": "PERF  \\. audio play=1",
  "channel": "guest",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "PERF  \\. audio play=1",
  "channel": "guest",
  "line": "<volatile>",
  "already": "<volatile>",
  "lines_total": "<volatile>",
  "lines_before": "<volatile>",
  "arrived_during": "<volatile>",
  "waited_s": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**4. `send_keys`**: OK pause: space reached the app

`send_keys` with `expect` proves the key reached the application, not only that the host sent one: the program logs every key it takes, by name.

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"],
  "expect": "key down SPACE",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "key down SPACE",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**10. `send_keys`**: OK confirm: Quit without saving

The program is left by its own keys, and its log says which button the confirm took, so the session closes over a guest that has quit rather than one killed under a running program.

<details><summary>call and reply</summary>

```json
{
  "keys": ["right", "enter"],
  "expect": "ask res=1",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["right", "enter"],
  "modifiers": [],
  "route": "guest",
  "posted": 2,
  "bytes": 6,
  "frames": 6,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ask res=1",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->
