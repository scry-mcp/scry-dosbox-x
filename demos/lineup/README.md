# LineUp: one script, two machines

![LineUp in play on the PC port](screen.png)

*LineUp* (Eco-Games / GAMART, 1994) was an arcade game on an NEC V30 board, and its team later
ported the same source to MS-DOS: VGA mode 13h and a Sound Blaster 16. This demo plays the PC port
with the very script the MAME server plays the arcade board with, `scry_core.games.lineup`: the
same steps, the same symbols, the same screen map, the same checks. Only a short binding differs
per machine: how it starts, which key is the coin, the screen's refresh, and the recording its
sound is held to. A script that needs anything more is a place where the two servers disagree.

It runs to the routine that draws the high scores by name, drops a coin and reads the credits the
game counted, starts a game, runs to the routine that writes its level, and plays: one column right,
the next colour, a shot, each read back off the player's own variables. Each screen it arrives at
is recognised off a map signed in palette indices, because the VGA's 6-bit DAC and the arcade's
5-bit palette show the same pixels in slightly different colours. Then it records two seconds of
the stage's music off the Sound Blaster and holds it, sample for sample, to [`music.wav`](music.wav)
beside this file.

## The game

LineUp is not distributed with this repository. The demo runs a copy of the PC port: a directory
holding `EXES/LINEUP.EXE` with the linker's symbol map beside it, `EXES/LINEUP.MAP`, and the
game's own `AUDIO/` and `GFX/`.

## Run it

```sh
uv run python demos/lineup/demo.py --cwd /path/to/game
```

The demo opens a window, the 320 x 200 screen drawn four times over by its conf, so the game can
be watched; nothing in it needs the window.

- `--cwd PATH` (absolute or `~`-led) is the copy of the game DOSBox-X runs from.
- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start; left out, `DOSBOX_X_BINARY`,
  else the `dosbox-x` on your `PATH`.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites the block below and `screen.png` from a run where every step passed.

Each step prints one `OK <step>: <summary>` or `FAIL <step>: <why>` line, then a `DEMO` verdict
line and the paths of the two transcripts. Exit codes: 0 every step passed, 1 a step failed, 2 a
usage error, 3 nothing was demonstrated (no copy of the game, a server that did not start).

## The prompt

Give this to an MCP client with this server connected:

> Start a session from `demos/lineup/lineup.conf` (its `@GUEST@` replaced by this repository's
> `guest` directory) running from the game's directory, with `EXES/LINEUP.MAP` as its symbols,
> and run it two seconds, which places the map where DOS loaded the game. Load the screen map
> `scry_core/games/lineup.screen-map.json` from scry-core. Run to
> `Draw_High_Scores_Screen` counting `Check_Money25`, run a second and a half and tell me which
> screen it is and what `Credits` holds. Press Tab, run a second, name the screen and read
> `Credits` again. Press 1, run to `Level_Write`, run 200 ms, name the screen and read `Credits`
> and `Stage_Act`. Run three seconds, name the screen and read the first six words of `Player1`.
> Press the right arrow, the space bar and the up arrow, letting the game run 200, 200 and 100 ms
> after each before reading `Player1`. Record two
> seconds of sound, measure it and compare it with `music.wav`, take a picture of the screen and
> close the session.

## What it walks

