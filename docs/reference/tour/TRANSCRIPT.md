Every call of the run with its reply, in order: 76 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `build_check`**: OK build: a debugger with every command the tour needs

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "binary": "<volatile>",
  "binary_origin": "<volatile>",
  "version": "<volatile>",
  "debugger": true,
  "heavy_debug": true,
  "debugger_commands": ["RUNSTATE", "STEPIN", "SAVESTATE", "LOADSTATE", "PRESENCE", "VGAMEMDUMP", "BPIF", "CAPTURE", "TAP", "PORTINFO", "DOSTRACE", "PIC", "A20", "MEMDUMPLIN"],
  "tools": ["a20", "audio_compare", "audio_record", "breakpoint_at", "breakpoint_interrupt", "build_check", "call_stack", "capture_frame", "captures", "close", "comment_list", "comment_write", "debug", "declaration_clear", "declaration_list", "disassemble", "drive", "find", "guest_file", "image_compare", "interrupt_vectors", "log", "log_wait", "machine_map", "memdump", "palette", "perform", "perform_export", "pic", "port", "promote", "read_memory", "record", "registers", "regpoint_add", "resume", "run_for", "run_to", "scan", "screen_map_find", "screen_map_write", "screen_signature", "screen_view", "screen_wait", "send_keys", "send_mouse", "series_capture", "set_register", "snapshot", "start", "state_list", "state_write", "status", "step", "stop", "symbols_find", "symbols_load", "trace", "wait", "watch_add", "window", "write"],
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>

**2. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "conf": "./demos/bricks/bricks.conf",
  "cwd": "./demos/bricks",
  "session_seconds": 900,
  "logfile": "./tmp/demos/tour/files/e9.log",
  "state_dir": "./tmp/demos/tour/files/states",
  "captures_dir": "./tmp/demos/tour/files/captures"
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
  "state_dir": "./tmp/demos/tour/files/states",
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
  "logfile": "./tmp/demos/tour/files/e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "1 saved for `promote`",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `status`**: OK status: stopped at the reset vector, before the BIOS has run

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "status: alive, stopped",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/bricks/bricks.conf",
  "conf_digest": "af0834584e2dad05",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/tour/files/states",
  "last_stop": {
    "stop_seq": 1,
    "pc": "F000:0000FFF0",
    "cause": "no declared code breakpoint at F000:0000FFF0, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
    "since_s": "<volatile>",
    "wall_at": "<volatile>"
  },
  "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false},
  "cpu_mode": "real",
  "pc": "F000:0000FFF0",
  "declarations": {"breakpoints": 0, "watches": 0, "regpoints": 0},
  "presence": true,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `window`**: OK window: the session's window is on screen

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "window": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `screen_map_write`**: OK map: the game's screen map loaded: 1 screen, 1 control

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/bricks/bricks-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 1 screen, 1 control of bricks",
  "status": "ok",
  "path": "./demos/bricks/bricks-screen-map.json",
  "application": "bricks",
  "mode": "verified",
  "screens": 1,
  "controls": 1,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `screen_wait`**: OK ready: the play screen is up after 2 retraces

<details><summary>call and reply</summary>

```json
{
  "screen": "play",
  "seconds": 60
}
```

