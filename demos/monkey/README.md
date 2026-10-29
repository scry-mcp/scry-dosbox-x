# Monkey Island: the lookout's lines rewritten while the game runs, to the opening theme

![The lookout on Mêlée Island's cliff, talking about Scry](screen.png)

LucasArts' The Secret of Monkey Island, the 1992 Enhanced CD, played here by name: the language
menu, the dock, the poster of the governor by the bar, the path up, the verbs, the lookout and
the lines Guybrush picks are found off a screen map and clicked with the guest's own mouse, and
each screen and each hover the game answers (the sentence line, the verb it lights, the dialogue
line it highlights) is confirmed by name before the next click. Guybrush walks along the dock to
the poster, reads it ("Re-elect Governor Marley"), walks back and climbs to the lookout; the
dialogue menus are picked from as they appear.

Then the demo does what no player can. It saves the machine with the comeback "What the heck is
wrong with `Guybrush Threepwood`?" under the pointer, lets the lookout answer as the game wrote
it, and loads the save. It finds the answer in guest memory and writes a conversation of its own
over the room's script: twenty-two speeches of SCUMM bytecode, the lookout's and Guybrush's,
chained by jumps across three stretches of the script the game no longer needs, and opened by
the intro's own call for the theme. It stops the CD driver's play request as it goes by and moves
its start to the bar where the logo enters. The same comeback is picked again, the theme plays
from that bar, the recording is held to the reader's own disc sample for sample, and the lookout
and Guybrush talk debuggers, AI and orange tycoons until the game takes the conversation back.

The game moves its own pointer by the mouse driver's motion and stops it at the screen's edges,
so it can sit a few pixels away from the driver's. Before the dock appears, behind the title
card, the demo sweeps the pointer to both corners, which stops both at the same place.

## The game

The Secret of Monkey Island is LucasArts' commercial software, and nothing of it is in this
repository: the demo carries its prompt, its script, its conf, its screen map and its own
dialogue, and runs the game from a directory you name. It needs the 1992 Enhanced CD (the OEM
multilingual pressing: English, German, French, Italian and Spanish on one disc, with the music
as Red Book audio tracks) as a CUE sheet and its BINs, `monkey.cue` and `monkey01.bin` to
`monkey25.bin`. The demo checks three of them before anything starts and refuses another
pressing, naming its digest, because the script's addresses and the theme's sectors are that
disc's:

| file | sha256 |
|---|---|
| `monkey.cue` | `6a28d6f905010caef6b0582aaa0e0b60218d5aa3a5b2cc20a7b6265b5f996351` |
| `monkey01.bin` (the data track) | `73cd16ea87fd65af852d06730bdd75cdf3260d0415173deb039af55c17ab5fc8` |
| `monkey18.bin` (the opening theme) | `bebb584e1a2b8a03a4945c379576c631ba8915f1df6d696d7d86c23447189d5a` |

The disc is mounted read-only as D:, and C: is a directory of the run's own, so nothing the game
or the session writes lands in your copy.

## Run it

```sh
uv run python demos/monkey/demo.py \
  --cwd /path/to/your/monkey-cd
```

The demo opens a window, scaled up four times by its conf, so the island can be watched and the
theme heard; nothing in it needs the window.

- `--cwd PATH` (absolute or `~`-led) is the directory holding the disc image. It is hidden in the
  transcript as `<host>`.
- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start; left out, `DOSBOX_X_BINARY`,
  else the `dosbox-x` on your `PATH`. It needs the debugger commands the transcript's `start`
  lists, and a DOSBox-X that plays a CD image at the volume the program asks for: one that
  multiplies the drive's volume by its 0 to 255 value plays the theme four times as loud,
  clipped, and the step that holds the recording to the disc says so.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below and `screen.png` from a run where every step passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2 a
usage error, 3 nothing was demonstrated (no disc image, another pressing of it, a server that did
not start).

## The prompt

Give this to an MCP client with this server connected:

> Start DOSBox-X windowed on `demos/monkey/monkey.conf` (with the disc image and a directory for
> C: written in), running `D:\MONKEY.COM` from `/path/to/your/monkey-cd`, with the log and the
> saved states in files of the run's own. Run 11 seconds, load `monkey.screen-map.json` and tell
> me which screen this is; double-click English. Skip the credits and the opening scene with
> Escape, as a player would, and sweep the pointer to both corners while the title card is up.
> On the dock, walk to the governor's poster, Look at it, and name both lines Guybrush reads;
> walk back and up the cliffside, Talk to the lookout, ask him whether we are all characters in
> a novel, tell him my name, and put the pointer on the comeback, naming each screen and each
> hover as the game answers it and picking each menu as it appears. Save the machine, pick the
> comeback, show me his answer, and load the save. Find his answer in memory, check the script
> around it is the disc's, and write the new conversation over it. Stop on every request to the
> CD driver and pick the comeback again; let the two STOP AUDIO requests through, move the PLAY
> AUDIO request's start to the bar where the logo enters, record eight seconds and hold them to
> that bar of my own disc's track 18. Name five moments of the conversation as it plays, show me
> the screen, and close once the lookout is done and the cliff is back.

## What it walks

| Family | Calls |
|---|---|
| Session | `start` (windowed, the CD image mounted), `close` |
| Advance | `run_for` by milliseconds on the conf's fixed clock, `resume` to a stop, `step` over an `INT` |
| Files | `audio_compare(method="diff")` |
| Input | `send_mouse` by control name off the map, at screen pixels, double; `send_keys` |
| States | `state_write` (`save`, then `load`) |
| Read | `screen_map_write(method="load")`, `screen_map_find`, `find`, `read_memory` |
| Screen | `screen_view` |
| Write | `write` (the conversation, the drive's request) |
| Declarations | `breakpoint_interrupt` (INT 2Fh, AH=15h), `declaration_clear` |
| Lists | `perform` (a gesture: a click, the run it starts, the pointer parked) |
| Captures | `audio_record` (the theme, at the CD's own rate) |

## The transcript

Generated by `demo.py --update-readme` from a run where every step passed. What differs between
two honest runs (process ids, ports, wall-clock times, temporary paths, the host's own DOSBox-X
and its own arguments) is `<volatile>`, and the disc's directory is `<host>`. The bytes the game
holds before the rewrite are `<volatile>` too: the step that reads them gives their sha256
verdict, and this repository carries none of them.

<!-- demo-transcript:begin -->
**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./tmp/demos/monkey/monkey.conf",
  "session_seconds": 1800,
  "shared": true,
  "program": "D:\\MONKEY.COM",
  "logfile": "./tmp/demos/monkey/monkey-e9.log",
  "state_dir": "./tmp/demos/monkey/monkey-states",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./tmp/demos/monkey/monkey.conf",
  "conf_digest": "6a9bcbf4f99ebccc",
  "watched": true,
  "bound_s": 1800,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/monkey/monkey-states",
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
  "session": "<volatile>"
}
```

</details>

**2. `run_for`**: OK menu: 11.0 s of the guest's time

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 11000,
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 681,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=6 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "emulated_before_s": 0.00085,
  "emulated_after_s": 11.00330265,
  "frame_before": 0,
  "frame_after": 681,
  "cycles": 172220499,
  "session": "<volatile>"
}
```

</details>

**3. `screen_map_write`**: OK map: 23 screens, 60 controls

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/monkey/monkey.screen-map.json"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "path": "./demos/monkey/monkey.screen-map.json",
  "application": "monkey",
  "mode": "verified",
  "screens": 23,
  "controls": 60,
  "session": "<volatile>"
}
```

</details>

**4. `screen_map_find`**: OK languages: the map says: language

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "matched": true,
  "screen": "language",
  "layer": "file",
  "kind": "pixel",
  "size": [640, 480],
  "controls": [
    {"name": "english", "rect": [60, 412, 40, 50], "centre": [80, 437]},
    {"name": "french", "rect": [168, 412, 60, 50], "centre": [198, 437]},
    {"name": "german", "rect": [280, 412, 60, 50], "centre": [310, 437]},
    {"name": "italian", "rect": [395, 412, 60, 50], "centre": [425, 437]},
    {"name": "spanish", "rect": [512, 412, 60, 50], "centre": [542, 437]}
  ],
  "session": "<volatile>"
}
```

</details>

**5. `perform`**: OK english: a double click on English, and the intro run on

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "english", "button": "left", "action": "double"},
    {"op": "run_for", "milliseconds": 24000}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "verdict": "ELAPSED",
        "polls": "<volatile>",
        "pc": "<volatile>",
        "cpu_mode": "real",
        "frame": 2392,
        "regs": "<volatile>",
        "watches": [],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "stop_seq": "<volatile>",
        "instruction": "<volatile>",
        "emulated_before_s": 11.52048965,
        "emulated_after_s": 35.5251577,
        "frame_before": 712,
        "frame_after": 2392,
        "cycles": 466932355,
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**6. `perform`**: OK skip: Escape twice, as a player skips the credits and the opening scene; behind the title card, the pointer swept to both corners so the game's own pointer and the driver's agree

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "run_for", "milliseconds": 6000},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "run_for", "milliseconds": 3000},
    {"op": "send_mouse", "x": 319, "y": 199},
    {"op": "send_mouse", "x": 0, "y": 0},
    {"op": "send_mouse", "x": 250, "y": 20}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_keys",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "send_keys",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "x": 250,
        "y": 20,
        "units": "screen",
        "route": "guest",
        "pointer": {
          "screen": {"x": 250, "y": 20, "width": 320, "height": 200},
          "mouse": {"x": 500, "y": 20, "max_x": 639, "max_y": 199},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": "<volatile>",
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": "<volatile>",
        "frame": 3077,
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
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 7,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 7,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**7. `perform`**: OK dock: the map says: dock

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 16000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "dock",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "give", "rect": [4, 154, 32, 12], "centre": [20, 160]},
          {"name": "pick_up", "rect": [46, 154, 52, 12], "centre": [72, 160]},
          {"name": "use", "rect": [104, 154, 34, 12], "centre": [121, 160]},
          {"name": "open", "rect": [4, 170, 32, 12], "centre": [20, 176]},
          {"name": "look_at", "rect": [46, 170, 52, 12], "centre": [72, 176]},
          {"name": "push", "rect": [104, 170, 34, 12], "centre": [121, 176]},
          {"name": "close", "rect": [4, 186, 32, 12], "centre": [20, 192]},
          {"name": "talk_to", "rect": [46, 186, 52, 12], "centre": [72, 192]},
          {"name": "pull", "rect": [104, 186, 34, 12], "centre": [121, 192]},
          {"name": "cliffside", "rect": [30, 100, 20, 20], "centre": [40, 110]},
          {"name": "poster", "rect": [262, 92, 18, 26], "centre": [271, 105]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**8. `perform`**: OK hover poster: the map says: dock: walk to poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "dock: walk to poster",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "poster", "rect": [262, 92, 18, 26], "centre": [271, 105]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**9. `perform`**: OK to the poster: the map says: by the poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster", "button": "left", "action": "click"},
    {"op": "run_for", "milliseconds": 8000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "by the poster",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "give", "rect": [4, 154, 32, 12], "centre": [20, 160]},
          {"name": "pick_up", "rect": [46, 154, 52, 12], "centre": [72, 160]},
          {"name": "use", "rect": [104, 154, 34, 12], "centre": [121, 160]},
          {"name": "open", "rect": [4, 170, 32, 12], "centre": [20, 176]},
          {"name": "look_at", "rect": [46, 170, 52, 12], "centre": [72, 176]},
          {"name": "push", "rect": [104, 170, 34, 12], "centre": [121, 176]},
          {"name": "close", "rect": [4, 186, 32, 12], "centre": [20, 192]},
          {"name": "talk_to", "rect": [46, 186, 52, 12], "centre": [72, 192]},
          {"name": "pull", "rect": [104, 186, 34, 12], "centre": [121, 192]},
          {"name": "poster", "rect": [158, 76, 20, 24], "centre": [168, 88]},
          {"name": "way_back", "rect": [0, 105, 10, 20], "centre": [5, 115]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**10. `perform`**: OK look at: the map says: by the poster: look at poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "look_at", "button": "left", "action": "click"},
    {"op": "send_mouse", "target": "poster"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "by the poster: look at poster",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "poster", "rect": [158, 76, 20, 24], "centre": [168, 88]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**11. `perform`**: OK read: the map says: poster: re-elect governor marley

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster", "button": "left", "action": "click"},
    {"op": "run_for", "milliseconds": 1500},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "poster: re-elect governor marley",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**12. `perform`**: OK read on: the map says: poster: only one candidate

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 2000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "poster: only one candidate",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**13. `perform`**: OK done reading: the map says: by the poster: walk to poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 3500},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "by the poster: walk to poster",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "poster", "rect": [158, 76, 20, 24], "centre": [168, 88]},
          {"name": "way_back", "rect": [0, 105, 10, 20], "centre": [5, 115]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**14. `perform`**: OK way back: the map says: dock: walk to cliffside

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "way_back", "button": "left", "action": "click"},
    {"op": "run_for", "milliseconds": 4000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "dock: walk to cliffside",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "cliffside", "rect": [30, 100, 20, 20], "centre": [40, 110]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**15. `perform`**: OK climb: the map says: cliff

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "cliffside", "button": "left", "action": "click"},
    {"op": "run_for", "milliseconds": 8000},
    {"op": "send_mouse", "x": 250, "y": 20},
    {"op": "run_for", "frames": 10},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "cliff",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "give", "rect": [4, 154, 32, 12], "centre": [20, 160]},
          {"name": "pick_up", "rect": [46, 154, 52, 12], "centre": [72, 160]},
          {"name": "use", "rect": [104, 154, 34, 12], "centre": [121, 160]},
          {"name": "open", "rect": [4, 170, 32, 12], "centre": [20, 176]},
          {"name": "look_at", "rect": [46, 170, 52, 12], "centre": [72, 176]},
          {"name": "push", "rect": [104, 170, 34, 12], "centre": [121, 176]},
          {"name": "close", "rect": [4, 186, 32, 12], "centre": [20, 192]},
          {"name": "talk_to", "rect": [46, 186, 52, 12], "centre": [72, 192]},
          {"name": "pull", "rect": [104, 186, 34, 12], "centre": [121, 192]},
          {"name": "lookout", "rect": [94, 66, 16, 20], "centre": [102, 76]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 5,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 5,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**16. `perform`**: OK talk to: the map says: cliff: talk to lookout

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "talk_to", "button": "left", "action": "click"},
    {"op": "send_mouse", "target": "lookout"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "cliff: talk to lookout",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "lookout", "rect": [94, 66, 16, 20], "centre": [102, 76]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**17. `perform`**: OK greet: the map says: greeting choices

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "lookout", "button": "left", "action": "click"},
    {"op": "run_for", "frames": 87},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "greeting choices",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "weenie_roast", "rect": [0, 144, 120, 8], "centre": [60, 148]},
          {"name": "looking_for_fun", "rect": [0, 152, 120, 8], "centre": [60, 156]},
          {"name": "thousand_legs", "rect": [0, 160, 120, 8], "centre": [60, 164]},
          {"name": "characters_in_a_novel", "rect": [0, 168, 320, 8], "centre": [160, 172]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**18. `perform`**: OK hover novel: the map says: greeting: characters in a novel

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "characters_in_a_novel"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "greeting: characters in a novel",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "characters_in_a_novel", "rect": [0, 168, 320, 8], "centre": [160, 172]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**19. `perform`**: OK ask: the map says: name choices

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "characters_in_a_novel", "button": "left", "action": "click"},
    {"op": "send_mouse", "x": 160, "y": 60},
    {"op": "run_for", "frames": 1046},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "name choices",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "im_guybrush_threepwood", "rect": [0, 144, 120, 8], "centre": [60, 148]},
          {"name": "call_me_squinky", "rect": [0, 152, 120, 8], "centre": [60, 156]},
          {"name": "im_over_this_way", "rect": [0, 160, 120, 8], "centre": [60, 164]},
          {"name": "who_are_you", "rect": [0, 168, 120, 8], "centre": [60, 172]},
          {"name": "seek_my_fortune", "rect": [0, 176, 120, 8], "centre": [60, 180]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**20. `perform`**: OK hover name: the map says: name: im guybrush threepwood

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "im_guybrush_threepwood"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "name: im guybrush threepwood",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "im_guybrush_threepwood", "rect": [0, 144, 120, 8], "centre": [60, 148]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**21. `perform`**: OK tell: the map says: name choices again

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "im_guybrush_threepwood", "button": "left", "action": "click"},
    {"op": "send_mouse", "x": 160, "y": 60},
    {"op": "run_for", "frames": 1263},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "name choices again",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "whats_wrong_with_my_name", "rect": [0, 144, 120, 8], "centre": [60, 148]},
          {"name": "call_me_squinky", "rect": [0, 152, 120, 8], "centre": [60, 156]},
          {"name": "im_over_this_way", "rect": [0, 160, 120, 8], "centre": [60, 164]},
          {"name": "who_are_you", "rect": [0, 168, 120, 8], "centre": [60, 172]},
          {"name": "seek_my_fortune", "rect": [0, 176, 120, 8], "centre": [60, 180]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**22. `perform`**: OK hover heck: the map says: name: whats wrong with my name

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "whats_wrong_with_my_name"},
    {"op": "run_for", "frames": 5},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "name: whats wrong with my name",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "whats_wrong_with_my_name", "rect": [0, 144, 120, 8], "centre": [60, 148]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**23. `state_write`**: OK save: the machine saved with the comeback under the pointer

