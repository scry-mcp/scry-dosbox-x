Every call of the run with its reply, in order: 37 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "conf": "./demos/mines/mines.conf",
  "cwd": "./demos/mines",
  "session_seconds": 900,
  "program": "MINES.COM",
  "break_on_int3": true,
  "logfile": "./tmp/demos/mines/mines-e9.log",
  "state_dir": "./tmp/demos/mines/mines-states",
  "capture_video": true,
  "captures_dir": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/mines/mines.conf",
  "conf_digest": "d7ad5cdd0a4642de",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "./tmp/demos/mines/video",
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
  "background": true,
  "presence": true,
  "window": "<volatile>",
  "logfile": "./tmp/demos/mines/mines-e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "kept 1 (promote to review)",
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

**7. `send_mouse`**: OK play: a click on the title started a beginner's game

<details><summary>call and reply</summary>

```json
{
  "target": "start",
  "button": "left",
  "expect": "NEW 9 9 10$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 400,316, program's own pointer not read; effect seen, 22 retraces to frame 24",
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
  "polls": 22,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 25,
  "frame": 24,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**8. `run_to`**: OK board drawn: the board drawn

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
  "frame": 24,
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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `screen_map_find`**: OK is board: the board screen, its controls game

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

**10. `send_mouse`**: OK menu: Game opened the menu

<details><summary>call and reply</summary>

```json
{
  "target": "game",
  "button": "left",
  "expect": "MENU OPEN$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 28,12, program's own pointer not read; effect seen, 25 retraces to frame 49",
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
  "frame": 49,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**11. `run_to`**: OK menu drawn: the menu drawn

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
  "frame": 49,
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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `screen_map_find`**: OK is menu: the menu screen, its controls new game, beginner, intermediate, expert

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

**13. `send_mouse`**: OK level: Beginner started a new beginner's game

<details><summary>call and reply</summary>

```json
{
  "target": "beginner",
  "button": "left",
  "expect": "NEW 9 9 10$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 84,62, program's own pointer not read; effect seen, 25 retraces to frame 74",
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
  "frame": 74,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**14. `run_to`**: OK board drawn again: the new board drawn

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
  "frame": 74,
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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `screen_map_find`**: OK is board again: the board screen, its controls game

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

**16. `read_memory`**: OK size: rows 9, cols 9

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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `read_memory`**: OK mines: mines at 0,3, 1,2, 1,4, 2,0, 5,4, 6,5, 6,8, 7,2, 8,0, 8,3

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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `read_memory`**: OK origin: the board's top-left corner at pixel 292,192

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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `perform`**: OK flags: 2 mines flagged with the right button

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
      "reply": {
        "summary": "send_mouse: pointer at 376,204, program's own pointer not read; effect seen, 25 retraces to frame 99",
        "status": "ok",
        "stop_seq": 103,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 352,228, program's own pointer not read; effect seen, 25 retraces to frame 124",
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
        "stop_seq": 128,
        "frame": 124,
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
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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
      }
    }
  ],
  "steps_total": 2,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 79,
    "stop_seq_last": 128,
    "surveyed": 2,
    "by_cause": {
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 2
    },
    "unaccounted": 48
  },
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `perform`**: OK clear: 19 clicks opened every safe cell, none on a mine

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "x": 304, "y": 204, "button": "left", "expect": "REVEAL 0 0 ", "seconds": 10},
    {"op": "send_mouse", "x": 352, "y": 204, "button": "left", "expect": "REVEAL 0 2 ", "seconds": 10},
    {"op": "send_mouse", "x": 400, "y": 204, "button": "left", "expect": "REVEAL 0 4 ", "seconds": 10},
    {"op": "send_mouse", "x": 424, "y": 204, "button": "left", "expect": "REVEAL 0 5 ", "seconds": 10},
    {"op": "send_mouse", "x": 448, "y": 204, "button": "left", "expect": "REVEAL 0 6 ", "seconds": 10},
    {"op": "send_mouse", "x": 376, "y": 228, "button": "left", "expect": "REVEAL 1 3 ", "seconds": 10},
    {"op": "send_mouse", "x": 400, "y": 348, "button": "left", "expect": "REVEAL 6 4 ", "seconds": 10},
    {"op": "send_mouse", "x": 448, "y": 348, "button": "left", "expect": "REVEAL 6 6 ", "seconds": 10},
    {"op": "send_mouse", "x": 472, "y": 348, "button": "left", "expect": "REVEAL 6 7 ", "seconds": 10},
    {"op": "send_mouse", "x": 376, "y": 372, "button": "left", "expect": "REVEAL 7 3 ", "seconds": 10},
    {"op": "send_mouse", "x": 400, "y": 372, "button": "left", "expect": "REVEAL 7 4 ", "seconds": 10},
    {"op": "send_mouse", "x": 424, "y": 372, "button": "left", "expect": "REVEAL 7 5 ", "seconds": 10},
    {"op": "send_mouse", "x": 448, "y": 372, "button": "left", "expect": "REVEAL 7 6 ", "seconds": 10},
    {"op": "send_mouse", "x": 472, "y": 372, "button": "left", "expect": "REVEAL 7 7 ", "seconds": 10},
    {"op": "send_mouse", "x": 496, "y": 372, "button": "left", "expect": "REVEAL 7 8 ", "seconds": 10},
    {"op": "send_mouse", "x": 328, "y": 396, "button": "left", "expect": "REVEAL 8 1 ", "seconds": 10},
    {"op": "send_mouse", "x": 352, "y": 396, "button": "left", "expect": "REVEAL 8 2 ", "seconds": 10},
    {"op": "send_mouse", "x": 400, "y": 396, "button": "left", "expect": "REVEAL 8 4 ", "seconds": 10},
    {"op": "send_mouse", "x": 424, "y": 396, "button": "left", "expect": "REVEAL 8 5 ", "seconds": 10}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 19 of 19 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 304,204, program's own pointer not read; effect seen, 25 retraces to frame 149",
        "status": "ok",
        "stop_seq": 153,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 352,204, program's own pointer not read; effect seen, 25 retraces to frame 174",
        "status": "ok",
        "stop_seq": 178,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 400,204, program's own pointer not read; effect seen, 25 retraces to frame 199",
        "status": "ok",
        "stop_seq": 203,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 424,204, program's own pointer not read; effect seen, 25 retraces to frame 224",
        "status": "ok",
        "stop_seq": 228,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 448,204, program's own pointer not read; effect seen, 25 retraces to frame 249",
        "status": "ok",
        "stop_seq": 253,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 376,228, program's own pointer not read; effect seen, 25 retraces to frame 274",
        "status": "ok",
        "stop_seq": 278,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 400,348, program's own pointer not read; effect seen, 25 retraces to frame 299",
        "status": "ok",
        "stop_seq": 303,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 448,348, program's own pointer not read; effect seen, 25 retraces to frame 324",
        "status": "ok",
        "stop_seq": 328,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 472,348, program's own pointer not read; effect seen, 25 retraces to frame 349",
        "status": "ok",
        "stop_seq": 353,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 376,372, program's own pointer not read; effect seen, 25 retraces to frame 374",
        "status": "ok",
        "stop_seq": 378,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 400,372, program's own pointer not read; effect seen, 25 retraces to frame 399",
        "status": "ok",
        "stop_seq": 403,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 424,372, program's own pointer not read; effect seen, 25 retraces to frame 424",
        "status": "ok",
        "stop_seq": 428,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 12,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 448,372, program's own pointer not read; effect seen, 25 retraces to frame 449",
        "status": "ok",
        "stop_seq": 453,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 13,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 472,372, program's own pointer not read; effect seen, 25 retraces to frame 474",
        "status": "ok",
        "stop_seq": 478,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 14,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 496,372, program's own pointer not read; effect seen, 25 retraces to frame 499",
        "status": "ok",
        "stop_seq": 503,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 328,396, program's own pointer not read; effect seen, 25 retraces to frame 524",
        "status": "ok",
        "stop_seq": 528,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 352,396, program's own pointer not read; effect seen, 25 retraces to frame 549",
        "status": "ok",
        "stop_seq": 553,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 17,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 400,396, program's own pointer not read; effect seen, 25 retraces to frame 574",
        "status": "ok",
        "stop_seq": 578,
        "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told"
      }
    },
    {
      "step": 18,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 424,396, program's own pointer not read; effect seen, 25 retraces to frame 599",
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
        "pc": "08DF:00000E0A",
        "cpu_mode": "real",
        "stop_seq": 603,
        "frame": 599,
        "instruction": {
          "address": "08DF:00000E0A",
          "bytes": "74FB",
          "text": "je 0xe07",
          "flow": "branch",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": "retrace",
          "delta": 11
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
          "EIP": "0x00000e0a",
          "CS": "0x08df",
          "DS": "0x08df",
          "ES": "0x08df",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x08df"
        },
        "watches": [],
        "cause": "no declared code breakpoint at 08DF:00000E0A: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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
      }
    }
  ],
  "steps_total": 19,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 129,
    "stop_seq_last": 603,
    "surveyed": 19,
    "by_cause": {
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 19
    },
    "unaccounted": 456
  },
  "steps_completed": 19,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `run_to`**: OK cleared drawn: the last reveal and the win dialog drawn

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
  "frame": 599,
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
  "stop_seq": 604,
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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `log`**: OK won: the game logged WIN

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

**23. `send_mouse`**: OK park: the pointer parked at 790,590, off every region the map signs

<details><summary>call and reply</summary>

```json
{
  "x": 790,
  "y": 590
}
```

```json
{
  "summary": "send_mouse: pointer at 790,590, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 614",
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
  "polls": 15,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "stop_seq": 619,
  "frame": 614,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**24. `screen_map_find`**: OK is win: the win screen, its controls ok

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

**25. `screen_view`**: OK screen: mode M_LIN8, 800x600 by palette index

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

**26. `run_for`**: OK win: 240 retraces with the win dialog up

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
  "frame": 854,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 620,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 614,
  "frame_after": 854,
  "cycles": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**27. `send_mouse`**: OK again: OK started the next game

<details><summary>call and reply</summary>

```json
{
  "target": "ok",
  "button": "left",
  "expect": "NEW 9 9 10$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 400,330, program's own pointer not read; effect seen, 21 retraces to frame 875",
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
  "stop_seq": 641,
  "frame": 875,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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
  "identified_at_stop": 619,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**28. `run_to`**: OK next board drawn: the next board drawn

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
  "frame": 875,
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
  "stop_seq": 642,
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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**29. `read_memory`**: OK next mines: mines at 0,7, 1,1, 1,7, 2,0, 4,1, 4,4, 5,0, 5,2, 7,5, 8,4

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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**30. `send_mouse`**: OK mine: a left click on the mine at 0,7, the machine left stopped a few retraces later, the explosion already sounding

<details><summary>call and reply</summary>

```json
{
  "x": 472,
  "y": 204,
  "button": "left",
  "expect": "BOOM 0 7$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 472,204, program's own pointer not read; effect seen, 25 retraces to frame 900",
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
  "stop_seq": 667,
  "frame": 900,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**31. `log`**: OK boom: the game logged BOOM 0 7

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

**32. `audio_record`**: OK record: 45 retraces recorded from where the click left the machine

<details><summary>call and reply</summary>

```json
{
  "frames": 45,
  "dest": "./tmp/demos/mines/boom.wav"
}
```

```json
{
  "summary": "audio_record wav 45 frames: ELAPSED, 30768 samples at 48000 Hz at ./tmp/demos/mines/boom.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 45,
  "pc": "08DF:00000E08",
  "cpu_mode": "real",
  "frame": 945,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 668,
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
  "emulated_before_s": 12.818086224999998,
  "emulated_after_s": 13.459407425,
  "frame_before": 900,
  "frame_after": 945,
  "cycles": 1789674,
  "kind": "wav",
  "frames": 45,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 123116,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 30768,
  "emulated_s": 0.6413212,
  "sample_min": -18099,
  "sample_max": 18479,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**33. `audio_compare`**: OK heard: a sound, peaking at -4.98 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "./tmp/demos/mines/boom.wav"
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
      "silence_spans": {"count": 1, "first": [0.5204, 0.641]},
      "onset_s": 0.0,
      "clipping_run": 7,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -4.98,
      "rms_dbfs": -18.47,
      "silent": false,
      "silence_spans": {"count": 1, "first": [0.5204, 0.641]},
      "onset_s": 0.0,
      "clipping_run": 7,
      "clipped": false
    }
  ],
  "pcm_sha256": "770c3049ce3f08cbbd1a4576cc1ebc8fc99a5f3674b073a1495d88dd2092e08a",
  "path": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**34. `audio_compare`**: OK exact: the explosion is boom.wav, sample for sample

<details><summary>call and reply</summary>

```json
{
  "method": "diff",
  "a": "./tmp/demos/mines/boom.wav",
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

**35. `send_mouse`**: OK park again: the pointer parked at 790,590, off every region the map signs

<details><summary>call and reply</summary>

```json
{
  "x": 790,
  "y": 590
}
```

```json
{
  "summary": "send_mouse: pointer at 790,590, program's own pointer not read; no button pressed; posted, unverified, 11 retraces to frame 956",
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
  "stop_seq": 679,
  "frame": 956,
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
  "cause": "no declared code breakpoint at 08DF:00000E08: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
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

**36. `screen_map_find`**: OK is lose: the lose screen, its controls ok

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

**37. `close`**: OK close: closed: quit

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
  "conf": "./demos/mines/mines.conf",
  "conf_digest": "d7ad5cdd0a4642de",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "./tmp/demos/mines/video",
  "state_dir": "./tmp/demos/mines/mines-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
