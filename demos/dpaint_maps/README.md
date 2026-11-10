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
- `--update-readme` rewrites the block below, `TRANSCRIPT.md` and `screen.png` from a run where every step
  passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2
a usage error, 3 nothing was demonstrated (no program directory, another build of it, a
DOSBox-X without relative motion, a server that did not start).

## The map

`dpaint-screen-map.json` names eleven screens of Deluxe Paint at 640 x 480, each known by regions
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

> Start DOSBox-X windowed on `demos/dpaint_maps/dpaint-maps.conf`, running from
> `/path/to/your/dpaint2`, with `DP.EXE k` as the program and the log in a file. Run 400 retraces and load the screen map `dpaint-screen-map.json` beside the conf. Pick
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
| Input | `send_mouse` by control name off the map (a press to open a menu, a release to choose), at screen pixels, and as drags; `send_keys` for the word |
| Read | `screen_map_write(method="load")`, `screen_map_find` after every move between screens |
| Screen | `palette` for the mixed colour, `screen_view` for rows of the picture and the screen |
| Lists | `perform` (each move with the map's word on where it landed; a shape's tool, colour and drags) |

## The transcript

Generated by `demo.py --update-readme` from a run where every step passed. What differs between
two honest runs (process ids, ports, wall-clock times, temporary paths, the host's own DOSBox-X
and its own arguments) is `<volatile>`, and the program's directory is `<host>`.

<!-- demo-transcript:begin -->
The run is 21 calls; these are the ones that show how it is done, and every call with its reply is in [TRANSCRIPT.md](TRANSCRIPT.md).

**7. `perform`**: OK mix: the brown slot picked, and red's arrow held from the press to the release

Deluxe Paint's menus and arrows act only while the button is held. `send_mouse` takes `action: down` and `action: up` as the two halves of a click, and `perform` sends the pick, the press and the release as one call, so the arrow is held exactly from one step to the next.

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

`palette` reads the VGA DAC back: the entry the dialog's arrows mixed, as the colour the screen will show. The DAC holds six bits per channel; the reply gives both its raw values and the eight-bit colour. Nothing but the program's own dialog touched it.

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

**13. `perform`**: OK flip the boat: the map named paint: grab, then paint: custom brush, then brush menu, then paint: custom brush, then paint: custom brush

The longest chain of map names in the run: lift the boat as a brush, flip it from the Brush menu, stamp the mirror image. After each move the map is asked where it landed, because the same pixels mean a different tool in hand.

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
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 15 retraces to frame 1487",
        "status": "ok",
        "stop_seq": 1070,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
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
        "cause": "the retrace the input's post ran to, at 0DA5:0000034E"
      }
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {
        "summary": "run_for 10 frames: ELAPSED, 10 polls, at F000:0000CFC0",
        "status": "ok",
        "stop_seq": 1101,
        "cause": "the retrace run_for ran to, at F000:0000CFC0"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1538",
        "status": "ok",
        "stop_seq": 1112,
        "cause": "the retrace the input's post ran to, at 13F6:000002D3"
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
        "cause": "the retrace the input's post ran to, at 0955:00000335"
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
        "cause": "the retrace the input's post ran to, at 0DA5:000002DE"
      }
    },
    {
      "step": 10,
      "op": "run_for",
      "reply": {
        "summary": "run_for 20 frames: ELAPSED, 20 polls, at 19A5:000001DD",
        "status": "ok",
        "stop_seq": 1153,
        "cause": "the retrace run_for ran to, at 19A5:000001DD"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1609",
        "status": "ok",
        "stop_seq": 1164,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
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
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 14,
      "op": "run_for",
      "reply": {
        "summary": "run_for 10 frames: ELAPSED, 10 polls, at F000:0000CFC5",
        "status": "ok",
        "stop_seq": 1190,
        "cause": "the retrace run_for ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300; posted, unverified, 11 retraces to frame 1655",
        "status": "ok",
        "stop_seq": 1201,
        "cause": "the retrace the input's post ran to, at 1009:00000273"
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
<!-- demo-transcript:end -->
