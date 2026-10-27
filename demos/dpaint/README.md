# Deluxe Paint: a sunset painted through the debugger, and the byte that holds the colour

![A sunset painted in Deluxe Paint II through the server: the sun sinking into the sea, a boat and the word SCRY](screen.png)

Electronic Arts' Deluxe Paint II, the 1988 PC version, paints a sunset here with every stroke
sent by the server: tools and colours are picked by name off a screen map, each shape is a drag
of the guest's own mouse, and the picture is checked by reading its pixels back out of video
memory. Halfway through, the demo does what no mouse macro can: it picks two colours off the
palette with a value scan between the clicks, finds the bytes where the program keeps its
current colour, tells the four static ones from the copies in the stack's frames, and watches
the first, so every later pick shows its colour at the stop it lands on.

## Bring your own copy

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
WINDOW_APP=/path/to/your/placement-helper uv run python demos/dpaint/demo.py \
  --cwd /path/to/your/dpaint2
```

The demo opens a window, scaled up four times by its conf, so the painting can be watched; nothing
in it needs the window. Deluxe Paint takes the mouse as movement events, so it needs a DOSBox-X
whose input device carries relative motion (the repository's REFERENCE.md, *Input and the
screen*), named with `--binary` or `DOSBOX_X_BINARY`; on a build without it the demo stops at its
second step, saying so, because a drag would paint nothing between its button events.

Where that window goes is your machine's to say, exactly as for the [bricks
demo](../bricks/README.md): the server asks the placement helper named by `WINDOW_APP`, for the
secondary display on a run nobody watches, and the demo refuses to start rather than open the
window on top of your work when the helper cannot place it.

- `--cwd PATH` (absolute or `~`-led) is the directory of your copy, which the session runs from and mounts
  as C:. It is hidden in the transcript as `<host>`.
- `--shared` says somebody is watching: the window opens on the main display.
- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start; left out, `DOSBOX_X_BINARY`, else the
  `dosbox-x` on your `PATH`.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below and `screen.png` from a run where every step
  passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2
a usage error, 3 nothing was demonstrated (no copy, another build of it, no placement for the
window, a DOSBox-X without relative motion, a server that did not start).

## The prompt

Give this to an MCP client with this server connected:

> Start DOSBox-X windowed on `demos/dpaint/dpaint.conf`, placed where my placement helper says,
> running from my copy of Deluxe Paint II at `/path/to/your/dpaint2`, with `DP.EXE f` as the
> program and the log in a file. Run
> 400 retraces and tell me where its data segment is. Load the screen map
> `dpaint.scry-map.json` beside the conf and tell me which screen this is. Pick blue off the
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
| Session | `start` (windowed, running the reader's copy from `cwd`), `close` |
| Advance | `run_for` by retraces on the conf's fixed clock |
| Files | `map_write(method="load")`, `map_find` |
| Input | `send_mouse` by control name off the map, at screen pixels, and as drags; `send_keys` for the word |
| Scan | `scan` (`start`, `filter` twice, `clear`) |
| Declarations | `watch_add` (the colour byte in view at every stop), `declaration_clear(kind="watch")` |
| Sequences | `perform` (one shape a call: its tool, its colour, its drags) |
| Read | `read_memory` of rows of video memory, `screen_view` |

## The transcript

Generated by `demo.py --update-readme` from a run where every step passed. What differs between
two honest runs (process ids, ports, wall-clock times, temporary paths, the host's own DOSBox-X
and where it put the window) is `<volatile>`, and the directory of your copy is `<host>`.

<!-- demo-transcript:begin -->
**1. `start`**: OK start: DOSBox-X in a window, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./demos/dpaint/dpaint.conf",
  "session_seconds": 900,
  "shared": true,
  "display": "secondary",
  "program": "DP.EXE f",
  "logfile": "./tmp/demos/dpaint/dpaint-e9.log",
  "state_dir": "./tmp/demos/dpaint/dpaint-states",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/dpaint/dpaint.conf",
  "conf_digest": "cd9edac1f1a515a6",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint/dpaint-states",
  "shared": true,
  "display": "secondary",
  "ready_after_s": "<volatile>",
  "argv": "<volatile>",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger_commands": [
    "BPIF",
    "CAPTURE",
    "DOSTRACE",
    "LOADSTATE",
    "PORTINFO",
    "PRESENCE",
    "RUNSTATE",
    "SAVESTATE",
    "STEPIN",
    "TAP",
    "VGAMEMDUMP"
  ],
  "stub": "./guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": false,
  "presence": true,
  "declarations": {
    "rearm": {
      "rearmed": [],
      "stale": [],
      "unresolved": [],
      "ambiguous": [],
      "unarmable": []
    }
  },
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
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
  "summary": "run_for 400 frames: ELAPSED, 400 polls, at 0B92:00000241",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 400,
  "pc": "0B92:00000241",
  "cpu_mode": "real",
  "frame": 400,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x000003e4",
    "ECX": "0x005b0000",
    "EDX": "0x0000a5ea",
    "ESI": "0x00006e42",
    "EDI": "0x00006e52",
    "EBP": "0x00009ffc",
    "ESP": "0x00009ff8",
    "EIP": "0x00000241",
    "CS": "0x0b92",
    "DS": "0x31b0",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b0"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0B92:00000241",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": [
      "Bochs port E9h: STUB  . scry device=present proto=6 motion=1"
    ],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "seg_off": "0B92:00000241",
    "bytes": "8B4708",
    "text": "mov ax, word ptr [bx + 8]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "emulated_before_s": 0.0007,
  "emulated_after_s": 5.6986656,
  "frame_before": 0,
  "frame_after": 400,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and which core runs is not something this server can read, so no count is given"
  },
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**3. `map_write`**: OK map: 1 screen and 13 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/dpaint/dpaint.scry-map.json"
}
```

