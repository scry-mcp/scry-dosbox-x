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
  "window": {
    "display": 0,
    "bounds": {"x": 40, "y": 30, "width": 640, "height": 432},
    "onscreen": true,
    "front": true,
    "fullscreen": false
  },
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "kept": "kept 1 (promote to review)",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `run_for`**: OK loaded: 400 retraces: Deluxe Paint is up, its data segment at 0x31b2

<details><summary>call and reply</summary>

```json
{
  "frames": 400,
  "seconds": 60
}
```

```json
{
  "summary": "run_for 400 frames: ELAPSED, 400 polls, at 0E85:00000B12",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 400,
  "pc": "0E85:00000B12",
  "cpu_mode": "real",
  "frame": 400,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x0000018e",
    "ECX": "0x005b0000",
    "EDX": "0x0000a5ea",
    "ESI": "0x00000008",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a010",
    "ESP": "0x0000a010",
    "EIP": "0x00000b12",
    "CS": "0x0e85",
    "DS": "0x31b2",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b2"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 0E85:00000B12",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "0E85:00000B12",
    "bytes": "A31205",
    "text": "mov word ptr [0x512], ax",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "emulated_before_s": 0.0007,
  "emulated_after_s": 5.6986656,
  "frame_before": 0,
  "frame_after": 400,
  "cycles": 56500352,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_map_write`**: OK map: 1 screen and 13 controls loaded

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

**4. `screen_map_find`**: OK find: the painting screen, 13 controls named

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

