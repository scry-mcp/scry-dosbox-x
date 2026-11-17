# Speed Fight: the PC game boots from its own recipe

![Speed Fight's title on the PC](screen.png)

*Speed Fight* (Eco-Games / GAMART, 1994) ran on an NEC V30 arcade board, and its team ported the
same source to MS-DOS. This demo boots the PC game from the run recipe its own repository
declares in `.scry/start/dos.json`: the conf the game's script derives, the working directory,
the program spelled from where the autoexec leaves the guest, and the TLINK map that names its
variables. The call gives only what is the run's own, and the reply says which keys the recipe
filled.

It then runs to the routine the title calls once both its planes are drawn, reads the credits
by name, and saves a picture of the screen. Every arrival is a place in the game's code, on the
normal core and a fixed clock: the dynamic core the game's conf keeps can pass a code breakpoint
over, and its `cycles=max` would hand the game as many cycles a second as the host can.

## The game

Speed Fight is not distributed with this repository. The demo needs a copy of it with its blessed `EXES/SPEEDF.EXE` and `EXES/SPEEDF.MAP`, its `.scry/` and
its `SCRIPTS/`; a checkout of it is what `--cwd` names.

## Run it

```sh
uv run python demos/speedf/demo.py --cwd /path/to/speedf-msdos
```

- `--cwd PATH` (absolute or `~`-led) is the game's own repository checkout.
- `--binary PATH` picks the DOSBox-X to start; left out, `DOSBOX_X_BINARY`, else the `dosbox-x`
  on your `PATH`.
- `--display N` opens the window on that display; left out, on the host's main one. The
  window opens behind, so the run takes nobody's focus.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below, `TRANSCRIPT.md`, `screen.png` and `loop.mp4` from a run where
  every step passed.

Each line it prints is one call and its check. Exit codes: 0 every step passed, 1 a step failed,
2 a usage error, 3 nothing was demonstrated (a copy without its store or its program, a relative
path, a server that did not start, a loop that could not be converted).

## The prompt

Give this to an MCP client with this server connected:

> Derive the game's live-session conf with `SCRIPTS/dosbox-mcp-conf.sh`, then start from the
> recipe `.scry/start/dos.json` in the `--cwd` checkout, with a window, the normal core and
> `cycles=fixed 50000`. Stop
> at the game's first VESA call (`INT 10h AH=4Fh`) so its map is placed, run to
> `titulo_dibuja_cred` counting `draw_block` on the way, read `creditos`, save a picture of the
> screen and close.

## The transcript

<!-- demo-transcript:begin -->
The run is 9 calls; these are the ones that show how it is done, and every call with its reply is in [TRANSCRIPT.md](TRANSCRIPT.md).

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

`start(profile=...)` boots from the recipe the game's own repository declares: the conf its script derives, the working directory, the program spelled from where the autoexec leaves the guest, and the TLINK map. The call gives only what is the run's own, and the reply says which keys the recipe filled.

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "profile": "<host>",
  "flags": ["-set", "cpu core=normal", "-set", "cpu cycles=fixed 50000"],
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
  "bound_s": 900,
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
  "background": true,
  "presence": true,
  "window": "<volatile>",
  "logfile": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "symbols": {
    "held": "<volatile>",
    "base_from": "program",
    "checked": {
      "available": false,
      "why": "the table carries no symbol kinds (a link map lists none), so its code symbols cannot be told from the rest"
    }
  },
  "kept": "kept 1 (promote to review)",
  "profile": {
    "name": "<volatile>",
    "file": "<volatile>",
    "supplied": ["conf", "logfile", "program", "session_seconds", "symbols"]
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `run_to`**: OK title: stopped at titulo_dibuja_cred

The run arrives by the game's own routine, not by time: `run_to` stops where the title calls its credits line, once both planes are drawn, so the picture that follows is the same on any host.

<details><summary>call and reply</summary>

```json
{
  "ref": "titulo_dibuja_cred",
  "control": "draw_block",
  "seconds": 120
}
```

```json
{
  "summary": "run_to titulo_dibuja_cred: TARGET at 0951:00000819, control counted 35",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08EB:0E79",
  "ref": "titulo_dibuja_cred",
  "pc": "0951:00000819",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 35,
  "controls": [
    {"ref": "draw_block", "at": "08EB:46F4", "hits_in_run": 35, "removed": true}
  ],
  "frame": 125,
  "regs": {
    "EAX": "0x0000491e",
    "EBX": "0x00007fff",
    "ECX": "0x005b0000",
    "EDX": "0x00000089",
    "ESI": "0x0000c7cb",
    "EDI": "0x0000bfcb",
    "EBP": "0x0000b1aa",
    "ESP": "0x0000b19e",
    "EIP": "0x00000819",
    "CS": "0x0951",
    "DS": "0x1b73",
    "ES": "0x491e",
    "FS": "0x0008",
    "GS": "0x0000",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "run_to's target titulo_dibuja_cred at 0951:00000819",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "0951:00000819",
    "bytes": "52",
    "text": "push dx",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "titulo_dibuja_cred",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `read_memory`**: OK no credits: creditos holds 0

`creditos` is read by name: the map `start` placed names the game's own variables at the segment DOS loaded it at, the same name the arcade build's map gives.

<details><summary>call and reply</summary>

```json
{
  "ref": "creditos",
  "length": 2
}
```

```json
{
  "summary": "read_memory creditos: 2 bytes at 26AB:00000006: 0000",
  "status": "ok",
  "ref": "creditos",
  "seg_off": "26AB:00000006",
  "length": 2,
  "hex": "0000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->