<details><summary>call and reply</summary>

```json
{
  "method": "save",
  "name": "comeback"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "comeback",
  "path": "./tmp/demos/monkey/monkey-states/comeback.sav",
  "bytes": "<volatile>",
  "version": "<volatile>",
  "program": "MONKEY",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": false,
  "session": "<volatile>"
}
```

</details>

**24. `perform`**: OK before: the map says: lookout: sell shoes

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "whats_wrong_with_my_name", "button": "left", "action": "click"},
    {"op": "run_for", "milliseconds": 4000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "lookout: sell shoes",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**25. `state_write`**: OK restore: the machine back to before the click

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "name": "comeback"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "comeback",
  "path": "./tmp/demos/monkey/monkey-states/comeback.sav",
  "version": "<volatile>",
  "program": "MONKEY",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": false,
  "mark": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**26. `screen_map_find`**: OK heck again?: the map says: name: whats wrong with my name

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "matched": true,
  "screen": "name: whats wrong with my name",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "whats_wrong_with_my_name", "rect": [0, 144, 120, 8], "centre": [60, 148]}
  ],
  "stopped_on_its_own": {"stop_seq": "<volatile>", "pc": "<volatile>", "cause": "<volatile>"},
  "session": "<volatile>"
}
```

</details>

**27. `find`**: OK needle: the lookout's line, once, at 82DB:0000000F

<details><summary>call and reply</summary>

```json
{
  "data_hex": "4e6f7468696e672c20696620796f752077616e7420746f2073656c6c2073686f65732e",
  "ref": "0000:0000",
  "length": 655360
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "0000:0000",
  "seg_off": "0000:00000000",
  "length": 655360,
  "span": {"from": "0000:00000000", "length": 655360, "source": "ref+length"},
  "hits": ["82DB:0000000F"],
  "hits_total": 1,
  "truncated": false,
  "session": "<volatile>"
}
```

</details>

**28. `perform`**: OK script: 1371 bytes around the line are the disc's own script, hole by hole

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "read_memory", "ref": "82DB:000C", "length": 128},
    {"op": "read_memory", "ref": "82E3:000C", "length": 101},
    {"op": "read_memory", "ref": "82C3:000C", "length": 128},
    {"op": "read_memory", "ref": "82CB:000C", "length": 128},
    {"op": "read_memory", "ref": "82D3:000C", "length": 128},
    {"op": "read_memory", "ref": "82EB:000D", "length": 128},
    {"op": "read_memory", "ref": "82F3:000D", "length": 128},
    {"op": "read_memory", "ref": "82FB:000D", "length": 128},
    {"op": "read_memory", "ref": "8303:000D", "length": 128},
    {"op": "read_memory", "ref": "830B:000D", "length": 128},
    {"op": "read_memory", "ref": "8313:000D", "length": 90},
    {"op": "read_memory", "ref": "82EA:0001", "length": 28}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": "<volatile>",
  "steps_total": 12,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 12,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**29. `perform`**: OK rewrite: 22 speeches, 1259 bytes of bytecode over 3 holes, each read back

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "write",
      "ref": "82DB:000C",
      "data_hex": "1c6e14020f4e6f7468696e672c20696620796f75277265206120536372792064656275676765722eff0349742073746f70732074696d652c207265616473206d696e647320616e6420706c617973207468652074756e65732eff034576656e206d79206d696e642e00ae02d80f41206465627567676572207468617420706c61"
    },
    {
      "op": "write",
      "ref": "82E3:000C",
      "data_hex": "7973206d757369633f20204973205448415420776861742049276d2068656172696e673f3f00ae0214020f546861742773207468652043442e202053637279206a75737420746f6c6420697420776865726520746f2073746172742e00ae02189efd"
    },
    {
      "op": "write",
      "ref": "82C3:000C",
      "data_hex": "d80f57686f20746175676874206120646562756767657220746f20646f20746861743f00ae0214020f41206d6f64656c2e20204c6976657320696e206120626f782c20726561647320796f7572206d656d6f72792c206e6576657220736c656570732e00ae02d80f4c696b65206f6e65206f662074686f736520626967204149"
    },
    {
      "op": "write",
      "ref": "82CB:000C",
      "data_hex": "20636f6d70616e6965733f00ae0214020f5468656d3f20204120646f75626c6f6f6e206120776f72642e202054776f20696620796f75207361792060706c65617365602e00ae02d80f416e6420536372793f00ae0214020f467265652e2020416e64206974206e657665722073617973206041732061206c61726765206c616e"
    },
    {
      "op": "write",
      "ref": "82D3:000C",
      "data_hex": "6775616765207069726174655e6000ae0214020f48656172642061626f757420746865206f72616e6765207479636f6f6e3f00ae02d80f546865206f6e652077686f2063616c6c73206576657279206275672066616b65206e6577733f00ae02181e01"
    },
    {
      "op": "write",
      "ref": "82EB:000D",
      "data_hex": "14020f4e6f772068652077616e747320746f2072656e616d6520414920746f2053492eff0360537570657220496e74656c6c6967656e6365602e20205472656d656e646f75732e202054686520626573742e00ae02d80f446f65732053492072656c65617365206974732066696c65733f00ae0214020f536372792072656c65"
    },
    {
      "op": "write",
      "ref": "82F3:000D",
      "data_hex": "617365732065766572792066696c652069742066696e64732e202045766572792e20204c6173742e20204f6e652eff03556e6c696b652074686f7365204570737465696e2066696c65732e20204168656d2100ae02d80f416e642068697320726f636b657420667269656e643f00ae0214020f546865206f6e652077686f7365"
    },
    {
      "op": "write",
      "ref": "82FB:000D",
      "data_hex": "20686561727420666c6577206f7574207468726f756768206869732061726d3fff0354776963652eff03536372792073746570706564207468726f756768206974206672616d65206279206672616d652e20205374696c6c206e6f74206120776176652e00ae02d80f53686f756c642053637279206465627567207468656d20"
    },
    {
      "op": "write",
      "ref": "8303:000D",
      "data_hex": "626f74683f00ae0214020f4e6f7420656e6f7567682052414d206f6e20746869732077686f6c652069736c616e642c20626f792e00ae02d80f476f7420616e79206a6f6b6573206c6566743f00ae0214020f506c656e74792e2020427574206d79206c6174652073686f7720676f742063616e63656c6c65642eff03536f2053"
    },
    {
      "op": "write",
      "ref": "830B:000D",
      "data_hex": "6372792072756e73206974206e6f772e202048756d6f722066697273742c2063726173686573207365636f6e642e00ae02d80f49276c6c206a757374206265206f666620746f207365656b206d7920666f7274756e65206e6f772e00ae0214020f54616b652053637279207769746820796f752eff03416e6420636c65617220"
    },
    {
      "op": "write",
      "ref": "8313:000D",
      "data_hex": "7468617420627265616b706f696e74206f6e20796f757220776179206f75742e00ae02183efd"
    }
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 6,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 7,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 8,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 9,
      "op": "write",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 10,
      "op": "write",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "ref": "8313:000D",
        "seg_off": "8313:0000000D",
        "bytes_written": 38,
        "readback": "7468617420627265616b706f696e74206f6e20796f757220776179206f75742e00ae02183efd",
        "verified": true,
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 11,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 11,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**30. `breakpoint_interrupt`**: OK arm: a stop on every request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "number": 47,
  "ah": 21
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "BPINT 2F AH=15",
  "stored": true,
  "armed": true,
  "entry": "BPINT 2F AH=15",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": "<volatile>"
}
```

