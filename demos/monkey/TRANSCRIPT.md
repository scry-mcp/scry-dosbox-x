**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "conf": "./tmp/demos/monkey/monkey.conf",
  "session_seconds": 1800,
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
  "conf_digest": "<volatile>",
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
  "debugger_commands": ["A20", "BPIF", "CAPTURE", "DOSTRACE", "LOADSTATE", "MEMDUMPLIN", "PIC", "PORTINFO", "PRESENCE", "RUNSTATE", "SAVESTATE", "STEPIN", "TAP", "VGAMEMDUMP"],
  "stub": "./src/scry_dosbox_x/guest/SCRY.COM",
  "input_port": "<volatile>",
  "background": true,
  "presence": true,
  "window": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**2. `screen_map_write`**: OK map: 24 screens, 60 controls

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/monkey/monkey-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 24 screens, 60 controls of monkey",
  "status": "ok",
  "path": "./demos/monkey/monkey-screen-map.json",
  "application": "monkey",
  "mode": "verified",
  "screens": 24,
  "controls": 60,
  "session": "<volatile>"
}
```

</details>

**3. `screen_wait`**: OK menu: the machine run until the map names {'name': 'language', 'layer': 'file'}

<details><summary>call and reply</summary>

```json
{
  "screen": "language",
  "every": 7,
  "seconds": 180
}
```

```json
{
  "summary": "screen_wait screen 'language': found after 637 retraces",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": "<volatile>",
  "sampled_every": 7,
  "screen": {"name": "language", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": "<volatile>",
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

**4. `screen_map_find`**: OK languages: the map says: language

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: language (file), 5 controls",
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

**5. `machine_map`**: OK placed: SCUMM's tick at 0985:011E

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "machine_map (real): 12 mcbs, 3 devs, 22 kern, 1 ems, 4 ems_pages, left out: bios_mem, callbacks, vga (see `omitted`)",
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
      "size_bytes": 1136,
      "psp_seg": "0812",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0811",
      "size_bytes": 2048,
      "psp_seg": "0812",
      "filename": "SCRY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0892",
      "size_bytes": 1136,
      "psp_seg": "08DB",
      "filename": "MONKEY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "08DA",
      "size_bytes": 1296,
      "psp_seg": "08DB",
      "filename": "MONKEY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "092C",
      "size_bytes": 1136,
      "psp_seg": "0975",
      "filename": "MONKEY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "0974",
      "size_bytes": 588800,
      "psp_seg": "0975",
      "filename": "MONKEY"
    },
    {
      "memory": "conventional",
      "mcb_seg": "9935",
      "size_bytes": 27792,
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
    {"header": "00F9:0000", "attr": "8013", "strat": "FFFF", "intr": "FFFF", "name": "CON"},
    {"header": "C404:0000", "attr": "C800", "strat": "0016", "intr": "001B", "name": "MSCD001"}
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
    {"seg": "c403", "size_bytes": 16, "what": "i33loc"},
    {"seg": "c404", "size_bytes": 32, "what": "MSCDEX device header"},
    {"seg": "c406", "size_bytes": 4704, "what": "MSCDEX temp buffer"}
  ],
  "xms": [],
  "ems": [
    {"handle": 0, "addr": "0x00110000", "size_bytes": 393216, "name": ""}
  ],
  "ems_pages": [
    {"handle": "--", "page": "0/", "start": "000e0000", "end": "000e3fff"},
    {"handle": "--", "page": "1/", "start": "000e4000", "end": "000e7fff"},
    {"handle": "--", "page": "2/", "start": "000e8000", "end": "000ebfff"},
    {"handle": "--", "page": "3/", "start": "000ec000", "end": "000effff"}
  ],
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
    "tr": {"selector": "0000", "base": "000E0985", "limit": "00000139*1"},
    "ldtr": {"selector": "0000", "base": "000E0985", "limit": "00000139*1"}
  },
  "counts": {"mcbs": 12, "devs": 3, "kern": 22, "xms": 0, "ems": 1, "ems_pages": 4},
  "sources": {
    "mcbs": ["DOS MCBS"],
    "devs": ["DOS DEVS"],
    "kern": ["DOS KERN"],
    "xms": ["DOS XMS"],
    "ems": ["DOS EMS"],
    "ems_pages": ["DOS EMS"],
    "emu_mem": ["EMU MEM"],
    "machine": ["EMU MACHINE"],
    "control": ["CPU"]
  },
  "coverage_note": "read from the debugger's own listings at this stop. `gdt` and `ldt` are absent: the cpu is in real mode, where the debugger reads the interrupt vector table as descriptors. `paging` is absent: paging is off",
  "truncated": false,
  "omitted": ["bios_mem", "callbacks", "vga"],
  "how": "sections=[...] names the sections to read; dest=<absolute path> writes every section read whole",
  "session": "<volatile>"
}
```

</details>

**6. `perform`**: OK english: a double click on English

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "english", "button": "left", "action": "double"}
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
        "x": 80,
        "y": 437,
        "units": "screen",
        "button": "left",
        "action": "double",
        "route": "guest",
        "pointer": {
          "screen": {"x": 80, "y": 437, "width": 640, "height": 480},
          "mouse": {"x": 313, "y": 1714, "max_x": 2488, "max_y": 1880},
          "buttons": [],
          "bios_mode": "0x12"
        },
        "driver_arrived": true,
        "polls": "<volatile>",
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": "<volatile>",
        "frame": "<volatile>",
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
        "target": "english",
        "screen": "language",
        "identified_at_stop": "<volatile>",
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

**7. `perform`**: OK intro: the room variable read 35664, 35664, 0, 0, 10 up to the first scene; Escapes at SCUMM's ticks skipped it to the title card, room 96

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "watch_add", "ref": "220B:73EA", "mode": "change", "fmt": "u16"},
    {"op": "resume", "seconds": 300},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "resume", "seconds": 300},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "resume", "seconds": 300},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "resume", "seconds": 300},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "resume", "seconds": 300},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "declaration_clear", "kind": "watch", "all": true},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "resume", "seconds": 180},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "send_keys", "keys": ["escape"]},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "resume", "seconds": 180},
    {"op": "read_memory", "ref": "220B:73EA", "length": 2},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true}
  ],
  "settle_seconds": 300,
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
      "op": "watch_add",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "read_memory",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "read_memory",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
      "op": "read_memory",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 7,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 8,
      "op": "read_memory",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 9,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 10,
      "op": "read_memory",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 11,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 12,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 13,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 14,
      "op": "send_keys",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 15,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 16,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 17,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 18,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 19,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 20,
      "op": "send_keys",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 21,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 22,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 23,
      "op": "resume",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 43,
      "op": "declaration_clear",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "declarations_cleared": 1,
        "disarmed": ["BP 0985:011E"],
        "session": "<volatile>"
      }
    }
  ],
  "steps_total": 44,
  "truncated": true,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 44,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**8. `perform`**: OK title: the title card, judged at SCUMM's tick

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "part one", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true}
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "declaration_clear",
      "reply": {
        "summary": "<volatile>",
        "status": "ok",
        "declarations_cleared": 1,
        "disarmed": ["BP 0985:011E"],
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

**9. `screen_map_write`**: OK pointer: the game's own pointer declared: each move is steered onto it

<details><summary>call and reply</summary>

```json
{
  "method": "pointer",
  "pointer": {"x": "2000:94EA", "y": "2000:94EC", "bytes": 2}
}
```

```json
{
  "summary": "screen_map_write pointer: the program's pointer at 2000:94EA and 2000:94EC, 2 bytes each",
  "status": "ok",
  "pointer": {"x": "2000:94EA", "y": "2000:94EC", "bytes": 2},
  "session": "<volatile>"
}
```

</details>

**10. `perform`**: OK dock: the map says: dock

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "dock", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
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

**11. `perform`**: OK hover poster: the map says: dock: walk to poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "dock: walk to poster",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**12. `perform`**: OK to the poster: the map says: by the poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster", "button": "left", "action": "click"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "by the poster", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**13. `perform`**: OK look at: the map says: by the poster: look at poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "look_at", "button": "left", "action": "click"},
    {"op": "send_mouse", "target": "poster"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "by the poster: look at poster",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
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

**14. `perform`**: OK read: the map says: poster: re-elect governor marley

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "poster", "button": "left", "action": "click"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "poster: re-elect governor marley",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**15. `perform`**: OK read on: the map says: poster: only one candidate

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "poster: only one candidate",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
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
        "screen": "poster: only one candidate",
        "layer": "file",
        "kind": "pixel",
        "size": [320, 200],
        "controls": [],
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

**16. `perform`**: OK done reading: the map says: by the poster: walk to poster

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "by the poster: walk to poster",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 1,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
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

**17. `perform`**: OK way back: the map says: dock: walk to cliffside

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "way_back", "button": "left", "action": "click"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "dock: walk to cliffside",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**18. `perform`**: OK climb: the map says: cliff

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "cliffside", "button": "left", "action": "click"},
    {"op": "send_mouse", "x": 250, "y": 20},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "cliff", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
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

**19. `perform`**: OK talk to: the map says: cliff: talk to lookout

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "talk_to", "button": "left", "action": "click"},
    {"op": "send_mouse", "target": "lookout"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "cliff: talk to lookout",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
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

**20. `perform`**: OK greet: the map says: greeting choices

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "lookout", "button": "left", "action": "click"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "greeting choices", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**21. `perform`**: OK hover novel: the map says: greeting: characters in a novel

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "characters_in_a_novel"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "greeting: characters in a novel",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**22. `perform`**: OK ask: the map says: name choices

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "characters_in_a_novel", "button": "left", "action": "click"},
    {"op": "send_mouse", "x": 160, "y": 60},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "name choices", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
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

**23. `perform`**: OK hover name: the map says: name: im guybrush threepwood

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "im_guybrush_threepwood"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "name: im guybrush threepwood",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**24. `perform`**: OK tell: the map says: name choices again

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "im_guybrush_threepwood", "button": "left", "action": "click"},
    {"op": "send_mouse", "x": 160, "y": 60},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "name choices again", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "send_mouse",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 2,
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 3,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 4,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 6,
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

**25. `perform`**: OK hover heck: the map says: name: whats wrong with my name

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "whats_wrong_with_my_name"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {
      "op": "screen_wait",
      "screen": "name: whats wrong with my name",
      "on_breakpoint": "0985:011E",
      "seconds": 180
    },
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**26. `state_write`**: OK save: the machine saved with the comeback under the pointer

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

**27. `perform`**: OK before: the map says: lookout: sell shoes

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "target": "whats_wrong_with_my_name", "button": "left", "action": "click"},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "lookout: sell shoes", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**28. `state_write`**: OK restore: the machine back to before the click

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "name": "comeback"
}
```