```json
{
  "summary": "map_write load: 1 screen, 13 controls of dpaint",
  "status": "ok",
  "path": "./demos/dpaint/dpaint.scry-map.json",
  "application": "dpaint",
  "screens": 1,
  "controls": 13,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**4. `map_find`**: OK find: the painting screen, 13 controls named

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "map_find: paint (file), 13 controls",
  "status": "ok",
  "matched": true,
  "screen": "paint",
  "layer": "file",
  "kind": "pixel",
  "size": [
    320,
    200
  ],
  "controls": [
    {
      "name": "line",
      "rect": [
        297,
        46,
        10,
        10
      ],
      "centre": [
        302,
        51
      ]
    },
    {
      "name": "fill",
      "rect": [
        297,
        58,
        10,
        10
      ],
      "centre": [
        302,
        63
      ]
    },
    {
      "name": "rect_filled",
      "rect": [
        304,
        75,
        4,
        5
      ],
      "centre": [
        306,
        77
      ]
    },
    {
      "name": "circle_filled",
      "rect": [
        315,
        75,
        4,
        5
      ],
      "centre": [
        317,
        77
      ]
    },
    {
      "name": "text",
      "rect": [
        309,
        93,
        10,
        10
      ],
      "centre": [
        314,
        98
      ]
    },
    {
      "name": "clear",
      "rect": [
        309,
        128,
        10,
        11
      ],
      "centre": [
        314,
        133
      ]
    },
    {
      "name": "navy",
      "rect": [
        297,
        162,
        6,
        2
      ],
      "centre": [
        300,
        163
      ]
    },
    {
      "name": "brown",
      "rect": [
        297,
        172,
        6,
        2
      ],
      "centre": [
        300,
        173
      ]
    },
    {
      "name": "blue",
      "rect": [
        297,
        178,
        6,
        2
      ],
      "centre": [
        300,
        179
      ]
    },
    {
      "name": "yellow",
      "rect": [
        297,
        188,
        6,
        2
      ],
      "centre": [
        300,
        189
      ]
    },
    {
      "name": "white",
      "rect": [
        297,
        190,
        6,
        2
      ],
      "centre": [
        300,
        191
      ]
    },
    {
      "name": "peach",
      "rect": [
        315,
        168,
        5,
        2
      ],
      "centre": [
        317,
        169
      ]
    },
    {
      "name": "orange",
      "rect": [
        315,
        174,
        5,
        2
      ],
      "centre": [
        317,
        175
      ]
    }
  ],
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**5. `send_mouse`**: OK blue: blue picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "blue",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 300,179; posted, unverified, 21 retraces to frame 421",
  "status": "ok",
  "x": 300,
  "y": 179,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {
      "x": 300,
      "y": 179,
      "width": 320,
      "height": 200
    },
    "mouse": {
      "x": 2404,
      "y": 1436,
      "max_x": 2552,
      "max_y": 1592
    },
    "buttons": [],
    "bios_mode": "0x13"
  },
  "arrived": true,
  "polls": 21,
  "pc": "F000:0000CFC5",
  "cpu_mode": "real",
  "stop_seq": 23,
  "frame": 421,
  "instruction": {
    "seg_off": "F000:0000CFC5",
    "bytes": "CF",
    "text": "iret",
    "flow": "return",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "regs": {
    "EAX": "0x0000011c",
    "EBX": "0x00001094",
    "ECX": "0x005b0000",
    "EDX": "0x000000fe",
    "ESI": "0x0000ffff",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a00c",
    "ESP": "0x00009ff8",
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
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "target": "blue",
  "screen": "paint",
  "identified_at_stop": 2,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**6. `scan`**: OK scan: 65535 bytes of the data segment are candidates

<details><summary>call and reply</summary>

```json
{
  "method": "start",
  "ref": "31B0:0000",
  "length": 65535,
  "cell_bytes": 1
}
```

```json
{
  "summary": "scan start: 31B0:0000, 65535 cells of 1 byte",
  "status": "ok",
  "ref": "31B0:0000",
  "seg_off": "31B0:00000000",
  "length": 65535,
  "cell_bytes": 1,
  "addr": "0x00031b00",
  "hits_total": 65535,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**7. `scan`**: OK is blue: 75 bytes hold 0x09 now

<details><summary>call and reply</summary>

```json
{
  "method": "filter",
  "value": 9,
  "limit": 8
}
```

```json
{
  "summary": "scan filter: = 9, 75 survivors, the first 8 listed",
  "status": "ok",
  "operator": "=",
  "value": "0x09",
  "iterations": 1,
  "closed": false,
  "hits": [
    {
      "seg_off": "31B0:0000017C",
      "addr": "0x00031c7c",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:000001AE",
      "addr": "0x00031cae",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:00000370",
      "addr": "0x00031e70",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:00000470",
      "addr": "0x00031f70",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:00000597",
      "addr": "0x00032097",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:000006B3",
      "addr": "0x000321b3",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:000008F9",
      "addr": "0x000323f9",
      "value": "0x09"
    },
    {
      "seg_off": "31B0:00000919",
      "addr": "0x00032419",
      "value": "0x09"
    }
  ],
  "hits_total": 75,
  "truncated": true,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**8. `send_mouse`**: OK orange: orange picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "orange",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 317,175; posted, unverified, 25 retraces to frame 446",
  "status": "ok",
  "x": 317,
  "y": 175,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {
      "x": 317,
      "y": 175,
      "width": 320,
      "height": 200
    },
    "mouse": {
      "x": 2540,
      "y": 1404,
      "max_x": 2552,
      "max_y": 1592
    },
    "buttons": [],
    "bios_mode": "0x13"
  },
  "arrived": true,
  "polls": 25,
  "pc": "13F6:00000220",
  "cpu_mode": "real",
  "stop_seq": 48,
  "frame": 446,
  "instruction": {
    "seg_off": "13F6:00000220",
    "bytes": "83EC06",
    "text": "sub sp, 6",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  },
  "regs": {
    "EAX": "0x0000a01c",
    "EBX": "0x00001094",
    "ECX": "0x005b0000",
    "EDX": "0x000000fe",
    "ESI": "0x0000a030",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a00c",
    "ESP": "0x0000a00c",
    "EIP": "0x00000220",
    "CS": "0x13f6",
    "DS": "0x31b0",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b0"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 13F6:00000220",
  "e9": {
    "lines_total": 0,
    "truncated": false,
    "lines": [],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "target": "orange",
  "screen": "paint",
  "identified_at_stop": 2,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**9. `scan`**: OK is orange: 7 bytes followed both clicks: 3 in the stack's frames above A00C, and 4 static ones from 31B0:017C

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
    {
      "seg_off": "31B0:0000017C",
      "addr": "0x00031c7c",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:000001AE",
      "addr": "0x00031cae",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:00000470",
      "addr": "0x00031f70",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:000010B0",
      "addr": "0x00032bb0",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:0000A57E",
      "addr": "0x0003c07e",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:0000A57F",
      "addr": "0x0003c07f",
      "value": "0x37"
    },
    {
      "seg_off": "31B0:0000A580",
      "addr": "0x0003c080",
      "value": "0x37"
    }
  ],
  "hits_total": 7,
  "truncated": false,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**10. `scan`**: OK unscan: scan closed

<details><summary>call and reply</summary>

```json
{
  "method": "clear"
}
```

```json
{
  "summary": "scan clear: cleared",
  "status": "ok",
  "cleared": true,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**11. `watch_add`**: OK watch: the colour byte shown at every stop

<details><summary>call and reply</summary>

```json
{
  "ref": "31B0:017C",
  "mode": "show",
  "fmt": "u8"
}
```

```json
{
  "summary": "watch_add 31B0:017C: evaluated",
  "status": "ok",
  "ref": "31B0:017C",
  "by": "address",
  "mode": "show",
  "fmt": "u8",
  "length": 1,
  "stored": true,
  "armed": false,
  "state": "evaluated",
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**12. `perform`**: OK sky: peach, the colour byte at 52, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "rect_filled",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "target": "peach",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 2,
      "y": 14,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 294,
      "y": 112
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 5 of 5 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 306,77; posted, unverified, 25 retraces to frame 471",
        "status": "ok",
        "stop_seq": 73,
        "cause": "the retrace the input's post ran to, at 1009:00000326"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 317,169; posted, unverified, 25 retraces to frame 496",
        "status": "ok",
        "stop_seq": 98,
        "cause": "the retrace the input's post ran to, at 1009:00000240"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 2,14; posted, unverified, 20 retraces to frame 516",
        "status": "ok",
        "stop_seq": 118,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,112; posted, unverified, 15 retraces to frame 531",
        "status": "ok",
        "stop_seq": 133,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,112; posted, unverified, 15 retraces to frame 546",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 294,
            "y": 112,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 2356,
            "y": 900,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 15,
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 148,
        "frame": 546,
        "instruction": {
          "seg_off": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x0000011c",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf3",
          "ESI": "0x0000ffff",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a00c",
          "ESP": "0x00009ff8",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 52,
            "bytes": "34"
          }
        ],
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 5,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 49,
    "stop_seq_last": 148,
    "surveyed": 5,
    "by_cause": {
      "the retrace the input's post ran to,": 5
    },
    "unaccounted": 95
  },
  "steps_completed": 5,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**13. `perform`**: OK sun: yellow, the colour byte at 14, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "circle_filled",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "target": "yellow",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 210,
      "y": 112,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 238,
      "y": 112
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 5 of 5 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 317,77; posted, unverified, 25 retraces to frame 571",
        "status": "ok",
        "stop_seq": 173,
        "cause": "the retrace the input's post ran to, at 13F6:00000228"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,189; posted, unverified, 25 retraces to frame 596",
        "status": "ok",
        "stop_seq": 198,
        "cause": "the retrace the input's post ran to, at 1009:0000032D"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 210,112; posted, unverified, 20 retraces to frame 616",
        "status": "ok",
        "stop_seq": 218,
        "cause": "the retrace the input's post ran to, at 0E83:00000970"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 238,112; posted, unverified, 15 retraces to frame 631",
        "status": "ok",
        "stop_seq": 233,
        "cause": "the retrace the input's post ran to, at 1009:00000239"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 238,112; posted, unverified, 15 retraces to frame 646",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 238,
            "y": 112,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 1908,
            "y": 900,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 15,
        "pc": "1009:0000023F",
        "cpu_mode": "real",
        "stop_seq": 248,
        "frame": 646,
        "instruction": {
          "seg_off": "1009:0000023F",
          "bytes": "56",
          "text": "push si",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x00000000",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf3",
          "ESI": "0x00000008",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a024",
          "ESP": "0x0000a022",
          "EIP": "0x0000023f",
          "CS": "0x1009",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 14,
            "bytes": "0e"
          }
        ],
        "cause": "the retrace the input's post ran to, at 1009:0000023F",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 5,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 149,
    "stop_seq_last": 248,
    "surveyed": 5,
    "by_cause": {
      "the retrace the input's post ran to,": 5
    },
    "unaccounted": 95
  },
  "steps_completed": 5,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**14. `perform`**: OK sea: navy, the colour byte at 1, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "rect_filled",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "target": "navy",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 2,
      "y": 113,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 294,
      "y": 198
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 5 of 5 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 306,77; posted, unverified, 25 retraces to frame 671",
        "status": "ok",
        "stop_seq": 273,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,163; posted, unverified, 25 retraces to frame 696",
        "status": "ok",
        "stop_seq": 298,
        "cause": "the retrace the input's post ran to, at 13F6:0000023B"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 2,113; posted, unverified, 20 retraces to frame 716",
        "status": "ok",
        "stop_seq": 318,
        "cause": "the retrace the input's post ran to, at 1009:000002CE"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,198; posted, unverified, 15 retraces to frame 731",
        "status": "ok",
        "stop_seq": 333,
        "cause": "the retrace the input's post ran to, at 0955:00000057"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,198; posted, unverified, 15 retraces to frame 746",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 294,
            "y": 198,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 2356,
            "y": 1588,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 15,
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 348,
        "frame": 746,
        "instruction": {
          "seg_off": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x0000011c",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf3",
          "ESI": "0x0000ffff",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a00c",
          "ESP": "0x00009ff8",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 1,
            "bytes": "01"
          }
        ],
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 5,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 249,
    "stop_seq_last": 348,
    "surveyed": 5,
    "by_cause": {
      "the retrace the input's post ran to,": 5
    },
    "unaccounted": 95
  },
  "steps_completed": 5,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**15. `perform`**: OK hull: brown, the colour byte at 6, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "brown",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 60,
      "y": 150,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 112,
      "y": 158
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 4 of 4 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,173; posted, unverified, 25 retraces to frame 771",
        "status": "ok",
        "stop_seq": 373,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 60,150; posted, unverified, 20 retraces to frame 791",
        "status": "ok",
        "stop_seq": 393,
        "cause": "the retrace the input's post ran to, at 0955:0000004F"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 112,158; posted, unverified, 15 retraces to frame 806",
        "status": "ok",
        "stop_seq": 408,
        "cause": "the retrace the input's post ran to, at 0E83:00000A6D"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 112,158; posted, unverified, 15 retraces to frame 821",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 112,
            "y": 158,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 900,
            "y": 1268,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 15,
        "pc": "0E83:00000146",
        "cpu_mode": "real",
        "stop_seq": 423,
        "frame": 821,
        "instruction": {
          "seg_off": "0E83:00000146",
          "bytes": "8BEC",
          "text": "mov bp, sp",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x00006e42",
          "EBX": "0x000003e4",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf3",
          "ESI": "0x00000008",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a006",
          "ESP": "0x00009ffc",
          "EIP": "0x00000146",
          "CS": "0x0e83",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 6,
            "bytes": "06"
          }
        ],
        "cause": "the retrace the input's post ran to, at 0E83:00000146",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 349,
    "stop_seq_last": 423,
    "surveyed": 4,
    "by_cause": {
      "the retrace the input's post ran to,": 4
    },
    "unaccounted": 71
  },
  "steps_completed": 4,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**16. `perform`**: OK sail: white, the colour byte at 15, 3 drags

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "line",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "target": "white",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 86,
      "y": 149,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 86,
      "y": 118
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    },
    {
      "op": "send_mouse",
      "x": 86,
      "y": 118,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 108,
      "y": 146
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    },
    {
      "op": "send_mouse",
      "x": 108,
      "y": 146,
      "button": "left",
      "action": "down"
    },
    {
      "op": "send_mouse",
      "x": 86,
      "y": 146
    },
    {
      "op": "send_mouse",
      "button": "left",
      "action": "up"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 11 of 11 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 302,51; posted, unverified, 25 retraces to frame 846",
        "status": "ok",
        "stop_seq": 448,
        "cause": "the retrace the input's post ran to, at 0955:0000004C"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,191; posted, unverified, 25 retraces to frame 871",
        "status": "ok",
        "stop_seq": 473,
        "cause": "the retrace the input's post ran to, at 0955:00000051"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,149; posted, unverified, 20 retraces to frame 891",
        "status": "ok",
        "stop_seq": 493,
        "cause": "the retrace the input's post ran to, at 0E83:000001AB"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,118; posted, unverified, 15 retraces to frame 906",
        "status": "ok",
        "stop_seq": 508,
        "cause": "the retrace the input's post ran to, at 1009:00000382"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,118; posted, unverified, 15 retraces to frame 921",
        "status": "ok",
        "stop_seq": 523,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,118; posted, unverified, 20 retraces to frame 941",
        "status": "ok",
        "stop_seq": 543,
        "cause": "the retrace the input's post ran to, at 0B92:000001FF"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 108,146; posted, unverified, 15 retraces to frame 956",
        "status": "ok",
        "stop_seq": 558,
        "cause": "the retrace the input's post ran to, at F000:0000CFC1"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 108,146; posted, unverified, 15 retraces to frame 971",
        "status": "ok",
        "stop_seq": 573,
        "cause": "the retrace the input's post ran to, at 1009:000001D4"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 108,146; posted, unverified, 20 retraces to frame 991",
        "status": "ok",
        "stop_seq": 593,
        "cause": "the retrace the input's post ran to, at 0E83:00000A90"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,146; posted, unverified, 15 retraces to frame 1006",
        "status": "ok",
        "stop_seq": 608,
        "cause": "the retrace the input's post ran to, at 0E83:000004F3"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,146; posted, unverified, 15 retraces to frame 1021",
        "status": "ok",
        "units": "screen",
        "button": "left",
        "action": "up",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 86,
            "y": 146,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 692,
            "y": 1172,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 15,
        "pc": "0E83:00000A14",
        "cpu_mode": "real",
        "stop_seq": 623,
        "frame": 1021,
        "instruction": {
          "seg_off": "0E83:00000A14",
          "bytes": "CB",
          "text": "retf",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x00000000",
          "EBX": "0x000003e4",
          "ECX": "0x005b0000",
          "EDX": "0x0000a5ea",
          "ESI": "0x00000008",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a006",
          "ESP": "0x00009ffe",
          "EIP": "0x00000a14",
          "CS": "0x0e83",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 15,
            "bytes": "0f"
          }
        ],
        "cause": "the retrace the input's post ran to, at 0E83:00000A14",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 11,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 424,
    "stop_seq_last": 623,
    "surveyed": 11,
    "by_cause": {
      "the retrace the input's post ran to,": 11
    },
    "unaccounted": 189
  },
  "steps_completed": 11,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**17. `perform`**: OK word: SCRY typed at 20,180, then the line tool again, which ends the text

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "send_mouse",
      "target": "text",
      "button": "left"
    },
    {
      "op": "send_mouse",
      "x": 20,
      "y": 180,
      "button": "left"
    },
    {
      "op": "send_keys",
      "keys": [
        "S",
        "C",
        "R",
        "Y"
      ],
      "modifiers": [
        "shift"
      ]
    },
    {
      "op": "send_mouse",
      "target": "line",
      "button": "left"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 4 of 4 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 314,98; posted, unverified, 25 retraces to frame 1046",
        "status": "ok",
        "stop_seq": 648,
        "cause": "the retrace the input's post ran to, at 0955:00000037"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 20,180; posted, unverified, 25 retraces to frame 1071",
        "status": "ok",
        "stop_seq": 673,
        "cause": "the retrace the input's post ran to, at 1483:000005E7"
      }
    },
    {
      "step": 2,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 50 retraces to frame 1121",
        "status": "ok",
        "stop_seq": 723,
        "cause": "the retrace the input's post ran to, at 0955:0000002A"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 302,51; posted, unverified, 25 retraces to frame 1146",
        "status": "ok",
        "x": 302,
        "y": 51,
        "units": "screen",
        "button": "left",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {
            "x": 302,
            "y": 51,
            "width": 320,
            "height": 200
          },
          "mouse": {
            "x": 2420,
            "y": 412,
            "max_x": 2552,
            "max_y": 1592
          },
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": 25,
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 748,
        "frame": 1146,
        "instruction": {
          "seg_off": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {
            "available": false,
            "why": "no symbol table is loaded"
          },
          "delta": {
            "available": false,
            "why": "no symbol table is loaded"
          }
        },
        "regs": {
          "EAX": "0x0000011c",
          "EBX": "0x0000105c",
          "ECX": "0x005b0000",
          "EDX": "0x00000bc7",
          "ESI": "0x0000ffff",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a00c",
          "ESP": "0x00009ff8",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b0",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b0"
        },
        "watches": [
          {
            "ref": "31B0:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 15,
            "bytes": "0f"
          }
        ],
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
        "e9": {
          "lines_total": 0,
          "truncated": false,
          "lines": [],
          "mark": "<volatile>"
        },
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "target": "line",
        "screen": "paint",
        "identified_at_stop": 2,
        "session": {
          "alive": true,
          "running": false,
          "altered": false
        }
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 624,
    "stop_seq_last": 748,
    "surveyed": 4,
    "by_cause": {
      "the retrace the input's post ran to,": 4
    },
    "unaccounted": 121
  },
  "steps_completed": 4,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0,
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**18. `read_memory`**: OK sun row: the row reads peach x 25, then yellow x 51, then peach x 52

<details><summary>call and reply</summary>

```json
{
  "ref": "A000:7DA0",
  "length": 128
}
```

```json
{
  "summary": "read_memory A000:7DA0: 128 bytes at A000:00007DA0",
  "status": "ok",
  "ref": "A000:7DA0",
  "seg_off": "A000:00007DA0",
  "length": 128,
  "hex": "343434343434343434343434343434343434343434343434340e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e34343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434",
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**19. `read_memory`**: OK boat row: the row reads navy x 30, then brown x 53, then navy x 29

<details><summary>call and reply</summary>

```json
{
  "ref": "A000:C09E",
  "length": 112
}
```

```json
{
  "summary": "read_memory A000:C09E: 112 bytes at A000:0000C09E",
  "status": "ok",
  "ref": "A000:C09E",
  "seg_off": "A000:0000C09E",
  "length": 112,
  "hex": "01010101010101010101010101010101010101010101010101010101010106060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060101010101010101010101010101010101010101010101010101010101",
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**20. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/dpaint/screen.png"
}
```

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 1280x800 PNG x4, inline",
  "status": "ok",
  "vga_mode": "M_VGA",
  "kind": "pixel",
  "width": 320,
  "height": 200,
  "crop": [
    0,
    0,
    320,
    200
  ],
  "image": {
    "path": "./tmp/demos/dpaint/screen.png",
    "bytes": 7911,
    "sha256": "8440167220f277f21c93eac61323f6ab5ae17ea5583c06f1fa4620bd356f959a",
    "width": 1280,
    "height": 800,
    "scale": 4,
    "indexed": true,
    "inline": true
  },
  "display_start": "0h",
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

Also attached: image/png.

</details>

**21. `declaration_clear`**: OK unwatch: watch cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "watch",
  "all": true
}
```

```json
{
  "summary": "declaration_clear watch all: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": [],
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>

**22. `close`**: OK close: closed: quit

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
  "conf": "./demos/dpaint/dpaint.conf",
  "conf_digest": "cd9edac1f1a515a6",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint/dpaint-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": [
    "stdout_tail",
    "errorlog_tail"
  ],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "session": {
    "alive": true,
    "running": false,
    "altered": false
  }
}
```

</details>
<!-- demo-transcript:end -->