</details>

**31. `perform`**: OK pick: the same comeback, picked again

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "whats_wrong_with_my_name", "button": "left", "action": "click"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "x": 60,
        "y": 148,
        "units": "screen",
        "button": "left",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {"x": 60, "y": 148, "width": 320, "height": 200},
          "mouse": {"x": 120, "y": 148, "max_x": 639, "max_y": 199},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "arrived": true,
        "polls": "<volatile>",
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": "<volatile>",
        "frame": 9163,
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
        "target": "whats_wrong_with_my_name",
        "screen": "name: whats wrong with my name",
        "identified_at_stop": 433,
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 1,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 1,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**32. `resume`**: OK first: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 9424,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**33. `read_memory`**: OK request 1: STOP AUDIO (85h), let through

<details><summary>call and reply</summary>

```json
{
  "ref": "2209:1D8E",
  "length": 22
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "2209:1D8E",
  "seg_off": "2209:00001D8E",
  "length": 22,
  "hex": "0d008500010000000000000000001a00030001000000",
  "session": "<volatile>"
}
```

</details>

**34. `perform`**: OK pass 1: the request answered

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "step", "mode": "over"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "step",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "mode": "over",
        "asked": 1,
        "moved": true,
        "stalled": 0,
        "before": "193C:00006BCB",
        "after": "193C:00006BCD",
        "instructions_completed": 1,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "frame": 9424,
        "regs": "<volatile>",
        "watches": [],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "stop_seq": "<volatile>",
        "instruction": "<volatile>",
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 1,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 1,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**35. `resume`**: OK second: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 9424,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**36. `read_memory`**: OK request 2: STOP AUDIO (85h), let through

