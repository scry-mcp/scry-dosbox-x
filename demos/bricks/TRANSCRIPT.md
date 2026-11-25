Every call of the run with its reply, in order: 44 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": false,
  "display": "<host>",
  "conf": "./tmp/demos/bricks/bricks-capture.conf",
  "cwd": "./demos/bricks",
  "session_seconds": 900,
  "break_on_int3": true,
  "logfile": "./tmp/demos/bricks/bricks-e9.log",
  "state_dir": "./tmp/demos/bricks/bricks-states",
  "program": "BRICKS.COM",
  "captures_dir": "<host>",
  "binary": "~/.local/state/scry/apps/Scry DOSBox-X.app"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./tmp/demos/bricks/bricks-capture.conf",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "10ae0e9fac043b43",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/bricks/bricks-states",
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
  "logfile": "./tmp/demos/bricks/bricks-e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "1 saved for `promote`",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `resume`**: OK ready: the program's own int 3 at 08DF:0119: loaded at 08DF

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:00000119",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:00000119",
  "cpu_mode": "real",
  "frame": 1,
  "regs": {
    "EAX": "0xd05b0e0a",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x00000566",
    "EDI": "0x0000bc1e",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000119",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 03`: the guest is at `int 03`, at 08DF:00000119",
  "e9": {
    "lines_total": 3,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1", "Bochs port E9h: STUB  . scry already resident", "Bochs port E9h: BRICKS ready"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08DF:00000119",
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

**3. `symbols_load`**: OK symbols: 63 symbols placed at base 0x00008df0

<details><summary>call and reply</summary>

```json
{
  "path": "./demos/bricks/bricks.sym",
  "base": "0x8df0"
}
```

```json
{
  "summary": "symbols_load: 63 loaded of 63 parsed, base 0x00008df0, not checked against a build: no executable named bricks.exe beside the table, so it could not be checked against its build",
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
    "why": "no executable named bricks.exe beside the table, so it could not be checked against its build"
  },
  "base_from": "caller",
  "parsed": 63,
  "kept": 63,
  "excluded_sections": 0,
  "excluded_pattern": 0,
  "excluded_unplaceable": 0,
  "unencodable": [],
  "unencodable_total": 0,
  "truncated_names": 0,
  "disambiguated": 0,
  "renamed": 0,
  "unreadable": 0,
  "overlay_idle": 0,
  "table_mode": "replaced",
  "table_total": 63,
  "loaded": 63,
  "bytes": 1262,
  "symbols_typed": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `disassemble`**: OK look: brick_hit opens with: mov bh, bl

<details><summary>call and reply</summary>

```json
{
  "ref": "brick_hit",
  "length": 32
}
```

```json
{
  "summary": "disassemble brick_hit: 14 lines at 08DF:000002A5, 16-bit",
  "status": "ok",
  "ref": "brick_hit",
  "seg_off": "08DF:000002A5",
  "length": 32,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["08DF:000002A5 88DF                 mov bh, bl", "08DF:000002A7 88C3                 mov bl, al", "08DF:000002A9 E81FFF               call 0x1cb", "08DF:000002AC C684DE0500           mov byte ptr [si + 0x5de], 0", "08DF:000002B1 FE0EDD05             dec byte ptr [0x5dd]", "08DF:000002B5 53                   push bx", "08DF:000002B6 30C0                 xor al, al", "08DF:000002B8 E81BFF               call 0x1d6", "08DF:000002BB 5B                   pop bx", "08DF:000002BC B006                 mov al, 6", "08DF:000002BE 28D8                 sub al, bl", "08DF:000002C0 B40A                 mov ah, 0xa", "08DF:000002C2 F6E4                 mul ah", "08DF:000002C4 0106C905             add word ptr [0x5c9], ax"],
  "flow": ["sequential", "sequential", "call", "sequential", "sequential", "sequential", "sequential", "call", "sequential", "sequential", "sequential", "sequential", "sequential", "sequential"],
  "flow_source": "capstone",
  "resolved": [
    {
      "line": 2,
      "operand": "0x1cb",
      "kind": "target",
      "seg_off": "08DF:000001CB",
      "addr": "0x00008fbb",
      "symbol": "brick_index",
      "delta": 0
    },
    {
      "line": 4,
      "operand": "byte ptr [0x5dd]",
      "kind": "memory",
      "register": "DS",
      "seg_off": "08DF:000005DD",
      "addr": "0x000093cd",
      "symbol": "bricks_left",
      "delta": 0
    },
    {
      "line": 7,
      "operand": "0x1d6",
      "kind": "target",
      "seg_off": "08DF:000001D6",
      "addr": "0x00008fc6",
      "symbol": "brick_rect",
      "delta": 0
    },
    {
      "line": 13,
      "operand": "word ptr [0x5c9]",
      "kind": "memory",
      "register": "DS",
      "seg_off": "08DF:000005C9",
      "addr": "0x000093b9",
      "symbol": "score",
      "delta": 0
    }
  ],
  "names": [
    {"field": "given.ref", "number": "0x00009095", "kind": "symbol", "name": "brick_hit"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `breakpoint_at`**: OK break: breakpoint BP 08DF:02A5

<details><summary>call and reply</summary>

```json
{
  "ref": "brick_hit"
}
```

```json
{
  "summary": "breakpoint_at brick_hit: armed",
  "status": "ok",
  "ref": "brick_hit",
  "by": "symbol",
  "role": "stop",
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 08DF:02A5",
  "names": [
    {"field": "given.ref", "number": "0x00009095", "kind": "symbol", "name": "brick_hit"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `watch_add`**: OK watch: score shown at every stop

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "mode": "show",
  "fmt": "u16"
}
```

```json
{
  "summary": "watch_add score: evaluated",
  "status": "ok",
  "ref": "score",
  "by": "symbol",
  "mode": "show",
  "fmt": "u16",
  "length": 2,
  "stored": true,
  "armed": false,
  "state": "evaluated",
  "names": [
    {"field": "given.ref", "number": "0x000093b9", "kind": "symbol", "name": "score"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `resume`**: OK first brick: brick_hit for the first brick, row 5 column 7, score 0

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002A5",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:000002A5",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0xd05b0005",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002a5",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 0,
      "bytes": "0000"
    }
  ],
  "cause": "breakpoint brick_hit (by symbol) at 08DF:000002A5",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DF:000002A5",
    "bytes": "88DF",
    "text": "mov bh, bl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `record`**: OK brick seen: the fall into the second brick, 104 frames in 1.48 s

<details><summary>call and reply</summary>

```json
{
  "frames": 200,
  "dest": "./tmp/demos/bricks/first-brick.avi",
  "seconds": 300
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "OTHER_STOP",
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
  "retrace_pending": true,
  "note": "<volatile>",
  "kind": "avi",
  "frames": 200,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/bricks/first-brick.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `declaration_clear`**: OK unbreak: breakpoint cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "breakpoint",
  "all": true
}
```

```json
{
  "summary": "declaration_clear breakpoint all: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BP 08DF:02A5"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `run_for`**: OK frames: three retraces, the emulated clock moved on

<details><summary>call and reply</summary>

```json
{
  "frames": 3,
  "seconds": 60
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 3,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 143,
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 20,
      "bytes": "1400"
    }
  ],
  "cause": "<volatile>",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 6"], "mark": "<volatile>"},
  "stop_seq": 5,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 140,
  "frame_after": 143,
  "cycles": 68495,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `read_memory`**: OK ball: the ball at (188, 82) moving (-2, +2)

<details><summary>call and reply</summary>

```json
{
  "ref": "ball_x",
  "length": 8
}
```

```json
{
  "summary": "read_memory ball_x: 8 bytes at 08DF:000005D5: bc005200feff0200",
  "status": "ok",
  "ref": "ball_x",
  "seg_off": "08DF:000005D5",
  "length": 8,
  "hex": "bc005200feff0200",
  "names": [
    {"field": "given.ref", "number": "0x000093c5", "kind": "symbol", "name": "ball_x"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/bricks/screen.png"
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
  "mode": "render",
  "crop": [0, 0, 320, 200],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/bricks/screen.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 1280,
    "height": 800,
    "scale": 4,
    "indexed": true,
    "inline": true
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

Also attached: image/png.

</details>

**13. `read_memory`**: OK score: score 20, read by name

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "length": 2
}
```

```json
{
  "summary": "read_memory score: 2 bytes at 08DF:000005C9: 1400",
  "status": "ok",
  "ref": "score",
  "seg_off": "08DF:000005C9",
  "length": 2,
  "hex": "1400",
  "names": [
    {"field": "given.ref", "number": "0x000093b9", "kind": "symbol", "name": "score"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `record`**: OK score seen: recorded 110 frames in ./tmp/demos/bricks/score-seen.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 110,
  "dest": "./tmp/demos/bricks/score-seen.avi",
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
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/bricks/score-seen.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `disassemble`**: OK lives routine: lose_life opens with mov si, 0x5a0 and decrements the lives

<details><summary>call and reply</summary>

```json
{
  "ref": "lose_life",
  "length": 16
}
```

```json
{
  "summary": "disassemble lose_life: 6 lines at 08DF:00000343, 16-bit",
  "status": "ok",
  "ref": "lose_life",
  "seg_off": "08DF:00000343",
  "length": 16,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["08DF:00000343 BEA005               mov si, 0x5a0", "08DF:00000346 E8DF01               call 0x528", "08DF:00000349 FE0ECB05             dec byte ptr [0x5cb]", "08DF:0000034D 7509                 jne 0x358", "08DF:0000034F BEA505               mov si, 0x5a5", "08DF:00000352 E8D301               call 0x528"],
  "flow": ["sequential", "call", "sequential", "branch", "sequential", "call"],
  "flow_source": "capstone",
  "resolved": [
    {
      "line": 1,
      "operand": "0x528",
      "kind": "target",
      "seg_off": "08DF:00000528",
      "addr": "0x00009318",
      "symbol": "e9_line",
      "delta": 0
    },
    {
      "line": 2,
      "operand": "byte ptr [0x5cb]",
      "kind": "memory",
      "register": "DS",
      "seg_off": "08DF:000005CB",
      "addr": "0x000093bb",
      "symbol": "lives",
      "delta": 0
    },
    {
      "line": 3,
      "operand": "0x358",
      "kind": "target",
      "seg_off": "08DF:00000358",
      "addr": "0x00009148",
      "symbol": "lose_life",
      "delta": 21
    },
    {
      "line": 5,
      "operand": "0x528",
      "kind": "target",
      "seg_off": "08DF:00000528",
      "addr": "0x00009318",
      "symbol": "e9_line",
      "delta": 0
    }
  ],
  "names": [
    {"field": "given.ref", "number": "0x00009133", "kind": "symbol", "name": "lose_life"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `breakpoint_at`**: OK break lives: breakpoint BP 08DF:0343 on lose_life

<details><summary>call and reply</summary>

```json
{
  "ref": "lose_life"
}
```

```json
{
  "summary": "breakpoint_at lose_life: armed",
  "status": "ok",
  "ref": "lose_life",
  "by": "symbol",
  "role": "stop",
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 08DF:0343",
  "names": [
    {"field": "given.ref", "number": "0x00009133", "kind": "symbol", "name": "lose_life"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `send_keys`**: OK key right: the right arrow took the paddle from the game

<details><summary>call and reply</summary>

```json
{
  "keys": ["right"],
  "expect": "KEY R$"
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 16 frames to frame 269",
  "status": "ok",
  "keys": ["right"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 16,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 22,
  "frame": 269,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0004",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x0000057a",
    "EDI": "0x0000e426",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 30,
      "bytes": "1e00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: PLAYER", "Bochs port E9h: KEY R"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "KEY R$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: KEY R",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `send_keys`**: OK key left: the left arrow moved the paddle back

<details><summary>call and reply</summary>

```json
{
  "keys": ["left"],
  "expect": "KEY L$"
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 20 frames to frame 289",
  "status": "ok",
  "keys": ["left"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 20,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 42,
  "frame": 289,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0004",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000574",
    "EDI": "0x0000e41e",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 30,
      "bytes": "1e00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: KEY L"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "KEY L$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: KEY L",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `send_keys`**: OK key right again: the right arrow moved it again

<details><summary>call and reply</summary>

```json
{
  "keys": ["right"],
  "expect": "KEY R$"
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 20 frames to frame 309",
  "status": "ok",
  "keys": ["right"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 20,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 62,
  "frame": 309,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0004",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x0000057a",
    "EDI": "0x0000e426",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 30,
      "bytes": "1e00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: KEY R"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "KEY R$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: KEY R",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `record`**: OK keys seen: recorded 110 frames in ./tmp/demos/bricks/keys-seen.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 110,
  "dest": "./tmp/demos/bricks/keys-seen.avi",
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
  "note": "<volatile>",
  "kind": "avi",
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/bricks/keys-seen.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `state_write`**: OK save: state saved as before-the-miss.sav

<details><summary>call and reply</summary>

```json
{
  "method": "save",
  "name": "before_the_miss"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "before-the-miss",
  "path": "./tmp/demos/bricks/bricks-states/before-the-miss.sav",
  "bytes": "<volatile>",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": false,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `send_keys`**: OK serve: SPACE served the ball that was waiting on the paddle

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"],
  "expect": "SERVE$",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 6 frames to frame 425",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 69,
  "frame": 425,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0804",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000599",
    "EDI": "0x0000d532",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 30,
      "bytes": "1e00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: SERVE"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "SERVE$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: SERVE",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `resume`**: OK miss: the stop at breakpoint lose_life (by symbol) at 08DF:00000343

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
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
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 70,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**24. `declaration_clear`**: OK past: the breakpoint on lose_life cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "breakpoint",
  "all": true
}
```

```json
{
  "summary": "declaration_clear breakpoint all: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BP 08DF:0343"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**25. `run_to`**: OK carry: TARGET: the next ball waits on the paddle

<details><summary>call and reply</summary>

```json
{
  "ref": "carry",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to carry: TARGET at 08DF:0000035E, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:035E",
  "ref": "carry",
  "pc": "08DF:0000035E",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0536", "hits_in_run": 0, "removed": true}
  ],
  "frame": 529,
  "regs": {
    "EAX": "0xd05b0e00",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x000005c9",
    "EDI": "0x0000f5f2",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000035e",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    }
  ],
  "cause": "run_to's target carry at 08DF:0000035E",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: LOST"], "mark": "<volatile>"},
  "stop_seq": 71,
  "instruction": {
    "address": "08DF:0000035E",
    "bytes": "A1D305",
    "text": "mov ax, word ptr [0x5d3]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "carry",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x0000914e", "kind": "symbol", "name": "carry"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**26. `run_for`**: OK shown: 20 retraces with the status line redrawn

<details><summary>call and reply</summary>

```json
{
  "frames": 20,
  "seconds": 60
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 20,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 549,
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    }
  ],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 72,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 529,
  "frame_after": 549,
  "cycles": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**27. `read_memory`**: OK lives: the lives read 2

<details><summary>call and reply</summary>

```json
{
  "ref": "lives",
  "length": 1
}
```

```json
{
  "summary": "read_memory lives: 1 byte at 08DF:000005CB: 02",
  "status": "ok",
  "ref": "lives",
  "seg_off": "08DF:000005CB",
  "length": 1,
  "hex": "02",
  "names": [
    {"field": "given.ref", "number": "0x000093bb", "kind": "symbol", "name": "lives"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**28. `state_write`**: OK load: state loaded from before-the-miss.sav

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "name": "before_the_miss"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "before-the-miss",
  "path": "./tmp/demos/bricks/bricks-states/before-the-miss.sav",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": false,
  "mark": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**29. `watch_add`**: OK pin: the lives pinned at 3

<details><summary>call and reply</summary>

```json
{
  "ref": "lives",
  "mode": "freeze",
  "length": 1
}
```

```json
{
  "summary": "watch_add lives: freeze armed, 1 byte pinned at 03",
  "status": "ok",
  "ref": "lives",
  "by": "symbol",
  "mode": "freeze",
  "fmt": "u8",
  "length": 1,
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "FM 000005CB (03)",
  "entries": ["FM 000005CB (03)"],
  "addr": "08DF:000005CB",
  "frozen_hex": "03",
  "stopped_on_its_own": {
    "stop_seq": 73,
    "pc": "08DF:0000053F",
    "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
  },
  "names": [
    {"field": "given.ref", "number": "0x000093bb", "kind": "symbol", "name": "lives"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**30. `breakpoint_at`**: OK break again: breakpoint BP 08DF:0343 on lose_life again

<details><summary>call and reply</summary>

```json
{
  "ref": "lose_life"
}
```

```json
{
  "summary": "breakpoint_at lose_life: armed",
  "status": "ok",
  "ref": "lose_life",
  "by": "symbol",
  "role": "stop",
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 08DF:0343",
  "names": [
    {"field": "given.ref", "number": "0x00009133", "kind": "symbol", "name": "lose_life"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**31. `send_keys`**: OK serve 2: SPACE served the same ball from the saved machine

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"],
  "expect": "SERVE$",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 11 frames to frame 560",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 11,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 84,
  "frame": 560,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0804",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000599",
    "EDI": "0x0000d532",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 30,
      "bytes": "1e00"
    },
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:000005CB",
      "frozen_hex": "03",
      "entries": ["FM 000005CB (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: SERVE"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "SERVE$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: SERVE",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**32. `resume`**: OK miss 2: the stop at breakpoint lose_life (by symbol) at 08DF:00000343 again

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
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
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 85,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**33. `declaration_clear`**: OK past 2: the breakpoint cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "breakpoint",
  "all": true
}
```

```json
{
  "summary": "declaration_clear breakpoint all: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BP 08DF:0343"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**34. `run_to`**: OK carry 2: TARGET: the next ball waits on the paddle

<details><summary>call and reply</summary>

```json
{
  "ref": "carry",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to carry: TARGET at 08DF:0000035E, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:035E",
  "ref": "carry",
  "pc": "08DF:0000035E",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0536", "hits_in_run": 0, "removed": true}
  ],
  "frame": 664,
  "regs": {
    "EAX": "0xd05b0e00",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x000005c9",
    "EDI": "0x0000f5f2",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000035e",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    },
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:000005CB",
      "frozen_hex": "03",
      "entries": ["FM 000005CB (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "run_to's target carry at 08DF:0000035E",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: LOST"], "mark": "<volatile>"},
  "stop_seq": 86,
  "instruction": {
    "address": "08DF:0000035E",
    "bytes": "A1D305",
    "text": "mov ax, word ptr [0x5d3]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "carry",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x0000914e", "kind": "symbol", "name": "carry"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**35. `run_for`**: OK shown 2: 20 retraces with the status line redrawn

<details><summary>call and reply</summary>

```json
{
  "frames": 20,
  "seconds": 60
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 20,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 684,
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    },
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:000005CB",
      "frozen_hex": "03",
      "entries": ["FM 000005CB (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 87,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 664,
  "frame_after": 684,
  "cycles": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**36. `read_memory`**: OK lives 2: the lives read 3

<details><summary>call and reply</summary>

```json
{
  "ref": "lives",
  "length": 1
}
```

```json
{
  "summary": "read_memory lives: 1 byte at 08DF:000005CB: 03",
  "status": "ok",
  "ref": "lives",
  "seg_off": "08DF:000005CB",
  "length": 1,
  "hex": "03",
  "names": [
    {"field": "given.ref", "number": "0x000093bb", "kind": "symbol", "name": "lives"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**37. `record`**: OK lives held: recorded 110 frames in ./tmp/demos/bricks/lives-held.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 110,
  "dest": "./tmp/demos/bricks/lives-held.avi",
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
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/bricks/lives-held.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**38. `log`**: OK log 2: the game logged LOST twice: the same ball, lost twice

<details><summary>call and reply</summary>

```json
{
  "channel": "guest",
  "pattern": "SERVE|HIT|LOST"
}
```

```json
{
  "summary": "log guest /SERVE|HIT|LOST/: 9 of 9 lines",
  "status": "ok",
  "pattern": "SERVE|HIT|LOST",
  "channel": "guest",
  "lines_total": 9,
  "truncated": false,
  "lines": ["Bochs port E9h: HIT 5 7", "Bochs port E9h: HIT 5 6", "Bochs port E9h: HIT 5 0", "Bochs port E9h: SERVE", "Bochs port E9h: HIT 5 8", "Bochs port E9h: LOST", "Bochs port E9h: SERVE", "Bochs port E9h: HIT 5 8", "Bochs port E9h: LOST"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**39. `send_keys`**: OK mouse on: M handed the paddle to the mouse: the game logged MOUSE ON

<details><summary>call and reply</summary>

```json
{
  "keys": ["m"],
  "expect": "MOUSE ON$",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): reaction seen, 6 frames to frame 800",
  "status": "ok",
  "keys": ["m"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 94,
  "frame": 800,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0004",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000589",
    "EDI": "0x0000e426",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    },
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:000005CB",
      "frozen_hex": "03",
      "entries": ["FM 000005CB (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: MOUSE ON"],
    "mark": "<volatile>"
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MOUSE ON$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MOUSE ON",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**40. `send_mouse`**: OK mouse: the pointer read back at pixel 240,100 and the game logged MOUSE

<details><summary>call and reply</summary>

```json
{
  "x": 240,
  "y": 100,
  "expect": "MOUSE$"
}
```

```json
{
  "summary": "send_mouse: pointer at 240,100, program's own pointer not read; no button pressed; reaction seen, 15 frames to frame 815",
  "status": "ok",
  "x": 240,
  "y": 100,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {"x": 240, "y": 100, "width": 320, "height": 200},
    "mouse": {"x": 480, "y": 100, "max_x": 639, "max_y": 199},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "polls": 15,
  "pc": "08DF:0000053F",
  "cpu_mode": "real",
  "stop_seq": 109,
  "frame": 815,
  "instruction": {
    "address": "08DF:0000053F",
    "bytes": "A808",
    "text": "test al, 8",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 9
  },
  "regs": {
    "EAX": "0xd05b0004",
    "EBX": "0x00000000",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000580",
    "EDI": "0x0000e46e",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x0000053f",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 40,
      "bytes": "2800"
    },
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:000005CB",
      "frozen_hex": "03",
      "entries": ["FM 000005CB (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:0000053F, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {
    "lines_total": "<volatile>",
    "truncated": false,
    "lines": ["Bochs port E9h: MOUSE"],
    "mark": "<volatile>"
  },
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MOUSE$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MOUSE",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**41. `record`**: OK pointer seen: recorded 110 frames in ./tmp/demos/bricks/pointer-seen.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 110,
  "dest": "./tmp/demos/bricks/pointer-seen.avi",
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
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/bricks/pointer-seen.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**42. `read_memory`**: OK paddle: the paddle at x 220, centred under the pointer at pixel 240

<details><summary>call and reply</summary>

```json
{
  "ref": "paddle_x",
  "length": 2
}
```

```json
{
  "summary": "read_memory paddle_x: 2 bytes at 08DF:000005D3: dc00",
  "status": "ok",
  "ref": "paddle_x",
  "seg_off": "08DF:000005D3",
  "length": 2,
  "hex": "dc00",
  "names": [
    {"field": "given.ref", "number": "0x000093c3", "kind": "symbol", "name": "paddle_x"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**43. `declaration_clear`**: OK unwatch: watch cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "watch",
  "all": true
}
```

```json
{
  "summary": "declaration_clear watch all: 2 cleared",
  "status": "ok",
  "declarations_cleared": 2,
  "disarmed": ["FM 000005CB (03)"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**44. `close`**: OK close: closed: quit

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
  "conf": "./tmp/demos/bricks/bricks-capture.conf",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "10ae0e9fac043b43",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/bricks/bricks-states",
  "ended_by": "quit",
  "exit_code": {"available": false, "why": "the emulator's exit code could not be read"},
  "stdout_tail": {
    "available": false,
    "why": "the emulator wrote to a console of its own, which this server does not read (Windows, a build whose debugger draws a screen)"
  },
  "errorlog_tail": "s=924\nDEBUG: RUNSTATE stopped cycles=30573391 ms=11372.098600000 frames=925\nEV of 'EAX EBX ECX EDX ESI EDI EBP ESP EIP CS DS ES FS GS SS EFLAGS CR0' is:\nd05b0004 0 5b0004 3da 580 e46e 91c fffc 53f 8df 8df a000 0 0 8df 7246 10\nBreakpoint list:\n-------------------------------------------------------------------------\n00. FM 000005CB (03)\n01. BPINT 03\nEV of 'PSPSEG' is:\n8df\nDEBUG: Memory dump binary success.\nDEBUG: Memory dump binary success.\nDEBUG: Memory dump binary success.\nDEBUG: RUNSTATE stopped cycles=30573391 ms=11372.098600000 frames=925\nStopped capturing video.\nDEBUG: CAPTURE VIDEO off path=./tmp/demos/bricks/video/bricks_000.avi\nPRESENCE acting frames=510 pointer=1 output=640x400x32 px_read=0 px_written=0 bytes_presented=0 uploads=10 upload_bytes=1080576 layers=edge,pointer,record\nPRESENCE held frames=510 pointer=1 output=640x400x32 px_read=0 px_written=0 bytes_presented=0 uploads=10 upload_bytes=1080576 layers=edge,pointer,record\nEV of 'EAX EBX ECX EDX ESI EDI EBP ESP EIP CS DS ES FS GS SS EFLAGS CR0' is:\nd05b0004 0 5b0004 3da 580 e46e 91c fffc 53f 8df 8df a000 0 0 8df 7246 10\nDEBUG: Memory dump binary success.\nBreakpoint list:\n-------------------------------------------------------------------------\n00. FM 000005CB (03)\n01. BPINT 03\nDEBUG: Breakpoint deletion success.\nBreakpoint list:\n-------------------------------------------------------------------------\n00. BPINT 03\nSDLNET: Closed client TCP listening socket\n--END OF LOG--\n",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