**5. `send_mouse`**: OK blue: blue picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "blue",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 300,179, program's own pointer not read; posted, unverified, 21 retraces to frame 421",
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
  "pc": "100B:000002D1",
  "cpu_mode": "real",
  "stop_seq": 23,
  "frame": 421,
  "instruction": {
    "address": "100B:000002D1",
    "bytes": "50",
    "text": "push ax",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "regs": {
    "EAX": "0x0000a030",
    "EBX": "0x00001094",
    "ECX": "0x005b0000",
    "EDX": "0x000000fe",
    "ESI": "0x00000008",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a03e",
    "ESP": "0x0000a02a",
    "EIP": "0x000002d1",
    "CS": "0x100b",
    "DS": "0x31b2",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b2"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at 100B:000002D1",
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

**6. `scan`**: OK scan: 65535 bytes of the data segment are candidates

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

**7. `scan`**: OK is blue: 71 bytes hold 0x09 now

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

**8. `send_mouse`**: OK orange: orange picked off the palette

<details><summary>call and reply</summary>

```json
{
  "target": "orange",
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: pointer at 317,175, program's own pointer not read; posted, unverified, 25 retraces to frame 446",
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
  "pc": "F000:0000CFC5",
  "cpu_mode": "real",
  "stop_seq": 48,
  "frame": 446,
  "instruction": {
    "address": "F000:0000CFC5",
    "bytes": "CF",
    "text": "iret",
    "flow": "return",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {"available": false, "why": "no symbol table is loaded"},
    "delta": {"available": false, "why": "no symbol table is loaded"}
  },
  "regs": {
    "EAX": "0x0000011c",
    "EBX": "0x00001094",
    "ECX": "0x005b0000",
    "EDX": "0x000000fe",
    "ESI": "0x0000ffff",
    "EDI": "0x0000a0ae",
    "EBP": "0x0000a00c",
    "ESP": "0x00009ff8",
    "EIP": "0x0000cfc5",
    "CS": "0xf000",
    "DS": "0x31b2",
    "ES": "0x0000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x31b2"
  },
  "watches": [],
  "cause": "the retrace the input's post ran to, at F000:0000CFC5",
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

**9. `scan`**: OK is orange: 7 bytes followed both clicks: 3 in the stack's frames above 9FF8, and 4 static ones from 31B2:017C

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

**10. `scan`**: OK unscan: scan closed

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

**11. `watch_add`**: OK watch: the colour byte shown at every stop

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

**12. `perform`**: OK sky: peach, the colour byte at 52, 1 drag

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
        "summary": "send_mouse: pointer at 306,77, program's own pointer not read; posted, unverified, 25 retraces to frame 471",
        "status": "ok",
        "stop_seq": 73,
        "cause": "the retrace the input's post ran to, at 13F8:000002D7"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 317,169, program's own pointer not read; posted, unverified, 25 retraces to frame 496",
        "status": "ok",
        "stop_seq": 98,
        "cause": "the retrace the input's post ran to, at 0957:0000002C"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,112, program's own pointer not read; posted, unverified, 30 retraces to frame 526",
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
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 128,
        "frame": 526,
        "instruction": {
          "address": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x0000011c",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf5",
          "ESI": "0x0000ffff",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a00c",
          "ESP": "0x00009ff8",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
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

**13. `perform`**: OK sun: yellow, the colour byte at 14, 1 drag

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
        "summary": "send_mouse: pointer at 317,77, program's own pointer not read; posted, unverified, 25 retraces to frame 551",
        "status": "ok",
        "stop_seq": 153,
        "cause": "the retrace the input's post ran to, at 0957:00000029"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,189, program's own pointer not read; posted, unverified, 25 retraces to frame 576",
        "status": "ok",
        "stop_seq": 178,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 238,112, program's own pointer not read; posted, unverified, 30 retraces to frame 606",
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
        "pc": "100B:0000036A",
        "cpu_mode": "real",
        "stop_seq": 208,
        "frame": 606,
        "instruction": {
          "address": "100B:0000036A",
          "bytes": "740F",
          "text": "je 0x37b",
          "flow": "branch",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x00000070",
          "EBX": "0x0000018e",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf5",
          "ESI": "0x00000008",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a03e",
          "ESP": "0x0000a02a",
          "EIP": "0x0000036a",
          "CS": "0x100b",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at 100B:0000036A",
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

**14. `perform`**: OK sea: navy, the colour byte at 1, 1 drag

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
        "summary": "send_mouse: pointer at 306,77, program's own pointer not read; posted, unverified, 25 retraces to frame 631",
        "status": "ok",
        "stop_seq": 233,
        "cause": "the retrace the input's post ran to, at 13F8:000002CC"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,163, program's own pointer not read; posted, unverified, 25 retraces to frame 656",
        "status": "ok",
        "stop_seq": 258,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 294,198, program's own pointer not read; posted, unverified, 30 retraces to frame 686",
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
        "pc": "0957:00000041",
        "cpu_mode": "real",
        "stop_seq": 288,
        "frame": 686,
        "instruction": {
          "address": "0957:00000041",
          "bytes": "8B4402",
          "text": "mov ax, word ptr [si + 2]",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x00000128",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf5",
          "ESI": "0x00000190",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a014",
          "ESP": "0x0000a012",
          "EIP": "0x00000041",
          "CS": "0x0957",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at 0957:00000041",
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

**15. `perform`**: OK hull: brown, the colour byte at 6, 1 drag

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
        "summary": "send_mouse: pointer at 300,173, program's own pointer not read; posted, unverified, 25 retraces to frame 711",
        "status": "ok",
        "stop_seq": 313,
        "cause": "the retrace the input's post ran to, at 100B:0000032D"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 112,158, program's own pointer not read; posted, unverified, 30 retraces to frame 741",
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
        "pc": "F000:0000CFC5",
        "cpu_mode": "real",
        "stop_seq": 343,
        "frame": 741,
        "instruction": {
          "address": "F000:0000CFC5",
          "bytes": "CF",
          "text": "iret",
          "flow": "return",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x0000011c",
          "EBX": "0x00000000",
          "ECX": "0x005b0000",
          "EDX": "0x00000cf5",
          "ESI": "0x0000ffff",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a00c",
          "ESP": "0x00009ff8",
          "EIP": "0x0000cfc5",
          "CS": "0xf000",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at F000:0000CFC5",
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

**16. `perform`**: OK sail: white, the colour byte at 15, 3 drags

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
        "summary": "send_mouse: pointer at 302,51, program's own pointer not read; posted, unverified, 25 retraces to frame 766",
        "status": "ok",
        "stop_seq": 368,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 300,191, program's own pointer not read; posted, unverified, 25 retraces to frame 791",
        "status": "ok",
        "stop_seq": 393,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,118, program's own pointer not read; posted, unverified, 30 retraces to frame 821",
        "status": "ok",
        "stop_seq": 423,
        "cause": "the retrace the input's post ran to, at 0E85:000009A8"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 108,146, program's own pointer not read; posted, unverified, 30 retraces to frame 851",
        "status": "ok",
        "stop_seq": 453,
        "cause": "the retrace the input's post ran to, at F000:0000CFC5"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 86,146, program's own pointer not read; posted, unverified, 30 retraces to frame 881",
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
        "pc": "0E85:00000A71",
        "cpu_mode": "real",
        "stop_seq": 483,
        "frame": 881,
        "instruction": {
          "address": "0E85:00000A71",
          "bytes": "B8426E",
          "text": "mov ax, 0x6e42",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x00006e52",
          "EBX": "0x000003e4",
          "ECX": "0x005b0000",
          "EDX": "0x0000a5ea",
          "ESI": "0x00000008",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a006",
          "ESP": "0x0000a004",
          "EIP": "0x00000a71",
          "CS": "0x0e85",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at 0E85:00000A71",
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

**17. `perform`**: OK word: SCRY typed at 20,180, then the line tool again, which ends the text

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
        "summary": "send_mouse: pointer at 314,98, program's own pointer not read; posted, unverified, 25 retraces to frame 906",
        "status": "ok",
        "stop_seq": 508,
        "cause": "the retrace the input's post ran to, at 100B:00000239"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 20,180, program's own pointer not read; posted, unverified, 25 retraces to frame 931",
        "status": "ok",
        "stop_seq": 533,
        "cause": "the retrace the input's post ran to, at 13F8:00000212"
      }
    },
    {
      "step": 2,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 50 retraces to frame 981",
        "status": "ok",
        "stop_seq": 583,
        "cause": "the retrace the input's post ran to, at 0E85:00000B1C"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 302,51, program's own pointer not read; posted, unverified, 25 retraces to frame 1006",
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
        "pc": "0957:00000058",
        "cpu_mode": "real",
        "stop_seq": 608,
        "frame": 1006,
        "instruction": {
          "address": "0957:00000058",
          "bytes": "5E",
          "text": "pop si",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": {"available": false, "why": "no symbol table is loaded"},
          "delta": {"available": false, "why": "no symbol table is loaded"}
        },
        "regs": {
          "EAX": "0x00000001",
          "EBX": "0x0000105c",
          "ECX": "0x005b0000",
          "EDX": "0x00000bc9",
          "ESI": "0x0000105e",
          "EDI": "0x0000a0ae",
          "EBP": "0x0000a014",
          "ESP": "0x0000a012",
          "EIP": "0x00000058",
          "CS": "0x0957",
          "DS": "0x31b2",
          "ES": "0x0000",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x31b2"
        },
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
        "cause": "the retrace the input's post ran to, at 0957:00000058",
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

**18. `read_memory`**: OK sun row: the row reads peach x 25, then yellow x 51, then peach x 52

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

**19. `read_memory`**: OK boat row: the row reads navy x 30, then brown x 53, then navy x 29

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

**20. `screen_view`**: OK screen: mode M_VGA, 320x200 by palette index

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
    "bytes": 7911,
    "sha256": "8440167220f277f21c93eac61323f6ab5ae17ea5583c06f1fa4620bd356f959a",
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

**21. `declaration_clear`**: OK unwatch: watch cleared

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

**22. `close`**: OK close: closed: quit

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
  "draft": ["start/dp"],
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