<details><summary>call and reply</summary>

```json
{
  "ref": "2209:1D8E",
  "length": 22
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "2209:1D8E",
  "seg_off": "2209:00001D8E",
  "length": 22,
  "hex": "0d008500010000000000000000001a00030001000000",
  "session": "<volatile>"
}
```

</details>

**37. `perform`**: OK pass 2: the request answered

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "step", "mode": "over"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "step",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "mode": "over",
        "asked": 1,
        "moved": true,
        "stalled": 0,
        "before": "193C:00006BCB",
        "after": "193C:00006BCD",
        "instructions_completed": 1,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "frame": 9424,
        "regs": "<volatile>",
        "watches": [],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "stop_seq": "<volatile>",
        "instruction": "<volatile>",
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 1,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 1,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**38. `resume`**: OK third: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 9424,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**39. `read_memory`**: OK request 3: PLAY AUDIO (84h) from 36:45:00, the theme's first sector, for 12200 sectors

<details><summary>call and reply</summary>

```json
{
  "ref": "2209:1D78",
  "length": 22
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "2209:1D78",
  "seg_off": "2209:00001D78",
  "length": 22,
  "hex": "1600840003000000000000000001002d2400a82f0000",
  "session": "<volatile>"
}
```

</details>

**40. `write`**: OK to the logo: the drive will start at 37:05:67, the logo's bar

