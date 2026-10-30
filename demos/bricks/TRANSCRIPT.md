**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./demos/bricks/bricks.conf",
  "cwd": "./demos/bricks",
  "session_seconds": 900,
  "shared": true,
  "break_on_int3": true,
  "logfile": "./tmp/demos/bricks/bricks-e9.log",
  "state_dir": "./tmp/demos/bricks/bricks-states"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
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
  "debugger_commands": ["A20", "BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "PIC", "PORTINFO", "PRESENCE", "RUNSTATE", "SAVESTATE", "STEPIN", "TAP", "VGAMEMDUMP"],
  "stub": "./src/scry_dosbox_x/guest/SCRY.COM",
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

**2. `resume`**: OK ready: the program's own int 3 at 08DD:0119: loaded at 08DD

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DD:00000119",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DD:00000119",
  "cpu_mode": "real",
  "frame": 1,
  "regs": {
    "EAX": "0x00000e0a",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x000005b2",
    "EDI": "0x0000bc1e",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000119",
    "CS": "0x08dd",
    "DS": "0x08dd",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08dd"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 03`: the guest is at `int 03`, at 08DD:00000119",
  "e9": {
    "lines_total": 2,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=6 motion=1", "Bochs port E9h: BRICKS ready"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08DD:00000119",
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

**3. `symbols_load`**: OK symbols: 65 symbols placed at base 0x8dd0

<details><summary>call and reply</summary>

```json
{
  "path": "./demos/bricks/bricks.sym",
  "base": "8dd0"
}
```

```json
{
  "summary": "symbols_load: 65 loaded of 65 parsed, base 36304",
  "status": "ok",
  "base": 36304,
  "limit": -1,
  "descriptor": -1,
  "declarations": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []},
  "pending": false,
  "checked": {
    "available": false,
    "why": "no executable named bricks.exe beside the table, so it could not be checked against its build"
  },
  "base_from": "caller",
  "parsed": 65,
  "kept": 65,
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
  "table_total": 65,
  "loaded": 65,
  "bytes": 1302,
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
  "summary": "disassemble brick_hit: 14 lines at 08DD:000002C8, 16-bit",
  "status": "ok",
  "ref": "brick_hit",
  "seg_off": "08DD:000002C8",
  "length": 32,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["08DD:000002C8 88DF                 mov bh, bl", "08DD:000002CA 88C3                 mov bl, al", "08DD:000002CC E81FFF               call 0x1ee", "08DD:000002CF C6842C0600           mov byte ptr [si + 0x62c], 0", "08DD:000002D4 FE0E2B06             dec byte ptr [0x62b]", "08DD:000002D8 53                   push bx", "08DD:000002D9 30C0                 xor al, al", "08DD:000002DB E81BFF               call 0x1f9", "08DD:000002DE 5B                   pop bx", "08DD:000002DF B006                 mov al, 6", "08DD:000002E1 28D8                 sub al, bl", "08DD:000002E3 B40A                 mov ah, 0xa", "08DD:000002E5 F6E4                 mul ah", "08DD:000002E7 01061506             add word ptr [0x615], ax"],
  "flow": ["sequential", "sequential", "call", "sequential", "sequential", "sequential", "sequential", "call", "sequential", "sequential", "sequential", "sequential", "sequential", "sequential"],
  "flow_source": "capstone",
  "resolved": [
    {
      "line": 2,
      "operand": "0x1ee",
      "kind": "target",
      "seg_off": "08DD:000001EE",
      "addr": "0x00008fbe",
      "symbol": "brick_index",
      "delta": 0
    },
    {
      "line": 4,
      "operand": "byte ptr [0x62b]",
      "kind": "memory",
      "register": "DS",
      "seg_off": "08DD:0000062B",
      "addr": "0x000093fb",
      "symbol": "bricks_left",
      "delta": 0
    },
    {
      "line": 7,
      "operand": "0x1f9",
      "kind": "target",
      "seg_off": "08DD:000001F9",
      "addr": "0x00008fc9",
      "symbol": "brick_rect",
      "delta": 0
    },
    {
      "line": 13,
      "operand": "word ptr [0x615]",
      "kind": "memory",
      "register": "DS",
      "seg_off": "08DD:00000615",
      "addr": "0x000093e5",
      "symbol": "score",
      "delta": 0
    }
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `breakpoint_at`**: OK break: breakpoint BP 08DD:02C8

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
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BP 08DD:02C8",
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
  "summary": "resume: OTHER_STOP, stopped at 08DD:000002C8",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DD:000002C8",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08dd",
    "DS": "0x08dd",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08dd"
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
  "cause": "breakpoint brick_hit (by symbol) at 08DD:000002C8",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DD:000002C8",
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

**8. `resume`**: OK second brick: brick_hit for the second brick, row 5 column 6, score 10

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DD:000002C8",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DD:000002C8",
  "cpu_mode": "real",
  "frame": 140,
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000606",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000038",
    "EDI": "0x000064c2",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08dd",
    "DS": "0x08dd",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08dd"
  },
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 10,
      "bytes": "0a00"
    }
  ],
  "cause": "breakpoint brick_hit (by symbol) at 08DD:000002C8",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 7"], "mark": "<volatile>"},
  "stop_seq": 4,
  "instruction": {
    "address": "08DD:000002C8",
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

**9. `read_memory`**: OK score: score 10, read by name

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "length": 2
}
```

```json
{
  "summary": "read_memory score: 2 bytes at 08DD:00000615: 0a00",
  "status": "ok",
  "ref": "score",
  "seg_off": "08DD:00000615",
  "length": 2,
  "hex": "0a00",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

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
    "bytes": 5608,
    "sha256": "64126aceb88896f082fe44ad8e0b33f4e873fe46e5db8a5ea2d152b6488b0df6",
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

**11. `declaration_clear`**: OK unbreak: breakpoint cleared

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
  "disarmed": ["BP 08DD:02C8"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `run_for`**: OK frames: three retraces, the emulated clock from 2.0023 s to 2.0318 s

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
  "emulated_before_s": 2.0022688,
  "emulated_after_s": 2.0317822000000003,
  "frame_before": 140,
  "frame_after": 143,
  "cycles": 68499,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `read_memory`**: OK ball: the ball at (188, 82) moving (-2, +2)

<details><summary>call and reply</summary>

```json
{
  "ref": "ball_x",
  "length": 8
}
```

```json
{
  "summary": "read_memory ball_x: 8 bytes at 08DD:00000621: bc005200feff0200",
  "status": "ok",
  "ref": "ball_x",
  "seg_off": "08DD:00000621",
  "length": 8,
  "hex": "bc005200feff0200",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `resume`**: OK play: the game runs

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

**15. `drive`**: OK keys: the game logged PLAYER, KEY R, KEY R, KEY R

<details><summary>call and reply</summary>

```json
{
  "act": [
    {"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10},
    {"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10},
    {"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10}
  ],
  "pattern": "KEY|PLAYER"
}
```

```json
{
  "summary": "drive: no expectation",
  "status": "ok",
  "act": {
    "ran": [
      {
        "op": "send_keys",
        "reply": {
          "summary": "send_keys (guest): effect seen",
          "status": "ok",
          "keys": ["right"],
          "modifiers": [],
          "route": "guest",
          "posted": 1,
          "bytes": 4,
          "frames": 4,
          "verify": {
            "checked": true,
            "seen": true,
            "expected": "KEY R",
            "verdict": "TARGET",
            "line": "Bochs port E9h: KEY R",
            "seen_before_waiting": "<volatile>",
            "lines_before": "<volatile>",
            "waited_s": "<volatile>",
            "lines_total": "<volatile>"
          },
          "session": {"alive": true, "running": true, "altered": false}
        }
      },
      {
        "op": "send_keys",
        "reply": {
          "summary": "send_keys (guest): effect seen",
          "status": "ok",
          "keys": ["right"],
          "modifiers": [],
          "route": "guest",
          "posted": 1,
          "bytes": 4,
          "frames": 4,
          "verify": {
            "checked": true,
            "seen": true,
            "expected": "KEY R",
            "verdict": "TARGET",
            "line": "Bochs port E9h: KEY R",
            "seen_before_waiting": "<volatile>",
            "lines_before": "<volatile>",
            "waited_s": "<volatile>",
            "lines_total": "<volatile>"
          },
          "session": {"alive": true, "running": true, "altered": false}
        }
      },
      {
        "op": "send_keys",
        "reply": {
          "summary": "send_keys (guest): effect seen",
          "status": "ok",
          "keys": ["right"],
          "modifiers": [],
          "route": "guest",
          "posted": 1,
          "bytes": 4,
          "frames": 4,
          "verify": {
            "checked": true,
            "seen": true,
            "expected": "KEY R",
            "verdict": "TARGET",
            "line": "Bochs port E9h: KEY R",
            "seen_before_waiting": "<volatile>",
            "lines_before": "<volatile>",
            "waited_s": "<volatile>",
            "lines_total": "<volatile>"
          },
          "session": {"alive": true, "running": true, "altered": false}
        }
      }
    ],
    "steps_completed": 3,
    "failed_at": {"available": false, "why": "no step failed"},
    "still_running": true,
    "note": "the list began with the machine running and no step of it released it, so no stop was waited for",
    "held": 0
  },
  "verify": {
    "checked": false,
    "why": "no `expect` given; the act's own steps carried whatever verification they asked for"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": "<volatile>",
      "lines_written": "<volatile>",
      "lines_total": "<volatile>",
      "truncated": false,
      "lines": ["Bochs port E9h: PLAYER", "Bochs port E9h: KEY R", "Bochs port E9h: KEY R", "Bochs port E9h: KEY R"],
      "pattern": "KEY|PLAYER"
    }
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**16. `stop`**: OK pause: stopped through the debugger channel

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
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 6,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `read_memory`**: OK paddle: the paddle at x 164: the middle, then 3 steps right

<details><summary>call and reply</summary>

```json
{
  "ref": "paddle_x",
  "length": 2
}
```

```json
{
  "summary": "read_memory paddle_x: 2 bytes at 08DD:0000061F: a400",
  "status": "ok",
  "ref": "paddle_x",
  "seg_off": "08DD:0000061F",
  "length": 2,
  "hex": "a400",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `resume`**: OK again: the game runs

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

**19. `send_keys`**: OK mouse on: M handed the paddle to the mouse: the game logged MOUSE ON

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
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["m"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
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
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**20. `send_mouse`**: OK mouse: the pointer read back at pixel 240,100 and the game logged MOUSE

<details><summary>call and reply</summary>

```json
{
  "x": 240,
  "y": 100,
  "expect": "MOUSE$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 240,100; effect seen",
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
  "arrived": true,
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
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**21. `send_keys`**: OK mouse off: M took the paddle back, so the pointer moves nothing from here on

<details><summary>call and reply</summary>

```json
{
  "keys": ["m"],
  "expect": "MOUSE OFF$",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["m"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MOUSE OFF$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MOUSE OFF",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**22. `stop`**: OK mark: stopped through the debugger channel

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
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 7,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `read_memory`**: OK before save: the paddle at x 220, centred under the pointer at pixel 240

<details><summary>call and reply</summary>

```json
{
  "ref": "paddle_x",
  "length": 2
}
```

```json
{
  "summary": "read_memory paddle_x: 2 bytes at 08DD:0000061F: dc00",
  "status": "ok",
  "ref": "paddle_x",
  "seg_off": "08DD:0000061F",
  "length": 2,
  "hex": "dc00",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**24. `resume`**: OK on again: the game runs

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

**25. `state_write`**: OK save: state saved as bricks.sav

<details><summary>call and reply</summary>

```json
{
  "method": "save",
  "name": "bricks"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "bricks",
  "path": "./tmp/demos/bricks/bricks-states/bricks.sav",
  "bytes": "<volatile>",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": true,
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**26. `send_keys`**: OK left: the left arrow moved the paddle after the save

<details><summary>call and reply</summary>

```json
{
  "keys": ["left"],
  "expect": "KEY L$",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["left"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
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
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**27. `state_write`**: OK load: state loaded from bricks.sav

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "name": "bricks"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "bricks",
  "path": "./tmp/demos/bricks/bricks-states/bricks.sav",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": true,
  "mark": "<volatile>",
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**28. `stop`**: OK halt: stopped through the debugger channel

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
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": "<volatile>",
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 8,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**29. `read_memory`**: OK restored: the paddle is back where the state was saved: the load undid the left arrow

<details><summary>call and reply</summary>

```json
{
  "ref": "paddle_x",
  "length": 2
}
```

```json
{
  "summary": "read_memory paddle_x: 2 bytes at 08DD:0000061F: dc00",
  "status": "ok",
  "ref": "paddle_x",
  "seg_off": "08DD:0000061F",
  "length": 2,
  "hex": "dc00",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**30. `resume`**: OK play on: the game runs

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
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**31. `send_keys`**: OK serve: SPACE served the ball that was waiting on the paddle

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
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
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
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**32. `declaration_clear`**: OK unwatch: watch cleared

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
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**33. `close`**: OK close: closed: quit

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
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/bricks/bricks-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
