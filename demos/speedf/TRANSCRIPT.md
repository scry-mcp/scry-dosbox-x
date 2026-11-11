**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "profile": "<host>",
  "shared": true,
  "captures_dir": "<host>",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "<volatile>",
  "conf_digest": "fa6947f920eb337d",
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
  "background": false,
  "presence": true,
  "window": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "symbols": {
    "held": "<volatile>",
    "base_from": "program",
    "checked": {
      "available": false,
      "why": "the table carries no symbol kinds (a link map lists none), so its code symbols cannot be told from the rest"
    }
  },
  "note": "this session runs the dynamic core, which checks breakpoints only between compiled blocks, so a code breakpoint inside one can be passed over and a run that never reaches it proves nothing. Start on the normal core: `start(flags=[\"-set\", \"cpu core=normal\"])`",
  "kept": "kept 1 (promote to review)",
  "profile": {
    "name": "<volatile>",
    "file": "<volatile>",
    "supplied": ["conf", "logfile", "program", "session_seconds", "symbols"]
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `run_for`**: OK boot: booted: DOS running the game, its map placed at segment 08EB, 294 symbols

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 5000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 5000 ms: ELAPSED, 351 polls, at 15FC:0000002D",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 351,
  "pc": "15FC:0000002D",
  "cpu_mode": "real",
  "frame": 351,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x005b005a",
    "EDX": "0x00000000",
    "ESI": "0x0000b8a6",
    "EDI": "0xe0068998",
    "EBP": "0x00000035",
    "ESP": "0x0000b158",
    "EIP": "0x0000002d",
    "CS": "0x15fc",
    "DS": "0x397e",
    "ES": "0x491e",
    "FS": "0x0008",
    "GS": "0x1b73",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 15FC:0000002D",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "15FC:0000002D",
    "bytes": "6626670FB61E",
    "text": "movzx ebx, byte ptr es:[esi]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "compose_frame",
    "delta": 45
  },
  "symbols_placed": {"placed": true, "path": "<volatile>", "load_segment": "08EB", "base": 36528, "loaded": 294},
  "emulated_before_s": 0.0,
  "emulated_after_s": 5.00101,
  "frame_before": 0,
  "frame_after": 351,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `run_for`**: OK attract: the title and the attract

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 10000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 10000 ms: ELAPSED, 628 polls, at 15FC:00000058",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 628,
  "pc": "15FC:00000058",
  "cpu_mode": "real",
  "frame": 1052,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000000",
    "ECX": "0x005b0071",
    "EDX": "0x00000000",
    "ESI": "0x000023cf",
    "EDI": "0xe001e33c",
    "EBP": "0x000000ac",
    "ESP": "0x0000b156",
    "EIP": "0x00000058",
    "CS": "0x15fc",
    "DS": "0x397e",
    "ES": "0x491e",
    "FS": "0x0008",
    "GS": "0x1b73",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 15FC:00000058",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "15FC:00000058",
    "bytes": "668BD0",
    "text": "mov edx, eax",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "compose_frame",
    "delta": 88
  },
  "emulated_before_s": 5.00101,
  "emulated_after_s": 15.01401,
  "frame_before": 351,
  "frame_after": 1052,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `read_memory`**: OK no credits: creditos holds 0

<details><summary>call and reply</summary>

```json
{
  "ref": "creditos",
  "length": 2
}
```

```json
{
  "summary": "read_memory creditos: 2 bytes at 26AB:00000006: 0000",
  "status": "ok",
  "ref": "creditos",
  "seg_off": "26AB:00000006",
  "length": 2,
  "hex": "0000",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `screen_view`**: OK screen: mode M_LIN15, 640x480 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/speedf/screen.png"
}
```

```json
{
  "summary": "screen_view M_LIN15: 640x480 at [0, 0] pixels; 640x480 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_LIN15",
  "kind": "pixel",
  "width": 640,
  "height": 480,
  "mode": "render",
  "crop": [0, 0, 640, 480],
  "screen_indexed": false,
  "image": {
    "path": "<volatile>",
    "bytes": 6718,
    "sha256": "838bf8ecfddf977cb21dc4d7695709a5d967d8d78c89d45f339af5ff149b9d1d",
    "width": 640,
    "height": 480,
    "scale": 1,
    "indexed": false,
    "inline": true
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

Also attached: image/png.

</details>

**6. `close`**: OK close: closed: DOSBox-X quit on its own

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
  "conf": "<volatile>",
  "conf_digest": "fa6947f920eb337d",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "<volatile>",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": ["start/dos"],
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
