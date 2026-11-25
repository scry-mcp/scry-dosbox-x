Every call of the run with its reply, in order: 43 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": false,
  "display": "<host>",
  "conf": "./demos/mines/mines.conf",
  "cwd": "./demos/mines",
  "session_seconds": 900,
  "program": "MINES.COM",
  "break_on_int3": true,
  "logfile": "./tmp/demos/mines/mines-e9.log",
  "state_dir": "./tmp/demos/mines/mines-states",
  "binary": "~/.local/state/scry/apps/Scry DOSBox-X.app"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/mines/mines.conf",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "d7ad5cdd0a4642de",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/mines/mines-states",
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
  "overlay": {"layers": ["edge", "pointer", "record"]},
  "window": "<volatile>",
  "logfile": "./tmp/demos/mines/mines-e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "1 saved for `promote`",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `resume`**: OK ready: the program's own int 3, in VBE mode 103h, loaded at 08DF

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:00000129",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:00000129",
  "cpu_mode": "real",
  "frame": 0,
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00020003",
    "ECX": "0x00000190",
    "EDX": "0x0000012c",
    "ESI": "0x00000e83",
    "EDI": "0x00001835",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000129",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 03`: the guest is at `int 03`, at 08DF:00000129",
  "e9": {
    "lines_total": 2,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1", "Bochs port E9h: MINES ready"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08DF:00000129",
    "bytes": "CD03",
    "text": "int 3",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `symbols_load`**: OK symbols: 141 symbols placed at base 0x00008df0

<details><summary>call and reply</summary>

```json
{
  "path": "./demos/mines/mines.sym",
  "base": "0x8df0"
}
```

```json
{
  "summary": "symbols_load: 141 loaded of 141 parsed, base 0x00008df0, not checked against a build: no executable named mines.exe beside the table, so it could not be checked against its build",
  "status": "ok",
  "base": "0x00008df0",
  "limit": {
    "available": false,
    "why": "no descriptor was read: the base was given, or each section has its own"
  },
  "descriptor": {
    "available": false,
    "why": "no descriptor was read: the base was given, or each section has its own"
  },
  "declarations": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []},
  "pending": false,
  "checked": {
    "available": false,
    "why": "no executable named mines.exe beside the table, so it could not be checked against its build"
  },
  "base_from": "caller",
  "parsed": 141,
  "kept": 141,
  "excluded_sections": 0,
  "excluded_pattern": 0,
  "excluded_unplaceable": 0,
  "unencodable": [],
  "unencodable_total": 0,
  "truncated_names": 3,
  "disambiguated": 0,
  "renamed": 3,
  "unreadable": 0,
  "overlay_idle": 0,
  "table_mode": "replaced",
  "table_total": 141,
  "loaded": 141,
  "bytes": 2822,
  "symbols_typed": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `screen_map_write`**: OK map: 5 screens and 8 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/mines/mines-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 5 screens, 8 controls of mines",
  "status": "ok",
  "path": "./demos/mines/mines-screen-map.json",
  "application": "mines",
  "mode": "verified",
  "screens": 5,
  "controls": 8,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `run_to`**: OK title: the game's loop reached: the title drawn and the pointer up

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 2,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x0002010f",
    "ECX": "0x00000148",
    "EDX": "0x00000180",
    "ESI": "0x000017d5",
    "EDI": "0x00001835",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: TITLE"], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `screen_map_find`**: OK is title: the title screen, its controls start

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: title (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "title",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "start", "rect": [216, 300, 368, 32], "centre": [400, 316]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `record`**: OK title seen: recorded 130 frames in ./tmp/demos/mines/title-seen.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 130,
  "dest": "./tmp/demos/mines/title-seen.avi",
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
  "frames": 130,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/mines/title-seen.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `send_mouse`**: OK play: a click on the title started a beginner's game

<details><summary>call and reply</summary>

```json
{
  "target": "start",
  "button": "left",
  "expect": "NEW 9 9 10$"
}
```

```json
{
  "summary": "send_mouse: pointer at 400,316, program's own pointer not read; reaction seen, 21 frames to frame 153",
  "status": "ok",
  "x": 400,
  "y": 316,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 400, "y": 316, "width": 800, "height": 600},
    "mouse": {"x": 400, "y": 316, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 21,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 25,
  "frame": 153,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: NEW 9 9 10"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "NEW 9 9 10$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: NEW 9 9 10",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "target": "start",
  "screen": "title",
  "identified_at_stop": 3,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `run_to`**: OK board drawn: the board drawn

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 153,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x00000000",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 26,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `screen_map_find`**: OK is board: the board screen, its controls game

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: board (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "board",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "game", "rect": [4, 0, 48, 24], "centre": [28, 12]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `send_mouse`**: OK menu: Game opened the menu

<details><summary>call and reply</summary>

```json
{
  "target": "game",
  "button": "left",
  "expect": "MENU OPEN$"
}
```

```json
{
  "summary": "send_mouse: pointer at 28,12, program's own pointer not read; reaction seen, 25 frames to frame 178",
  "status": "ok",
  "x": 28,
  "y": 12,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 28, "y": 12, "width": 800, "height": 600},
    "mouse": {"x": 28, "y": 12, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 25,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 51,
  "frame": 178,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: MENU OPEN"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MENU OPEN$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MENU OPEN",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "target": "game",
  "screen": "board",
  "identified_at_stop": 26,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `run_to`**: OK menu drawn: the menu drawn

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 178,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x00000000",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 52,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `screen_map_find`**: OK is menu: the menu screen, its controls new game, beginner, intermediate, expert

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: menu (file), 4 controls",
  "status": "ok",
  "matched": true,
  "screen": "menu",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "new game", "rect": [2, 26, 164, 24], "centre": [84, 38]},
    {"name": "beginner", "rect": [2, 50, 164, 24], "centre": [84, 62]},
    {"name": "intermediate", "rect": [2, 74, 164, 24], "centre": [84, 86]},
    {"name": "expert", "rect": [2, 98, 164, 24], "centre": [84, 110]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `send_mouse`**: OK level: Beginner started a new beginner's game

<details><summary>call and reply</summary>

```json
{
  "target": "beginner",
  "button": "left",
  "expect": "NEW 9 9 10$"
}
```

```json
{
  "summary": "send_mouse: pointer at 84,62, program's own pointer not read; reaction seen, 25 frames to frame 203",
  "status": "ok",
  "x": 84,
  "y": 62,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 84, "y": 62, "width": 800, "height": 600},
    "mouse": {"x": 84, "y": 62, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 25,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 77,
  "frame": 203,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: MENU CLOSE", "Bochs port E9h: NEW 9 9 10"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "NEW 9 9 10$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: NEW 9 9 10",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "target": "beginner",
  "screen": "menu",
  "identified_at_stop": 52,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `run_to`**: OK board drawn again: the new board drawn

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 203,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x00000000",
    "EDX": "0x00000000",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 78,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `screen_map_find`**: OK is board again: the board screen, its controls game

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: board (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "board",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "game", "rect": [4, 0, 48, 24], "centre": [28, 12]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `read_memory`**: OK size: rows 9, cols 9

<details><summary>call and reply</summary>

```json
{
  "ref": "rows",
  "length": 2
}
```

```json
{
  "summary": "read_memory rows: 2 bytes at 08DF:00000FFF: 0909",
  "status": "ok",
  "ref": "rows",
  "seg_off": "08DF:00000FFF",
  "length": 2,
  "hex": "0909",
  "names": [
    {"field": "given.ref", "number": "0x00009def", "kind": "symbol", "name": "rows"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `read_memory`**: OK mines: mines at 0,3, 1,2, 1,4, 2,0, 5,4, 6,5, 6,8, 7,2, 8,0, 8,3

<details><summary>call and reply</summary>

```json
{
  "ref": "mines",
  "length": 81
}
```

```json
{
  "summary": "read_memory mines: 81 bytes at 08DF:00001030: 00000001000000000000000100010000000001000000000000000000000000000000000000000000000000000000000000010000000000000000000100000100... (17 more bytes in `hex`)",
  "status": "ok",
  "ref": "mines",
  "seg_off": "08DF:00001030",
  "length": 81,
  "hex": "000000010000000000000001000100000000010000000000000000000000000000000000000000000000000000000000000100000000000000000001000001000001000000000000010000010000000000",
  "names": [
    {"field": "given.ref", "number": "0x00009e20", "kind": "symbol", "name": "mines"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `record`**: OK mines read: recorded 130 frames in ./tmp/demos/mines/mines-read.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 130,
  "dest": "./tmp/demos/mines/mines-read.avi",
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
  "frames": 130,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/mines/mines-read.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `read_memory`**: OK origin: the board's top-left corner at pixel 292,192

<details><summary>call and reply</summary>

```json
{
  "ref": "board_x",
  "length": 4
}
```

```json
{
  "summary": "read_memory board_x: 4 bytes at 08DF:00001001: 2401c000",
  "status": "ok",
  "ref": "board_x",
  "seg_off": "08DF:00001001",
  "length": 4,
  "hex": "2401c000",
  "names": [
    {"field": "given.ref", "number": "0x00009df1", "kind": "symbol", "name": "board_x"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `perform`**: OK flags: 2 mines flagged with the right button

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "x": 376, "y": 204, "button": "right", "expect": "FLAG 0 3$", "seconds": 10},
    {"op": "send_mouse", "x": 352, "y": 228, "button": "right", "expect": "FLAG 1 2$", "seconds": 10}
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
      "frame_before": 333,
      "frame_after": 354,
      "reply": {
        "summary": "send_mouse: pointer at 376,204, program's own pointer not read; reaction seen, 21 frames to frame 354",
        "status": "ok",
        "stop_seq": 100,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 352,228, program's own pointer not read; reaction seen, 25 frames to frame 379",
        "status": "ok",
        "x": 352,
        "y": 228,
        "units": "screen",
        "button": "right",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {"x": 352, "y": 228, "width": 800, "height": 600},
          "mouse": {"x": 352, "y": 228, "max_x": 799, "max_y": 599},
          "buttons": [],
          "bios_mode": "0x6b",
          "vbe_mode": "0x103"
        },
        "driver_arrived": true,
        "polls": 25,
        "pc": "08DF:00000E08",
        "cpu_mode": "real",
        "stop_seq": 125,
        "frame": 379,
        "instruction": {
          "address": "08DF:00000E08",
          "bytes": "A808",
          "text": "test al, 8",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": "retrace",
          "delta": 9
        },
        "regs": {
          "EAX": "0x00000004",
          "EBX": "0x00000000",
          "ECX": "0x00000160",
          "EDX": "0x000003da",
          "ESI": "0x000017d5",
          "EDI": "0x000017d1",
          "EBP": "0x0000091c",
          "ESP": "0x0000fffc",
          "EIP": "0x00000e08",
          "CS": "0x08df",
          "DS": "0x08df",
          "ES": "0x08df",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x08df"
        },
        "watches": [],
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
        "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: FLAG 1 2"], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": true,
          "seen": true,
          "expected": "FLAG 1 2$",
          "verdict": "TARGET",
          "line": "Bochs port E9h: FLAG 1 2",
          "seen_before_waiting": true,
          "lines_before": 0,
          "waited_s": "<volatile>",
          "lines_total": 1
        },
        "session": {"alive": true, "running": false, "altered": false}
      },
      "frame_before": 354,
      "frame_after": 379
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 80,
    "stop_seq_last": 125,
    "surveyed": 2,
    "by_cause": {
      "no declared code breakpoint, and the debugger does not say which row stopped the machine, so what made this stop cannot be told": 2
    },
    "unaccounted": 44
  },
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `send_mouse`**: OK safe: a left click on the safe cell at 0,0: the game revealed it

<details><summary>call and reply</summary>

```json
{
  "x": 304,
  "y": 204,
  "button": "left",
  "expect": "REVEAL 0 0 "
}
```

```json
{
  "summary": "send_mouse: pointer at 304,204, program's own pointer not read; reaction seen, 25 frames to frame 404",
  "status": "ok",
  "x": 304,
  "y": 204,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 304, "y": 204, "width": 800, "height": 600},
    "mouse": {"x": 304, "y": 204, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 25,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 150,
  "frame": 404,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x000013f0",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: REVEAL 0 0 4"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "REVEAL 0 0 ",
    "verdict": "TARGET",
    "line": "Bochs port E9h: REVEAL 0 0 4",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `record`**: OK safe opened: recorded 130 frames in ./tmp/demos/mines/safe-opened.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 130,
  "dest": "./tmp/demos/mines/safe-opened.avi",
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
  "frames": 130,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/mines/safe-opened.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**24. `perform`**: OK clear: 18 clicks opened every safe cell, none on a mine

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "x": 352, "y": 204, "button": "left", "expect": "REVEAL 0 2 "},
    {"op": "send_mouse", "x": 400, "y": 204, "button": "left", "expect": "REVEAL 0 4 "},
    {"op": "send_mouse", "x": 424, "y": 204, "button": "left", "expect": "REVEAL 0 5 "},
    {"op": "send_mouse", "x": 448, "y": 204, "button": "left", "expect": "REVEAL 0 6 "},
    {"op": "send_mouse", "x": 376, "y": 228, "button": "left", "expect": "REVEAL 1 3 "},
    {"op": "send_mouse", "x": 400, "y": 348, "button": "left", "expect": "REVEAL 6 4 "},
    {"op": "send_mouse", "x": 448, "y": 348, "button": "left", "expect": "REVEAL 6 6 "},
    {"op": "send_mouse", "x": 472, "y": 348, "button": "left", "expect": "REVEAL 6 7 "},
    {"op": "send_mouse", "x": 376, "y": 372, "button": "left", "expect": "REVEAL 7 3 "},
    {"op": "send_mouse", "x": 400, "y": 372, "button": "left", "expect": "REVEAL 7 4 "},
    {"op": "send_mouse", "x": 424, "y": 372, "button": "left", "expect": "REVEAL 7 5 "},
    {"op": "send_mouse", "x": 448, "y": 372, "button": "left", "expect": "REVEAL 7 6 "},
    {"op": "send_mouse", "x": 472, "y": 372, "button": "left", "expect": "REVEAL 7 7 "},
    {"op": "send_mouse", "x": 496, "y": 372, "button": "left", "expect": "REVEAL 7 8 "},
    {"op": "send_mouse", "x": 328, "y": 396, "button": "left", "expect": "REVEAL 8 1 "},
    {"op": "send_mouse", "x": 352, "y": 396, "button": "left", "expect": "REVEAL 8 2 "},
    {"op": "send_mouse", "x": 400, "y": 396, "button": "left", "expect": "REVEAL 8 4 "},
    {"op": "send_mouse", "x": 424, "y": 396, "button": "left", "expect": "REVEAL 8 5 "}
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
      "frame_before": 534,
      "frame_after": 555,
      "reply": {
        "summary": "send_mouse: pointer at 352,204, program's own pointer not read; reaction seen, 21 frames to frame 555",
        "status": "ok",
        "stop_seq": 172,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "frame_before": 555,
      "frame_after": 580,
      "reply": {
        "summary": "send_mouse: pointer at 400,204, program's own pointer not read; reaction seen, 25 frames to frame 580",
        "status": "ok",
        "stop_seq": 197,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "frame_before": 580,
      "frame_after": 605,
      "reply": {
        "summary": "send_mouse: pointer at 424,204, program's own pointer not read; reaction seen, 25 frames to frame 605",
        "status": "ok",
        "stop_seq": 222,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "frame_before": 605,
      "frame_after": 630,
      "reply": {
        "summary": "send_mouse: pointer at 448,204, program's own pointer not read; reaction seen, 25 frames to frame 630",
        "status": "ok",
        "stop_seq": 247,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "frame_before": 630,
      "frame_after": 655,
      "reply": {
        "summary": "send_mouse: pointer at 376,228, program's own pointer not read; reaction seen, 25 frames to frame 655",
        "status": "ok",
        "stop_seq": 272,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "frame_before": 655,
      "frame_after": 680,
      "reply": {
        "summary": "send_mouse: pointer at 400,348, program's own pointer not read; reaction seen, 25 frames to frame 680",
        "status": "ok",
        "stop_seq": 297,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "frame_before": 680,
      "frame_after": 705,
      "reply": {
        "summary": "send_mouse: pointer at 448,348, program's own pointer not read; reaction seen, 25 frames to frame 705",
        "status": "ok",
        "stop_seq": 322,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "frame_before": 705,
      "frame_after": 730,
      "reply": {
        "summary": "send_mouse: pointer at 472,348, program's own pointer not read; reaction seen, 25 frames to frame 730",
        "status": "ok",
        "stop_seq": 347,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "frame_before": 730,
      "frame_after": 755,
      "reply": {
        "summary": "send_mouse: pointer at 376,372, program's own pointer not read; reaction seen, 25 frames to frame 755",
        "status": "ok",
        "stop_seq": 372,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "frame_before": 755,
      "frame_after": 780,
      "reply": {
        "summary": "send_mouse: pointer at 400,372, program's own pointer not read; reaction seen, 25 frames to frame 780",
        "status": "ok",
        "stop_seq": 397,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "frame_before": 780,
      "frame_after": 805,
      "reply": {
        "summary": "send_mouse: pointer at 424,372, program's own pointer not read; reaction seen, 25 frames to frame 805",
        "status": "ok",
        "stop_seq": 422,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "frame_before": 805,
      "frame_after": 830,
      "reply": {
        "summary": "send_mouse: pointer at 448,372, program's own pointer not read; reaction seen, 25 frames to frame 830",
        "status": "ok",
        "stop_seq": 447,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 12,
      "op": "send_mouse",
      "frame_before": 830,
      "frame_after": 855,
      "reply": {
        "summary": "send_mouse: pointer at 472,372, program's own pointer not read; reaction seen, 25 frames to frame 855",
        "status": "ok",
        "stop_seq": 472,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 13,
      "op": "send_mouse",
      "frame_before": 855,
      "frame_after": 880,
      "reply": {
        "summary": "send_mouse: pointer at 496,372, program's own pointer not read; reaction seen, 25 frames to frame 880",
        "status": "ok",
        "stop_seq": 497,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 14,
      "op": "send_mouse",
      "frame_before": 880,
      "frame_after": 905,
      "reply": {
        "summary": "send_mouse: pointer at 328,396, program's own pointer not read; reaction seen, 25 frames to frame 905",
        "status": "ok",
        "stop_seq": 522,
        "cause": "no declared code breakpoint at 08DF:00000E07, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "frame_before": 905,
      "frame_after": 930,
      "reply": {
        "summary": "send_mouse: pointer at 352,396, program's own pointer not read; reaction seen, 25 frames to frame 930",
        "status": "ok",
        "stop_seq": 547,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "frame_before": 930,
      "frame_after": 955,
      "reply": {
        "summary": "send_mouse: pointer at 400,396, program's own pointer not read; reaction seen, 25 frames to frame 955",
        "status": "ok",
        "stop_seq": 572,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 17,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 424,396, program's own pointer not read; reaction seen, 25 frames to frame 980",
        "status": "ok",
        "x": 424,
        "y": 396,
        "units": "screen",
        "button": "left",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {"x": 424, "y": 396, "width": 800, "height": 600},
          "mouse": {"x": 424, "y": 396, "max_x": 799, "max_y": 599},
          "buttons": [],
          "bios_mode": "0x6b",
          "vbe_mode": "0x103"
        },
        "driver_arrived": true,
        "polls": 25,
        "pc": "08DF:00000E08",
        "cpu_mode": "real",
        "stop_seq": 597,
        "frame": 980,
        "instruction": {
          "address": "08DF:00000E08",
          "bytes": "A808",
          "text": "test al, 8",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": "retrace",
          "delta": 9
        },
        "regs": {
          "EAX": "0x00000004",
          "EBX": "0x00000000",
          "ECX": "0x00000160",
          "EDX": "0x000003da",
          "ESI": "0x000017d5",
          "EDI": "0x00000fc4",
          "EBP": "0x0000091c",
          "ESP": "0x0000fffc",
          "EIP": "0x00000e08",
          "CS": "0x08df",
          "DS": "0x08df",
          "ES": "0x08df",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x08df"
        },
        "watches": [],
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
        "e9": {
          "lines_total": 2,
          "truncated": false,
          "lines": ["Bochs port E9h: REVEAL 8 5 4", "Bochs port E9h: WIN"],
          "mark": "<volatile>"
        },
        "motion": true,
        "verify": {
          "checked": true,
          "seen": true,
          "expected": "REVEAL 8 5 ",
          "verdict": "TARGET",
          "line": "Bochs port E9h: REVEAL 8 5 4",
          "seen_before_waiting": true,
          "lines_before": 0,
          "waited_s": "<volatile>",
          "lines_total": 1
        },
        "session": {"alive": true, "running": false, "altered": false}
      },
      "frame_before": 955,
      "frame_after": 980
    }
  ],
  "steps_total": 18,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 152,
    "stop_seq_last": 597,
    "surveyed": 18,
    "by_cause": {
      "no declared code breakpoint, and the debugger does not say which row stopped the machine, so what made this stop cannot be told": 18
    },
    "unaccounted": 428
  },
  "steps_completed": 18,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**25. `record`**: OK board cleared: recorded 130 frames in ./tmp/demos/mines/board-cleared.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 130,
  "dest": "./tmp/demos/mines/board-cleared.avi",
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
  "frames": 130,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/mines/board-cleared.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**26. `run_to`**: OK cleared drawn: the last reveal and the win dialog drawn

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 1110,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000000e4",
    "ESI": "0x000017d5",
    "EDI": "0x00000fc4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 599,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**27. `log`**: OK won: the game logged WIN

<details><summary>call and reply</summary>

```json
{
  "channel": "guest",
  "pattern": "WIN$"
}
```

```json
{
  "summary": "log guest /WIN$/: 1 of 1 line",
  "status": "ok",
  "pattern": "WIN$",
  "channel": "guest",
  "lines_total": 1,
  "truncated": false,
  "lines": ["Bochs port E9h: WIN"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**28. `send_mouse`**: OK park: the pointer parked at 790,590, off every region the map signs

<details><summary>call and reply</summary>

```json
{
  "x": 790,
  "y": 590
}
```

```json
{
  "summary": "send_mouse: pointer at 790,590, program's own pointer not read; no button pressed; sent, reaction not checked, 12 frames to frame 1122",
  "status": "ok",
  "x": 790,
  "y": 590,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {"x": 790, "y": 590, "width": 800, "height": 600},
    "mouse": {"x": 790, "y": 590, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 12,
  "pc": "08DF:00000E07",
  "cpu_mode": "real",
  "stop_seq": 611,
  "frame": 1122,
  "instruction": {
    "address": "08DF:00000E07",
    "bytes": "EC",
    "text": "in al, dx",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 8
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x00000fc4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e07",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E07, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**29. `screen_map_find`**: OK is win: the win screen, its controls ok

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: win (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "win",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "ok", "rect": [360, 316, 80, 28], "centre": [400, 330]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**30. `screen_view`**: OK screen: mode M_LIN8, 800x600 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/mines/screen.png"
}
```

```json
{
  "summary": "screen_view M_LIN8: 800x600 at [0, 0] pixels; 800x600 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_LIN8",
  "kind": "pixel",
  "width": 800,
  "height": 600,
  "mode": "render",
  "crop": [0, 0, 800, 600],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/mines/screen.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 800,
    "height": 600,
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

**31. `run_for`**: OK win: 240 retraces with the win dialog up

<details><summary>call and reply</summary>

```json
{
  "frames": 240,
  "seconds": 60
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 240,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 1362,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 612,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 1122,
  "frame_after": 1362,
  "cycles": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**32. `send_mouse`**: OK again: OK started the next game

<details><summary>call and reply</summary>

```json
{
  "target": "ok",
  "button": "left",
  "expect": "NEW 9 9 10$"
}
```

```json
{
  "summary": "send_mouse: pointer at 400,330, program's own pointer not read; reaction seen, 21 frames to frame 1383",
  "status": "ok",
  "x": 400,
  "y": 330,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 400, "y": 330, "width": 800, "height": 600},
    "mouse": {"x": 400, "y": 330, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 21,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 633,
  "frame": 1383,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: OK", "Bochs port E9h: NEW 9 9 10"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "NEW 9 9 10$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: NEW 9 9 10",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "target": "ok",
  "screen": "win",
  "identified_at_stop": 611,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**33. `run_to`**: OK next board drawn: the next board drawn

<details><summary>call and reply</summary>

```json
{
  "ref": "main_loop",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 1383,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000000e4",
    "ESI": "0x000017d5",
    "EDI": "0x000017d1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 634,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**34. `read_memory`**: OK next mines: mines at 0,7, 1,1, 1,7, 2,0, 4,1, 4,4, 5,0, 5,2, 7,5, 8,4

<details><summary>call and reply</summary>

```json
{
  "ref": "mines",
  "length": 81
}
```

```json
{
  "summary": "read_memory mines: 81 bytes at 08DF:00001030: 00000000000000010000010000000000010001000000000000000000000000000000000000010000010000000001000100000000000000000000000000000000... (17 more bytes in `hex`)",
  "status": "ok",
  "ref": "mines",
  "seg_off": "08DF:00001030",
  "length": 81,
  "hex": "000000000000000100000100000000000100010000000000000000000000000000000000000100000100000000010001000000000000000000000000000000000000000001000000000000000100000000",
  "names": [
    {"field": "given.ref", "number": "0x00009e20", "kind": "symbol", "name": "mines"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**35. `send_mouse`**: OK mine: a left click on the mine at 0,7, the machine left stopped a few retraces later, the explosion already sounding

<details><summary>call and reply</summary>

```json
{
  "x": 472,
  "y": 204,
  "button": "left",
  "expect": "BOOM 0 7$"
}
```

```json
{
  "summary": "send_mouse: pointer at 472,204, program's own pointer not read; reaction seen, 25 frames to frame 1408",
  "status": "ok",
  "x": 472,
  "y": 204,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 472, "y": 204, "width": 800, "height": 600},
    "mouse": {"x": 472, "y": 204, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 25,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 659,
  "frame": 1408,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x00000fe3",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: BOOM 0 7"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "BOOM 0 7$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: BOOM 0 7",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**36. `log`**: OK boom: the game logged BOOM 0 7

<details><summary>call and reply</summary>

```json
{
  "channel": "guest",
  "pattern": "BOOM"
}
```

```json
{
  "summary": "log guest /BOOM/: 1 of 1 line",
  "status": "ok",
  "pattern": "BOOM",
  "channel": "guest",
  "lines_total": 1,
  "truncated": false,
  "lines": ["Bochs port E9h: BOOM 0 7"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**37. `audio_record`**: OK record: 45 retraces recorded from where the click left the machine

<details><summary>call and reply</summary>

```json
{
  "frames": 45,
  "dest": "./tmp/demos/mines/run.wav"
}
```

```json
{
  "summary": "audio_record wav 45 frames: ELAPSED, 30816 samples at 48000 Hz at ./tmp/demos/mines/run.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 45,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "frame": 1453,
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x00000fe3",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 660,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "emulated_before_s": 20.057881225000003,
  "emulated_after_s": 20.699201425,
  "frame_before": 1408,
  "frame_after": 1453,
  "cycles": 1789637,
  "kind": "wav",
  "frames": 45,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 123308,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 30816,
  "emulated_s": 0.6413202,
  "sample_min": -18099,
  "sample_max": 18479,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**38. `audio_compare`**: OK exact: the explosion is boom.wav, sample for sample

<details><summary>call and reply</summary>

```json
{
  "method": "diff",
  "a": "./tmp/demos/mines/run.wav",
  "b": "./demos/mines/boom.wav",
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
  "a": "<volatile>",
  "b": "./demos/mines/boom.wav",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**39. `record`**: OK explosion shown: recorded 130 frames in ./tmp/demos/mines/explosion-shown.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 130,
  "dest": "./tmp/demos/mines/explosion-shown.avi",
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
  "frames": 130,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/mines/explosion-shown.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**40. `audio_compare`**: OK heard: a sound, peaking at -4.98 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "./tmp/demos/mines/run.wav"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -4.98 dBFS, onset 0.0 s, ch1 peak -4.98 dBFS, onset 0.0 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": "<volatile>",
  "measures": [
    {
      "channel": 0,
      "peak_dbfs": -4.98,
      "rms_dbfs": -18.47,
      "silent": false,
      "silence_spans": {"count": 1, "first": [0.5212, 0.642]},
      "onset_s": 0.0,
      "clipping_run": 7,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -4.98,
      "rms_dbfs": -18.47,
      "silent": false,
      "silence_spans": {"count": 1, "first": [0.5212, 0.642]},
      "onset_s": 0.0,
      "clipping_run": 7,
      "clipped": false
    }
  ],
  "pcm_sha256": "d9e7fde4e6cc592459de60472500d2ff670db86cfbc81759cfe0671319936f13",
  "path": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**41. `send_mouse`**: OK park again: the pointer parked at 790,590, off every region the map signs

<details><summary>call and reply</summary>

```json
{
  "x": 790,
  "y": 590
}
```

```json
{
  "summary": "send_mouse: pointer at 790,590, program's own pointer not read; no button pressed; sent, reaction not checked, 11 frames to frame 1594",
  "status": "ok",
  "x": 790,
  "y": 590,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {"x": 790, "y": 590, "width": 800, "height": 600},
    "mouse": {"x": 790, "y": 590, "max_x": 799, "max_y": 599},
    "buttons": [],
    "bios_mode": "0x6b",
    "vbe_mode": "0x103"
  },
  "driver_arrived": true,
  "polls": 11,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 672,
  "frame": 1594,
  "instruction": {
    "address": "08DF:00000E08",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0x00000004",
    "EBX": "0x00000000",
    "ECX": "0x00000160",
    "EDX": "0x000003da",
    "ESI": "0x000017d5",
    "EDI": "0x00000fe3",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000e08",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**42. `screen_map_find`**: OK is lose: the lose screen, its controls ok

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: lose (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "lose",
  "layer": "file",
  "kind": "pixel",
  "size": [800, 600],
  "controls": [
    {"name": "ok", "rect": [360, 316, 80, 28], "centre": [400, 330]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**43. `close`**: OK close: closed: quit

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "close: quit, no exit code: the emulator's exit code could not be read",
  "status": "ok",
  "closed": true,
  "pid": "<volatile>",
  "conf": "./demos/mines/mines.conf",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "d7ad5cdd0a4642de",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/mines/mines-states",
  "ended_by": "quit",
  "exit_code": {"available": false, "why": "the emulator's exit code could not be read"},
  "stdout_tail": {
    "available": false,
    "why": "the emulator wrote to a console of its own, which this server does not read (Windows, a build whose debugger draws a screen)"
  },
  "errorlog_tail": "1f 3f371f-3f3f1f 373f1f 2f3f1f 273f1f \n48: 1f3f1f 1f3f27 1f3f2f 1f3f37-1f3f3f 1f373f 1f2f3f 1f273f \n50: 2d2d3f 312d3f 362d3f 3a2d3f-3f2d3f 3f2d3a 3f2d36 3f2d31 \n58: 3f2d2d 3f312d 3f362d 3f3a2d-3f3f2d 3a3f2d 363f2d 313f2d \n60: 2d3f2d 2d3f31 2d3f36 2d3f3a-2d3f3f 2d3a3f 2d363f 2d313f \n68: 00001c 07001c 0e001c 15001c-1c001c 1c0015 1c000e 1c0007 \n70: 1c0000 1c0700 1c0e00 1c1500-1c1c00 151c00 0e1c00 071c00 \n78: 001c00 001c07 001c0e 001c15-001c1c 00151c 000e1c 00071c \n80: 0e0e1c 110e1c 150e1c 180e1c-1c0e1c 1c0e18 1c0e15 1c0e11 \n88: 1c0e0e 1c110e 1c150e 1c180e-1c1c0e 181c0e 151c0e 111c0e \n90: 0e1c0e 0e1c11 0e1c15 0e1c18-0e1c1c 0e181c 0e151c 0e111c \n98: 14141c 16141c 18141c 1a141c-1c141c 1c141a 1c1418 1c1416 \na0: 1c1414 1c1614 1c1814 1c1a14-1c1c14 1a1c14 181c14 161c14 \na8: 141c14 141c16 141c18 141c1a-141c1c 141a1c 14181c 14161c \nb0: 000010 040010 080010 0c0010-100010 10000c 100008 100004 \nb8: 100000 100400 100800 100c00-101000 0c1000 081000 041000 \nc0: 001000 001004 001008 00100c-001010 000c10 000810 000410 \nc8: 080810 0a0810 0c0810 0e0810-100810 10080e 10080c 10080a \nd0: 100808 100a08 100c08 100e08-101008 0e1008 0c1008 0a1008 \nd8: 081008 08100a 08100c 08100e-081010 080e10 080c10 080a10 \ne0: 0b0b10 0c0b10 0d0b10 0f0b10-100b10 100b0f 100b0d 100b0c \ne8: 100b0b 100c0b 100d0b 100f0b-10100b 0f100b 0d100b 0c100b \nf0: 0b100b 0b100c 0b100d 0b100f-0b1010 0b0f10 0b0d10 0b0c10 \nf8: 000000 000000 000000 000000-000000 000000 000000 000000 \nSDLNET: Closed client TCP listening socket\n--END OF LOG--\n",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
