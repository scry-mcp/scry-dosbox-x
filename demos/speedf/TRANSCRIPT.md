Every call of the run with its reply, in order: 10 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "profile": "<host>",
  "flags": ["-set", "cpu core=normal", "-set", "cpu cycles=fixed 300000"],
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
  "conf_digest": "<volatile>",
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
  "background": true,
  "presence": true,
  "window": "<volatile>",
  "logfile": "<volatile>",
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

**2. `breakpoint_interrupt`**: OK loaded: a stop on BPINT 10 AH=4F

<details><summary>call and reply</summary>

```json
{
  "number": "0x10",
  "ah": "0x4F"
}
```

```json
{
  "summary": "breakpoint_interrupt BPINT 10 AH=4F: stored",
  "status": "ok",
  "ref": "BPINT 10 AH=4F",
  "stored": true,
  "armed": true,
  "entry": "BPINT 10 AH=4F",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `resume`**: OK boot: stopped inside the game: its map placed at segment 08EB, 294 symbols

<details><summary>call and reply</summary>

```json
{
  "seconds": 120
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08EE:00000022",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "08EE:00000022",
  "cpu_mode": "real",
  "frame": 0,
  "regs": {
    "EAX": "0x00004f01",
    "EBX": "0x00000000",
    "ECX": "0x005b0110",
    "EDX": "0x000008db",
    "ESI": "0x00000000",
    "EDI": "0x0000a000",
    "EBP": "0x0000b1aa",
    "ESP": "0x0000b1a2",
    "EIP": "0x00000022",
    "CS": "0x08ee",
    "DS": "0x1b73",
    "ES": "0x1b73",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "most likely the held `BPINT 10 AH=4F`: the guest is at `int 10`, at 08EE:00000022",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08EE:00000022",
    "bytes": "CD10",
    "text": "int 0x10",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "hw_init_video",
    "delta": 14
  },
  "symbols_placed": {"placed": true, "path": "<volatile>", "load_segment": "08EB", "base": "0x00008eb0", "loaded": 294},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**4. `declaration_clear`**: OK unloaded: the boot's stop cleared

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
  "disarmed": ["BPINT 10 AH=4F"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `run_to`**: OK title: stopped at titulo_dibuja_cred

<details><summary>call and reply</summary>

```json
{
  "ref": "titulo_dibuja_cred",
  "control": "draw_block",
  "seconds": 120
}
```

```json
{
  "summary": "run_to titulo_dibuja_cred: TARGET at 0951:00000819, control counted 35",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08EB:0E79",
  "ref": "titulo_dibuja_cred",
  "pc": "0951:00000819",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 35,
  "controls": [
    {"ref": "draw_block", "at": "08EB:46F4", "hits_in_run": 35, "removed": true}
  ],
  "frame": 78,
  "regs": {
    "EAX": "0x0000491e",
    "EBX": "0x00007fff",
    "ECX": "0x005b0000",
    "EDX": "0x00000089",
    "ESI": "0x0000c7cb",
    "EDI": "0x0000bfcb",
    "EBP": "0x0000b1aa",
    "ESP": "0x0000b19e",
    "EIP": "0x00000819",
    "CS": "0x0951",
    "DS": "0x1b73",
    "ES": "0x491e",
    "FS": "0x0008",
    "GS": "0x0000",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "run_to's target titulo_dibuja_cred at 0951:00000819",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "0951:00000819",
    "bytes": "52",
    "text": "push dx",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "titulo_dibuja_cred",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `read_memory`**: OK no credits: creditos holds 0

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

**7. `run_to`**: OK to the demo: stopped at startdemo

<details><summary>call and reply</summary>

```json
{
  "ref": "startdemo",
  "control": "new_irq_video",
  "seconds": 120
}
```

```json
{
  "summary": "run_to startdemo: TARGET at 0C8B:00000004, control counted 265",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08EB:3A04",
  "ref": "startdemo",
  "pc": "0C8B:00000004",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 265,
  "controls": [
    {"ref": "new_irq_video", "at": "08EB:372B", "hits_in_run": 265, "removed": true}
  ],
  "frame": 449,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000421",
    "ECX": "0x005b0000",
    "EDX": "0x00000000",
    "ESI": "0x000047cb",
    "EDI": "0x0000c7cb",
    "EBP": "0x0000b1aa",
    "ESP": "0x0000b19e",
    "EIP": "0x00000004",
    "CS": "0x0c8b",
    "DS": "0x1b73",
    "ES": "0x491e",
    "FS": "0x0008",
    "GS": "0x0000",
    "SS": "0x1b73"
  },
  "watches": [],
  "cause": "run_to's target startdemo at 0C8B:00000004",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 4,
  "instruction": {
    "address": "0C8B:00000004",
    "bytes": "06",
    "text": "push es",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "startdemo",
    "delta": 0
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `record`**: OK plays: recorded 380 frames in ./tmp/demos/speedf/plays.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 380,
  "dest": "./tmp/demos/speedf/plays.avi",
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
  "frames": 380,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `screen_view`**: OK screen: mode M_LIN15, 640x480 by palette index

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
    "bytes": "<volatile>",
    "sha256": "<volatile>",
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

**10. `close`**: OK close: closed: DOSBox-X quit on its own

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
  "conf_digest": "<volatile>",
  "watched": true,
  "bound_s": 900,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "<volatile>",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
