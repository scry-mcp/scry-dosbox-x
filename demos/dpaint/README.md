# Deluxe Paint: a sunset painted through the debugger, and the byte that holds the colour

![A sunset painted in Deluxe Paint II through the server: the sun sinking into the sea, a boat and the word SCRY](screen.png)

Electronic Arts' Deluxe Paint II, the 1988 PC version, paints a sunset here with every stroke
sent by the server: tools and colours are picked by name off a screen map, each shape is a drag
of the guest's own mouse, and the picture is checked by reading its pixels back out of video
memory. Halfway through, the demo does what no mouse macro can: it picks two colours off the
palette with a value scan between the clicks, finds the bytes where the program keeps its
current colour, tells the four static ones from the copies in the stack's frames, and watches
the first, so every later pick shows its colour at the stop it lands on.

[`demos/dpaint_maps/`](../dpaint_maps/README.md) drives the same program at 640 x 480 through
its menus and a dialog, every screen found off a map of eleven.

## The program

Deluxe Paint II is Electronic Arts' commercial software, and nothing of it is in this
repository: the demo carries its prompt, its script, its conf and its screen map, and runs the
program from a directory you name. It needs version 1.0, the 1988 release on one 720k disk,
copied off the disk into a directory of its own (the disk's files, `DP.EXE` among them; its
installer is not needed). The demo checks `DP.EXE` before anything starts and refuses another
build, naming its digest, because the address of the colour and the picture are that release's.
The session's log and saved states go under this repository's `tmp/`, and nothing the run writes
stays in your directory.

## Run it

```sh
uv run python demos/dpaint/demo.py \
  --cwd /path/to/your/dpaint2
```

