**1. `start`**: OK start: DOSBox-X in a window, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "conf": "./demos/dpaint/dpaint.conf",
  "session_seconds": 900,
  "shared": true,
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
  "conf_digest": "5d4d6cc4851520a5",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint/dpaint-states",
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
  "window": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "kept 1 (promote to review)",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `screen_map_write`**: OK map: 1 screens and 13 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/dpaint/dpaint-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 1 screen, 13 controls of dpaint",
  "status": "ok",
  "path": "./demos/dpaint/dpaint-screen-map.json",
  "application": "dpaint",
  "mode": "verified",
  "screens": 1,
  "controls": 13,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_wait`**: OK loaded: Deluxe Paint is up: the map names its screen {'name': 'paint', 'layer': 'file'}

<details><summary>call and reply</summary>

```json
{
  "screen": "paint",
  "seconds": 60
}
```

```json
{
  "summary": "screen_wait screen 'paint': found after 7 retraces",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": 7,
  "sampled_every": 0,
  "screen": {"name": "paint", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 7,
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
  "summary": "machine_map (real): 15 mcbs, 2 devs, 20 kern, left out: bios_mem, callbacks, vga (see `omitted`)",
  "status": "ok",
  "cpu_mode": "real",
  "mcbs": [
    {
      "memory": "conventional",
      "mcb_seg": "0450",
      "size_bytes": 10992,
      "psp_seg": "0008",
      "notes": "DOS",
      "filename": "\u0002"
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
      "size_bytes": 64000,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "5354",
      "size_bytes": 28304,
      "psp_seg": "08DF",
      "filename": "DP"
    },
    {
      "memory": "conventional",
      "mcb_seg": "5A3E",
      "size_bytes": 9008,
      "psp_seg": "0000",
      "notes": "free",
      "filename": "DP"
    },
    {"memory": "conventional", "mcb_seg": "5C72", "size_bytes": 16, "psp_seg": "08DF", "filename": "DP"},
    {
      "memory": "conventional",
      "mcb_seg": "5C74",
      "size_bytes": 276640,
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
  "counts": {"mcbs": 15, "devs": 2, "kern": 20, "xms": 0},
  "sources": {
    "mcbs": ["DOS MCBS"],
    "devs": ["DOS DEVS"],
    "kern": ["DOS KERN"],
    "xms": ["DOS XMS"],
    "emu_mem": ["EMU MEM"],
    "machine": ["EMU MACHINE"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `ems` and `ems_pages` are absent: `DOS EMS` printed a line no known shape matches: '     1    0/   0 000e0000-000e3fff virt -> 00175000-00178fff phys'. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["bios_mem", "callbacks", "vga"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `screen_map_find`**: OK find: the painting screen, 13 controls named

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: paint (file), 13 controls",
  "status": "ok",
  "matched": true,
  "screen": "paint",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "line", "rect": [297, 46, 10, 10], "centre": [302, 51]},
    {"name": "fill", "rect": [297, 58, 10, 10], "centre": [302, 63]},
    {"name": "rect_filled", "rect": [304, 75, 4, 5], "centre": [306, 77]},
    {"name": "circle_filled", "rect": [315, 75, 4, 5], "centre": [317, 77]},
    {"name": "text", "rect": [309, 93, 10, 10], "centre": [314, 98]},
    {"name": "clear", "rect": [309, 128, 10, 11], "centre": [314, 133]},
    {"name": "navy", "rect": [297, 162, 6, 2], "centre": [300, 163]},
    {"name": "brown", "rect": [297, 172, 6, 2], "centre": [300, 173]},
    {"name": "blue", "rect": [297, 178, 6, 2], "centre": [300, 179]},
    {"name": "yellow", "rect": [297, 188, 6, 2], "centre": [300, 189]},
    {"name": "white", "rect": [297, 190, 6, 2], "centre": [300, 191]},
    {"name": "peach", "rect": [315, 168, 5, 2], "centre": [317, 169]},
    {"name": "orange", "rect": [315, 174, 5, 2], "centre": [317, 175]}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `send_mouse`**: OK blue: blue picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "blue",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 300,179, program's own pointer not read; posted, unverified, 21 retraces to frame 28",
  "status": "ok",
  "x": 300,
  "y": 179,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 300, "y": 179, "width": 320, "height": 200},
    "mouse": {"x": 2404, "y": 1436, "max_x": 2552, "max_y": 1592},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "polls": 21,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 23,
  "frame": 28,
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
  "target": "blue",
  "screen": "paint",
  "identified_at_stop": 2,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `scan`**: OK scan: 65535 bytes of the data segment are candidates

<details><summary>call and reply</summary>

```json
{
  "method": "start",
  "ref": "31B2:0000",
  "length": 65535,
  "cell_bytes": 1
}
```

```json
{
  "summary": "scan start: 31B2:0000, 65535 cells of 1 byte",
  "status": "ok",
  "ref": "31B2:0000",
  "seg_off": "31B2:00000000",
  "length": 65535,
  "cell_bytes": 1,
  "addr": "0x00031b20",
  "hits_total": 65535,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `scan`**: OK is blue: 71 bytes hold 0x09 now

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
  "summary": "scan filter: = 9, 71 survivors, the first 8 listed",
  "status": "ok",
  "operator": "=",
  "value": "0x09",
  "iterations": 1,
  "closed": false,
  "hits": [
    {"seg_off": "31B2:0000017C", "addr": "0x00031c9c", "value": "0x09"},
    {"seg_off": "31B2:000001AE", "addr": "0x00031cce", "value": "0x09"},
    {"seg_off": "31B2:00000370", "addr": "0x00031e90", "value": "0x09"},
    {"seg_off": "31B2:00000470", "addr": "0x00031f90", "value": "0x09"},
    {"seg_off": "31B2:00000597", "addr": "0x000320b7", "value": "0x09"},
    {"seg_off": "31B2:000006B3", "addr": "0x000321d3", "value": "0x09"},
    {"seg_off": "31B2:000008F9", "addr": "0x00032419", "value": "0x09"},
    {"seg_off": "31B2:00000919", "addr": "0x00032439", "value": "0x09"}
  ],
  "hits_total": 71,
  "truncated": true,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `send_mouse`**: OK orange: orange picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "orange",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 317,175, program's own pointer not read; posted, unverified, 25 retraces to frame 53",
  "status": "ok",
  "x": 317,
  "y": 175,
  "units": "screen",
  "button": "left",
  "action": "click",
  "route": "guest",
  "pointer": {
    "screen": {"x": 317, "y": 175, "width": 320, "height": 200},
    "mouse": {"x": 2540, "y": 1404, "max_x": 2552, "max_y": 1592},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "polls": 25,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 48,
  "frame": 53,
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
  "target": "orange",
  "screen": "paint",
  "identified_at_stop": 2,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `scan`**: OK is orange: 7 bytes followed both clicks: 3 in the stack's frames above A02A, and 4 static ones from 31B2:017C

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
    {"seg_off": "31B2:0000017C", "addr": "0x00031c9c", "value": "0x37"},
    {"seg_off": "31B2:000001AE", "addr": "0x00031cce", "value": "0x37"},
    {"seg_off": "31B2:00000470", "addr": "0x00031f90", "value": "0x37"},
    {"seg_off": "31B2:000010B0", "addr": "0x00032bd0", "value": "0x37"},
    {"seg_off": "31B2:0000A57E", "addr": "0x0003c09e", "value": "0x37"},
    {"seg_off": "31B2:0000A57F", "addr": "0x0003c09f", "value": "0x37"},
    {"seg_off": "31B2:0000A580", "addr": "0x0003c0a0", "value": "0x37"}
  ],
  "hits_total": 7,
  "truncated": false,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `scan`**: OK unscan: scan closed

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
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `watch_add`**: OK watch: the colour byte shown at every stop

<details><summary>call and reply</summary>

```json
{
  "ref": "31B2:017C",
  "mode": "show",
  "fmt": "u8"
}
```

```json
{
  "summary": "watch_add 31B2:017C: evaluated",
  "status": "ok",
  "ref": "31B2:017C",
  "by": "address",
  "mode": "show",
  "fmt": "u8",
  "length": 1,
  "stored": true,
  "armed": false,
  "state": "evaluated",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `perform`**: OK sky: peach, the colour byte at 52, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "peach", "button": "left"},
    {"op": "send_mouse", "x": 2, "y": 14, "button": "left", "action": "drag", "to_x": 294, "to_y": 112}
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
        "summary": "send_mouse: pointer at 306,77, program's own pointer not read; posted, unverified, 25 retraces to frame 78",
        "status": "ok",
        "stop_seq": 73,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 317,169, program's own pointer not read; posted, unverified, 25 retraces to frame 103",
        "status": "ok",
        "stop_seq": 98,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,112, program's own pointer not read; posted, unverified, 30 retraces to frame 133",
        "status": "ok",
        "x": 2,
        "y": 14,
        "units": "screen",
        "button": "left",
        "action": "drag",
        "route": "guest",
        "pointer": {
          "screen": {"x": 294, "y": 112, "width": 320, "height": 200},
          "mouse": {"x": 2356, "y": 900, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 30,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 128,
        "frame": 133,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 52,
            "bytes": "34"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 49,
    "stop_seq_last": 128,
    "surveyed": 3,
    "by_cause": {"the retrace the input's post ran to,": 3},
    "unaccounted": 77
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `perform`**: OK sun: yellow, the colour byte at 14, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "circle_filled", "button": "left"},
    {"op": "send_mouse", "target": "yellow", "button": "left"},
    {
      "op": "send_mouse",
      "x": 210,
      "y": 112,
      "button": "left",
      "action": "drag",
      "to_x": 238,
      "to_y": 112
    }
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
        "summary": "send_mouse: pointer at 317,77, program's own pointer not read; posted, unverified, 25 retraces to frame 158",
        "status": "ok",
        "stop_seq": 153,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,189, program's own pointer not read; posted, unverified, 25 retraces to frame 183",
        "status": "ok",
        "stop_seq": 178,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 238,112, program's own pointer not read; posted, unverified, 30 retraces to frame 213",
        "status": "ok",
        "x": 210,
        "y": 112,
        "units": "screen",
        "button": "left",
        "action": "drag",
        "route": "guest",
        "pointer": {
          "screen": {"x": 238, "y": 112, "width": 320, "height": 200},
          "mouse": {"x": 1908, "y": 900, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 30,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 208,
        "frame": 213,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 14,
            "bytes": "0e"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 129,
    "stop_seq_last": 208,
    "surveyed": 3,
    "by_cause": {"the retrace the input's post ran to,": 3},
    "unaccounted": 77
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `perform`**: OK sea: navy, the colour byte at 1, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "rect_filled", "button": "left"},
    {"op": "send_mouse", "target": "navy", "button": "left"},
    {"op": "send_mouse", "x": 2, "y": 113, "button": "left", "action": "drag", "to_x": 294, "to_y": 198}
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
        "summary": "send_mouse: pointer at 306,77, program's own pointer not read; posted, unverified, 25 retraces to frame 238",
        "status": "ok",
        "stop_seq": 233,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,163, program's own pointer not read; posted, unverified, 25 retraces to frame 263",
        "status": "ok",
        "stop_seq": 258,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,198, program's own pointer not read; posted, unverified, 30 retraces to frame 293",
        "status": "ok",
        "x": 2,
        "y": 113,
        "units": "screen",
        "button": "left",
        "action": "drag",
        "route": "guest",
        "pointer": {
          "screen": {"x": 294, "y": 198, "width": 320, "height": 200},
          "mouse": {"x": 2356, "y": 1588, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 30,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 288,
        "frame": 293,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 1,
            "bytes": "01"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 3,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 209,
    "stop_seq_last": 288,
    "surveyed": 3,
    "by_cause": {"the retrace the input's post ran to,": 3},
    "unaccounted": 77
  },
  "steps_completed": 3,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `perform`**: OK hull: brown, the colour byte at 6, 1 drag

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "brown", "button": "left"},
    {
      "op": "send_mouse",
      "x": 60,
      "y": 150,
      "button": "left",
      "action": "drag",
      "to_x": 112,
      "to_y": 158
    }
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
        "summary": "send_mouse: pointer at 300,173, program's own pointer not read; posted, unverified, 25 retraces to frame 318",
        "status": "ok",
        "stop_seq": 313,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 112,158, program's own pointer not read; posted, unverified, 30 retraces to frame 348",
        "status": "ok",
        "x": 60,
        "y": 150,
        "units": "screen",
        "button": "left",
        "action": "drag",
        "route": "guest",
        "pointer": {
          "screen": {"x": 112, "y": 158, "width": 320, "height": 200},
          "mouse": {"x": 900, "y": 1268, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 30,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 343,
        "frame": 348,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 6,
            "bytes": "06"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
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
    "stop_seq_first": 289,
    "stop_seq_last": 343,
    "surveyed": 2,
    "by_cause": {"the retrace the input's post ran to,": 2},
    "unaccounted": 53
  },
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `perform`**: OK sail: white, the colour byte at 15, 3 drags

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "line", "button": "left"},
    {"op": "send_mouse", "target": "white", "button": "left"},
    {"op": "send_mouse", "x": 86, "y": 149, "button": "left", "action": "drag", "to_x": 86, "to_y": 118},
    {
      "op": "send_mouse",
      "x": 86,
      "y": 118,
      "button": "left",
      "action": "drag",
      "to_x": 108,
      "to_y": 146
    },
    {
      "op": "send_mouse",
      "x": 108,
      "y": 146,
      "button": "left",
      "action": "drag",
      "to_x": 86,
      "to_y": 146
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
        "summary": "send_mouse: pointer at 302,51, program's own pointer not read; posted, unverified, 25 retraces to frame 373",
        "status": "ok",
        "stop_seq": 368,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,191, program's own pointer not read; posted, unverified, 25 retraces to frame 398",
        "status": "ok",
        "stop_seq": 393,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,118, program's own pointer not read; posted, unverified, 30 retraces to frame 428",
        "status": "ok",
        "stop_seq": 423,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 108,146, program's own pointer not read; posted, unverified, 30 retraces to frame 458",
        "status": "ok",
        "stop_seq": 453,
        "cause": "<volatile>"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,146, program's own pointer not read; posted, unverified, 30 retraces to frame 488",
        "status": "ok",
        "x": 108,
        "y": 146,
        "units": "screen",
        "button": "left",
        "action": "drag",
        "route": "guest",
        "pointer": {
          "screen": {"x": 86, "y": 146, "width": 320, "height": 200},
          "mouse": {"x": 692, "y": 1172, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 30,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 483,
        "frame": 488,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 15,
            "bytes": "0f"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 5,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 344,
    "stop_seq_last": 483,
    "surveyed": 5,
    "by_cause": {"the retrace the input's post ran to,": 5},
    "unaccounted": 135
  },
  "steps_completed": 5,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `perform`**: OK word: SCRY typed at 20,180, then the line tool again, which ends the text

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "text", "button": "left"},
    {"op": "send_mouse", "x": 20, "y": 180, "button": "left"},
    {"op": "send_keys", "keys": ["S", "C", "R", "Y"], "modifiers": ["shift"]},
    {"op": "send_mouse", "target": "line", "button": "left"}
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
        "summary": "send_mouse: pointer at 314,98, program's own pointer not read; posted, unverified, 25 retraces to frame 513",
        "status": "ok",
        "stop_seq": 508,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 20,180, program's own pointer not read; posted, unverified, 25 retraces to frame 538",
        "status": "ok",
        "stop_seq": 533,
        "cause": "<volatile>"
      }
    },
    {
      "step": 2,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 50 retraces to frame 588",
        "status": "ok",
        "stop_seq": 583,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 302,51, program's own pointer not read; posted, unverified, 25 retraces to frame 613",
        "status": "ok",
        "x": 302,
        "y": 51,
        "units": "screen",
        "button": "left",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {"x": 302, "y": 51, "width": 320, "height": 200},
          "mouse": {"x": 2420, "y": 412, "max_x": 2552, "max_y": 1592},
          "buttons": [],
          "bios_mode": "0x13"
        },
        "driver_arrived": true,
        "polls": 25,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": 608,
        "frame": 613,
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [
          {
            "ref": "31B2:017C",
            "by": "address",
            "mode": "show",
            "length": 1,
            "fmt": "u8",
            "state": "evaluated",
            "value": 15,
            "bytes": "0f"
          }
        ],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "motion": true,
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "target": "line",
        "screen": "paint",
        "identified_at_stop": 2,
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 4,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 484,
    "stop_seq_last": 608,
    "surveyed": 4,
    "by_cause": {"the retrace the input's post ran to,": 4},
    "unaccounted": 121
  },
  "steps_completed": 4,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `read_memory`**: OK sun row: the row reads peach x 25, then yellow x 51, then peach x 52

<details><summary>call and reply</summary>

```json
{
  "ref": "A000:7DA0",
  "length": 128
}
```

```json
{
  "summary": "read_memory A000:7DA0: 128 bytes at A000:00007DA0: 343434343434343434343434343434343434343434343434340e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e... (64 more bytes in `hex`)",
  "status": "ok",
  "ref": "A000:7DA0",
  "seg_off": "A000:00007DA0",
  "length": 128,
  "hex": "343434343434343434343434343434343434343434343434340e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e34343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434343434",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `read_memory`**: OK boat row: the row reads navy x 30, then brown x 53, then navy x 29

<details><summary>call and reply</summary>

```json
{
  "ref": "A000:C09E",
  "length": 112
}
```

```json
{
  "summary": "read_memory A000:C09E: 112 bytes at A000:0000C09E: 01010101010101010101010101010101010101010101010101010101010106060606060606060606060606060606060606060606060606060606060606060606... (48 more bytes in `hex`)",
  "status": "ok",
  "ref": "A000:C09E",
  "seg_off": "A000:0000C09E",
  "length": 112,
  "hex": "01010101010101010101010101010101010101010101010101010101010106060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060606060101010101010101010101010101010101010101010101010101010101",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

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
  "mode": "render",
  "crop": [0, 0, 320, 200],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/dpaint/screen.png",
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

**22. `declaration_clear`**: OK unwatch: watch cleared

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
  "conf": "./demos/dpaint/dpaint.conf",
  "conf_digest": "5d4d6cc4851520a5",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "./tmp/demos/dpaint/dpaint-states",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
