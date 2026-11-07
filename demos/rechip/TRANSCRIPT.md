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
  "conf_digest": "cf567b64d155d547",
  "watched": true,
  "bound_s": 14400,
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
  "note": "this session runs the dynamic core, which checks breakpoints only between compiled blocks, so a code breakpoint inside one can be passed over and a run that never reaches it proves nothing. Start on the normal core: `start(flags=[\"-set\", \"cpu core=normal\"])`",
  "kept": "kept 1 (promote to review)",
  "profile": {
    "name": "<volatile>",
    "file": "<volatile>",
    "supplied": ["conf", "logfile", "program", "session_seconds"]
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**2. `resume`**: OK run: DOS boots and the autoexec hands over to the program

<details><summary>call and reply</summary>

```json
{
  "seconds": 0
}
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

**3. `log_wait`**: OK sounding: the app is up and the song sounds

<details><summary>call and reply</summary>

```json
{
  "pattern": "PERF  \\. audio play=1",
  "channel": "guest",
  "seconds": 120
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "PERF  \\. audio play=1",
  "channel": "guest",
  "line": "<volatile>",
  "already": "<volatile>",
  "lines_total": "<volatile>",
  "lines_before": "<volatile>",
  "arrived_during": "<volatile>",
  "waited_s": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**4. `send_keys`**: OK pause: space reached the app

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"],
  "expect": "key down SPACE",
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
    "expected": "key down SPACE",
    "verdict": "TARGET",
    "line": "Bochs port E9h: [+   8.459] ACT   . key down SPACE mods=0",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**5. `log_wait`**: OK paused: the transport stopped

<details><summary>call and reply</summary>

```json
{
  "pattern": "ACT   \\. play=0",
  "channel": "guest",
  "seconds": 10
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "ACT   \\. play=0",
  "channel": "guest",
  "line": "<volatile>",
  "already": "<volatile>",
  "lines_total": "<volatile>",
  "lines_before": "<volatile>",
  "arrived_during": "<volatile>",
  "waited_s": "<volatile>",
  "lines_examined": "<volatile>",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**6. `stop`**: OK hold: the machine stopped

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
  "note": "the stop landed in F000:0000D224 (linear 0xFD224), inside a ROM handler the program called into rather than in the program: `run_for` or `resume` leaves it, and `step` moves one instruction inside the handler",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "the `stop` call at F000:0000D224",
  "e9": "<volatile>",
  "stop_seq": 2,
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `screen_view`**: OK screen: mode M_LIN8, 1024x768 by palette index

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/rechip/screen.png"
}
```

```json
{
  "summary": "screen_view M_LIN8: 1024x768 at [0, 0] pixels; 1024x768 PNG x1, inline",
  "status": "ok",
  "vga_mode": "M_LIN8",
  "kind": "pixel",
  "width": 1024,
  "height": 768,
  "mode": "render",
  "crop": [0, 0, 1024, 768],
  "screen_indexed": true,
  "entries": 256,
  "image": {
    "path": "./tmp/demos/rechip/screen.png",
    "bytes": 11114,
    "sha256": "d827133cb6b5122afd7dd524172629142acee19fcaecd16e20034d4144b3a38c",
    "width": 1024,
    "height": 768,
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

**8. `resume`**: OK go on: the program runs on

<details><summary>call and reply</summary>

```json
{
  "seconds": 0
}
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

**9. `send_keys`**: OK quit: File, Quit: the song is dirty, so the confirm opened

<details><summary>call and reply</summary>

```json
{
  "keys": ["x"],
  "modifiers": ["alt"],
  "expect": "ask opens",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["x"],
  "modifiers": ["alt"],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ask opens",
    "verdict": "TARGET",
    "line": "Bochs port E9h: [+   8.792] UI    . ask opens action=1 'Salir de ReChip!'",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**10. `send_keys`**: OK confirm: Quit without saving

<details><summary>call and reply</summary>

```json
{
  "keys": ["right", "enter"],
  "expect": "ask res=1",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): effect seen",
  "status": "ok",
  "keys": ["right", "enter"],
  "modifiers": [],
  "route": "guest",
  "posted": 2,
  "bytes": 6,
  "frames": 6,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ask res=1",
    "verdict": "TARGET",
    "line": "Bochs port E9h: [+   9.451] UI    . ask res=1 action=1",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**11. `close`**: OK close: closed: DOSBox-X quit on its own

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
  "conf_digest": "cf567b64d155d547",
  "watched": true,
  "bound_s": 14400,
  "elapsed_s": "<volatile>",
  "captures": "off",
  "state_dir": "<volatile>",
  "ended_by": "quit",
  "exit_code": 0,
  "omitted": ["stdout_tail", "errorlog_tail"],
  "how": "close(detail=True) keeps the emulator's last words on a clean quit too; once a close has answered its output is gone (the logfile stays at its path)",
  "draft": ["start/dev"],
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