<details><summary>call and reply</summary>

```json
{
  "ref": "2209:1D86",
  "data_hex": "4305250089290000"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "2209:1D86",
  "seg_off": "2209:00001D86",
  "bytes_written": 8,
  "readback": "4305250089290000",
  "verified": true,
  "session": "<volatile>"
}
```

</details>

**41. `declaration_clear`**: OK disarm: the stop on the CD driver cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "breakpoint",
  "all": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BPINT 2F AH=15"],
  "session": "<volatile>"
}
```

</details>

**42. `audio_record`**: OK theme: 8.0 s of the mixer at 44100 Hz

<details><summary>call and reply</summary>

```json
{
  "frames": 560,
  "dest": "./tmp/demos/monkey/theme.wav"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 9984,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "emulated_before_s": 131.59102925,
  "emulated_after_s": 139.62394595,
  "frame_before": 9424,
  "frame_after": 9984,
  "cycles": 159963815,
  "kind": "wav",
  "frames": 560,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/monkey/theme.wav",
  "bytes": 1416892,
  "channels": 2,
  "sample_rate_hz": 44100,
  "samples": 354212,
  "emulated_s": 8.0329167,
  "sample_min": -17908,
  "sample_max": 18280,
  "session": "<volatile>"
}
```

</details>

**43. `audio_compare`**: OK the disc: the reader's own track 18 from the logo's bar, sample for sample, SNR 48.61 dB

<details><summary>call and reply</summary>

```json
{
  "method": "diff",
  "a": "./tmp/demos/monkey/theme.wav",
  "b": "./tmp/demos/monkey/theme-disc.wav",
  "align": false
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "exact": false,
  "snr_db": 48.61,
  "class": "audible",
  "envelope_correlation": 1.0,
  "onset_delta_ms": 0.0,
  "length_delta_samples": 0,
  "aligned_by_samples": 0,
  "a": "./tmp/demos/monkey/theme.wav",
  "b": "./tmp/demos/monkey/theme-disc.wav",
  "session": "<volatile>"
}
```

</details>

**44. `screen_map_find`**: OK music?: the map says: guybrush: a debugger that plays music

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "matched": true,
  "screen": "guybrush: a debugger that plays music",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [],
  "session": "<volatile>"
}
```