```json
{
  "summary": "screen_wait screen 'play': found after 2 frames",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": 2,
  "sampled_every": 0,
  "screen": {"name": "play", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 2,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {
    "lines_total": 2,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1", "Bochs port E9h: BRICKS ready"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `screen_map_find`**: OK screen: the play screen, its control court

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: play (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "play",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "court", "rect": [200, 80, 80, 40], "centre": [240, 100]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `machine_map`**: OK memory: DOS holds BRICKS at segment 08DF

<details><summary>call and reply</summary>

```json
{
  "sections": ["mcbs"]
}
```

```json
{
  "summary": "machine_map (real): 9 mcbs, left out: devs, kern, xms, ems, ems_pages, bios_mem, callbacks, emu_mem, machine, control, vga (see `omitted`)",
  "status": "ok",
  "cpu_mode": "real",
  "mcbs": [
    {
      "memory": "conventional",
      "mcb_seg": "0450",
      "size_bytes": 10992,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "\"\u0005"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0700",
      "size_bytes": 2464,
      "psp_seg": "0701",
      "filename": "COMMAND"
    },
    {
      "memory": "conventional",
      "mcb_seg": "079B",
      "size_bytes": 720,
      "psp_seg": "0701",
      "filename": "COMMAND"
    },
    {
      "memory": "conventional",
      "mcb_seg": "07C9",
      "size_bytes": 1168,
      "psp_seg": "0814",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0813",
      "size_bytes": 2048,
      "psp_seg": "0814",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0894",
      "size_bytes": 1168,
      "psp_seg": "08DF",
      "filename": "BRICKS"
    },
    {
      "memory": "conventional",
      "mcb_seg": "08DE",
      "size_bytes": 619008,
      "psp_seg": "08DF",
      "filename": "BRICKS"
    },
    {
      "memory": "upper",
      "mcb_seg": "9FFF",
      "size_bytes": 180224,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "SC"
    },
    {
      "memory": "upper",
      "mcb_seg": "CC00",
      "size_bytes": 81904,
      "psp_seg": "0000",
      "notes": "free",
      "filename": ""
    }
  ],
  "counts": {"mcbs": 9},
  "sources": {"mcbs": ["DOS MCBS"]},
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["devs", "kern", "xms", "ems", "ems_pages", "bios_mem", "callbacks", "emu_mem", "machine", "control", "vga"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `symbols_load`**: OK symbols: 65 symbols placed at base 0x00008df0

<details><summary>call and reply</summary>

```json
{
  "path": "./demos/bricks/bricks.sym",
  "base": "0x8df0"
}
```

```json
{
  "summary": "symbols_load: 65 loaded of 65 parsed, base 0x00008df0, not checked against a build: no executable named bricks.exe beside the table, so it could not be checked against its build",
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

**10. `symbols_find`**: OK names: five names begin with ball: ball_rect, ball_x, ball_y, ball_dx, ball_dy

<details><summary>call and reply</summary>

```json
{
  "name": "ball"
}
```

```json
{
  "summary": "symbols_find ball: 5 symbols",
  "status": "ok",
  "query": "ball",
  "symbols_total": 5,
  "symbols": [
    {
      "name": "ball_rect",
      "kind": "T",
      "offset": "0x398",
      "section": -1,
      "addr": "0x00009188",
      "idle": false
    },
    {
      "name": "ball_x",
      "kind": "D",
      "offset": "0x621",
      "section": -1,
      "addr": "0x00009411",
      "idle": false
    },
    {
      "name": "ball_y",
      "kind": "D",
      "offset": "0x623",
      "section": -1,
      "addr": "0x00009413",
      "idle": false
    },
    {
      "name": "ball_dx",
      "kind": "D",
      "offset": "0x625",
      "section": -1,
      "addr": "0x00009415",
      "idle": false
    },
    {
      "name": "ball_dy",
      "kind": "D",
      "offset": "0x627",
      "section": -1,
      "addr": "0x00009417",
      "idle": false
    }
  ],
  "truncated": false,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `interrupt_vectors`**: OK vector: INT 33h points at C402:00000010

<details><summary>call and reply</summary>

```json
{
  "number": "0x33"
}
```

```json
{
  "summary": "interrupt_vectors INT 33: C402:00000010, mcbs 9FFF SC (DOS)",
  "status": "ok",
  "cpu_mode": "real",
  "vectors": [
    {
      "number": "0x33",
      "seg_off": "C402:00000010",
      "addr": "0x000c4030",
      "mcbs": {
        "memory": "upper",
        "mcb_seg": "9FFF",
        "size_bytes": 180224,
        "psp_seg": "0008",
        "notes": "DOS",
        "filename": "SC"
      }
    }
  ],
  "counts": {"vectors": 256, "held": 112, "named": 0},
  "sources": {
    "vectors": ["INTVEC"],
    "mcbs": ["DOS MCBS"],
    "kern": ["DOS KERN"],
    "bios_mem": ["BIOS MEM"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `screen_view`**: OK picture: mode M_VGA, 320x200 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/tour/files/wall.png"
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
    "path": "./tmp/demos/tour/files/wall.png",
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

**13. `palette`**: OK palette: entries 32 to 38 hold the game's own row colours

<details><summary>call and reply</summary>

```json
{
  "first": 32,
  "count": 8,
  "dest": "./tmp/demos/tour/files/palette.png"
}
```

```json
{
  "summary": "palette: entries 32 to 39 of 256; 1024x128 PNG x8, inline",
  "status": "ok",
  "entries": 256,
  "first": 32,
  "count": 8,
  "colors": ["#ff2020", "#ff9200", "#fff330", "#41eb41", "#20d3eb", "#5161ff", "#c3c3d3", "#0841f7"],
  "rgb": ["3f0808", "3f2400", "3f3c0c", "103a10", "08343a", "14183f", "303034", "02103d"],
  "bits": 6,
  "pel_mask": "ffh",
  "image": {
    "path": "./tmp/demos/tour/files/palette.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 1024,
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

**14. `screen_signature`**: OK signature: the SCORE label signs as the committed map says

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 0, 52, 8]
}
```

```json
{
  "summary": "screen_signature M_VGA 52x8 at [0, 0]: f38d22147fd6e2bd",
  "status": "ok",
  "signature": "f38d22147fd6e2bd",
  "kind": "pixel",
  "vga_mode": "M_VGA",
  "width": 320,
  "height": 200,
  "crop": [0, 0, 52, 8],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `read_memory`**: OK score: score 0: no brick has fallen

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "length": 2
}
```

```json
{
  "summary": "read_memory score: 2 bytes at 08DF:00000615: 0000",
  "status": "ok",
  "ref": "score",
  "seg_off": "08DF:00000615",
  "length": 2,
  "hex": "0000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `memdump`**: OK dump: the wall's 60 bytes, every brick standing

<details><summary>call and reply</summary>

```json
{
  "ref": "bricks",
  "length": 60,
  "dest": "./tmp/demos/tour/files/wall.bin"
}
```

```json
{
  "summary": "memdump bricks: 60 bytes to ./tmp/demos/tour/files/wall.bin",
  "status": "ok",
  "ref": "bricks",
  "seg_off": "08DF:0000062C",
  "length": 60,
  "path": "./tmp/demos/tour/files/wall.bin",
  "bytes": 60,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `find`**: OK find: the text SCORE once, at 08DF:00000601

<details><summary>call and reply</summary>

```json
{
  "data_hex": "53434f5245",
  "ref": "start",
  "length": 1384
}
```

```json
{
  "summary": "find start: 1 hit of 53434f5245 in 1384 bytes",
  "status": "ok",
  "ref": "start",
  "seg_off": "08DF:00000100",
  "length": 1384,
  "span": {"from": "08DF:00000100", "length": 1384, "source": "ref+length"},
  "hits": ["08DF:00000601"],
  "hits_total": 1,
  "truncated": false,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `comment_write`**: OK comment: a comment on brick_hit

<details><summary>call and reply</summary>

```json
{
  "method": "add",
  "ref": "brick_hit",
  "text": "AL = row, BL = column of the brick that falls"
}
```

```json
{
  "summary": "comment_write add: brick_hit at 0x000090b8, stored",
  "status": "ok",
  "comment": {
    "ref": "brick_hit",
    "by": "symbol",
    "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
    "created_at": "<volatile>",
    "origin": "<volatile>",
    "inherited": false,
    "age_s": "<volatile>",
    "text": "AL = row, BL = column of the brick that falls",
    "addr": "0x000090b8",
    "state": "resolved"
  },
  "replaced_comments": [],
  "declarations": {"persistent": true, "path": "<volatile>"},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `disassemble`**: OK listing: brick_hit opens with mov bh, bl, the comment beside it

<details><summary>call and reply</summary>

```json
{
  "ref": "brick_hit",
  "length": 12
}
```

```json
{
  "summary": "disassemble brick_hit: 4 lines at 08DF:000002C8, 16-bit",
  "status": "ok",
  "ref": "brick_hit",
  "seg_off": "08DF:000002C8",
  "length": 12,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["08DF:000002C8 88DF                 mov bh, bl // AL = row, BL = column of the brick that falls", "08DF:000002CA 88C3                 mov bl, al", "08DF:000002CC E81FFF               call 0x1ee", "08DF:000002CF C6842C0600           mov byte ptr [si + 0x62c], 0"],
  "flow": ["sequential", "sequential", "call", "sequential"],
  "flow_source": "capstone",
  "resolved": [
    {
      "line": 2,
      "operand": "0x1ee",
      "kind": "target",
      "seg_off": "08DF:000001EE",
      "addr": "0x00008fde",
      "symbol": "brick_index",
      "delta": 0
    }
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `comment_list`**: OK comments: one comment, on brick_hit

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "comment_list: 1 comment",
  "status": "ok",
  "comments": [
    {
      "ref": "brick_hit",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "text": "AL = row, BL = column of the brick that falls",
      "addr": "0x000090b8",
      "state": "resolved"
    }
  ],
  "comments_total": 1,
  "truncated": false,
  "declarations": {"persistent": true, "path": "<volatile>"},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `scan`**: OK scan: 216 one-byte cells are candidates

<details><summary>call and reply</summary>

```json
{
  "method": "start",
  "ref": "row_colours",
  "cell_bytes": 1,
  "length": 216
}
```

```json
{
  "summary": "scan start: row_colours, 216 cells of 1 byte",
  "status": "ok",
  "ref": "row_colours",
  "seg_off": "08DF:00000590",
  "length": 216,
  "cell_bytes": 1,
  "addr": "0x00009380",
  "hits_total": 216,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `port`**: OK port: the next DAC entry to write is 40: the game just set its frame's pen

<details><summary>call and reply</summary>

```json
{
  "method": "read",
  "port": "0x3C8"
}
```

```json
{
  "summary": "port read: 8-bit read of 0x03C8: 0x28",
  "status": "ok",
  "port": "0x03C8",
  "bits": 8,
  "value": "0x28",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**23. `pic`**: OK lines: the timer and the keyboard lines are open

<details><summary>call and reply</summary>

```json
{
  "method": "read"
}
```

```json
{
  "summary": "pic read: 2 controllers, masked 3, 5, 6, 7, 10, 11, requested none",
  "status": "ok",
  "controllers": [
    {
      "controller": "master",
      "icw_index": 0,
      "icw_words": 0,
      "special": false,
      "auto_eoi": false,
      "rotate_eoi": false,
      "single": false,
      "request_issr": false,
      "vector_base": "0x08",
      "active_irq": {"available": false, "why": "no line is in service"},
      "isr": "0x00",
      "isrr": "0xFF",
      "isr_ignore": "0x00"
    },
    {
      "controller": "slave",
      "icw_index": 0,
      "icw_words": 0,
      "special": false,
      "auto_eoi": false,
      "rotate_eoi": false,
      "single": false,
      "request_issr": false,
      "vector_base": "0x70",
      "active_irq": {"available": false, "why": "no line is in service"},
      "isr": "0x00",
      "isrr": "0xFF",
      "isr_ignore": "0x00"
    }
  ],
  "irqs": [
    {"irq": 0, "vector": "0x08", "requested": false, "masked": false, "in_service": false},
    {"irq": 1, "vector": "0x09", "requested": false, "masked": false, "in_service": false},
    {
      "irq": 2,
      "vector": "0x0A",
      "requested": false,
      "masked": false,
      "in_service": false,
      "cascade": true
    },
    {"irq": 3, "vector": "0x0B", "requested": false, "masked": true, "in_service": false},
    {"irq": 4, "vector": "0x0C", "requested": false, "masked": false, "in_service": false},
    {"irq": 5, "vector": "0x0D", "requested": false, "masked": true, "in_service": false},
    {"irq": 6, "vector": "0x0E", "requested": false, "masked": true, "in_service": false},
    {"irq": 7, "vector": "0x0F", "requested": false, "masked": true, "in_service": false},
    {"irq": 8, "vector": "0x70", "requested": false, "masked": false, "in_service": false},
    {"irq": 9, "vector": "0x71", "requested": false, "masked": false, "in_service": false},
    {"irq": 10, "vector": "0x72", "requested": false, "masked": true, "in_service": false},
    {"irq": 11, "vector": "0x73", "requested": false, "masked": true, "in_service": false},
    {"irq": 12, "vector": "0x74", "requested": false, "masked": false, "in_service": false},
    {"irq": 13, "vector": "0x75", "requested": false, "masked": false, "in_service": false},
    {"irq": 14, "vector": "0x76", "requested": false, "masked": false, "in_service": false},
    {"irq": 15, "vector": "0x77", "requested": false, "masked": false, "in_service": false}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**24. `a20`**: OK gate: the A20 gate is on

<details><summary>call and reply</summary>

```json
{
  "method": "read"
}
```

```json
{
  "summary": "a20 read: the A20 gate is on",
  "status": "ok",
  "enabled": true,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**25. `debug`**: OK fpu: the FPU's eight registers, which no typed tool reads

<details><summary>call and reply</summary>

```json
{
  "command": "FPU"
}
```

```json
{
  "summary": "debug 'FPU': 460 chars",
  "status": "ok",
  "command": "FPU",
  "output": "status: B=0 C3-C0=0000 ES=0 SF=0 PE=0 UE=0 OE=0 ZE=0 DE=0 IE=0 TOP=0\n st(0): empty use80=0 val=0 (0x0000000000000000)\n st(1): empty use80=0 val=0 (0x0000000000000000)\n st(2): empty use80=0 val=0 (0x0000000000000000)\n st(3): empty use80=0 val=0 (0x0000000000000000)\n st(4): empty use80=0 val=0 (0x0000000000000000)\n st(5): empty use80=0 val=0 (0x0000000000000000)\n st(6): empty use80=0 val=0 (0x0000000000000000)\n st(7): empty use80=0 val=0 (0x0000000000000000)",
  "clipped": false,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**26. `watch_add`**: OK ball: the ball shown at every stop, as a struct

<details><summary>call and reply</summary>

```json
{
  "ref": "ball_x",
  "mode": "show",
  "fmt": "{x:i16,y:i16,dx:i16,dy:i16}"
}
```

```json
{
  "summary": "watch_add ball_x: evaluated",
  "status": "ok",
  "ref": "ball_x",
  "by": "symbol",
  "mode": "show",
  "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
  "length": 8,
  "stored": true,
  "armed": false,
  "state": "evaluated",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**27. `run_to`**: OK first brick: at brick_hit for the brick at row 5 column 7, after 34 retraces

<details><summary>call and reply</summary>

```json
{
  "ref": "brick_hit",
  "control": "retrace",
  "seconds": 60
}
```

```json
{
  "summary": "run_to brick_hit: TARGET at 08DF:000002C8, control counted 34",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:02C8",
  "ref": "brick_hit",
  "pc": "08DF:000002C8",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 34,
  "controls": [
    {"ref": "retrace", "at": "08DF:0580", "hits_in_run": 34, "removed": true}
  ],
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
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": -2},
      "bytes": "e6004e000200feff"
    }
  ],
  "cause": "run_to's target brick_hit at 08DF:000002C8",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DF:000002C8",
    "bytes": "88DF",
    "text": "mov bh, bl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "comment": "AL = row, BL = column of the brick that falls",
    "symbol": "brick_hit",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**28. `registers`**: OK registers: AL 5 and BL 7: the row and the column

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "registers: 15 registers",
  "status": "ok",
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
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**29. `call_stack`**: OK callers: 1 row, the stop itself: the game keeps no frame pointer

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "call_stack: 1 call, innermost brick_hit, heuristic",
  "status": "ok",
  "heuristic": true,
  "code_bits": 16,
  "calls": [
    {
      "seg_off": "08DF:000002C8",
      "via": "stop",
      "call": {"available": false, "why": "the stop itself: no call leads to it"},
      "bp": {"available": false, "why": "no frame was read beside it"},
      "addr": "0x000090b8",
      "symbol": "brick_hit",
      "delta": 0
    }
  ],
  "truncated": false,
  "ended_why": "the return address beside the frame at SS:91C follows no call instruction",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**30. `set_register`**: OK force: AX forced to 0: the brick now counts as one of the top row

<details><summary>call and reply</summary>

```json
{
  "name": "ax",
  "value": 0
}
```

```json
{
  "summary": "set_register ax = 0, verified True",
  "status": "ok",
  "value": "0x0000",
  "register": "ax",
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "readback": "0x0000",
  "verified": true,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**31. `step`**: OK step: two instructions on, BH holds column 7 and BL row 0

<details><summary>call and reply</summary>

```json
{
  "count": 2
}
```

```json
{
  "summary": "step 2: 2 done, at 08DF:000002CC",
  "status": "ok",
  "mode": "into",
  "asked": 2,
  "moved": true,
  "stalled": 0,
  "before": "08DF:000002C8",
  "after": "08DF:000002CC",
  "instructions_completed": 2,
  "pc": "08DF:000002CC",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000700",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002cc",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": -2},
      "bytes": "e6004e000200feff"
    }
  ],
  "cause": "the stop `step` made after 2 steps, at 08DF:000002CC",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 4,
  "instruction": {
    "address": "08DF:000002CC",
    "bytes": "E81FFF",
    "text": "call 0x1ee",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 4
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**32. `perform_export`**: OK export: 15 steps and 4 checks written, 13 reads left out, nothing cut

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/tour/files/session.json"
}
```

```json
{
  "summary": "perform_export: 15 steps, 4 checks, 13 dropped to ./tmp/demos/tour/files/session.json",
  "status": "ok",
  "path": "./tmp/demos/tour/files/session.json",
  "steps": 15,
  "checks": 4,
  "dropped": [
    {"call": 1, "op": "status", "why": "a read the export does not check"},
    {"call": 5, "op": "machine_map", "why": "it changes nothing in the emulated machine"},
    {"call": 7, "op": "symbols_find", "why": "a read the export does not check"},
    {"call": 8, "op": "interrupt_vectors", "why": "it changes nothing in the emulated machine"},
    {"call": 9, "op": "screen_view", "why": "it changes nothing in the emulated machine"},
    {"call": 10, "op": "palette", "why": "it changes nothing in the emulated machine"},
    {"call": 13, "op": "memdump", "why": "it changes nothing in the emulated machine"},
    {"call": 14, "op": "find", "why": "a read the export does not check"},
    {"call": 15, "op": "comment_write", "why": "it changes nothing in the emulated machine"},
    {"call": 16, "op": "disassemble", "why": "a read the export does not check"},
    {"call": 17, "op": "comment_list", "why": "a read the export does not check"},
    {"call": 18, "op": "scan", "why": "it changes nothing in the emulated machine"},
    {"call": 26, "op": "call_stack", "why": "a read the export does not check"}
  ],
  "dropped_total": 13,
  "cut": {"available": false, "why": "the recording kept every call a replay takes"},
  "replay": "uv run python -m scry_core.replay ./tmp/demos/tour/files/session.json",
  "kept": "2 saved for `promote`",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**33. `promote`**: OK review: reviewed and nothing written: perform/session, start/bricks

<details><summary>call and reply</summary>

```json
{
  "dry_run": true
}
```

```json
{
  "summary": "promote: 2 candidates in ./.scry",
  "status": "ok",
  "store": "./.scry",
  "candidates": [
    {
      "entry": "perform/session",
      "kind": "perform",
      "name": "session",
      "file": ".scry/perform/session.json",
      "bytes": 5129,
      "change": "new"
    },
    {
      "entry": "start/bricks",
      "kind": "start",
      "name": "bricks",
      "file": ".scry/start/bricks.json",
      "bytes": 154,
      "change": "update",
      "diff": {
        "added": [],
        "removed": ["break_on_int3"],
        "changed": [
          {
            "path": "conf",
            "was": "${env:DOSBOX_X_LIVE_BRICKS_DIR}/bricks.conf",
            "now": "${root}/demos/bricks/bricks.conf"
          },
          {"path": "cwd", "was": "${env:DOSBOX_X_LIVE_BRICKS_DIR}", "now": "${root}/demos/bricks"}
        ]
      }
    }
  ],
  "unchanged": [],
  "total_bytes": 5283,
  "store_bytes": 10100,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**34. `trace`**: OK trace: 40 instructions traced through brick_index, brick_rect, fill_rect, brick_hit

<details><summary>call and reply</summary>

```json
{
  "instructions": 40
}
```

```json
{
  "summary": "trace 40 normal: ELAPSED, 40 executed at 34 addresses, at 08DF:00000221, to ./tmp/demos/tour/files/captures/trace-1.trace",
  "status": "ok",
  "pc": "08DF:00000221",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000700",
    "ECX": "0x005b0002",
    "EDX": "0x00000008",
    "ESI": "0x00000007",
    "EDI": "0x00001efd",
    "EBP": "0x0000091c",
    "ESP": "0x0000fff0",
    "EIP": "0x00000221",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": -2},
      "bytes": "e6004e000200feff"
    }
  ],
  "cause": "the end of the trace's count, at 08DF:00000221",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 5,
  "instruction": {
    "address": "08DF:00000221",
    "bytes": "F3AA",
    "text": "rep stosb byte ptr es:[di], al",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "fill_rect",
    "delta": 3
  },
  "verdict": "ELAPSED",
  "trace": {
    "path": "./tmp/demos/tour/files/captures/trace-1.trace",
    "bytes": 10209,
    "shape": "normal",
    "instructions": 40,
    "addresses": 34,
    "unplaced": 0,
    "set_path": "./tmp/demos/tour/files/captures/trace-1-trace-set.jsonl",
    "symbols": [
      {
        "symbol": "brick_index",
        "addr": "0x00008fde",
        "addresses": 6,
        "instructions": 6,
        "first": "0x00008fde",
        "last": "0x00008fe8"
      },
      {
        "symbol": "brick_rect",
        "addr": "0x00008fe9",
        "addresses": 18,
        "instructions": 18,
        "first": "0x00008fe9",
        "last": "0x0000900c"
      },
      {
        "symbol": "fill_rect",
        "addr": "0x0000900e",
        "addresses": 4,
        "instructions": 10,
        "first": "0x0000900e",
        "last": "0x00009011"
      },
      {
        "symbol": "brick_hit",
        "addr": "0x000090b8",
        "addresses": 6,
        "instructions": 6,
        "first": "0x000090bc",
        "last": "0x000090cb"
      }
    ],
    "symbols_total": 4,
    "truncated": false
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**35. `watch_add`**: OK watch: a stop armed on any change of the score

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "mode": "change",
  "fmt": "u16"
}
```

```json
{
  "summary": "watch_add score: armed",
  "status": "ok",
  "ref": "score",
  "by": "symbol",
  "mode": "change",
  "fmt": "u16",
  "length": 2,
  "stored": true,
  "armed": true,
  "state": "armed",
  "entry": "BPMEM 08DF:0615",
  "entries": ["BPMEM 08DF:0615", "BPMEM 08DF:0616"],
  "command": "BPM 08DF:0615",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**36. `resume`**: OK score changes: stopped inside brick_hit, the score just written: 60

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002EB",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:000002EB",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x0000003c",
    "EBX": "0x00000700",
    "ECX": "0x005b001e",
    "EDX": "0x00000000",
    "ESI": "0x00000007",
    "EDI": "0x00001ee1",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002eb",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": -2},
      "bytes": "e6004e000200feff"
    },
    {
      "ref": "score",
      "by": "symbol",
      "mode": "change",
      "length": 2,
      "fmt": "u16",
      "state": "armed",
      "value": 60,
      "bytes": "3c00"
    }
  ],
  "cause": "no declared code breakpoint at 08DF:000002EB, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 6,
  "instruction": {
    "address": "08DF:000002EB",
    "bytes": "F71E2706",
    "text": "neg word ptr [0x627]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "brick_hit",
    "delta": 35
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**37. `scan`**: OK survivors: 2 cells hold 60, score among them

<details><summary>call and reply</summary>

```json
{
  "method": "filter",
  "value": 60
}
```

```json
{
  "summary": "scan filter: = 60, 2 left",
  "status": "ok",
  "operator": "=",
  "value": "0x3c",
  "iterations": 1,
  "closed": false,
  "hits": [
    {"seg_off": "08DF:00000597", "addr": "0x00009387", "value": "0x3c"},
    {"seg_off": "08DF:00000615", "addr": "0x00009405", "value": "0x3c"}
  ],
  "hits_total": 2,
  "truncated": false,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**38. `declaration_clear`**: OK unwatch: 1 cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "watch",
  "ref": "score"
}
```

```json
{
  "summary": "declaration_clear watch score: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BPMEM 08DF:0615 (3C)", "BPMEM 08DF:0616 (00)"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**39. `regpoint_add`**: OK regpoint: a stop armed on DX holding 3DAh

<details><summary>call and reply</summary>

```json
{
  "condition": "DX==3DA"
}
```

```json
{
  "summary": "regpoint_add DX==3DA: armed",
  "status": "ok",
  "ref": "DX==3DA",
  "by": "expr",
  "condition": "DX==3DA",
  "stored": true,
  "while_running": false,
  "armed": true,
  "state": "armed",
  "entry": "BPIF DX==3DA",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**40. `resume`**: OK status port: stopped in retrace, the routine that loads DX with the VGA status port

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:00000583",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:00000583",
  "cpu_mode": "real",
  "frame": 36,
  "regs": {
    "EAX": "0x0000000f",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x000003da",
    "ESI": "0x00000615",
    "EDI": "0x00006266",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffc",
    "EIP": "0x00000583",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 230, "y": 78, "dx": 2, "dy": 2},
      "bytes": "e6004e0002000200"
    }
  ],
  "cause": "registerpoint DX==3DA, whose condition came true at 08DF:00000583",
  "regpoint_hit": {
    "ref": "DX==3DA",
    "condition": "DX==3DA",
    "pc": "08DF:00000583",
    "note": "still armed: a registerpoint stops at every instruction where its condition holds, so the next advance stops again; `declaration_clear(kind=\"regpoint\")` removes it"
  },
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 0 7"], "mark": "<volatile>"},
  "stop_seq": 7,
  "instruction": {
    "address": "08DF:00000583",
    "bytes": "EC",
    "text": "in al, dx",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "retrace",
    "delta": 3
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**41. `declaration_clear`**: OK unregpoint: 1 cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "regpoint",
  "all": true
}
```

```json
{
  "summary": "declaration_clear regpoint all: 1 cleared",
  "status": "ok",
  "declarations_cleared": 1,
  "disarmed": ["BPIF DX==3DA"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**42. `watch_add`**: OK tally: every write of the score counted, with its writer

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "mode": "count",
  "fmt": "u16"
}
```

```json
{
  "summary": "watch_add score: count watch armed as TAP 1, 2 bytes",
  "status": "ok",
  "ref": "score",
  "by": "symbol",
  "mode": "count",
  "fmt": "u16",
  "length": 2,
  "stored": true,
  "armed": true,
  "state": "armed",
  "tally_id": "1",
  "entry": "TAP 1",
  "addr": "08DF:00000615",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**43. `watch_add`**: OK reads: every read of the paddle's place captured, with the beam line

<details><summary>call and reply</summary>

```json
{
  "ref": "paddle_x",
  "mode": "capture",
  "trigger_type": "r"
}
```

```json
{
  "summary": "watch_add paddle_x: capture watch armed as TAP 2, 1 byte",
  "status": "ok",
  "ref": "paddle_x",
  "by": "symbol",
  "mode": "capture",
  "fmt": "u8",
  "length": 1,
  "stored": true,
  "trigger_type": "r",
  "armed": true,
  "state": "armed",
  "tally_id": "2",
  "entry": "TAP 2",
  "addr": "08DF:0000061F",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**44. `record`**: OK film: 110 retraces filmed, the second brick's fall among them

<details><summary>call and reply</summary>

```json
{
  "frames": 110,
  "dest": "./tmp/demos/tour/files/second-brick.avi",
  "seconds": 60
}
```

```json
{
  "summary": "record 110 frames: ELAPSED, 109 frames at ./tmp/demos/tour/files/second-brick.avi",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 110,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 146,
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated",
      "value": {"x": 182, "y": 88, "dx": -2, "dy": 2},
      "bytes": "<volatile>"
    },
    {
      "ref": "score",
      "by": "symbol",
      "mode": "count",
      "length": 2,
      "fmt": "u16",
      "tally_id": "1",
      "addr": "08DF:00000615",
      "installed": true,
      "state": "tallied",
      "total": 1,
      "since_last_stop": 1,
      "overflow_values": 0,
      "overflow_pcs": 0
    },
    {
      "ref": "paddle_x",
      "by": "symbol",
      "mode": "capture",
      "length": 1,
      "fmt": "u8",
      "tally_id": "2",
      "addr": "08DF:0000061F",
      "trigger_type": "r",
      "installed": true,
      "state": "captured",
      "total": 110,
      "since_last_stop": 110,
      "rows_path": "<volatile>",
      "rows_kept": 110,
      "overflow_rows": 0,
      "rows_max": 100000
    }
  ],
  "cause": "<volatile>",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 6"], "mark": "<volatile>"},
  "stop_seq": 8,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 36,
  "frame_after": 146,
  "cycles": 3595712,
  "kind": "avi",
  "frames": 110,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/tour/files/second-brick.avi",
  "bytes": "<volatile>",
  "avi_frames": 109,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**45. `declaration_list`**: OK declared: the score was written once, 70 by brick_hit+0x1f; the paddle was read 110 times, by draw_paddle+0xe

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "declaration_list: 0 breakpoints declared, 0 regpoints declared, 3 watches declared",
  "status": "ok",
  "breakpoints": [],
  "regpoints": [],
  "watches": [
    {
      "ref": "ball_x",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "show",
      "length": 8,
      "fmt": "{x:i16,y:i16,dx:i16,dy:i16}",
      "state": "evaluated"
    },
    {
      "ref": "score",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "count",
      "length": 2,
      "fmt": "u16",
      "tally_id": "1",
      "addr": "08DF:00000615",
      "installed": true,
      "state": "tallied",
      "total": 1,
      "overflow_values": 0,
      "overflow_pcs": 0,
      "values": [
        {"at": "08DF:00000615", "raw_hex": "4600", "count": 1, "value": 70}
      ],
      "values_total": 1,
      "writers": [
        {"pc": "08DF:000002E7", "count": 1, "symbol": "brick_hit+0x1f"}
      ],
      "writers_total": 1
    },
    {
      "ref": "paddle_x",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "mode": "capture",
      "length": 1,
      "fmt": "u8",
      "tally_id": "2",
      "addr": "08DF:0000061F",
      "trigger_type": "r",
      "installed": true,
      "state": "captured",
      "total": 110,
      "rows_path": "<volatile>",
      "rows_kept": 110,
      "overflow_rows": 0,
      "rows_max": 100000,
      "first_rows": [
        {
          "n": 1,
          "frame": 37,
          "line": 417,
          "time_s": 0.532617,
          "pc": "08DF:000003E4",
          "data": "0xd4000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 2,
          "frame": 38,
          "line": 417,
          "time_s": 0.5468845999999999,
          "pc": "08DF:000003E4",
          "data": "0xd6000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 3,
          "frame": 39,
          "line": 417,
          "time_s": 0.5611531,
          "pc": "08DF:000003E4",
          "data": "0xd8000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 4,
          "frame": 40,
          "line": 417,
          "time_s": 0.5754217,
          "pc": "08DF:000003E4",
          "data": "0xda000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 5,
          "frame": 41,
          "line": 417,
          "time_s": 0.589689,
          "pc": "08DF:000003E4",
          "data": "0xdc000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 6,
          "frame": 42,
          "line": 417,
          "time_s": 0.6039579,
          "pc": "08DF:000003E4",
          "data": "0xde000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 7,
          "frame": 43,
          "line": 417,
          "time_s": 0.6182251,
          "pc": "08DF:000003E4",
          "data": "0xe0000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 8,
          "frame": 44,
          "line": 417,
          "time_s": 0.6324938,
          "pc": "08DF:000003E4",
          "data": "0xe2000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 9,
          "frame": 45,
          "line": 417,
          "time_s": 0.6467625,
          "pc": "08DF:000003E4",
          "data": "0xe4000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 10,
          "frame": 46,
          "line": 417,
          "time_s": 0.6610297,
          "pc": "08DF:000003E4",
          "data": "0xe6000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 11,
          "frame": 47,
          "line": 417,
          "time_s": 0.6752983,
          "pc": "08DF:000003E4",
          "data": "0xe8000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 12,
          "frame": 48,
          "line": 417,
          "time_s": 0.6895669,
          "pc": "08DF:000003E4",
          "data": "0xea000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 13,
          "frame": 49,
          "line": 417,
          "time_s": 0.7038343,
          "pc": "08DF:000003E4",
          "data": "0xec000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 14,
          "frame": 50,
          "line": 417,
          "time_s": 0.7181028,
          "pc": "08DF:000003E4",
          "data": "0xee000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 15,
          "frame": 51,
          "line": 417,
          "time_s": 0.7323702,
          "pc": "08DF:000003E4",
          "data": "0xf0000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 16,
          "frame": 52,
          "line": 417,
          "time_s": 0.7466387999999999,
          "pc": "08DF:000003E4",
          "data": "0xf2000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 17,
          "frame": 53,
          "line": 417,
          "time_s": 0.7609075000000001,
          "pc": "08DF:000003E4",
          "data": "0xf4000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 18,
          "frame": 54,
          "line": 417,
          "time_s": 0.7751747,
          "pc": "08DF:000003E4",
          "data": "0xf6000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 19,
          "frame": 55,
          "line": 417,
          "time_s": 0.7894433000000001,
          "pc": "08DF:000003E4",
          "data": "0xf8000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 20,
          "frame": 56,
          "line": 417,
          "time_s": 0.803712,
          "pc": "08DF:000003E4",
          "data": "0xfa000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 21,
          "frame": 57,
          "line": 417,
          "time_s": 0.8179793,
          "pc": "08DF:000003E4",
          "data": "0xfc000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 22,
          "frame": 58,
          "line": 417,
          "time_s": 0.8322478,
          "pc": "08DF:000003E4",
          "data": "0xfe000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 23,
          "frame": 59,
          "line": 417,
          "time_s": 0.8465151,
          "pc": "08DF:000003E4",
          "data": "0x00000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        },
        {
          "n": 24,
          "frame": 60,
          "line": 417,
          "time_s": 0.8607839,
          "pc": "08DF:000003E4",
          "data": "0x02000000",
          "mask": "0xff000000",
          "symbol": "draw_paddle+0xe"
        }
      ]
    }
  ],
  "debugger_read": true,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**46. `declaration_clear`**: OK untap: 3 cleared

<details><summary>call and reply</summary>

```json
{
  "kind": "watch",
  "all": true
}
```

```json
{
  "summary": "declaration_clear watch all: 3 cleared",
  "status": "ok",
  "declarations_cleared": 3,
  "disarmed": ["TAP 1", "TAP 2"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**47. `capture_frame`**: OK still: frame 104 of the film as a PNG

<details><summary>call and reply</summary>

```json
{
  "frame": 104,
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "dest": "./tmp/demos/tour/files/brick-gone.png"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "path": "./tmp/demos/tour/files/brick-gone.png",
  "bytes": "<volatile>",
  "sha256": "<volatile>",
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "frame": 104,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**48. `series_capture`**: OK series: 14 frames of the film and their manifest

<details><summary>call and reply</summary>

```json
{
  "first": 95,
  "last": 108,
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "dest": "./tmp/demos/tour/files/series"
}
```

```json
{
  "summary": "series_capture: 14 AVI frames 95..108, 14 distinct, manifest ./tmp/demos/tour/files/series/manifest.json",
  "status": "ok",
  "manifest": "./tmp/demos/tour/files/series/manifest.json",
  "count": 14,
  "first": 95,
  "last": 108,
  "distinct": 14,
  "frames_asked": 14,
  "kept_after_close": true,
  "frame_source": "avi",
  "capture_path": "./tmp/demos/tour/files/second-brick.avi",
  "crop": [0, 0, 640, 400],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**49. `audio_record`**: OK sound: a WAV of silence: the game makes no sound

<details><summary>call and reply</summary>

```json
{
  "frames": 20,
  "dest": "./tmp/demos/tour/files/sound.wav"
}
```

```json
{
  "summary": "audio_record wav 20 frames: ELAPSED, 13680 samples at 48000 Hz, silent at ./tmp/demos/tour/files/sound.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 20,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 166,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 9,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 146,
  "frame_after": 166,
  "cycles": 659349,
  "kind": "wav",
  "frames": 20,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/tour/files/sound.wav",
  "bytes": 54764,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 13680,
  "emulated_s": 0.285362,
  "sample_min": 0,
  "sample_max": 0,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**50. `breakpoint_at`**: OK break: a breakpoint on brick_hit

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
  "entry": "BP 08DF:02C8",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**51. `resume`**: OK third brick: at brick_hit for the brick at row 5 column 0

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:000002C8",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:000002C8",
  "cpu_mode": "real",
  "frame": 244,
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000000",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000032",
    "EDI": "0x00006410",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "breakpoint brick_hit (by symbol) at 08DF:000002C8",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 10,
  "instruction": {
    "address": "08DF:000002C8",
    "bytes": "88DF",
    "text": "mov bh, bl",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "comment": "AL = row, BL = column of the brick that falls",
    "symbol": "brick_hit",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**52. `state_write`**: OK save: the machine saved as third-brick.sav

<details><summary>call and reply</summary>

```json
{
  "method": "save",
  "name": "third-brick"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "third-brick",
  "path": "./tmp/demos/tour/files/states/third-brick.sav",
  "bytes": "<volatile>",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": false,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**53. `state_list`**: OK states: one state, third-brick

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "state_list: 1 state in ./tmp/demos/tour/files/states",
  "status": "ok",
  "state_dir": "./tmp/demos/tour/files/states",
  "states": [
    {
      "name": "third-brick",
      "path": "./tmp/demos/tour/files/states/third-brick.sav",
      "bytes": "<volatile>",
      "version": "<volatile>",
      "program": "BRICKS",
      "machine": "MCH_VGA",
      "memory_mb": 4096,
      "saved_at": "<volatile>"
    }
  ],
  "working_slot": {"available": false, "why": "the emulator's own numbered slot has not been written"},
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**54. `declaration_clear`**: OK unbreak: 1 cleared

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
  "disarmed": ["BP 08DF:02C8"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**55. `run_for`**: OK frames: three frames on, stopped again

<details><summary>call and reply</summary>

```json
{
  "frames": 3
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
  "frame": 247,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 0"], "mark": "<volatile>"},
  "stop_seq": 11,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": 244,
  "frame_after": 247,
  "cycles": 68499,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**56. `watch_add`**: OK pin: the lives pinned at 3

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
  "entry": "FM 00000617 (03)",
  "entries": ["FM 00000617 (03)"],
  "addr": "08DF:00000617",
  "frozen_hex": "03",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**57. `send_keys`**: OK key: the right arrow took the paddle from the game: it logged KEY R

<details><summary>call and reply</summary>

```json
{
  "keys": ["right"],
  "expect": "KEY R$",
  "seconds": 10
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "keys": ["right"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": "<volatile>",
  "frame": "<volatile>",
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:00000617",
      "frozen_hex": "03",
      "entries": ["FM 00000617 (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "<volatile>",
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
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**58. `resume`**: OK play: the game runs

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

**59. `drive`**: OK mouse on: M handed the paddle to the mouse: the game logged MOUSE ON

<details><summary>call and reply</summary>

```json
{
  "act": [
    {"op": "send_keys", "keys": ["m"]}
  ],
  "expect": "MOUSE ON$",
  "seconds": 10
}
```

```json
{
  "summary": "drive: reaction seen",
  "status": "ok",
  "act": {
    "ran": [
      {
        "op": "send_keys",
        "reply": {
          "summary": "send_keys (guest): sent, reaction not checked",
          "status": "ok",
          "keys": ["m"],
          "modifiers": [],
          "route": "guest",
          "posted": 1,
          "bytes": 2,
          "frames": 2,
          "verify": {
            "checked": false,
            "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
          },
          "session": {"alive": true, "running": true, "altered": true}
        }
      }
    ],
    "steps_completed": 1,
    "failed_at": {"available": false, "why": "no step failed"},
    "still_running": true,
    "note": "the act ended with the machine running; `drive`'s wait for `expect` is the wait",
    "held": 0
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
  "looked": {
    "guest": {
      "available": true,
      "since_mark": "<volatile>",
      "lines_written": "<volatile>",
      "lines_total": "<volatile>",
      "truncated": false,
      "lines": ["Bochs port E9h: MOUSE ON"],
      "pattern": "."
    }
  },
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**60. `send_mouse`**: OK mouse: the pointer on the map's court, pixel 240,100: the paddle centres under it, at x 220

<details><summary>call and reply</summary>

```json
{
  "target": "court",
  "expect": "MOUSE$",
  "seconds": 10
}
```

```json
{
  "summary": "send_mouse: pointer at 240,100, program's own pointer not read; no button pressed; reaction seen",
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
  "target": "court",
  "screen": "play",
  "identified_at_stop": 2,
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**61. `snapshot`**: OK snapshot: a still taken while the game runs

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/tour/files/held.png"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "route": "guest",
  "path": "./tmp/demos/tour/files/held.png",
  "bytes": "<volatile>",
  "sha256": "<volatile>",
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**62. `perform`**: OK serve: the mouse given back and the ball served, in one call

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_keys", "keys": ["m"], "expect": "MOUSE OFF$", "seconds": 10},
    {"op": "send_keys", "keys": ["space"], "expect": "SERVE$", "seconds": 10}
  ]
}
```

```json
{
  "summary": "perform: 2 of 2 steps, still running",
  "status": "ok",
  "ran": [
    {
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): reaction seen",
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
        "session": {"alive": true, "running": true, "altered": true}
      }
    },
    {
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): reaction seen",
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
    }
  ],
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "still_running": true,
  "note": "the sequence ended with the machine running after a step that answers on a running machine, and nothing declared can stop it (no breakpoint, no interrupt breakpoint, no change watch), so no stop was waited for; declare one, or end the list with the step that releases the machine, to wait for its stop",
  "held": 0,
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**63. `log_wait`**: OK lost: the game logged LOST: nobody moved the paddle

<details><summary>call and reply</summary>

```json
{
  "pattern": "LOST$",
  "channel": "guest",
  "seconds": 60
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "LOST$",
  "channel": "guest",
  "line": "Bochs port E9h: LOST",
  "already": "<volatile>",
  "lines_total": "<volatile>",
  "lines_before": "<volatile>",
  "arrived_during": "<volatile>",
  "waited_s": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**64. `wait`**: OK wait: the game runs

<details><summary>call and reply</summary>

```json
{
  "seconds": 1
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "waited_s": "<volatile>",
  "note": "the machine is still running after 1 s; a deliberate wait that expires is this answer, not a failure",
  "session": {"alive": true, "running": true, "altered": true}
}
```

</details>

**65. `stop`**: OK stop: stopped through the debugger

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
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**66. `log`**: OK log: the game logged HIT 0 7, HIT 5 6, HIT 5 0, SERVE, HIT 5 9, LOST

<details><summary>call and reply</summary>

```json
{
  "pattern": "SERVE|HIT|LOST",
  "channel": "guest"
}
```

```json
{
  "summary": "log guest /SERVE|HIT|LOST/: 6 of 6 lines",
  "status": "ok",
  "pattern": "SERVE|HIT|LOST",
  "channel": "guest",
  "lines_total": 6,
  "truncated": false,
  "lines": ["Bochs port E9h: HIT 0 7", "Bochs port E9h: HIT 5 6", "Bochs port E9h: HIT 5 0", "Bochs port E9h: SERVE", "Bochs port E9h: HIT 5 9", "Bochs port E9h: LOST"],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**67. `read_memory`**: OK lives: a ball was lost and the lives still read 3: the freeze undid the write

<details><summary>call and reply</summary>

```json
{
  "ref": "lives",
  "length": 1
}
```

```json
{
  "summary": "read_memory lives: 1 byte at 08DF:00000617: 03",
  "status": "ok",
  "ref": "lives",
  "seg_off": "08DF:00000617",
  "length": 1,
  "hex": "03",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**68. `state_write`**: OK load: the machine of third-brick loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "name": "third-brick"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "third-brick",
  "path": "./tmp/demos/tour/files/states/third-brick.sav",
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

**69. `read_memory`**: OK restored: score 70: the third brick is not counted yet, as when the state was saved

<details><summary>call and reply</summary>

```json
{
  "ref": "score",
  "length": 2
}
```

```json
{
  "summary": "read_memory score: 2 bytes at 08DF:00000615: 4600",
  "status": "ok",
  "ref": "score",
  "seg_off": "08DF:00000615",
  "length": 2,
  "hex": "4600",
  "stopped_on_its_own": {
    "stop_seq": 29,
    "pc": "08DF:000002C8",
    "cause": "no declared code breakpoint at 08DF:000002C8, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**70. `write`**: OK quit: the game's quit flag set

<details><summary>call and reply</summary>

```json
{
  "ref": "quit",
  "data_hex": "01"
}
```

```json
{
  "summary": "write quit: 1 byte, verified True",
  "status": "ok",
  "ref": "quit",
  "seg_off": "08DF:00000619",
  "bytes_written": 1,
  "readback": "01",
  "verified": true,
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**71. `breakpoint_interrupt`**: OK exit: armed as BPINT 21 AH=4C

<details><summary>call and reply</summary>

```json
{
  "number": "0x21",
  "ah": "0x4C"
}
```

```json
{
  "summary": "breakpoint_interrupt BPINT 21 AH=4C: stored",
  "status": "ok",
  "ref": "BPINT 21 AH=4C",
  "stored": true,
  "armed": true,
  "entry": "BPINT 21 AH=4C",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**72. `resume`**: OK leaving: stopped at the game's own exit call, INT 21h with AX 4C00h

<details><summary>call and reply</summary>

```json
{
  "seconds": 60
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08DF:0000013C",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08DF:0000013C",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": {
    "EAX": "0x00004c00",
    "EBX": "0x0000000f",
    "ECX": "0x005b0004",
    "EDX": "0x00000000",
    "ESI": "0x00000615",
    "EDI": "0x00006192",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x0000013c",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [
    {
      "ref": "lives",
      "by": "symbol",
      "mode": "freeze",
      "length": 1,
      "fmt": "u8",
      "addr": "08DF:00000617",
      "frozen_hex": "03",
      "entries": ["FM 00000617 (03)"],
      "bytes": "03",
      "state": "holding"
    }
  ],
  "cause": "most likely the held `BPINT 21 AH=4C`: the guest is at `int 21`, at 08DF:0000013C",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: HIT 5 0"], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": {
    "address": "08DF:0000013C",
    "bytes": "CD21",
    "text": "int 0x21",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 33
  },
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**73. `captures`**: OK captures: 10 files written by the session, all there

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "captures: 10 files",
  "status": "ok",
  "captures": [
    {"kind": "png", "path": "./tmp/demos/tour/files/wall.png", "present": true, "bytes": "<volatile>"},
    {
      "kind": "png",
      "path": "./tmp/demos/tour/files/palette.png",
      "present": true,
      "bytes": "<volatile>"
    },
    {"kind": "bin", "path": "./tmp/demos/tour/files/wall.bin", "present": true, "bytes": "<volatile>"},
    {
      "kind": "json",
      "path": "./tmp/demos/tour/files/session.json",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "trace",
      "path": "./tmp/demos/tour/files/captures/trace-1.trace",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "avi",
      "path": "./tmp/demos/tour/files/second-brick.avi",
      "present": true,
      "bytes": "<volatile>",
      "riff_avi": true,
      "avi_frames": 109,
      "complete": true
    },
    {
      "kind": "png",
      "path": "./tmp/demos/tour/files/brick-gone.png",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "series",
      "path": "./tmp/demos/tour/files/series/manifest.json",
      "present": true,
      "bytes": "<volatile>"
    },
    {
      "kind": "wav",
      "path": "./tmp/demos/tour/files/sound.wav",
      "present": true,
      "bytes": "<volatile>",
      "complete": true,
      "samples": 13680,
      "channels": 2,
      "sample_rate_hz": 48000
    },
    {"kind": "png", "path": "./tmp/demos/tour/files/held.png", "present": true, "bytes": "<volatile>"}
  ],
  "session": {"alive": true, "running": false, "altered": true}
}
```

</details>

**74. `close`**: OK close: closed: quit

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
  "state_dir": "./tmp/demos/tour/files/states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>

**75. `image_compare`**: OK compare: 944 pixels of the second brick's rectangle change at frame 104 of the film: the brick is gone

<details><summary>call and reply</summary>

```json
{
  "method": "region",
  "manifest": "./tmp/demos/tour/files/series/manifest.json",
  "crop": [386, 148, 60, 16],
  "measure": "changed_pixels"
}
```

```json
{
  "summary": "image_compare region: changed_pixels, 4 transitions over 14 frames",
  "status": "ok",
  "measure": "changed_pixels",
  "crop": [386, 148, 60, 16],
  "frames": 14,
  "start": {
    "available": false,
    "why": "`changed_pixels` counts a change from the frame before, and the first frame has none"
  },
  "transitions": [
    [103, 32],
    [104, 944],
    [105, 40],
    [106, 8]
  ],
  "gaps": [1, 1, 1],
  "transitions_total": 4,
  "path": "./tmp/demos/tour/files/series/track-1.json",
  "manifest": "./tmp/demos/tour/files/series/manifest.json",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>

**76. `audio_compare`**: OK measure: a sound, peaking at -4.98 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "./demos/mines/boom.wav"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -4.98 dBFS, onset 0.0 s, ch1 peak -4.98 dBFS, onset 0.0 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": [0.0, 0.641],
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
  "path": "./demos/mines/boom.wav",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
