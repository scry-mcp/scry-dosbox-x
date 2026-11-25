Every call of the run with its reply, in order: 27 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "conf": "<host>",
  "cwd": "<host>",
  "program": "XCOMAPOC.EXE",
  "dos_calls": true,
  "session_seconds": 900,
  "logfile": "<host>",
  "captures_dir": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./tmp/demos/xcom/xcom.conf",
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
  "overlay": {"layers": ["edge", "pointer", "record"]},
  "window": "<volatile>",
  "logfile": "<volatile>",
  "dos_calls": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "note": "this session runs the dynamic core, which checks breakpoints only between compiled blocks, so a code breakpoint inside one can be passed over and a run that never reaches it proves nothing. Start on the normal core: `start(flags=[\"-set\", \"cpu core=normal\"])`",
  "kept": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `resume`**: OK run: the game runs

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "resume: running",
  "status": "ok",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**3. `log_wait`**: OK intro: the intro film plays from the CD: smk/intro1.smk

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "smk/intro1\\.smk",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "smk/intro1\\.smk",
  "channel": "dos",
  "call": "<volatile>",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "lines_before": "<volatile>",
  "lines_total": "<volatile>",
  "arrived_during": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**4. `send_keys`**: OK skip: the input went in

<details><summary>call and reply</summary>