```json
{
  "summary": "state_write load: comeback, loaded",
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

**29. `screen_map_find`**: OK heck again?: the map says: name: whats wrong with my name

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: name: whats wrong with my name (file), 1 control",
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

**30. `find`**: OK needle: the lookout's line, once, at 82DD:0000000F

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
  "summary": "find 0000:0000: 1 hit of 4e6f7468696e672c20696620796f752077616e7420746f2073656c6c2073686f65732e in 655360 bytes",
  "status": "ok",
  "ref": "0000:0000",
  "seg_off": "0000:00000000",
  "length": 655360,
  "span": {"from": "0000:00000000", "length": 655360, "source": "ref+length"},
  "hits": ["82DD:0000000F"],
  "hits_total": 1,
  "truncated": false,
  "session": "<volatile>"
}
```

</details>

**31. `perform`**: OK script: 1371 bytes around the line are the disc's own script, hole by hole

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "read_memory", "ref": "82DD:000C", "length": 128},
    {"op": "read_memory", "ref": "82E5:000C", "length": 101},
    {"op": "read_memory", "ref": "82C5:000C", "length": 128},
    {"op": "read_memory", "ref": "82CD:000C", "length": 128},
    {"op": "read_memory", "ref": "82D5:000C", "length": 128},
    {"op": "read_memory", "ref": "82ED:000D", "length": 128},
    {"op": "read_memory", "ref": "82F5:000D", "length": 128},
    {"op": "read_memory", "ref": "82FD:000D", "length": 128},
    {"op": "read_memory", "ref": "8305:000D", "length": 128},
    {"op": "read_memory", "ref": "830D:000D", "length": 128},
    {"op": "read_memory", "ref": "8315:000D", "length": 90},
    {"op": "read_memory", "ref": "82EC:0001", "length": 28}
  ],
  "summaries": true
}
```

```json
{
  "summary": "perform: 12 of 12 steps",
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

**32. `perform`**: OK rewrite: 22 speeches, 1259 bytes of bytecode over 3 holes, each read back

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {
      "op": "write",
      "ref": "82DD:000C",
      "data_hex": "1c6e14020f4e6f7468696e672c20696620796f75277265206120536372792064656275676765722eff0349742073746f70732074696d652c207265616473206d696e647320616e6420706c617973207468652074756e65732eff034576656e206d79206d696e642e00ae02d80f41206465627567676572207468617420706c61"
    },
    {
      "op": "write",
      "ref": "82E5:000C",
      "data_hex": "7973206d757369633f20204973205448415420776861742049276d2068656172696e673f3f00ae0214020f546861742773207468652043442e202053637279206a75737420746f6c6420697420776865726520746f2073746172742e00ae02189efd"
    },
    {
      "op": "write",
      "ref": "82C5:000C",
      "data_hex": "d80f57686f20746175676874206120646562756767657220746f20646f20746861743f00ae0214020f41206d6f64656c2e20204c6976657320696e206120626f782c20726561647320796f7572206d656d6f72792c206e6576657220736c656570732e00ae02d80f4c696b65206f6e65206f662074686f736520626967204149"
    },
    {
      "op": "write",
      "ref": "82CD:000C",
      "data_hex": "20636f6d70616e6965733f00ae0214020f5468656d3f20204120646f75626c6f6f6e206120776f72642e202054776f20696620796f75207361792060706c65617365602e00ae02d80f416e6420536372793f00ae0214020f467265652e2020416e64206974206e657665722073617973206041732061206c61726765206c616e"
    },
    {
      "op": "write",
      "ref": "82D5:000C",
      "data_hex": "6775616765207069726174655e6000ae0214020f48656172642061626f757420746865206f72616e6765207479636f6f6e3f00ae02d80f546865206f6e652077686f2063616c6c73206576657279206275672066616b65206e6577733f00ae02181e01"
    },
    {
      "op": "write",
      "ref": "82ED:000D",
      "data_hex": "14020f4e6f772068652077616e747320746f2072656e616d6520414920746f2053492eff0360537570657220496e74656c6c6967656e6365602e20205472656d656e646f75732e202054686520626573742e00ae02d80f446f65732053492072656c65617365206974732066696c65733f00ae0214020f536372792072656c65"
    },
    {
      "op": "write",
      "ref": "82F5:000D",
      "data_hex": "617365732065766572792066696c652069742066696e64732e202045766572792e20204c6173742e20204f6e652eff03556e6c696b652074686f7365204570737465696e2066696c65732e20204168656d2100ae02d80f416e642068697320726f636b657420667269656e643f00ae0214020f546865206f6e652077686f7365"
    },
    {
      "op": "write",
      "ref": "82FD:000D",
      "data_hex": "20686561727420666c6577206f7574207468726f756768206869732061726d3fff0354776963652eff03536372792073746570706564207468726f756768206974206672616d65206279206672616d652e20205374696c6c206e6f74206120776176652e00ae02d80f53686f756c642053637279206465627567207468656d20"
    },
    {
      "op": "write",
      "ref": "8305:000D",
      "data_hex": "626f74683f00ae0214020f4e6f7420656e6f7567682052414d206f6e20746869732077686f6c652069736c616e642c20626f792e00ae02d80f476f7420616e79206a6f6b6573206c6566743f00ae0214020f506c656e74792e2020427574206d79206c6174652073686f7720676f742063616e63656c6c65642eff03536f2053"
    },
    {
      "op": "write",
      "ref": "830D:000D",
      "data_hex": "6372792072756e73206974206e6f772e202048756d6f722066697273742c2063726173686573207365636f6e642e00ae02d80f49276c6c206a757374206265206f666620746f207365656b206d7920666f7274756e65206e6f772e00ae0214020f54616b652053637279207769746820796f752eff03416e6420636c65617220"
    },
    {
      "op": "write",
      "ref": "8315:000D",
      "data_hex": "7468617420627265616b706f696e74206f6e20796f757220776179206f75742e00ae02183efd"
    }
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
      "op": "write",
      "reply": {"summary": "write 82DD:000C: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 1,
      "op": "write",
      "reply": {"summary": "write 82E5:000C: 98 bytes, verified True", "status": "ok"}
    },
    {
      "step": 2,
      "op": "write",
      "reply": {"summary": "write 82C5:000C: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 3,
      "op": "write",
      "reply": {"summary": "write 82CD:000C: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 4,
      "op": "write",
      "reply": {"summary": "write 82D5:000C: 99 bytes, verified True", "status": "ok"}
    },
    {
      "step": 5,
      "op": "write",
      "reply": {"summary": "write 82ED:000D: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 6,
      "op": "write",
      "reply": {"summary": "write 82F5:000D: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 7,
      "op": "write",
      "reply": {"summary": "write 82FD:000D: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 8,
      "op": "write",
      "reply": {"summary": "write 8305:000D: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 9,
      "op": "write",
      "reply": {"summary": "write 830D:000D: 128 bytes, verified True", "status": "ok"}
    },
    {
      "step": 10,
      "op": "write",
      "reply": {
        "summary": "write 8315:000D: 38 bytes, verified True",
        "status": "ok",
        "ref": "8315:000D",
        "seg_off": "8315:0000000D",
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

**33. `breakpoint_interrupt`**: OK arm: a stop on every request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "number": "0x2F",
  "ah": "0x15"
}
```

```json
{
  "summary": "breakpoint_interrupt BPINT 2F AH=15: stored",
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

**34. `perform`**: OK pick: the same comeback, picked again

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
          "screen": {"x": 55, "y": 148, "width": 320, "height": 200},
          "mouse": {"x": 110, "y": 148, "max_x": 639, "max_y": 199},
          "buttons": [],
          "bios_mode": "0x13",
          "program": {"x": 60, "y": 148, "corrections": 0}
        },
        "arrived": true,
        "polls": "<volatile>",
        "pc": "<volatile>",
        "cpu_mode": "real",
        "stop_seq": "<volatile>",
        "frame": "<volatile>",
        "instruction": "<volatile>",
        "regs": "<volatile>",
        "watches": [],
        "cause": "<volatile>",
        "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
        "verify": {
          "checked": false,
          "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
        },
        "target": "whats_wrong_with_my_name",
        "screen": "name: whats wrong with my name",
        "identified_at_stop": "<volatile>",
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

**35. `resume`**: OK first: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 193E:00006BCB",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "193E:00006BCB",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": {
    "EAX": "0x00001510",
    "EBX": "0x00001d8e",
    "ECX": "0x005b0003",
    "EDX": "0x000048fc",
    "ESI": "0x0000006e",
    "EDI": "0x0000006e",
    "EBP": "0x00008296",
    "ESP": "0x00008296",
    "EIP": "0x00006bcb",
    "CS": "0x193e",
    "DS": "0x220b",
    "ES": "0x220b",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x220b"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 2F AH=15`: the guest is at `int 2F`, at 193E:00006BCB",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": {
    "address": "193E:00006BCB",
    "bytes": "CD2F",
    "text": "int 0x2f",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "session": "<volatile>"
}
```

</details>

**36. `read_memory`**: OK request 1: STOP AUDIO (85h), let through

<details><summary>call and reply</summary>

```json
{
  "ref": "220B:1D8E",
  "length": 22
}
```

```json
{
  "summary": "read_memory 220B:1D8E: 22 bytes at 220B:00001D8E: 0d008500010000000000000000001a00030001000000",
  "status": "ok",
  "ref": "220B:1D8E",
  "seg_off": "220B:00001D8E",
  "length": 22,
  "hex": "0d008500010000000000000000001a00030001000000",
  "session": "<volatile>"
}
```

</details>

**37. `perform`**: OK pass 1: the request answered

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
        "before": "193E:00006BCB",
        "after": "193E:00006BCD",
        "instructions_completed": 1,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "frame": "<volatile>",
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

**38. `resume`**: OK second: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 193E:00006BCB",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "193E:00006BCB",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": {
    "EAX": "0x00001510",
    "EBX": "0x00001d8e",
    "ECX": "0x005b0003",
    "EDX": "0x000048fc",
    "ESI": "0x0000006e",
    "EDI": "0x0000006e",
    "EBP": "0x00008296",
    "ESP": "0x00008296",
    "EIP": "0x00006bcb",
    "CS": "0x193e",
    "DS": "0x220b",
    "ES": "0x220b",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x220b"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 2F AH=15`: the guest is at `int 2F`, at 193E:00006BCB",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": {
    "address": "193E:00006BCB",
    "bytes": "CD2F",
    "text": "int 0x2f",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "session": "<volatile>"
}
```

</details>

**39. `read_memory`**: OK request 2: STOP AUDIO (85h), let through

<details><summary>call and reply</summary>

```json
{
  "ref": "220B:1D8E",
  "length": 22
}
```

```json
{
  "summary": "read_memory 220B:1D8E: 22 bytes at 220B:00001D8E: 0d008500010000000000000000001a00030001000000",
  "status": "ok",
  "ref": "220B:1D8E",
  "seg_off": "220B:00001D8E",
  "length": 22,
  "hex": "0d008500010000000000000000001a00030001000000",
  "session": "<volatile>"
}
```

</details>

**40. `perform`**: OK pass 2: the request answered

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
        "before": "193E:00006BCB",
        "after": "193E:00006BCD",
        "instructions_completed": 1,
        "pc": "<volatile>",
        "cpu_mode": "real",
        "frame": "<volatile>",
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

**41. `resume`**: OK third: stopped on INT 2Fh AX=1510h, a request to the CD driver

<details><summary>call and reply</summary>

```json
{
  "seconds": 30
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 193E:00006BCB",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "193E:00006BCB",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": {
    "EAX": "0x00001510",
    "EBX": "0x00001d78",
    "ECX": "0x005b0003",
    "EDX": "0x00000000",
    "ESI": "0x0000000e",
    "EDI": "0x000048fc",
    "EBP": "0x0000828c",
    "ESP": "0x0000828c",
    "EIP": "0x00006bcb",
    "CS": "0x193e",
    "DS": "0x220b",
    "ES": "0x220b",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x220b"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 2F AH=15`: the guest is at `int 2F`, at 193E:00006BCB",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": {
    "address": "193E:00006BCB",
    "bytes": "CD2F",
    "text": "int 0x2f",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "session": "<volatile>"
}
```

</details>

**42. `read_memory`**: OK request 3: PLAY AUDIO (84h) from 36:45:00, the theme's first sector, for 12200 sectors

<details><summary>call and reply</summary>

```json
{
  "ref": "220B:1D78",
  "length": 22
}
```

```json
{
  "summary": "read_memory 220B:1D78: 22 bytes at 220B:00001D78: 1600840003000000000000000001002d2400a82f0000",
  "status": "ok",
  "ref": "220B:1D78",
  "seg_off": "220B:00001D78",
  "length": 22,
  "hex": "1600840003000000000000000001002d2400a82f0000",
  "session": "<volatile>"
}
```

</details>

**43. `write`**: OK to the logo: the drive will start at 37:05:67, the logo's bar

<details><summary>call and reply</summary>

```json
{
  "ref": "220B:1D86",
  "data_hex": "4305250089290000"
}
```

```json
{
  "summary": "write 220B:1D86: 8 bytes, verified True",
  "status": "ok",
  "ref": "220B:1D86",
  "seg_off": "220B:00001D86",
  "bytes_written": 8,
  "readback": "4305250089290000",
  "verified": true,
  "session": "<volatile>"
}
```

</details>

**44. `declaration_clear`**: OK disarm: the stop on the CD driver cleared

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
  "disarmed": ["BPINT 2F AH=15"],
  "session": "<volatile>"
}
```

</details>

**45. `audio_record`**: OK theme: 8.0 s of the mixer at 44100 Hz

<details><summary>call and reply</summary>

```json
{
  "frames": 560,
  "dest": "./tmp/demos/monkey/theme.wav"
}
```

```json
{
  "summary": "audio_record wav 560 frames: ELAPSED, 354564 samples at 44100 Hz at ./tmp/demos/monkey/theme.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": "<volatile>",
  "frame_after": "<volatile>",
  "cycles": "<volatile>",
  "kind": "wav",
  "frames": 560,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/monkey/theme.wav",
  "bytes": 1418300,
  "channels": 2,
  "sample_rate_hz": 44100,
  "samples": 354564,
  "emulated_s": "<volatile>",
  "sample_min": -17908,
  "sample_max": 18280,
  "session": "<volatile>"
}
```

</details>

**46. `audio_compare`**: OK the disc: the reader's own track 18 from the logo's bar, compared sample against sample with no realigning, SNR 48.62 dB

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
  "summary": "audio_compare diff: audible, SNR 48.62 dB, envelope 1.0",
  "status": "ok",
  "exact": false,
  "snr_db": 48.62,
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

**47. `screen_map_find`**: OK music?: the map says: guybrush: a debugger that plays music

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: guybrush: a debugger that plays music (file), 0 controls",
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

**48. `perform`**: OK talk 1: the map says: lookout: the orange tycoon

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "screen_wait", "screen": "lookout: the orange tycoon", "every": 7, "seconds": 180},
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
      "op": "screen_wait",
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
        "screen": "lookout: the orange tycoon",
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

**49. `perform`**: OK talk 2: the map says: lookout: those files

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "screen_wait", "screen": "lookout: those files", "every": 7, "seconds": 180},
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
      "op": "screen_wait",
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
        "screen": "lookout: those files",
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

**50. `perform`**: OK talk 3: the map says: lookout: still not a wave

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "screen_wait", "screen": "lookout: still not a wave", "every": 7, "seconds": 180},
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
      "op": "screen_wait",
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
        "screen": "lookout: still not a wave",
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

**51. `perform`**: OK talk 4: the map says: lookout: humor first

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "screen_wait", "screen": "lookout: humor first", "every": 7, "seconds": 180},
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
      "op": "screen_wait",
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
        "screen": "lookout: humor first",
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

**52. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/monkey/screen.png",
  "scale": 2
}
```

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 640x400 PNG x2, inline",
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
    "bytes": "<volatile>",
    "sha256": "<volatile>",
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

**53. `record`**: OK loop: recording 240 frames in ./tmp/demos/monkey/loop.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 240,
  "dest": "./tmp/demos/monkey/loop.avi"
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
  "frames": 240,
  "began": true,
  "ended": true,
  "path": "./tmp/demos/monkey/loop.avi",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": "<volatile>"
}
```

</details>

**54. `perform`**: OK goodbye: the map says: cliff

<details><summary>call and reply</summary>

```json
{
  "steps": [
    {"op": "send_mouse", "x": 250, "y": 20},
    {"op": "breakpoint_at", "ref": "0985:011E"},
    {"op": "screen_wait", "screen": "cliff", "on_breakpoint": "0985:011E", "seconds": 180},
    {"op": "declaration_clear", "kind": "breakpoint", "all": true},
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
      "op": "breakpoint_at",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "<volatile>", "status": "ok"}
    },
    {
      "step": 4,
      "op": "run_for",
      "reply": {"summary": "<volatile>", "status": "ok", "stop_seq": "<volatile>", "cause": "<volatile>"}
    },
    {
      "step": 5,
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
  "steps_total": 6,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": "<volatile>",
  "steps_completed": 6,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": "<volatile>"
}
```

</details>

**55. `close`**: OK close: closed: quit

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
  "conf": "./tmp/demos/monkey/monkey.conf",
  "conf_digest": "<volatile>",
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
  "draft": "<volatile>",
  "session": "<volatile>"
}
```

</details>
