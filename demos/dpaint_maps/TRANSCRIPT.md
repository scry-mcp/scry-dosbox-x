**1. `start`**: OK start: DOSBox-X in a window, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "conf": "./demos/dpaint_maps/dpaint-maps.conf",
  "session_seconds": 900,
  "program": "DP.EXE k",
  "logfile": "./tmp/demos/dpaint_maps/dpaint-maps-e9.log",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "./demos/dpaint_maps/dpaint-maps.conf",
  "conf_digest": "daae6ab9a0232442",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
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
  "logfile": "./tmp/demos/dpaint_maps/dpaint-maps-e9.log",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `screen_map_write`**: OK map: 11 screens and 109 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/dpaint_maps/dpaint-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 11 screens, 109 controls of dpaint",
  "status": "ok",
  "path": "./demos/dpaint_maps/dpaint-screen-map.json",
  "application": "dpaint",
  "mode": "verified",
  "screens": 11,
  "controls": 109,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_wait`**: OK loaded: Deluxe Paint is up: the map names its screen {'name': 'paint: freehand', 'layer': 'file'}

<details><summary>call and reply</summary>

```json
{
  "screen": "paint: freehand",
  "seconds": 60
}
```

```json
{
  "summary": "screen_wait screen 'paint: freehand': found after 13 retraces",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": 13,
  "sampled_every": 0,
  "screen": {"name": "paint: freehand", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 13,
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

**4. `machine_map`**: OK placed: DP loaded with its PSP at 08DF, its data at 31B2

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "machine_map (real): 22 mcbs, 2 devs, 20 kern, left out: bios_mem, callbacks, vga (see `omitted`)",
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
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "08DE",
      "size_bytes": 232752,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "41B2",
      "size_bytes": 8192,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "43B3",
      "size_bytes": 38400,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "4D14",
      "size_bytes": 3824,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "4E04",
      "size_bytes": 3824,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "4EF4",
      "size_bytes": 3824,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "4FE4",
      "size_bytes": 3824,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "50D4",
      "size_bytes": 9008,
      "psp_seg": "0000",
      "notes": "free",
      "filename": "DP"
    },
    {"memory": "conventional", "mcb_seg": "5308", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {"memory": "conventional", "mcb_seg": "530A", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {"memory": "conventional", "mcb_seg": "530C", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {"memory": "conventional", "mcb_seg": "530E", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {"memory": "conventional", "mcb_seg": "5310", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {
      "memory": "conventional",
      "mcb_seg": "5312",
      "size_bytes": 315072,
      "psp_seg": "0000",
      "notes": "free",
      "filename": ""
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
  "devs": [
    {"header": "0071:0048", "attr": "8004", "strat": "0000", "intr": "0000", "name": "NUL"},
    {"header": "00F9:0000", "attr": "8013", "strat": "FFFF", "intr": "FFFF", "name": "CON"}
  ],
  "kern": [
    {"seg": "0070", "size_bytes": 16, "what": "DOS_IHSEG"},
    {"seg": "0071", "size_bytes": 800, "what": "DOS_INFOBLOCK_SEG"},
    {"seg": "00a3", "size_bytes": 1376, "what": "DOS_SDA_SEG"},
    {"seg": "00f9", "size_bytes": 64, "what": "DOS_CONDRV_SEG"},
    {"seg": "00fd", "size_bytes": 256, "what": "DOS_CDA_SEG"},
    {"seg": "010d", "size_bytes": 64, "what": "dos.tables.tempdta"},
    {"seg": "0111", "size_bytes": 64, "what": "dos.tables.fcbdelete"},
    {"seg": "0115", "size_bytes": 11520, "what": "SFT secondary table"},
    {"seg": "03e5", "size_bytes": 192, "what": "dos.tables.dbcs"},
    {"seg": "03f1", "size_bytes": 32, "what": "dos.tables.filenamechar"},
    {"seg": "03f3", "size_bytes": 400, "what": "dos.tables.collatingseq"},
    {"seg": "040c", "size_bytes": 64, "what": "Fake FCB SFT"},
    {"seg": "0410", "size_bytes": 864, "what": "dos.tables.dpb"},
    {"seg": "0446", "size_bytes": 48, "what": "External device command packet"},
    {"seg": "0449", "size_bytes": 96, "what": "Fake disk buffer head"},
    {"seg": "044f", "size_bytes": 16, "what": "driver.sys.data.list"},
    {"seg": "0450", "size_bytes": 0, "what": "DOS_MEM_START"},
    {"seg": "c400", "size_bytes": 16, "what": "xms_callback"},
    {"seg": "c401", "size_bytes": 32, "what": "ems_baseseg"},
    {"seg": "c403", "size_bytes": 16, "what": "i33loc"}
  ],
  "xms": [],
  "emu_mem": {
    "a20_gate": "ON",
    "cpu_address_bits": 32,
    "cpu_address_mask": "0xffffffff",
    "cpu_address_mask_current": "0xffffffff",
    "memory_reported_size_bytes": 16777216
  },
  "machine": "VGA S3 Trio",
  "control": {
    "cr0": "00000010",
    "cr2": "00000000",
    "cr3": "00000000",
    "cpl": 0,
    "eflags": "<volatile>",
    "vm": 0,
    "iopl": 3,
    "nt": 1,
    "gdtr": {"base": "00000000", "limit": "0000FFFF"},
    "idt": {"base": "00000000", "limit": "000003FF"},
    "tr": {"selector": "0000", "base": "000E3001", "limit": "000000B7*1"},
    "ldtr": {"selector": "0000", "base": "000E3001", "limit": "000000B7*1"}
  },
  "counts": {"mcbs": 22, "devs": 2, "kern": 20, "xms": 0},
  "sources": {
    "mcbs": ["DOS MCBS"],
    "devs": ["DOS DEVS"],
    "kern": ["DOS KERN"],
    "xms": ["DOS XMS"],
    "emu_mem": ["EMU MEM"],
    "machine": ["EMU MACHINE"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `ems` and `ems_pages` are absent: `DOS EMS` printed a line no known shape matches: '     4    0/   0 000e0000-000e3fff virt -> 00199000-0019cfff phys'. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["bios_mem", "callbacks", "vga"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `screen_map_find`**: OK is paint: the map says: paint: freehand

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: paint: freehand (file), 14 controls",
  "status": "ok",
  "matched": true,
  "screen": "paint: freehand",
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
```

</details>

**6. `perform`**: OK open Color: the map named color menu

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "color", "button": "left", "action": "down"},
    {"op": "screen_wait", "screen": "color menu", "seconds": 60},
    {"op": "screen_map_find"}
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
        "summary": "send_mouse: pointer at 251,5, program's own pointer not read; posted, unverified, 16 retraces to frame 29",
        "status": "ok",
        "stop_seq": 18,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'color menu': already on screen", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: color menu (file), 2 controls",
        "status": "ok",
        "matched": true,
        "screen": "color menu",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "palette", "rect": [232, 13, 170, 11], "centre": [317, 18]},
          {"name": "color", "rect": [231, 0, 41, 11], "centre": [251, 5]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 3,
    "stop_seq_last": 18,
    "surveyed": 1,
    "by_cause": {"the retrace the input's post ran to,": 1},
    "unaccounted": 15
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `perform`**: OK choose Palette: the map named palette

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "palette", "button": "left", "action": "up"},
    {"op": "run_to", "screen": "palette"},
    {"op": "screen_wait", "screen": "palette", "seconds": 60},
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
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": 38, "cause": "<volatile>"}
    },
    {
      "step": 1,
      "op": "run_to",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": 39, "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "matched": true,
        "screen": "palette",
        "layer": "file",
        "kind": "pixel",
        "size": [640, 480],
        "controls": [
          {"name": "brown", "rect": [91, 57, 18, 4], "centre": [100, 59]},
          {"name": "red_up", "rect": [4, 34, 7, 10], "centre": [7, 39]},
          {"name": "green_up", "rect": [18, 34, 7, 10], "centre": [21, 39]},
          {"name": "blue_up", "rect": [32, 34, 7, 10], "centre": [35, 39]},
          {"name": "ok", "rect": [10, 143, 55, 12], "centre": [37, 149]},
          {"name": "cancel", "rect": [138, 143, 60, 12], "centre": [168, 149]}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 19,
    "stop_seq_last": 39,
    "surveyed": 2,
    "by_cause": {"the retrace the input's post ran to,": 1, "the retrace a run to a screen ran to,": 1},
    "unaccounted": 19
  },
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `perform`**: OK mix: the brown slot picked, and red's arrow held until brown's red reached the top

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "brown", "button": "left"},
    {"op": "watch_add", "ref": "31B2:31BC", "mode": "change", "fmt": "u8"},
    {"op": "send_mouse", "target": "red_up", "button": "left", "action": "down"},
    {
      "op": "screen_wait",
      "screen": "palette",
      "on_watch": "31B2:31BC",
      "condition": "b@31B2:31BC == 0x3f",
      "seconds": 60
    },
    {"op": "send_mouse", "button": "left", "action": "up"},
    {"op": "declaration_clear", "kind": "watch", "all": true}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 6 of 6 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 100,59, program's own pointer not read; posted, unverified, 24 retraces to frame 74",
        "status": "ok",
        "stop_seq": 63,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "watch_add",
      "reply": {"summary": "watch_add 31B2:31BC: armed", "status": "ok"}
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 7,39, program's own pointer not read; posted, unverified, 22 retraces to frame 94",
        "status": "ok",
        "stop_seq": 85,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'palette': found after 28 firings of watch '31B2:31BC'",
        "status": "ok",
        "stop_seq": 86,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 7,39; posted, unverified, 75 retraces to frame 115",
        "status": "ok",
        "stop_seq": 161,
        "cause": "<volatile>"
      }
    },
    {
      "step": 5,
      "op": "declaration_clear",
      "reply": {
        "summary": "declaration_clear watch all: 1 cleared",
        "status": "ok",
        "declarations_cleared": 1,
        "disarmed": ["BPMEM 31B2:31BC (3F)"],
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 40,
    "stop_seq_last": 161,
    "surveyed": 4,
    "by_cause": {
      "the retrace the input's post ran to,": 1,
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 3
    },
    "unaccounted": 118
  },
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `palette`**: OK orange: the brown slot now holds #ff5500, orange

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
    "bytes": "<volatile>",
    "sha256": "<volatile>",
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

**10. `perform`**: OK sky, sun and sea: the map named paint: freehand, then paint: rectangle, then paint: circle, then paint: rectangle

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "ok", "button": "left"},
    {"op": "screen_wait", "screen": "paint: freehand", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "brown", "button": "left"},
    {"op": "send_mouse", "x": 4, "y": 14, "button": "left", "action": "drag", "to_x": 587, "to_y": 259},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: rectangle", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "circle_filled", "button": "left"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 296,
      "y": 259,
      "button": "left",
      "action": "drag",
      "to_x": 356,
      "to_y": 259
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: circle", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "blue", "button": "left"},
    {"op": "send_mouse", "x": 4, "y": 260, "button": "left", "action": "drag", "to_x": 587, "to_y": 475},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: rectangle", "seconds": 60},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 21 of 21 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 37,149, program's own pointer not read; posted, unverified, 25 retraces to frame 140",
        "status": "ok",
        "stop_seq": 186,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'paint: freehand': found after 2 retraces",
        "status": "ok",
        "stop_seq": 187,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: freehand (file), 14 controls", "status": "ok"}
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142, program's own pointer not read; posted, unverified, 23 retraces to frame 165",
        "status": "ok",
        "stop_seq": 210,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,448, program's own pointer not read; posted, unverified, 25 retraces to frame 190",
        "status": "ok",
        "stop_seq": 235,
        "cause": "<volatile>"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 587,259, program's own pointer not read; posted, unverified, 30 retraces to frame 220",
        "status": "ok",
        "stop_seq": 265,
        "cause": "<volatile>"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 235",
        "status": "ok",
        "stop_seq": 280,
        "cause": "<volatile>"
      }
    },
    {
      "step": 7,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: rectangle': already on screen", "status": "ok"}
    },
    {
      "step": 8,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: rectangle (file), 14 controls", "status": "ok"}
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 634,142, program's own pointer not read; posted, unverified, 25 retraces to frame 260",
        "status": "ok",
        "stop_seq": 305,
        "cause": "<volatile>"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448, program's own pointer not read; posted, unverified, 25 retraces to frame 285",
        "status": "ok",
        "stop_seq": 330,
        "cause": "<volatile>"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 356,259, program's own pointer not read; posted, unverified, 30 retraces to frame 315",
        "status": "ok",
        "stop_seq": 360,
        "cause": "<volatile>"
      }
    },
    {
      "step": 12,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 330",
        "status": "ok",
        "stop_seq": 375,
        "cause": "<volatile>"
      }
    },
    {
      "step": 13,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: circle': already on screen", "status": "ok"}
    },
    {
      "step": 14,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: circle (file), 14 controls", "status": "ok"}
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142, program's own pointer not read; posted, unverified, 25 retraces to frame 355",
        "status": "ok",
        "stop_seq": 400,
        "cause": "<volatile>"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,344, program's own pointer not read; posted, unverified, 25 retraces to frame 380",
        "status": "ok",
        "stop_seq": 425,
        "cause": "<volatile>"
      }
    },
    {
      "step": 17,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 587,475, program's own pointer not read; posted, unverified, 30 retraces to frame 410",
        "status": "ok",
        "stop_seq": 455,
        "cause": "<volatile>"
      }
    },
    {
      "step": 18,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 425",
        "status": "ok",
        "stop_seq": 470,
        "cause": "<volatile>"
      }
    },
    {
      "step": 19,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: rectangle': already on screen", "status": "ok"}
    },
    {
      "step": 20,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: rectangle (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: rectangle",
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
  "steps_total": 21,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 162,
    "stop_seq_last": 470,
    "surveyed": 14,
    "by_cause": {
      "the retrace the input's post ran to,": 13,
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 1
    },
    "unaccounted": 295
  },
  "steps_completed": 21,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `perform`**: OK glints and hull: the map named paint: line, then paint: rectangle

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "line", "button": "left"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 256,
      "y": 272,
      "button": "left",
      "action": "drag",
      "to_x": 336,
      "to_y": 272
    },
    {
      "op": "send_mouse",
      "x": 270,
      "y": 284,
      "button": "left",
      "action": "drag",
      "to_x": 322,
      "to_y": 284
    },
    {
      "op": "send_mouse",
      "x": 284,
      "y": 296,
      "button": "left",
      "action": "drag",
      "to_x": 308,
      "to_y": 296
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: line", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "black", "button": "left"},
    {
      "op": "send_mouse",
      "x": 100,
      "y": 380,
      "button": "left",
      "action": "drag",
      "to_x": 180,
      "to_y": 395
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: rectangle", "seconds": 60},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 14 of 14 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 605,89, program's own pointer not read; posted, unverified, 25 retraces to frame 450",
        "status": "ok",
        "stop_seq": 495,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448, program's own pointer not read; posted, unverified, 25 retraces to frame 475",
        "status": "ok",
        "stop_seq": 520,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 336,272, program's own pointer not read; posted, unverified, 30 retraces to frame 505",
        "status": "ok",
        "stop_seq": 550,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 322,284, program's own pointer not read; posted, unverified, 30 retraces to frame 535",
        "status": "ok",
        "stop_seq": 580,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 308,296, program's own pointer not read; posted, unverified, 30 retraces to frame 565",
        "status": "ok",
        "stop_seq": 610,
        "cause": "<volatile>"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 580",
        "status": "ok",
        "stop_seq": 625,
        "cause": "<volatile>"
      }
    },
    {
      "step": 6,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: line': already on screen", "status": "ok"}
    },
    {
      "step": 7,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: line (file), 14 controls", "status": "ok"}
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,142, program's own pointer not read; posted, unverified, 25 retraces to frame 605",
        "status": "ok",
        "stop_seq": 650,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,323, program's own pointer not read; posted, unverified, 25 retraces to frame 630",
        "status": "ok",
        "stop_seq": 675,
        "cause": "<volatile>"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 180,395, program's own pointer not read; posted, unverified, 30 retraces to frame 660",
        "status": "ok",
        "stop_seq": 705,
        "cause": "<volatile>"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 675",
        "status": "ok",
        "stop_seq": 720,
        "cause": "<volatile>"
      }
    },
    {
      "step": 12,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: rectangle': already on screen", "status": "ok"}
    },
    {
      "step": 13,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: rectangle (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: rectangle",
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
  "steps_total": 14,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 471,
    "stop_seq_last": 720,
    "surveyed": 10,
    "by_cause": {"the retrace the input's post ran to,": 10},
    "unaccounted": 240
  },
  "steps_completed": 14,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `perform`**: OK mast and sail: the map named paint: line, then paint: line

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "line", "button": "left"},
    {"op": "send_mouse", "target": "black", "button": "left"},
    {
      "op": "send_mouse",
      "x": 140,
      "y": 379,
      "button": "left",
      "action": "drag",
      "to_x": 140,
      "to_y": 320
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: line", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 142,
      "y": 322,
      "button": "left",
      "action": "drag",
      "to_x": 176,
      "to_y": 374
    },
    {
      "op": "send_mouse",
      "x": 176,
      "y": 374,
      "button": "left",
      "action": "drag",
      "to_x": 142,
      "to_y": 374
    },
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: line", "seconds": 60},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 12 of 12 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 605,89, program's own pointer not read; posted, unverified, 25 retraces to frame 700",
        "status": "ok",
        "stop_seq": 745,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 604,323, program's own pointer not read; posted, unverified, 25 retraces to frame 725",
        "status": "ok",
        "stop_seq": 770,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 140,320, program's own pointer not read; posted, unverified, 30 retraces to frame 755",
        "status": "ok",
        "stop_seq": 800,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 770",
        "status": "ok",
        "stop_seq": 815,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: line': already on screen", "status": "ok"}
    },
    {
      "step": 5,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: line (file), 14 controls", "status": "ok"}
    },
    {
      "step": 6,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 628,448, program's own pointer not read; posted, unverified, 25 retraces to frame 795",
        "status": "ok",
        "stop_seq": 840,
        "cause": "<volatile>"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 176,374, program's own pointer not read; posted, unverified, 30 retraces to frame 825",
        "status": "ok",
        "stop_seq": 870,
        "cause": "<volatile>"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 142,374, program's own pointer not read; posted, unverified, 30 retraces to frame 855",
        "status": "ok",
        "stop_seq": 900,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 870",
        "status": "ok",
        "stop_seq": 915,
        "cause": "<volatile>"
      }
    },
    {
      "step": 10,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: line': already on screen", "status": "ok"}
    },
    {
      "step": 11,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: line (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: line",
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
  "steps_total": 12,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 721,
    "stop_seq_last": 915,
    "surveyed": 8,
    "by_cause": {"the retrace the input's post ran to,": 8},
    "unaccounted": 187
  },
  "steps_completed": 12,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `perform`**: OK SCRY: the map named paint: text, then paint: freehand

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "black", "button": "left"},
    {"op": "send_mouse", "target": "text", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: text", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "x": 40, "y": 60, "button": "left"},
    {"op": "send_keys", "keys": ["S", "C", "R", "Y"], "modifiers": ["shift"]},
    {"op": "send_mouse", "target": "freehand", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: freehand", "seconds": 60},
    {"op": "screen_map_find"}
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
        "summary": "send_mouse: pointer at 604,323, program's own pointer not read; posted, unverified, 25 retraces to frame 895",
        "status": "ok",
        "stop_seq": 940,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,185, program's own pointer not read; posted, unverified, 25 retraces to frame 920",
        "status": "ok",
        "stop_seq": 965,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 935",
        "status": "ok",
        "stop_seq": 980,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: text': already on screen", "status": "ok"}
    },
    {
      "step": 4,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: text (file), 14 controls", "status": "ok"}
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 40,60, program's own pointer not read; posted, unverified, 25 retraces to frame 960",
        "status": "ok",
        "stop_seq": 1005,
        "cause": "<volatile>"
      }
    },
    {
      "step": 6,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 50 retraces to frame 1010",
        "status": "ok",
        "stop_seq": 1055,
        "cause": "<volatile>"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,65, program's own pointer not read; posted, unverified, 25 retraces to frame 1035",
        "status": "ok",
        "stop_seq": 1080,
        "cause": "<volatile>"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1050",
        "status": "ok",
        "stop_seq": 1095,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: freehand': already on screen", "status": "ok"}
    },
    {
      "step": 10,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: freehand (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: freehand",
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
  "steps_total": 11,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 916,
    "stop_seq_last": 1095,
    "surveyed": 7,
    "by_cause": {"the retrace the input's post ran to,": 7},
    "unaccounted": 173
  },
  "steps_completed": 11,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `perform`**: OK flip the boat: the map named paint: grab, then paint: custom brush, then brush menu, then paint: custom brush, then paint: custom brush

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "brush_grab", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: grab", "seconds": 60},
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
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: custom brush", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "brush", "button": "left", "action": "down"},
    {"op": "screen_wait", "screen": "brush menu", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "flip_horizontal", "button": "left", "action": "up"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: custom brush", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "x": 440, "y": 357, "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: custom brush", "seconds": 60},
    {"op": "screen_map_find"}
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
        "summary": "send_mouse: pointer at 605,185, program's own pointer not read; posted, unverified, 25 retraces to frame 1075",
        "status": "ok",
        "stop_seq": 1120,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1090",
        "status": "ok",
        "stop_seq": 1135,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: grab': already on screen", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: grab (file), 14 controls", "status": "ok"}
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 184,399, program's own pointer not read; posted, unverified, 30 retraces to frame 1120",
        "status": "ok",
        "stop_seq": 1165,
        "cause": "<volatile>"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1135",
        "status": "ok",
        "stop_seq": 1180,
        "cause": "<volatile>"
      }
    },
    {
      "step": 6,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: custom brush': already on screen", "status": "ok"}
    },
    {
      "step": 7,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: custom brush (file), 14 controls", "status": "ok"}
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 203,5, program's own pointer not read; posted, unverified, 20 retraces to frame 1155",
        "status": "ok",
        "stop_seq": 1200,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'brush menu': already on screen", "status": "ok"}
    },
    {
      "step": 10,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: brush menu (file), 2 controls", "status": "ok"}
    },
    {
      "step": 11,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 269,18, program's own pointer not read; posted, unverified, 20 retraces to frame 1175",
        "status": "ok",
        "stop_seq": 1220,
        "cause": "<volatile>"
      }
    },
    {
      "step": 12,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1190",
        "status": "ok",
        "stop_seq": 1235,
        "cause": "<volatile>"
      }
    },
    {
      "step": 13,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'paint: custom brush': found after 10 retraces",
        "status": "ok",
        "stop_seq": 1236,
        "cause": "<volatile>"
      }
    },
    {
      "step": 14,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: paint: custom brush (file), 14 controls", "status": "ok"}
    },
    {
      "step": 15,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 440,357, program's own pointer not read; posted, unverified, 21 retraces to frame 1221",
        "status": "ok",
        "stop_seq": 1257,
        "cause": "<volatile>"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1236",
        "status": "ok",
        "stop_seq": 1272,
        "cause": "<volatile>"
      }
    },
    {
      "step": 17,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: custom brush': already on screen", "status": "ok"}
    },
    {
      "step": 18,
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
  "steps_total": 19,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 1096,
    "stop_seq_last": 1272,
    "surveyed": 10,
    "by_cause": {
      "the retrace the input's post ran to,": 9,
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 1
    },
    "unaccounted": 167
  },
  "steps_completed": 19,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `perform`**: OK Pict, and the brush put down: the map named pict menu, then paint: custom brush, then paint: freehand

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "pict", "button": "left", "action": "down"},
    {"op": "screen_wait", "screen": "pict menu", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "button": "left", "action": "up"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: custom brush", "seconds": 60},
    {"op": "screen_map_find"},
    {"op": "send_mouse", "target": "brush_dot", "button": "left"},
    {"op": "send_mouse", "target": "freehand", "button": "left"},
    {"op": "send_mouse", "x": 610, "y": 300},
    {"op": "screen_wait", "screen": "paint: freehand", "seconds": 60},
    {"op": "screen_map_find"}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 12 of 12 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 119,5, program's own pointer not read; posted, unverified, 20 retraces to frame 1256",
        "status": "ok",
        "stop_seq": 1292,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'pict menu': already on screen", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: pict menu (file), 1 control", "status": "ok"}
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 119,5; posted, unverified, 15 retraces to frame 1271",
        "status": "ok",
        "stop_seq": 1307,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1286",
        "status": "ok",
        "stop_seq": 1322,
        "cause": "<volatile>"
      }
    },
    {
      "step": 5,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: custom brush': already on screen", "status": "ok"}
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
        "summary": "send_mouse: pointer at 599,21, program's own pointer not read; posted, unverified, 25 retraces to frame 1311",
        "status": "ok",
        "stop_seq": 1347,
        "cause": "<volatile>"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 629,65, program's own pointer not read; posted, unverified, 25 retraces to frame 1336",
        "status": "ok",
        "stop_seq": 1372,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 610,300, program's own pointer not read; no button pressed; posted, unverified, 15 retraces to frame 1351",
        "status": "ok",
        "stop_seq": 1387,
        "cause": "<volatile>"
      }
    },
    {
      "step": 10,
      "op": "screen_wait",
      "reply": {"summary": "screen_wait screen 'paint: freehand': already on screen", "status": "ok"}
    },
    {
      "step": 11,
      "op": "screen_map_find",
      "reply": {
        "summary": "screen_map_find: paint: freehand (file), 14 controls",
        "status": "ok",
        "matched": true,
        "screen": "paint: freehand",
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
  "steps_total": 12,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 1273,
    "stop_seq_last": 1387,
    "surveyed": 6,
    "by_cause": {"the retrace the input's post ran to,": 6},
    "unaccounted": 109
  },
  "steps_completed": 12,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `screen_view`**: OK word row: the row reads frame x 4, then orange x 37, then black x 4, then orange x 3, then black x 2, then orange x 6, then black x 5, then orange x 4, then black x 5, then orange x 518, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 57, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-57.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 57] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 57, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-57.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `screen_view`**: OK sun row: the row reads frame x 4, then orange x 239, then yellow x 107, then orange x 238, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 230, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-230.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 230] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 230, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-230.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `screen_view`**: OK glint row: the row reads frame x 4, then blue x 252, then yellow x 81, then blue x 251, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 272, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-272.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 272] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 272, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-272.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `screen_view`**: OK sail row: the row reads frame x 4, then blue x 136, then black x 1, then blue x 19, then yellow x 1, then blue x 258, then yellow x 1, then blue x 20, then black x 1, then blue x 147, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 350, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-350.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 350] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 350, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-350.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `screen_view`**: OK hull row: the row reads frame x 4, then blue x 96, then black x 81, then blue x 219, then black x 81, then blue x 107, then frame x 4

<details><summary>call and reply</summary>

```json
{
  "crop": [0, 388, 592, 1],
  "scale": 1,
  "dest": "./tmp/demos/dpaint_maps/row-388.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_EGA: 592x1 at [0, 388] pixels; 592x1 PNG x1, not inlined",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 388, 592, 1],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/row-388.png",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 592,
    "height": 1,
    "scale": 1,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `screen_view`**: OK screen: mode M_EGA, 640x480 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/dpaint_maps/screen.png"
}
```

```json
{
  "summary": "screen_view M_EGA: 640x480 at [0, 0] pixels; 640x480 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_EGA",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 0, 640, 480],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint_maps/screen.png",
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

**22. `record`**: OK loop: recording 240 frames in ./tmp/demos/dpaint_maps/loop.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 240,
  "dest": "./tmp/demos/dpaint_maps/loop.avi"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": "<volatile>",
  "note": "<volatile>",
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
  "frames": 240,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/dpaint_maps/loop.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `close`**: OK close: closed: quit

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
  "conf": "./demos/dpaint_maps/dpaint-maps.conf",
  "conf_digest": "daae6ab9a0232442",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint_maps/dpaint-maps-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