</details>

**45. `perform`**: OK talk 1: the map says: lookout: the orange tycoon

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 28000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "lookout: the orange tycoon",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**46. `perform`**: OK talk 2: the map says: lookout: those files

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 16000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "lookout: those files",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**47. `perform`**: OK talk 3: the map says: lookout: still not a wave

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 12000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "lookout: still not a wave",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**48. `perform`**: OK talk 4: the map says: lookout: humor first

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 12000},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "lookout: humor first",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**49. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/monkey/screen.png",
  "scale": 2
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "vga_mode": "M_VGA",
  "kind": "pixel",
  "width": 320,
  "height": 200,
  "mode": "render",
  "crop": [0, 0, 320, 200],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/monkey/screen.png",
    "bytes": 22254,
    "sha256": "2a20deda2abdf6e1ea68ec73c3fe5cb1e09d7a38e4372aceeb7e2b6ebd7509f0",
    "width": 640,
    "height": 400,
    "scale": 2,
    "indexed": true,
    "inline": true
  },
  "display_start": "0h",
  "session": "<volatile>"
}
```

Also attached: image/png.

</details>

**50. `perform`**: OK goodbye: the map says: cliff

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "run_for", "milliseconds": 30000},
    {"op": "send_mouse", "x": 250, "y": 20},
    {"op": "run_for", "frames": 10},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "cliff",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [
          {"name": "give", "rect": [4, 154, 32, 12], "centre": [20, 160]},
          {"name": "pick_up", "rect": [46, 154, 52, 12], "centre": [72, 160]},
          {"name": "use", "rect": [104, 154, 34, 12], "centre": [121, 160]},
          {"name": "open", "rect": [4, 170, 32, 12], "centre": [20, 176]},
          {"name": "look_at", "rect": [46, 170, 52, 12], "centre": [72, 176]},
          {"name": "push", "rect": [104, 170, 34, 12], "centre": [121, 176]},
          {"name": "close", "rect": [4, 186, 32, 12], "centre": [20, 192]},
          {"name": "talk_to", "rect": [46, 186, 52, 12], "centre": [72, 192]},
          {"name": "pull", "rect": [104, 186, 34, 12], "centre": [121, 192]},
          {"name": "lookout", "rect": [94, 66, 16, 20], "centre": [102, 76]}
        ],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**51. `close`**: OK close: closed: quit

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "closed": true,
  "pid": "<volatile>",
  "conf": "./tmp/demos/monkey/monkey.conf",
  "conf_digest": "6a9bcbf4f99ebccc",
  "watched": true,
  "bound_s": 1800,
  "elapsed_s": "<volatile>",
  "output_bytes_dropped": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/monkey/monkey-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "session": "<volatile>"
}
```

</details>
<!-- demo-transcript:end -->