<!-- demo-transcript:begin -->
**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./tmp/demos/lineup/lineup.conf",
  "session_seconds": 900,
  "shared": true,
  "symbols": "./tmp/demos/lineup/LINEUP.MAP",
  "state_dir": "./tmp/demos/lineup/lineup-states",
  "captures_dir": "./tmp/demos/lineup/lineup-captures",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./tmp/demos/lineup/lineup.conf",
  "conf_digest": "ce1af912359f3aef",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/lineup/lineup-states",
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
  "symbols": {"held": "./tmp/demos/lineup/LINEUP.MAP", "base_from": "program"},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `run_for`**: OK boot: booted: DOS running the game, its map placed at segment 08ED, 385 symbols

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 2000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 2000 ms: ELAPSED, 141 polls, at 08ED:00001CAE",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 141,
  "pc": "08ED:00001CAE",
  "cpu_mode": "real",
  "frame": 141,
  "regs": {
    "EAX": "0x00000020",
    "EBX": "0x0000000a",
    "ECX": "0x005b0000",
    "EDX": "0x00000000",
    "ESI": "0x00001260",
    "EDI": "0x00000dfd",
    "EBP": "0x00004288",
    "ESP": "0x00004282",
    "EIP": "0x00001cae",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:00001CAE",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08ED:00001CAE",
    "bytes": "74F9",
    "text": "je 0x1ca9",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Pal_Off",
    "delta": 127
  },
  "symbols_placed": {
    "placed": true,
    "path": "./tmp/demos/lineup/LINEUP.MAP",
    "load_segment": "08ED",
    "base": 36560,
    "loaded": 385
  },
  "emulated_before_s": 0.00094,
  "emulated_after_s": 2.00347702,
  "frame_before": 0,
  "frame_after": 141,
  "cycles": 96579553,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_map_write`**: OK map: 4 screens and 10 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./tmp/demos/lineup/lineup.screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 4 screens, 10 controls of lineup",
  "status": "ok",
  "path": "./tmp/demos/lineup/lineup.screen-map.json",
  "application": "lineup",
  "mode": "verified",
  "screens": 4,
  "controls": 10,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `run_to`**: OK to the high scores: stopped at Draw_High_Scores_Screen

<details><summary>call and reply</summary>

```json
{
  "ref": "Draw_High_Scores_Screen",
  "control": "Check_Money25",
  "seconds": 120
}
```

```json
{
  "summary": "run_to Draw_High_Scores_Screen: TARGET at 08ED:00001DF6, control counted 150",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08ED:1DF6",
  "ref": "Draw_High_Scores_Screen",
  "pc": "08ED:00001DF6",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 150,
  "controls": [
    {"ref": "Check_Money25", "at": "08ED:19DC", "hits_in_run": 150, "removed": true}
  ],
  "frame": 351,
  "regs": {
    "EAX": "0x00000a56",
    "EBX": "0x00000002",
    "ECX": "0x005b4208",
    "EDX": "0x00000000",
    "ESI": "0x00000024",
    "EDI": "0x0000fb28",
    "EBP": "0x00004288",
    "ESP": "0x00004284",
    "EIP": "0x00001df6",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "run_to's target Draw_High_Scores_Screen at 08ED:00001DF6",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 3,
  "instruction": {
    "address": "08ED:00001DF6",
    "bytes": "1E",
    "text": "push ds",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Draw_High_Scores_Screen",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `run_for`**: OK drawn: the table drawn

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 1500,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 1500 ms: ELAPSED, 106 polls, at 08ED:00001CAE",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 106,
  "pc": "08ED:00001CAE",
  "cpu_mode": "real",
  "frame": 457,
  "regs": {
    "EAX": "0x00000030",
    "EBX": "0x0000000a",
    "ECX": "0x005b0000",
    "EDX": "0x00000000",
    "ESI": "0x00001260",
    "EDI": "0x00000dfd",
    "EBP": "0x00004288",
    "ESP": "0x00004282",
    "EIP": "0x00001cae",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:00001CAE",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 4,
  "instruction": {
    "address": "08ED:00001CAE",
    "bytes": "74F9",
    "text": "je 0x1ca9",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Pal_Off",
    "delta": 127
  },
  "emulated_before_s": 5.00021248,
  "emulated_after_s": 6.5121853000000005,
  "frame_before": 351,
  "frame_after": 457,
  "cycles": 73158830,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `screen_map_find`**: OK is hiscores: the hiscores screen, its controls table, credits

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: hiscores (file), 2 controls",
  "status": "ok",
  "matched": true,
  "screen": "hiscores",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "table", "rect": [64, 30, 192, 145], "centre": [160, 102]},
    {"name": "credits", "rect": [230, 186, 76, 12], "centre": [268, 192]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `read_memory`**: OK no credits: Credits holds 0

<details><summary>call and reply</summary>

```json
{
  "ref": "Credits",
  "length": 2
}
```

```json
{
  "summary": "read_memory Credits: 2 bytes at 08ED:0000BC04: 0000",
  "status": "ok",
  "ref": "Credits",
  "seg_off": "08ED:0000BC04",
  "length": 2,
  "hex": "0000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `send_keys`**: OK press coin: COIN pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["tab"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 463",
  "status": "ok",
  "keys": ["tab"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "F000:0000CA40",
  "cpu_mode": "real",
  "stop_seq": 10,
  "frame": 463,
  "instruction": {
    "address": "F000:0000CA40",
    "bytes": "90",
    "text": "nop",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "outside the loaded table's span"},
    "delta": {"available": false, "why": "outside the loaded table's span"}
  },
  "regs": {
    "EAX": "0x00003f8e",
    "EBX": "0x00000007",
    "ECX": "0x005b7f7e",
    "EDX": "0x00000000",
    "ESI": "0x000082db",
    "EDI": "0x00000007",
    "EBP": "0x00004214",
    "ESP": "0x00004206",
    "EIP": "0x0000ca40",
    "CS": "0xf000",
    "DS": "0x88ee",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at F000:0000CA40",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `run_for`**: OK counted: the coin counted

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 1000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 1000 ms: ELAPSED, 71 polls, at 08ED:00001CAE",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 71,
  "pc": "08ED:00001CAE",
  "cpu_mode": "real",
  "frame": 534,
  "regs": {
    "EAX": "0x00000020",
    "EBX": "0x0000000a",
    "ECX": "0x005b0000",
    "EDX": "0x00000000",
    "ESI": "0x00001260",
    "EDI": "0x00000dfd",
    "EBP": "0x00004288",
    "ESP": "0x00004282",
    "EIP": "0x00001cae",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:00001CAE",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 11,
  "instruction": {
    "address": "08ED:00001CAE",
    "bytes": "74F9",
    "text": "je 0x1ca9",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Pal_Off",
    "delta": 127
  },
  "emulated_before_s": 6.59778594,
  "emulated_after_s": 7.61082626,
  "frame_before": 463,
  "frame_after": 534,
  "cycles": 48952839,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `screen_map_find`**: OK is insert: the insert screen, its controls banner, credits

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: insert (file), 2 controls",
  "status": "ok",
  "matched": true,
  "screen": "insert",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "banner", "rect": [0, 6, 320, 22], "centre": [160, 17]},
    {"name": "credits", "rect": [230, 186, 76, 12], "centre": [268, 192]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `read_memory`**: OK credits: Credits holds 3

<details><summary>call and reply</summary>

```json
{
  "ref": "Credits",
  "length": 2
}
```

```json
{
  "summary": "read_memory Credits: 2 bytes at 08ED:0000BC04: 0300",
  "status": "ok",
  "ref": "Credits",
  "seg_off": "08ED:0000BC04",
  "length": 2,
  "hex": "0300",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `send_keys`**: OK press start: START pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["1"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 540",
  "status": "ok",
  "keys": ["1"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "08ED:00009241",
  "cpu_mode": "real",
  "stop_seq": 17,
  "frame": 540,
  "instruction": {
    "address": "08ED:00009241",
    "bytes": "7407",
    "text": "je 0x924a",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_gfx_load_bg",
    "delta": 206
  },
  "regs": {
    "EAX": "0x0000013a",
    "EBX": "0x0000df75",
    "ECX": "0x005b423a",
    "EDX": "0x000067e8",
    "ESI": "0x00000200",
    "EDI": "0x000001da",
    "EBP": "0x00004266",
    "ESP": "0x00004254",
    "EIP": "0x00009241",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 08ED:00009241",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `run_to`**: OK to the level: stopped at Level_Write

<details><summary>call and reply</summary>

```json
{
  "ref": "Level_Write",
  "control": "Check_Money25",
  "seconds": 120
}
```

```json
{
  "summary": "run_to Level_Write: TARGET at 08ED:000058FE, control counted 6",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08ED:58FE",
  "ref": "Level_Write",
  "pc": "08ED:000058FE",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 6,
  "controls": [
    {"ref": "Check_Money25", "at": "08ED:19DC", "hits_in_run": 6, "removed": true}
  ],
  "frame": 548,
  "regs": {
    "EAX": "0x0000a000",
    "EBX": "0x000058fe",
    "ECX": "0x005b4208",
    "EDX": "0x00000000",
    "ESI": "0x00000422",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004282",
    "EIP": "0x000058fe",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "run_to's target Level_Write at 08ED:000058FE",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 18,
  "instruction": {
    "address": "08ED:000058FE",
    "bytes": "BB8834",
    "text": "mov bx, 0x3488",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Level_Write",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `run_for`**: OK level shown: LEVEL 1 written

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 200,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08ED:000004AF",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 15,
  "pc": "08ED:000004AF",
  "cpu_mode": "real",
  "frame": 563,
  "regs": {
    "EAX": "0x00000191",
    "EBX": "0x000058fe",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004af",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:000004AF",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 19,
  "instruction": {
    "address": "08ED:000004AF",
    "bytes": "2B066C12",
    "text": "sub ax, word ptr [0x126c]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 91
  },
  "emulated_before_s": 7.82040952,
  "emulated_after_s": 8.02460012,
  "frame_before": 548,
  "frame_after": 563,
  "cycles": 10101742,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `screen_map_find`**: OK is level: the level screen, its controls p1_well, p2_well, credits

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: level (file), 3 controls",
  "status": "ok",
  "matched": true,
  "screen": "level",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "p1_well", "rect": [15, 0, 98, 194], "centre": [64, 97]},
    {"name": "p2_well", "rect": [207, 0, 98, 194], "centre": [256, 97]},
    {"name": "credits", "rect": [152, 190, 16, 10], "centre": [160, 195]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `read_memory`**: OK one spent: Credits holds 2

<details><summary>call and reply</summary>

```json
{
  "ref": "Credits",
  "length": 2
}
```

```json
{
  "summary": "read_memory Credits: 2 bytes at 08ED:0000BC04: 0200",
  "status": "ok",
  "ref": "Credits",
  "seg_off": "08ED:0000BC04",
  "length": 2,
  "hex": "0200",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `read_memory`**: OK first stage: Stage_Act holds 0

<details><summary>call and reply</summary>

```json
{
  "ref": "Stage_Act",
  "length": 2
}
```

```json
{
  "summary": "read_memory Stage_Act: 2 bytes at 08ED:0000B0D8: 0000",
  "status": "ok",
  "ref": "Stage_Act",
  "seg_off": "08ED:0000B0D8",
  "length": 2,
  "hex": "0000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `run_for`**: OK play: the board filled

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 3000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 3000 ms: ELAPSED, 211 polls, at 08ED:00009390",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 211,
  "pc": "08ED:00009390",
  "cpu_mode": "real",
  "frame": 774,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x005b420d",
    "EDX": "0x00000000",
    "ESI": "0x00004ec8",
    "EDI": "0x00004ec6",
    "EBP": "0x0000425e",
    "ESP": "0x0000424a",
    "EIP": "0x00009390",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:00009390",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 20,
  "instruction": {
    "address": "08ED:00009390",
    "bytes": "D3E3",
    "text": "shl bx, cl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "F_LXRSH@",
    "delta": 16
  },
  "emulated_before_s": 8.02460012,
  "emulated_after_s": 11.03516166,
  "frame_before": 563,
  "frame_after": 774,
  "cycles": 148855844,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `screen_map_find`**: OK is play: the play screen, its controls p1_well, p2_well, credits

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: play (file), 3 controls",
  "status": "ok",
  "matched": true,
  "screen": "play",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "p1_well", "rect": [15, 0, 98, 194], "centre": [64, 97]},
    {"name": "p2_well", "rect": [207, 0, 98, 194], "centre": [256, 97]},
    {"name": "credits", "rect": [152, 190, 16, 10], "centre": [160, 195]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `read_memory`**: OK player in play: in play

<details><summary>call and reply</summary>

```json
{
  "ref": "Player1",
  "length": 12
}
```

```json
{
  "summary": "read_memory Player1: 12 bytes at 08ED:0000AE32: 010003000100000003000000",
  "status": "ok",
  "ref": "Player1",
  "seg_off": "08ED:0000AE32",
  "length": 12,
  "hex": "010003000100000003000000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `send_keys`**: OK press right: RIGHT pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["right"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified, 16 retraces to frame 790",
  "status": "ok",
  "keys": ["right"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 16,
  "pc": "08ED:000004AF",
  "cpu_mode": "real",
  "stop_seq": 36,
  "frame": 790,
  "instruction": {
    "address": "08ED:000004AF",
    "bytes": "2B066C12",
    "text": "sub ax, word ptr [0x126c]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 91
  },
  "regs": {
    "EAX": "0x00000233",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004af",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 08ED:000004AF",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `run_for`**: OK moved: the move taken

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 200,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08ED:00006106",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 15,
  "pc": "08ED:00006106",
  "cpu_mode": "real",
  "frame": 805,
  "regs": {
    "EAX": "0x00004b83",
    "EBX": "0x00001680",
    "ECX": "0x005b003e",
    "EDX": "0x0000000e",
    "ESI": "0x00001684",
    "EDI": "0x00008573",
    "EBP": "0x00004288",
    "ESP": "0x0000427a",
    "EIP": "0x00006106",
    "CS": "0x08ed",
    "DS": "0x4bef",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:00006106",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 37,
  "instruction": {
    "address": "08ED:00006106",
    "bytes": "E2FB",
    "text": "loop 0x6103",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Del_Brush_Game",
    "delta": 23
  },
  "emulated_before_s": 11.26345068,
  "emulated_after_s": 11.477471659999999,
  "frame_before": 790,
  "frame_after": 805,
  "cycles": 10580974,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `read_memory`**: OK player one column right: one column right

<details><summary>call and reply</summary>

```json
{
  "ref": "Player1",
  "length": 12
}
```

```json
{
  "summary": "read_memory Player1: 12 bytes at 08ED:0000AE32: 010004000100000003000000",
  "status": "ok",
  "ref": "Player1",
  "seg_off": "08ED:0000AE32",
  "length": 12,
  "hex": "010004000100000003000000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**24. `send_keys`**: OK press fire1: FIRE1 pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 811",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "08ED:000004B3",
  "cpu_mode": "real",
  "stop_seq": 43,
  "frame": 811,
  "instruction": {
    "address": "08ED:000004B3",
    "bytes": "78F7",
    "text": "js 0x4ac",
    "flow": "branch",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 95
  },
  "regs": {
    "EAX": "0x0000ffff",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004b3",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 08ED:000004B3",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**25. `run_for`**: OK raised: the colour taken

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 200,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08ED:0000871A",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 15,
  "pc": "08ED:0000871A",
  "cpu_mode": "real",
  "frame": 826,
  "regs": {
    "EAX": "0x0000fef0",
    "EBX": "0x00000000",
    "ECX": "0x005b420d",
    "EDX": "0x0000ffff",
    "ESI": "0x00000151",
    "EDI": "0x0000faa0",
    "EBP": "0x0000425e",
    "ESP": "0x0000425e",
    "EIP": "0x0000871a",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0x88ee",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:0000871A",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 44,
  "instruction": {
    "address": "08ED:0000871A",
    "bytes": "5D",
    "text": "pop bp",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_MENU_TEST",
    "delta": 1742
  },
  "emulated_before_s": 11.563080040000001,
  "emulated_after_s": 11.777101,
  "frame_before": 811,
  "frame_after": 826,
  "cycles": 10592464,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**26. `read_memory`**: OK player the next colour: the next colour

<details><summary>call and reply</summary>

```json
{
  "ref": "Player1",
  "length": 12
}
```

```json
{
  "summary": "read_memory Player1: 12 bytes at 08ED:0000AE32: 010004000200000003000000",
  "status": "ok",
  "ref": "Player1",
  "seg_off": "08ED:0000AE32",
  "length": 12,
  "hex": "010004000200000003000000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**27. `send_keys`**: OK press up: UP pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified, 16 retraces to frame 842",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 16,
  "pc": "08ED:000004AC",
  "cpu_mode": "real",
  "stop_seq": 60,
  "frame": 842,
  "instruction": {
    "address": "08ED:000004AC",
    "bytes": "A16A12",
    "text": "mov ax, word ptr [0x126a]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 88
  },
  "regs": {
    "EAX": "0x0000ffff",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004ac",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 08ED:000004AC",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**28. `run_for`**: OK shot: the shot launched

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 100,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 100 ms: ELAPSED, 8 polls, at 08ED:000004AC",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 8,
  "pc": "08ED:000004AC",
  "cpu_mode": "real",
  "frame": 850,
  "regs": {
    "EAX": "0x0000ffff",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004ac",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:000004AC",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 61,
  "instruction": {
    "address": "08ED:000004AC",
    "bytes": "A16A12",
    "text": "mov ax, word ptr [0x126a]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 88
  },
  "emulated_before_s": 12.00539002,
  "emulated_after_s": 12.11953454,
  "frame_before": 842,
  "frame_after": 850,
  "cycles": 5629904,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**29. `read_memory`**: OK player a shot of it: a shot of it

<details><summary>call and reply</summary>

```json
{
  "ref": "Player1",
  "length": 12
}
```

```json
{
  "summary": "read_memory Player1: 12 bytes at 08ED:0000AE32: 010004000200040003000200",
  "status": "ok",
  "ref": "Player1",
  "seg_off": "08ED:0000AE32",
  "length": 12,
  "hex": "010004000200040003000200",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**30. `audio_record`**: OK record: 141 frames recorded, the first whole frames past 2000 ms

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/music.wav"
}
```

```json
{
  "summary": "audio_record wav 141 frames: ELAPSED, 96576 samples at 48000 Hz at ./tmp/demos/lineup/music.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 141,
  "pc": "08ED:000004AF",
  "cpu_mode": "real",
  "frame": 991,
  "regs": {
    "EAX": "0x000002c2",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004af",
    "CS": "0x08ed",
    "DS": "0x138e",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138e"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08ED:000004AF",
  "e9": {
    "available": false,
    "why": "this session was started without a logfile, so there is no instrumentation channel to summarise"
  },
  "stop_seq": 62,
  "instruction": {
    "address": "08ED:000004AF",
    "bytes": "2B066C12",
    "text": "sub ax, word ptr [0x126c]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 91
  },
  "emulated_before_s": 12.11953454,
  "emulated_after_s": 14.13133158,
  "frame_before": 850,
  "frame_after": 991,
  "cycles": 99381475,
  "kind": "wav",
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 386348,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 96576,
  "emulated_s": 2.011797,
  "sample_min": -8560,
  "sample_max": 3019,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**31. `audio_compare`**: OK heard: a sound, peaking at -11.66 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "./tmp/demos/lineup/music.wav"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -11.66 dBFS, onset 0.0 s, ch1 peak -11.66 dBFS, onset 0.0 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": [0.0, 2.012],
  "measures": [
    {
      "channel": 0,
      "peak_dbfs": -11.66,
      "rms_dbfs": -28.32,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 0,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -11.66,
      "rms_dbfs": -28.32,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 0,
      "clipped": false
    }
  ],
  "pcm_sha256": "6a99b5e74159926a562c68887cddceabda7a79bfdcb28a3d66d632ed63c5fd81",
  "path": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**32. `audio_compare`**: OK exact: the recording is music.wav, sample for sample

<details><summary>call and reply</summary>

```json
{
  "method": "diff",
  "a": "./tmp/demos/lineup/music.wav",
  "b": "./demos/lineup/music.wav",
  "align": false
}
```

```json
{
  "summary": "audio_compare diff: exact, equal, envelope 1.0",
  "status": "ok",
  "exact": true,
  "snr_db": {
    "available": false,
    "why": "the two are equal after alignment: there is no error to measure the signal against"
  },
  "class": "exact",
  "envelope_correlation": 1.0,
  "onset_delta_ms": 0.0,
  "length_delta_samples": 0,
  "aligned_by_samples": 0,
  "a": "./tmp/demos/lineup/music.wav",
  "b": "./demos/lineup/music.wav",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**33. `screen_view`**: OK screen: the board, 320x200

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/lineup/screen.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 1280x800 PNG x4, not inlined",
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
    "path": "./tmp/demos/lineup/screen.png",
    "bytes": 16447,
    "sha256": "d8086f4e5c34cdbda5c8d049be105859abd90036ed2508834e05d9318e18b3af",
    "width": 1280,
    "height": 800,
    "scale": 4,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**34. `close`**: OK close: closed: quit

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
  "conf": "./tmp/demos/lineup/lineup.conf",
  "conf_digest": "ce1af912359f3aef",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/lineup/lineup-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->
