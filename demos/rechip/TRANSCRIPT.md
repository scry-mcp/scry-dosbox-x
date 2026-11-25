Every call of the run with its reply, in order: 23 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": false,
  "display": "<host>",
  "profile": "<host>",
  "symbols": "<host>",
  "flags": ["-set", "cpu core=normal"],
  "capture_video": true,
  "captures_dir": "<host>",
  "binary": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "cwd": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "pid": "<volatile>",
  "conf": "<volatile>",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "<volatile>",
  "watched": true,
  "bound_s": 14400,
  "elapsed_s": "<volatile>",
  "captures": "./tmp/demos/rechip/video",
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
  "overlay": {"layers": ["edge", "pointer", "record"]},
  "window": "<volatile>",
  "logfile": "<volatile>",
  "declarations": {
    "rearm": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []}
  },
  "symbols": {
    "held": "<volatile>",
    "base_from": "program",
    "checked": {"against": "<volatile>", "agree": 3214}
  },
  "kept": "1 saved for `promote`",
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
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "frame_before": 719,
  "frame_after": 726,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "key down SPACE",
    "verdict": "TARGET",
    "line": "<volatile>",
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

**6. `send_keys`**: OK rewind: home put the song back at its first row

<details><summary>call and reply</summary>

```json
{
  "keys": ["home"],
  "expect": "ACT   \\. rewind",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["home"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "frame_before": 730,
  "frame_after": 748,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ACT   \\. rewind",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**7. `wait`**: OK settle: the paused song waits under the playhead

<details><summary>call and reply</summary>

```json
{
  "seconds": 2
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "waited_s": "<volatile>",
  "note": "the machine is still running after 2 s; a deliberate wait that expires is this answer, not a failure",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**8. `stop`**: OK hold: the machine stopped in the program, its symbols placed

<details><summary>call and reply</summary>

```json
{
  "until": "protected"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "interrupted": true,
  "runs_to_protected": "<volatile>",
  "via": "break",
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": 2,
  "instruction": "<volatile>",
  "symbols_placed": {"placed": true, "path": "<volatile>", "base": "0x00400000", "loaded": 7932},
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `read_memory`**: OK ticks: the program's own counter, which sets the pulse

<details><summary>call and reply</summary>

```json
{
  "ref": "_g_ticks",
  "length": 4
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "ref": "_g_ticks",
  "seg_off": "<volatile>",
  "length": 4,
  "hex": "<volatile>",
  "names": [
    {"field": "given.ref", "number": "0x00657b9c", "kind": "symbol", "name": "_g_ticks"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `run_for`**: OK into lit: to the middle of the next lit half of the pulse

<details><summary>call and reply</summary>

```json
{
  "milliseconds": "<host>",
  "seconds": 10
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
  "watches": [],
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": "<volatile>",
  "frame_before": "<volatile>",
  "frame_after": "<volatile>",
  "cycles": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `screen_map_write`**: OK map: 2 looks of the warning button

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "./demos/rechip/rechip-screen-map.json"
}
```

```json
{
  "summary": "screen_map_write load: 2 screens, 0 controls of rechip",
  "status": "ok",
  "path": "./demos/rechip/rechip-screen-map.json",
  "application": "rechip",
  "mode": "verified",
  "screens": 2,
  "controls": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `screen_map_find`**: OK lit: the warning button shows warning_lit

<details><summary>call and reply</summary>

```json
{}
```

```json
{
  "summary": "screen_map_find: warning_lit (file), 0 controls",
  "status": "ok",
  "matched": true,
  "screen": "warning_lit",
  "layer": "file",
  "kind": "pixel",
  "size": [1024, 768],
  "controls": [],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `screen_wait`**: OK dark: the first frame it went dark

<details><summary>call and reply</summary>

```json
{
  "screen": "warning_dark",
  "seconds": 10
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "predicate": "screen",
  "already": false,
  "waited_s": "<volatile>",
  "polls": "<volatile>",
  "sampled_every": 0,
  "screen": {"name": "warning_dark", "layer": "file"},
  "pc": "<volatile>",
  "cpu_mode": "<volatile>",
  "frame": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": "<volatile>",
  "stop_seq": "<volatile>",
  "instruction": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `screen_view`**: OK screen: mode M_LIN8, 1024x768 by palette index

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
    "bytes": "<volatile>",
    "sha256": "<volatile>",
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

**15. `resume`**: OK go on: the program runs on

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

**16. `log_wait`**: OK report: the program reported after the rewind

<details><summary>call and reply</summary>

```json
{
  "pattern": "PERF  \\. fps=",
  "channel": "guest",
  "seconds": 10,
  "since_mark": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "PERF  \\. fps=",
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

**17. `log_wait`**: OK settled: a second report: the playhead is at the first row

<details><summary>call and reply</summary>

```json
{
  "pattern": "PERF  \\. fps=",
  "channel": "guest",
  "seconds": 10,
  "since_mark": "<host>"
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "verdict": "TARGET",
  "pattern": "PERF  \\. fps=",
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

**18. `send_keys`**: OK play: space set the song playing from its first row

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"],
  "expect": "ACT   \\. play=1",
  "seconds": 10
}
```

```json
{
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "frame_before": 1135,
  "frame_after": 1141,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ACT   \\. play=1",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**19. `wait`**: OK song: the song plays with its pattern scrolling

<details><summary>call and reply</summary>

```json
{
  "seconds": 2
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "waited_s": "<volatile>",
  "note": "the machine is still running after 2 s; a deliberate wait that expires is this answer, not a failure",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**20. `send_keys`**: OK quit: File, Quit: the song is dirty, so the confirm opened

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
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["x"],
  "modifiers": ["alt"],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "frame_before": 1281,
  "frame_after": 1300,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ask opens",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**21. `wait`**: OK dialog: the confirm dialog stays open

<details><summary>call and reply</summary>

```json
{
  "seconds": 2
}
```

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "waited_s": "<volatile>",
  "note": "the machine is still running after 2 s; a deliberate wait that expires is this answer, not a failure",
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**22. `send_keys`**: OK confirm: Quit without saving

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
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["right", "enter"],
  "modifiers": [],
  "route": "guest",
  "posted": 2,
  "bytes": 6,
  "frames": 6,
  "frame_before": 1442,
  "frame_after": 1470,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "ask res=1",
    "verdict": "TARGET",
    "line": "<volatile>",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "session": {"alive": true, "running": true, "altered": false}
}
```

</details>

**23. `close`**: OK close: closed: DOSBox-X quit on its own

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
  "conf": "<volatile>",
  "bundle": "~/.local/state/scry/apps/Scry DOSBox-X.app",
  "conf_digest": "<volatile>",
  "watched": true,
  "bound_s": 14400,
  "elapsed_s": "<volatile>",
  "captures": "./tmp/demos/rechip/video",
  "state_dir": "<volatile>",
  "ended_by": "quit",
  "exit_code": {"available": false, "why": "the emulator's exit code could not be read"},
  "stdout_tail": {
    "available": false,
    "why": "the emulator wrote to a console of its own, which this server does not read (Windows, a build whose debugger draws a screen)"
  },
  "errorlog_tail": "6.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3847218124 ms=20927.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3848032057 ms=20929.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3848439023 ms=20930.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3849252956 ms=20932.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3849659923 ms=20933.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3850473856 ms=20935.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3850880825 ms=20936.000002457 frames=1468\nDEBUG: RUNSTATE running cycles=3851694800 ms=20938.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3852101767 ms=20939.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3852915700 ms=20941.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3853322667 ms=20942.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3854136600 ms=20944.000000000 frames=1469\nDEBUG: RUNSTATE running cycles=3854543567 ms=20945.000000000 frames=1469\nDEBUG: RUNSTATE running cycles=3855357501 ms=20947.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3855764468 ms=20948.000002457 frames=1469\nDEBUG: RUNSTATE running cycles=3861369583 ms=20962.000002457 frames=1470\nDEBUG: RUNSTATE running cycles=3861776550 ms=20963.000002457 frames=1470\nPRESENCE held frames=578 pointer=0 output=720x400x32 px_read=0 px_written=0 bytes_presented=0 uploads=1 upload_bytes=1152000 layers=edge,pointer,record\nSDLNET: Closed client TCP listening socket\nStopped capturing video.\n--END OF LOG--\n",
  "draft": "<volatile>",
  "session": {"alive": false, "running": false, "altered": false}
}
```

</details>
