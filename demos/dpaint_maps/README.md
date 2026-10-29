# Deluxe Paint by screen maps: menus, a dialog and the tool in hand, found by name

![A sunset painted in Deluxe Paint II at 640 x 480 through the server: an orange sky mixed in the Palette dialog with SCRY typed in it, the sun on the horizon, and a boat stamped mirrored across the bay](screen.png)

Electronic Arts' Deluxe Paint II, the 1988 PC version, at VGA 640 x 480 in 16 colours: every
menu, dialog button, tool and colour is picked by the name a screen map gives it, and the shapes
are dragged at pixels. Its menus drop only while the button is held, so the demo opens one with a
press on its title and chooses with the release over an item; after every move to another screen
it asks the map where it landed, and the map knows each open menu, the Palette dialog, and the
painting screen in the state of whichever tool is in hand. In the dialog it mixes an orange out of
the brown slot and reads it back off the VGA DAC; then it paints a sunset, types SCRY into the sky
with the text tool, lifts the boat it drew as a brush, flips it with the Brush menu and stamps the mirror image across the bay. Last it opens
the Pict menu and lets go over its title, which chooses nothing and leaves the painting screen as
it was. The picture is checked by reading rows of it back out of the four bit planes, so a shape a
pixel short, or a boat that did not flip, fails the run.

The first Deluxe Paint demo, [`demos/dpaint/`](../dpaint/README.md), maps one screen at 320 x 200
and stops halfway for a value scan; this one maps eleven, the menus and the dialog among them.

## The program

Deluxe Paint II is Electronic Arts' commercial software, and nothing of it is in this
repository: the demo carries its prompt, its script, its conf and its screen map, and runs the
program from a directory you name. It needs what the first demo needs: version 1.0, the
1988 release on one 720k disk, copied off the disk into a directory of its own. The demo checks
`DP.EXE` before anything starts and refuses another build, naming its digest, because the
toolbox and the picture are that release's. The session's log and saved states go under this
repository's `tmp/`, and nothing the run writes stays in your directory.

## Run it

```sh
uv run python demos/dpaint_maps/demo.py \
  --cwd /path/to/your/dpaint2
```