```json
{
  "keys": ["esc"]
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked",
  "status": "ok",
  "keys": ["esc"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "frame_before": 11,
  "frame_after": 17,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**5. `log_wait`**: OK titles: the intro is skipped: ufodata/titles.pcx

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "ufodata/titles\\.pcx",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "ufodata/titles\\.pcx",
  "channel": "dos",
  "call": "<volatile>",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "lines_before": "<volatile>",
  "lines_total": "<volatile>",
  "arrived_during": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**6. `send_keys`**: OK skip again: the input went in

<details><summary>call and reply</summary>

```json
{
  "keys": ["esc"]
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked",
  "status": "ok",
  "keys": ["esc"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "frame_before": 178,
  "frame_after": 184,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**7. `log_wait`**: OK main menu: the main menu is on its way: ufodata/b-setup.pcx

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "ufodata/b-setup\\.pcx",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "ufodata/b-setup\\.pcx",
  "channel": "dos",
  "call": "<volatile>",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "lines_before": "<volatile>",
  "lines_total": "<volatile>",
  "arrived_during": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**8. `log_wait`**: OK menu ready: the main menu has looked at its save slots: savegame/tactgame.09

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "savegame/tactgame\\.09",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "savegame/tactgame\\.09",
  "channel": "dos",
  "call": "<volatile>",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "lines_before": "<volatile>",
  "lines_total": "<volatile>",
  "arrived_during": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**9. `stop`**: OK held: stopped on the way to the main menu

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "interrupted": true,
  "via": "break",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `screen_map_write`**: OK map: 2 screens, 8 controls

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/xcom/xcom-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 2 screens, 8 controls of xcom",
  "status": "ok",
  "path": "./demos/xcom/xcom-screen-map.json",
  "application": "xcom",
  "mode": "verified",
  "screens": 2,
  "controls": 8,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `screen_wait`**: OK main menu drawn: main_menu on screen

<details><summary>call and reply</summary>

```json
{
  "screen": "main_menu",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "polls": "<volatile>",
  "sampled_every": "<volatile>",
  "screen": {"name": "main_menu", "layer": "file"},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `screen_map_find`**: OK found menu: main_menu, 3 controls

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: main_menu (file), 3 controls",
  "status": "ok",
  "matched": true,
  "screen": "main_menu",
  "layer": "file",
  "kind": "pixel",
  "size": [640, 480],
  "controls": [
    {"name": "start_campaign", "rect": [190, 175, 256, 22], "centre": [318, 186]},
    {"name": "load_saved_game", "rect": [190, 213, 256, 22], "centre": [318, 224]},
    {"name": "quit", "rect": [190, 251, 256, 22], "centre": [318, 262]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `send_mouse`**: OK campaign: pressed at 318,186

<details><summary>call and reply</summary>

```json
{
  "target": "start_campaign",
  "action": "down"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "x": 318,
  "y": 186,
  "units": "screen",
  "button": "left",
  "action": "down",
  "route": "guest",
  "pointer": {
    "screen": {"x": 318, "y": 186, "width": 640, "height": 480},
    "mouse": {"x": 2548, "y": 1492, "max_x": 5120, "max_y": 3840},
    "buttons": ["left"],
    "bios_mode": "0x69",
    "vbe_mode": "0x101"
  },
  "driver_arrived": true,
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "stop_seq": 19,
  "frame": "<volatile>",
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "target": "start_campaign",
  "screen": "main_menu",
  "identified_at_stop": 2,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `run_for`**: OK campaign held: held for 35 frames

<details><summary>call and reply</summary>

```json
{
  "frames": 35,
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
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 20,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": "<volatile>",
  "frame_after": "<volatile>",
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `send_mouse`**: OK campaign up: released

<details><summary>call and reply</summary>

```json
{
  "action": "up"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "units": "screen",
  "button": "left",
  "action": "up",
  "route": "guest",
  "pointer": {
    "screen": {"x": 318, "y": 186, "width": 640, "height": 480},
    "mouse": {"x": 2548, "y": 1492, "max_x": 5120, "max_y": 3840},
    "buttons": [],
    "bios_mode": "0x69",
    "vbe_mode": "0x101"
  },
  "arrived": true,
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "stop_seq": 31,
  "frame": "<volatile>",
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `screen_wait`**: OK difficulty drawn: difficulty on screen

<details><summary>call and reply</summary>

```json
{
  "screen": "difficulty",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "polls": "<volatile>",
  "sampled_every": "<volatile>",
  "screen": {"name": "difficulty", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 32,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `screen_map_find`**: OK found difficulty: difficulty, 5 controls

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: difficulty (file), 5 controls",
  "status": "ok",
  "matched": true,
  "screen": "difficulty",
  "layer": "file",
  "kind": "pixel",
  "size": [640, 480],
  "controls": [
    {"name": "novice", "rect": [190, 175, 256, 22], "centre": [318, 186]},
    {"name": "easy", "rect": [190, 213, 256, 22], "centre": [318, 224]},
    {"name": "medium", "rect": [190, 251, 256, 22], "centre": [318, 262]},
    {"name": "hard", "rect": [190, 289, 256, 22], "centre": [318, 300]},
    {"name": "superhuman", "rect": [190, 327, 256, 22], "centre": [318, 338]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `send_mouse`**: OK novice: pressed at 318,186

<details><summary>call and reply</summary>

```json
{
  "target": "novice",
  "action": "down"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "x": 318,
  "y": 186,
  "units": "screen",
  "button": "left",
  "action": "down",
  "route": "guest",
  "pointer": {
    "screen": {"x": 318, "y": 186, "width": 640, "height": 480},
    "mouse": {"x": 2548, "y": 1492, "max_x": 5120, "max_y": 3840},
    "buttons": ["left"],
    "bios_mode": "0x69",
    "vbe_mode": "0x101"
  },
  "driver_arrived": true,
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "stop_seq": 48,
  "frame": "<volatile>",
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "target": "novice",
  "screen": "difficulty",
  "identified_at_stop": 32,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `run_for`**: OK novice held: held for 35 frames

<details><summary>call and reply</summary>

```json
{
  "frames": 35,
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
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 49,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": "<volatile>",
  "frame_after": "<volatile>",
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `send_mouse`**: OK novice up: released

<details><summary>call and reply</summary>

```json
{
  "action": "up"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "units": "screen",
  "button": "left",
  "action": "up",
  "route": "guest",
  "pointer": {
    "screen": {"x": 318, "y": 186, "width": 640, "height": 480},
    "mouse": {"x": 2548, "y": 1492, "max_x": 5120, "max_y": 3840},
    "buttons": [],
    "bios_mode": "0x69",
    "vbe_mode": "0x101"
  },
  "arrived": true,
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "stop_seq": 60,
  "frame": "<volatile>",
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `resume`**: OK on: the game runs

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "resume: running",
  "status": "ok",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**22. `log_wait`**: OK city: the campaign is loading its city: UFODATA/CITYMAP1.BLD

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "UFODATA/CITYMAP1\\.BLD",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "UFODATA/CITYMAP1\\.BLD",
  "channel": "dos",
  "call": "<volatile>",
  "already": "<volatile>",
  "waited_s": "<volatile>",
  "lines_before": "<volatile>",
  "lines_total": "<volatile>",
  "arrived_during": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**23. `stop`**: OK stopped: stopped with the city on its way

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "interrupted": true,
  "via": "break",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 61,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**24. `record`**: OK drawn: recorded 900 frames in ./tmp/demos/xcom/drawn.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 900,
  "dest": "./tmp/demos/xcom/drawn.avi",
  "seconds": 300
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": "<volatile>",
  "frame_after": "<volatile>",
  "cycles": "<volatile>",
  "kind": "avi",
  "frames": 900,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/xcom/drawn.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**25. `log`**: OK files: 100 FindFirst calls, one per file the game opened, UFODATA/CITYMAP1 among them

<details><summary>call and reply</summary>

```json
{
  "channel": "dos",
  "pattern": "find first",
  "limit": 400
}
```

```json
{
  "summary": "log dos /find first/: 100 of 100 calls",
  "status": "ok",
  "pattern": "find first",
  "channel": "dos",
  "lines_total": "<volatile>",
  "truncated": false,
  "calls": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**26. `screen_view`**: OK screen: mode M_LIN8, 640x480 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/xcom/screen.png"
}
```

```json
{
  "summary": "screen_view M_LIN8: 640x480 at [0, 0] pixels; 640x480 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_LIN8",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 0, 640, 480],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/xcom/screen.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
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

**27. `close`**: OK close: closed: quit

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
  "conf": "./tmp/demos/xcom/xcom.conf",
  "conf_digest": "<volatile>",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "<volatile>",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