The demo opens a window, scaled up four times by its conf, so the painting can be watched; nothing
in it needs the window. Deluxe Paint takes the mouse as movement events, so it needs a DOSBox-X
whose input device carries relative motion (the repository's REFERENCE.md, *Debugger commands*),
named with `--binary` or `DOSBOX_X_BINARY`; on a build without it the demo stops at its
third step, saying so, because a drag would paint nothing between its button events.

- `--cwd PATH` (absolute or `~`-led) is the directory holding `DP.EXE`, which the session runs
  from and mounts as C:. It is hidden in the transcript as `<host>`.
- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start; left out,
  `DOSBOX_X_BINARY`, else the `dosbox-x` on your `PATH`.
- `--display N` opens the window on that display; left out, on the host's main one. The
  window opens behind, so the run takes nobody's focus.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below, `TRANSCRIPT.md`, `screen.png` and `loop.mp4` from a run where every step
  passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2
a usage error, 3 nothing was demonstrated (no program directory, another build of it, a
DOSBox-X without relative motion, a server that did not start, a loop that could not be converted).

## The prompt

Give this to an MCP client with this server connected:

> Start DOSBox-X windowed on `demos/dpaint/dpaint.conf`,
> running from `/path/to/your/dpaint2`, with `DP.EXE f` as the
> program and the log in a file. Load the screen map
> `dpaint-screen-map.json` beside the conf, run until it names the painting screen, and tell me
> where DOS loaded the program and so where its data segment is. Pick blue off the
> palette, start a value scan of the data segment, keep what holds 9; pick orange, keep what
> holds 55, and tell me which survivors are static data and which are in the stack's frames.
> Close the scan and watch the first static one, then paint a sunset, one call a shape: a peach
> sky as a filled rectangle, a yellow sun as a filled circle on the horizon, a navy sea over its
> lower half, a brown hull with the rectangle tool still in hand, a white sail drawn with lines,
> and SCRY typed with the text tool. After
> every colour, tell me what the watched byte shows. Read a row across the sun and one across
> the boat to prove the colours landed, show me the screen, clear the watch and close.

## What it walks

| Family | Calls |
|---|---|
| Session | `start` (windowed, running the program from `cwd`), `close` |
| Advance | `screen_wait` until the map names the painting screen: the program has no symbols, no log and no place that runs once per change |
| Input | `send_mouse` by control name off the map, at screen pixels, and as drags; `send_keys` for the word |
| Scan | `scan` (`start`, `filter` twice, `clear`) |
| Declarations | `watch_add` (the colour byte in view at every stop), `declaration_clear(kind="watch")` |
| Lists | `perform` (one shape a call: its tool, its colour, its drags) |
| Read | `screen_map_write(method="load")`, `screen_map_find`, `read_memory` of rows of video memory |
| Screen | `screen_view` |
| Captures | `record` (the loop) |

## The transcript

Generated by `demo.py --update-readme` from a run where every step passed. What differs between
two honest runs (process ids, ports, wall-clock times, temporary paths, the host's own DOSBox-X
and its own arguments) is `<volatile>`, and the program's directory is `<host>`.

<!-- demo-transcript:begin -->
The run is 24 calls; these are the ones that show how it is done, and every call with its reply is in [TRANSCRIPT.md](TRANSCRIPT.md).

**6. `send_mouse`**: OK blue: blue picked off the palette

Tools and colours are picked by name: the screen map says where `blue` sits on the palette, and `send_mouse` with a `target` moves the guest's own mouse driver there and presses. The script holds no coordinates.

<details><summary>call and reply</summary>

```json
{
  "target": "blue",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 300,179, program's own pointer not read; posted, unverified, 21 retraces to frame 28",
  "status": "ok",
  "x": 300,
  "y": 179,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 300, "y": 179, "width": 320, "height": 200},
    "mouse": {"x": 2404, "y": 1436, "max_x": 2552, "max_y": 1592},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "polls": 21,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 23,
  "frame": 28,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "target": "blue",
  "screen": "paint",
  "identified_at_stop": 2,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `scan`**: OK is orange: 7 bytes followed both clicks: 3 in the stack's frames above the stack pointer, and 4 static ones from 31B2:017C

A value scan, the cheat finder's trick done through a debugger. The first scan kept every byte of the data segment, the filter after picking blue kept those holding blue's index, and this one, after orange, keeps those that held each in turn. The survivors are of two kinds, told apart by where they live: copies in the stack's frames, and static bytes in the data segment.

<details><summary>call and reply</summary>

```json
{
  "method": "filter",
  "value": 55
}
```

```json
{
  "summary": "scan filter: = 55, 7 survivors",
  "status": "ok",
  "operator": "=",
  "value": "0x37",
  "iterations": 2,
  "closed": false,
  "hits": [
    {"seg_off": "31B2:0000017C", "addr": "0x00031c9c", "value": "0x37"},
    {"seg_off": "31B2:000001AE", "addr": "0x00031cce", "value": "0x37"},
    {"seg_off": "31B2:00000470", "addr": "0x00031f90", "value": "0x37"},
    {"seg_off": "31B2:000010B0", "addr": "0x00032bd0", "value": "0x37"},
    {"seg_off": "31B2:0000A57E", "addr": "0x0003c09e", "value": "0x37"},
    {"seg_off": "31B2:0000A57F", "addr": "0x0003c09f", "value": "0x37"},
    {"seg_off": "31B2:0000A580", "addr": "0x0003c0a0", "value": "0x37"}
  ],
  "hits_total": 7,
  "truncated": false,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `read_memory`**: OK sun row: the row reads peach x 25, then yellow x 51, then peach x 52

The picture is checked by reading it back: a row of the screen comes out of video memory as colours and run lengths, in the order the strokes were painted.

<details><summary>call and reply</summary>

```json
{
  "ref": "A000:7DA0",
  "length": 128
}
```

```json
{
  "summary": "read_memory A000:7DA0: 128 bytes at A000:00007DA0: 343434343434343434343434343434343434343434343434340e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e... (64 more bytes in `hex`)",
  "status": "ok",
  "ref": "A000:7DA0",
  "seg_off": "A000:00007DA0",
  "length": 128,
  "hex": "343434343434343434343434343434343434343434343434340e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e34343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->