The demo opens a window, scaled up twice by its conf, so the menus can be watched as they open;
nothing in it needs the window. Like the first demo it needs a DOSBox-X whose input device
carries relative motion (the repository's REFERENCE.md, *Input and the screen*), named with
`--binary` or `DOSBOX_X_BINARY`; without it the demo stops at its second step, saying so.

- `--cwd PATH` (absolute or `~`-led) is the directory holding `DP.EXE`, which the session runs
  from and mounts as C:. It is hidden in the transcript as `<host>`.
- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start; left out,
  `DOSBOX_X_BINARY`, else the `dosbox-x` on your `PATH`.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below and `screen.png` from a run where every step
  passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2
a usage error, 3 nothing was demonstrated (no program directory, another build of it, a
DOSBox-X without relative motion, a server that did not start).

## The map

`dpaint.screen-map.json` names eleven screens of Deluxe Paint at 640 x 480, each known by regions
that stay still on it:

| Screen | Known by | Its names |
|---|---|---|
| `paint: freehand`, `paint: rectangle`, `paint: circle`, `paint: line`, `paint: grab`, `paint: text` | the menu bar at rest and that tool's cell, inverted | `pict`, `brush`, `color`; `freehand`, `line`, `rect_filled`, `circle_filled`, `brush_grab`, `text`; `black`, `blue`, `brown`, `yellow`; `brush_dot`, the one-pixel brush |
| `paint: custom brush` | the menu bar at rest, the dotted freehand tool lit and no built-in brush lit: a brush lifted off the picture is in hand | the same |
| `color menu` | the body of the open menu | `palette`, `color` |
| `brush menu` | the body of the open menu | `flip_horizontal`, `brush` |
| `pict menu` | the body of the open menu | `pict` |
| `palette` | the dialog's title and its buttons | `brown`, the slot; `red_up`, `green_up`, `blue_up`; `ok`, `cancel` |

The map names what the demo uses and, in the dialog, the buttons beside them. The swatches keep the default palette's names, so the slot
the dialog mixes to orange is still `brown`. The pointer is parked over the toolbox before a painting screen is read, because on the
canvas a shape tool draws it as a crosshair across the whole screen, through the regions the
map signs.

## The prompt

Give this to an MCP client with this server connected:

> Start DOSBox-X windowed on `demos/dpaint_maps/dpaint_maps.conf`, running from
> `/path/to/your/dpaint2`, with `DP.EXE k` as the program and the log in a file. Run 400 retraces and load the screen map `dpaint.screen-map.json` beside the conf. Pick
> menus, dialog buttons, tools and colours by the names it gives, drag the shapes at pixels, and
> after every move to another screen tell me which screen the map says it is. Hold the button on
> Color, choose Palette, pick the brown slot and hold the red arrow down until red tops out, read
> that slot off the DAC, and press OK. Paint a sunset, a few shapes a call: a sky in the
> brown slot as a filled rectangle, a yellow sun as a filled circle on the horizon, a blue sea
> over its lower half, three yellow glints as lines, a black hull, a black mast and a yellow
> sail. Pick black and the text tool, click the sky at 40,60, type SCRY and pick the freehand
> tool to end the text. Lift the boat with the brush tool, hold Brush and choose Flip Horizontal, stamp it
> across the bay, then hold Pict and let go over its title, which chooses nothing. Put the lifted
> brush down by picking the one-pixel brush and the freehand tool, read rows across the word,
> the sun, the glints, the sails and the hulls, show me the screen and close.

## What it walks

| Family | Calls |
|---|---|
| Session | `start` (windowed, running the program from `cwd`), `close` |
| Advance | `run_for` by retraces on the conf's fixed clock |
| Files | `screen_map_write(method="load")` |
| Input | `send_mouse` by control name off the map (a press to open a menu, a release to choose), at screen pixels, and as drags; `send_keys` for the word |
| Read | `screen_map_find` after every move between screens, `palette` for the mixed colour, `screen_view` for rows of the picture and the screen |
| Lists | `perform` (each move with the map's word on where it landed; a shape's tool, colour and drags) |

## The transcript

Generated by `demo.py --update-readme` from a run where every step passed. What differs between
two honest runs (process ids, ports, wall-clock times, temporary paths, the host's own DOSBox-X
and its own arguments) is `<volatile>`, and the program's directory is `<host>`.

<!-- demo-transcript:begin -->
**1. `start`**: OK start: DOSBox-X in a window, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./demos/dpaint_maps/dpaint_maps.conf",
  "session_seconds": 900,
  "shared": true,
  "program": "DP.EXE k",
  "logfile": "./tmp/demos/dpaint_maps/dpaint-maps-e9.log",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/dpaint_maps/dpaint_maps.conf",
  "conf_digest": "daae6ab9a0232442",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
  "shared": true,
  "ready_after_s": "<volatile>",
  "argv": "<volatile>",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger_commands": ["BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "PORTINFO", "PRESENCE", "RUNSTATE", "SAVESTATE", "STEPIN", "TAP", "VGAMEMDUMP"],
  "stub": "./guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": false,
  "presence": true,
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `run_for`**: OK loaded: 400 retraces: Deluxe Paint is up, its data segment at 0x31b0

<details><summary>call and reply</summary>

```json
{
  "frames": 400,
  "seconds": 60
}
```

```json
{
  "summary": "run_for 400 frames: ELAPSED, 400 polls, at 0E83:00000A83",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 400,
  "pc": "0E83:00000A83",
  "cpu_mode": "real",
  "frame": 400,
  "regs": {
    "EAX": "0x00006e42",
    "EBX": "0x000003e4",
    "ECX": "0x005b0000",
    "EDX": "0x0000a57c",
    "ESI": "0x00000007",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a006",
    "ESP": "0x0000a004",
    "EIP": "0x00000a83",
    "CS": "0x0e83",
    "DS": "0x31b0",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b0"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0E83:00000A83",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=6 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "0E83:00000A83",
    "bytes": "50",
    "text": "push ax",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "emulated_before_s": 0.0007,
  "emulated_after_s": 6.6465891,
  "frame_before": 0,
  "frame_after": 400,
  "cycles": 65734013,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_map_write`**: OK map: 11 screens and 109 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/dpaint_maps/dpaint.screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 11 screens, 109 controls of dpaint",
  "status": "ok",
  "path": "./demos/dpaint_maps/dpaint.screen-map.json",
  "application": "dpaint",
  "mode": "verified",
  "screens": 11,
  "controls": 109,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `screen_map_find`**: OK is paint: the map says: paint: freehand

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: paint: freehand (file), 14 controls",
  "status": "ok",
  "matched": true,
  "screen": "paint: freehand",
  "layer": "file",
  "kind": "pixel",
  "size": [640, 480],
  "controls": [
    {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
    {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
    {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
    {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
    {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
    {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
    {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
    {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
    {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
    {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
    {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
    {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
    {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
    {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `perform`**: OK open Color: the map named color menu

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "color", "button": "left", "action": "down"},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 2 of 2 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 251,5; posted, unverified, 16 retraces to frame 416",
        "status": "ok",
        "stop_seq": 18,
        "cause": "the retrace the input's post ran to, at 0955:0000035D"
      }
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: color menu (file), 2 controls",
        "status": "ok",
        "matched": true,
        "screen": "color menu",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "palette", "rect": [232, 13, 170, 11], "centre": [317, 18]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 3,
    "stop_seq_last": 18,
    "surveyed": 1,
    "by_cause": {"the retrace the input's post ran to,": 1},
    "unaccounted": 15
  },
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `perform`**: OK choose Palette: the map named palette

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "palette", "button": "left", "action": "up"},
    {"op": "run_to", "screen": "palette"},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 3 of 3 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 317,18; posted, unverified, 20 retraces to frame 436",
        "status": "ok",
        "stop_seq": 38,
        "cause": "the retrace the input's post ran to, at 0DA5:000002C1"
      }
    },
    {
      "step": 1,
      "op": "run_to",
      "reply": {
        "summary": "run_to screen palette (judged): TARGET at 0DA5:000000D3",
        "status": "ok",
        "stop_seq": 39,
        "cause": "the retrace a run to a screen ran to, at 0DA5:000000D3"
      }
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: palette (file), 6 controls",
        "status": "ok",
        "matched": true,
        "screen": "palette",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "brown", "rect": [91, 57, 18, 4], "centre": [100, 59]},
          {"name": "red_up", "rect": [4, 34, 7, 10], "centre": [7, 39]},
          {"name": "green_up", "rect": [18, 34, 7, 10], "centre": [21, 39]},
          {"name": "blue_up", "rect": [32, 34, 7, 10], "centre": [35, 39]},
          {"name": "ok", "rect": [10, 143, 55, 12], "centre": [37, 149]},
          {"name": "cancel", "rect": [138, 143, 60, 12], "centre": [168, 149]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 19,
    "stop_seq_last": 39,
    "surveyed": 2,
    "by_cause": {"the retrace the input's post ran to,": 1, "the retrace a run to a screen ran to,": 1},
    "unaccounted": 19
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `perform`**: OK mix: the brown slot picked, and red's arrow held from the press to the release

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "brown", "button": "left"},
    {"op": "send_mouse", "target": "red_up", "button": "left", "action": "down"},
    {"op": "send_mouse", "button": "left", "action": "up"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 3 of 3 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 100,59; posted, unverified, 24 retraces to frame 461",
        "status": "ok",
        "stop_seq": 63,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 7,39; posted, unverified, 20 retraces to frame 481",
        "status": "ok",
        "stop_seq": 83,
        "cause": "the retrace the input's post ran to, at F000:0000CBE5"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 7,39; posted, unverified, 15 retraces to frame 496",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {"x": 7, "y": 39, "width": 640, "height": 480},
          "mouse": {"x": 60, "y": 316, "max_x": 5112, "max_y": 3832},
          "buttons": [],
          "bios_mode": "0x12"
        },
        "arrived": true,
        "polls": 15,
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 98,
        "frame": 496,
        "instruction": {
          "address": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x000001b8",
          "EBX": "0x00000178",
          "ECX": "0x005b0003",
          "EDX": "0x00000000",
          "ESI": "0x0000ffff",
          "EDI": "0x00000000",
          "EBP": "0x00009fa8",
          "ESP": "0x00009f94",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [],
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 40,
    "stop_seq_last": 98,
    "surveyed": 3,
    "by_cause": {"the retrace the input's post ran to,": 3},
    "unaccounted": 56
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `palette`**: OK orange: the brown slot now holds #ff5500, orange

<details><summary>call and reply</summary>

```json
{
  "first": 6,
  "count": 1,
  "dest": "./tmp/demos/dpaint_maps/orange.png"
}
```

```json
{
  "summary": "palette: entry 6 #ff5500 of 256; 128x128 PNG x8, inline",
  "status": "ok",
  "entries": 256,
  "first": 6,
  "count": 1,
  "colors": ["#ff5500"],
  "rgb": ["3f1500"],
  "bits": 6,
  "pel_mask": "ffh",
  "image": {
    "path": "./tmp/demos/dpaint_maps/orange.png",
    "bytes": 927,
    "sha256": "4f2ecf162576eca795550ef23660053e58ee706814419b700b766c0a5f0bd9f8",
    "width": 128,
    "height": 128,
    "scale": 8,
    "indexed": true,
    "inline": true
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

Also attached: image/png.

</details>

**9. `perform`**: OK sky, sun and sea: the map named paint: freehand, then paint: rectangle, then paint: circle, then paint: rectangle

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "ok", "button": "left"},
    {"op": "run_for", "frames": 20},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "brown", "button": "left"},
    {"op": "send_mouse", "x": 4, "y": 14, "button": "left", "action": "drag", "to_x": 587, "to_y": 259},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "circle_filled", "button": "left"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 296,
      "y": 259,
      "button": "left",
      "action": "drag",
      "to_x": 356,
      "to_y": 259
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "blue", "button": "left"},
    {"op": "send_mouse", "x": 4, "y": 260, "button": "left", "action": "drag", "to_x": 587, "to_y": 475},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 18 of 18 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 37,149; posted, unverified, 25 retraces to frame 521",
        "status": "ok",
        "stop_seq": 123,
        "cause": "the retrace the input's post ran to, at 0DA5:000000BA"
      }
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {
        "summary": "run_for 20 frames: ELAPSED, 20 polls, at 1009:0000023A",
        "status": "ok",
        "stop_seq": 124,
        "cause": "the retrace run_for ran to, at 1009:0000023A"
      }
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: freehand (file), 14 controls", "status": "ok"}
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142; posted, unverified, 21 retraces to frame 562",
        "status": "ok",
        "stop_seq": 145,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,448; posted, unverified, 25 retraces to frame 587",
        "status": "ok",
        "stop_seq": 170,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 587,259; posted, unverified, 30 retraces to frame 617",
        "status": "ok",
        "stop_seq": 200,
        "cause": "the retrace the input's post ran to, at 0E83:00000A7C"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 632",
        "status": "ok",
        "stop_seq": 215,
        "cause": "the retrace the input's post ran to, at 1009:0000026B"
      }
    },
    {
      "step": 7,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: rectangle (file), 14 controls", "status": "ok"}
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 634,142; posted, unverified, 25 retraces to frame 657",
        "status": "ok",
        "stop_seq": 240,
        "cause": "the retrace the input's post ran to, at 1009:00000273"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448; posted, unverified, 25 retraces to frame 682",
        "status": "ok",
        "stop_seq": 265,
        "cause": "the retrace the input's post ran to, at 1009:000002A6"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 356,259; posted, unverified, 30 retraces to frame 712",
        "status": "ok",
        "stop_seq": 295,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 727",
        "status": "ok",
        "stop_seq": 310,
        "cause": "the retrace the input's post ran to, at 0955:00000029"
      }
    },
    {
      "step": 12,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: circle (file), 14 controls", "status": "ok"}
    },
    {
      "step": 13,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142; posted, unverified, 25 retraces to frame 752",
        "status": "ok",
        "stop_seq": 335,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 14,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,344; posted, unverified, 25 retraces to frame 777",
        "status": "ok",
        "stop_seq": 360,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 587,475; posted, unverified, 30 retraces to frame 807",
        "status": "ok",
        "stop_seq": 390,
        "cause": "the retrace the input's post ran to, at 1009:000001BF"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 822",
        "status": "ok",
        "stop_seq": 405,
        "cause": "the retrace the input's post ran to, at 13F6:000002DE"
      }
    },
    {
      "step": 17,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: rectangle (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: rectangle",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 18,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 99,
    "stop_seq_last": 405,
    "surveyed": 14,
    "by_cause": {"the retrace the input's post ran to,": 13, "the retrace run_for ran to,": 1},
    "unaccounted": 293
  },
  "steps_completed": 18,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `perform`**: OK glints and hull: the map named paint: line, then paint: rectangle

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "line", "button": "left"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 256,
      "y": 272,
      "button": "left",
      "action": "drag",
      "to_x": 336,
      "to_y": 272
    },
    {
      "op": "send_mouse",
      "x": 270,
      "y": 284,
      "button": "left",
      "action": "drag",
      "to_x": 322,
      "to_y": 284
    },
    {
      "op": "send_mouse",
      "x": 284,
      "y": 296,
      "button": "left",
      "action": "drag",
      "to_x": 308,
      "to_y": 296
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "black", "button": "left"},
    {
      "op": "send_mouse",
      "x": 100,
      "y": 380,
      "button": "left",
      "action": "drag",
      "to_x": 180,
      "to_y": 395
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 12 of 12 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 605,89; posted, unverified, 25 retraces to frame 847",
        "status": "ok",
        "stop_seq": 430,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448; posted, unverified, 25 retraces to frame 872",
        "status": "ok",
        "stop_seq": 455,
        "cause": "the retrace the input's post ran to, at 1009:000002AA"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 336,272; posted, unverified, 30 retraces to frame 902",
        "status": "ok",
        "stop_seq": 485,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 322,284; posted, unverified, 30 retraces to frame 932",
        "status": "ok",
        "stop_seq": 515,
        "cause": "the retrace the input's post ran to, at 1009:000001C9"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 308,296; posted, unverified, 30 retraces to frame 962",
        "status": "ok",
        "stop_seq": 545,
        "cause": "the retrace the input's post ran to, at 0DA5:00000350"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 977",
        "status": "ok",
        "stop_seq": 560,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 6,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: line (file), 14 controls", "status": "ok"}
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142; posted, unverified, 25 retraces to frame 1002",
        "status": "ok",
        "stop_seq": 585,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,323; posted, unverified, 25 retraces to frame 1027",
        "status": "ok",
        "stop_seq": 610,
        "cause": "the retrace the input's post ran to, at 1009:00000346"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 180,395; posted, unverified, 30 retraces to frame 1057",
        "status": "ok",
        "stop_seq": 640,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1072",
        "status": "ok",
        "stop_seq": 655,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 11,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: rectangle (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: rectangle",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 12,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 406,
    "stop_seq_last": 655,
    "surveyed": 10,
    "by_cause": {"the retrace the input's post ran to,": 10},
    "unaccounted": 240
  },
  "steps_completed": 12,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `perform`**: OK mast and sail: the map named paint: line, then paint: line

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "line", "button": "left"},
    {"op": "send_mouse", "target": "black", "button": "left"},
    {
      "op": "send_mouse",
      "x": 140,
      "y": 379,
      "button": "left",
      "action": "drag",
      "to_x": 140,
      "to_y": 320
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 142,
      "y": 322,
      "button": "left",
      "action": "drag",
      "to_x": 176,
      "to_y": 374
    },
    {
      "op": "send_mouse",
      "x": 176,
      "y": 374,
      "button": "left",
      "action": "drag",
      "to_x": 142,
      "to_y": 374
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 10 of 10 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 605,89; posted, unverified, 25 retraces to frame 1097",
        "status": "ok",
        "stop_seq": 680,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,323; posted, unverified, 25 retraces to frame 1122",
        "status": "ok",
        "stop_seq": 705,
        "cause": "the retrace the input's post ran to, at 0955:0000003F"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 140,320; posted, unverified, 30 retraces to frame 1152",
        "status": "ok",
        "stop_seq": 735,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1167",
        "status": "ok",
        "stop_seq": 750,
        "cause": "the retrace the input's post ran to, at 13F6:00000225"
      }
    },
    {
      "step": 4,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: line (file), 14 controls", "status": "ok"}
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448; posted, unverified, 25 retraces to frame 1192",
        "status": "ok",
        "stop_seq": 775,
        "cause": "the retrace the input's post ran to, at 0955:00000032"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 176,374; posted, unverified, 30 retraces to frame 1222",
        "status": "ok",
        "stop_seq": 805,
        "cause": "the retrace the input's post ran to, at 1009:0000032D"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 142,374; posted, unverified, 30 retraces to frame 1252",
        "status": "ok",
        "stop_seq": 835,
        "cause": "the retrace the input's post ran to, at 1009:00000324"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1267",
        "status": "ok",
        "stop_seq": 850,
        "cause": "the retrace the input's post ran to, at 1009:0000025C"
      }
    },
    {
      "step": 9,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: line (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: line",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 10,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 656,
    "stop_seq_last": 850,
    "surveyed": 8,
    "by_cause": {"the retrace the input's post ran to,": 8},
    "unaccounted": 187
  },
  "steps_completed": 10,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `perform`**: OK SCRY: the map named paint: text, then paint: freehand

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "black", "button": "left"},
    {"op": "send_mouse", "target": "text", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "x": 40, "y": 60, "button": "left"},
    {"op": "send_keys", "keys": ["S", "C", "R", "Y"], "modifiers": ["shift"]},
    {"op": "send_mouse", "target": "freehand", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 9 of 9 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,323; posted, unverified, 25 retraces to frame 1292",
        "status": "ok",
        "stop_seq": 875,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,185; posted, unverified, 25 retraces to frame 1317",
        "status": "ok",
        "stop_seq": 900,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1332",
        "status": "ok",
        "stop_seq": 915,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: text (file), 14 controls", "status": "ok"}
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 40,60; posted, unverified, 25 retraces to frame 1357",
        "status": "ok",
        "stop_seq": 940,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 5,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 50 retraces to frame 1407",
        "status": "ok",
        "stop_seq": 990,
        "cause": "the retrace the input's post ran to, at 2825:00000147"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,65; posted, unverified, 25 retraces to frame 1432",
        "status": "ok",
        "stop_seq": 1015,
        "cause": "the retrace the input's post ran to, at 0955:0000004C"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1447",
        "status": "ok",
        "stop_seq": 1030,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 8,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: freehand (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: freehand",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 9,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 851,
    "stop_seq_last": 1030,
    "surveyed": 7,
    "by_cause": {"the retrace the input's post ran to,": 7},
    "unaccounted": 173
  },
  "steps_completed": 9,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `perform`**: OK flip the boat: the map named paint: grab, then paint: custom brush, then brush menu, then paint: custom brush, then paint: custom brush

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "brush_grab", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {
      "op": "send_mouse",
      "x": 96,
      "y": 316,
      "button": "left",
      "action": "drag",
      "to_x": 184,
      "to_y": 399
    },
    {"op": "run_for", "frames": 10},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "brush", "button": "left", "action": "down"},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "flip_horizontal", "button": "left", "action": "up"},
    {"op": "run_for", "frames": 20},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "x": 440, "y": 357, "button": "left"},
    {"op": "run_for", "frames": 10},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 17 of 17 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 605,185; posted, unverified, 25 retraces to frame 1472",
        "status": "ok",
        "stop_seq": 1055,
        "cause": "the retrace the input's post ran to, at 0955:0000003C"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1487",
        "status": "ok",
        "stop_seq": 1070,
        "cause": "the retrace the input's post ran to, at 1009:00000311"
      }
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: grab (file), 14 controls", "status": "ok"}
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 184,399; posted, unverified, 30 retraces to frame 1517",
        "status": "ok",
        "stop_seq": 1100,
        "cause": "the retrace the input's post ran to, at 0E83:00000AF4"
      }
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {
        "summary": "run_for 10 frames: ELAPSED, 10 polls, at 0E83:00000AFC",
        "status": "ok",
        "stop_seq": 1101,
        "cause": "the retrace run_for ran to, at 0E83:00000AFC"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1538",
        "status": "ok",
        "stop_seq": 1112,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 6,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: custom brush (file), 14 controls", "status": "ok"}
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 203,5; posted, unverified, 20 retraces to frame 1558",
        "status": "ok",
        "stop_seq": 1132,
        "cause": "the retrace the input's post ran to, at 0955:0000033D"
      }
    },
    {
      "step": 8,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: brush menu (file), 2 controls", "status": "ok"}
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 269,18; posted, unverified, 20 retraces to frame 1578",
        "status": "ok",
        "stop_seq": 1152,
        "cause": "the retrace the input's post ran to, at 19A5:000001C7"
      }
    },
    {
      "step": 10,
      "op": "run_for",
      "reply": {
        "summary": "run_for 20 frames: ELAPSED, 20 polls, at 0DA5:00000330",
        "status": "ok",
        "stop_seq": 1153,
        "cause": "the retrace run_for ran to, at 0DA5:00000330"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1609",
        "status": "ok",
        "stop_seq": 1164,
        "cause": "the retrace the input's post ran to, at 1009:000002D2"
      }
    },
    {
      "step": 12,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: custom brush (file), 14 controls", "status": "ok"}
    },
    {
      "step": 13,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 440,357; posted, unverified, 25 retraces to frame 1634",
        "status": "ok",
        "stop_seq": 1189,
        "cause": "the retrace the input's post ran to, at 1009:00000341"
      }
    },
    {
      "step": 14,
      "op": "run_for",
      "reply": {
        "summary": "run_for 10 frames: ELAPSED, 10 polls, at 1009:00000367",
        "status": "ok",
        "stop_seq": 1190,
        "cause": "the retrace run_for ran to, at 1009:00000367"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1655",
        "status": "ok",
        "stop_seq": 1201,
        "cause": "the retrace the input's post ran to, at 1009:0000026D"
      }
    },
    {
      "step": 16,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: custom brush (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: custom brush",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 17,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 1031,
    "stop_seq_last": 1201,
    "surveyed": 12,
    "by_cause": {"the retrace the input's post ran to,": 9, "the retrace run_for ran to,": 3},
    "unaccounted": 159
  },
  "steps_completed": 17,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `perform`**: OK Pict, and the brush put down: the map named pict menu, then paint: custom brush, then paint: freehand

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "pict", "button": "left", "action": "down"},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "button": "left", "action": "up"},
    {"op": "run_for", "frames": 10},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "brush_dot", "button": "left"},
    {"op": "send_mouse", "target": "freehand", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 10 of 10 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 119,5; posted, unverified, 20 retraces to frame 1675",
        "status": "ok",
        "stop_seq": 1221,
        "cause": "the retrace the input's post ran to, at 0955:0000033D"
      }
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: pict menu (file), 1 control", "status": "ok"}
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 119,5; posted, unverified, 15 retraces to frame 1690",
        "status": "ok",
        "stop_seq": 1236,
        "cause": "the retrace the input's post ran to, at 13F6:00000228"
      }
    },
    {
      "step": 3,
      "op": "run_for",
      "reply": {
        "summary": "run_for 10 frames: ELAPSED, 10 polls, at F000:0000CFC5",
        "status": "ok",
        "stop_seq": 1237,
        "cause": "the retrace run_for ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1711",
        "status": "ok",
        "stop_seq": 1248,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 5,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: custom brush (file), 14 controls", "status": "ok"}
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 599,21; posted, unverified, 25 retraces to frame 1736",
        "status": "ok",
        "stop_seq": 1273,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,65; posted, unverified, 25 retraces to frame 1761",
        "status": "ok",
        "stop_seq": 1298,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1776",
        "status": "ok",
        "stop_seq": 1313,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 9,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: freehand (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: freehand",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "pict", "rect": [103, 0, 33, 11], "centre": [119, 5]},
          {"name": "brush", "rect": [183, 0, 41, 11], "centre": [203, 5]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]},
          {"name": "brush_dot", "rect": [598, 20, 3, 3], "centre": [599, 21]},
          {"name": "freehand", "rect": [618, 54, 22, 22], "centre": [629, 65]},
          {"name": "line", "rect": [594, 78, 22, 22], "centre": [605, 89]},
          {"name": "rect_filled", "rect": [606, 138, 9, 9], "centre": [610, 142]},
          {"name": "circle_filled", "rect": [630, 138, 9, 9], "centre": [634, 142]},
          {"name": "brush_grab", "rect": [594, 174, 22, 22], "centre": [605, 185]},
          {"name": "text", "rect": [618, 174, 22, 22], "centre": [629, 185]},
          {"name": "black", "rect": [596, 315, 17, 16], "centre": [604, 323]},
          {"name": "blue", "rect": [596, 337, 17, 14], "centre": [604, 344]},
          {"name": "brown", "rect": [596, 441, 17, 15], "centre": [604, 448]},
          {"name": "yellow", "rect": [620, 441, 17, 15], "centre": [628, 448]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 10,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 1202,
    "stop_seq_last": 1313,
    "surveyed": 7,
    "by_cause": {"the retrace the input's post ran to,": 6, "the retrace run_for ran to,": 1},
    "unaccounted": 105
  },
  "steps_completed": 10,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `screen_view`**: OK word row: the row reads frame x 4, then orange x 37, then black x 4, then orange x 3, then black x 2, then orange x 6, then black x 5, then orange x 4, then black x 5, then orange x 518, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 57, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-57.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 57] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 57, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-57.png",
    "bytes": 866,
    "sha256": "c6542d54e76dc4220a85b889e41406d264ff5633e3602ed525a1d907bfe5b87a",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `screen_view`**: OK sun row: the row reads frame x 4, then orange x 239, then yellow x 107, then orange x 238, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 230, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-230.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 230] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 230, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-230.png",
    "bytes": 862,
    "sha256": "bfe6a11d2b399d1cdf990309472e3e7a319dd0189e1d9d4e6b92038a2fa738fb",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `screen_view`**: OK glint row: the row reads frame x 4, then blue x 252, then yellow x 81, then blue x 251, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 272, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-272.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 272] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 272, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-272.png",
    "bytes": 862,
    "sha256": "374cb4507607384f48ae431769a8f6e8b5eb9bbbccd82e1efc1dd34324ea8338",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `screen_view`**: OK sail row: the row reads frame x 4, then blue x 136, then black x 1, then blue x 19, then yellow x 1, then blue x 258, then yellow x 1, then blue x 20, then black x 1, then blue x 147, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 350, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-350.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 350] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 350, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-350.png",
    "bytes": 870,
    "sha256": "7f67bd1cbb6676a90f1e71a5f7e425c7fce85cdd9ea47569d54a0f95b623ebba",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `screen_view`**: OK hull row: the row reads frame x 4, then blue x 96, then black x 81, then blue x 219, then black x 81, then blue x 107, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 388, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-388.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 388] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 388, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-388.png",
    "bytes": 865,
    "sha256": "0c6260b94b81920b1dfb89b6a5be77c7c9189dd446187bab6b6218814634051f",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `screen_view`**: OK screen: mode M_EGA, 640x480 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/dpaint_maps/screen.png"
}
```

```json
{
  "summary": "screen_view M_EGA: 640x480 at [0, 0] pixels; 640x480 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 0, 640, 480],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/screen.png",
    "bytes": 4012,
    "sha256": "64514af0c959a72efb2abe3dc58abdcc5190cb5acca2009d633537ca1fe08d7a",
    "width": 640,
    "height": 480,
    "scale": 1,
    "indexed": true,
    "inline": true
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

Also attached: image/png.

</details>

**21. `close`**: OK close: closed: quit

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "close: quit, exit code 0",
  "status": "ok",
  "closed": true,
  "pid": "<volatile>",
  "conf": "./demos/dpaint_maps/dpaint_maps.conf",
  "conf_digest": "daae6ab9a0232442",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->
