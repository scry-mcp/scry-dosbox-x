**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "profile": "<host>",
  "shared": true,
  "flags": ["-set", "cpu core=normal"],
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

**2. `breakpoint_interrupt`**: OK loaded: a stop on BPINT 21 AH=62

<details><summary>call and reply</summary>

```json
{
  "number": 33,
  "ah": 98
}
```

```json
{
  "summary": "breakpoint_interrupt BPINT 21 AH=62: stored",
  "status": "ok",
  "ref": "BPINT 21 AH=62",
  "stored": true,
  "armed": true,
  "entry": "BPINT 21 AH=62",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `resume`**: OK boot: stopped inside the game: its map placed at segment 08EB, 385 symbols

<details><summary>call and reply</summary>

```json
{
  "seconds": 120
}
```

```json
{
  "summary": "resume: OTHER_STOP, stopped at 08EB:00009B4E",
  "status": "ok",
  "verdict": "OTHER_STOP",
  "omitted": ["output", "output_chars", "clipped"],
  "how": "detail=True adds what the debugger printed for this command",
  "waited_s": "<volatile>",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 1,
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
  "symbols_placed": {"placed": true, "path": "<volatile>", "load_segment": "08EB", "base": 36528, "loaded": 385},
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
  "disarmed": ["BPINT 21 AH=62"],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `screen_map_write`**: OK map: 4 screens and 10 controls loaded

<details><summary>call and reply</summary>

```json
{
  "method": "load",
  "path": "<host>"
}
```

```json
{
  "summary": "screen_map_write load: 4 screens, 10 controls of lineup",
  "status": "ok",
  "path": "<volatile>",
  "application": "lineup",
  "mode": "verified",
  "screens": 4,
  "controls": 10,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `perform`**: OK script: 34 steps of the game's own document, 21 holding to it

<details><summary>call and reply</summary>

```json
{
  "path": "<host>",
  "summaries": true
}
```

```json
{
  "summary": "perform: 34 of 34 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_to",
      "reply": {
        "summary": "run_to Draw_High_Scores_Screen: TARGET at 08EB:00001DF6, control counted 250",
        "status": "ok",
        "stop_seq": 3,
        "cause": "<volatile>"
      }
    },
    {
      "step": 1,
      "op": "breakpoint_at",
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'hiscores': found after 2 firings of breakpoint 'Check_Money100'",
        "status": "ok",
        "stop_seq": 4,
        "cause": "<volatile>"
      }
    },
    {
      "step": 3,
      "op": "declaration_clear",
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 4,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: hiscores (file), 2 controls", "status": "ok"}
    },
    {
      "step": 5,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0000", "status": "ok"}
    },
    {
      "step": 6,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 361",
        "status": "ok",
        "stop_seq": 10,
        "cause": "<volatile>"
      }
    },
    {
      "step": 7,
      "op": "breakpoint_at",
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 8,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'insert': found after 1 firing of breakpoint 'Check_Money100'",
        "status": "ok",
        "stop_seq": 11,
        "cause": "<volatile>"
      }
    },
    {
      "step": 9,
      "op": "declaration_clear",
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 10,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: insert (file), 2 controls", "status": "ok"}
    },
    {
      "step": 11,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0300", "status": "ok"}
    },
    {
      "step": 12,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 9 retraces to frame 371",
        "status": "ok",
        "stop_seq": 20,
        "cause": "<volatile>"
      }
    },
    {
      "step": 13,
      "op": "run_to",
      "reply": {
        "summary": "run_to Level_Write: TARGET at 08EB:000058FE, control counted 7",
        "status": "ok",
        "stop_seq": 21,
        "cause": "<volatile>"
      }
    },
    {
      "step": 14,
      "op": "breakpoint_at",
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 15,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'level': found after 1 firing of breakpoint 'Check_Money100'",
        "status": "ok",
        "stop_seq": 22,
        "cause": "<volatile>"
      }
    },
    {
      "step": 16,
      "op": "declaration_clear",
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 17,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: level (file), 3 controls", "status": "ok"}
    },
    {
      "step": 18,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0200", "status": "ok"}
    },
    {
      "step": 19,
      "op": "read_memory",
      "reply": {"summary": "read_memory Stage_Act: 2 bytes at 08EB:0000B0D8: 0000", "status": "ok"}
    },
    {
      "step": 20,
      "op": "breakpoint_at",
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 21,
      "op": "screen_wait",
      "reply": {
        "summary": "screen_wait screen 'play': found after 150 firings of breakpoint 'Check_Money100'",
        "status": "ok",
        "stop_seq": 23,
        "cause": "<volatile>"
      }
    },
    {
      "step": 22,
      "op": "declaration_clear",
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 23,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: play (file), 3 controls", "status": "ok"}
    },
    {
      "step": 33,
      "op": "read_memory",
      "reply": {
        "summary": "read_memory Player1: 12 bytes at 08EB:0000AE32: 010004000200040003000200",
        "status": "ok",
        "ref": "Player1",
        "seg_off": "08EB:0000AE32",
        "length": 12,
        "hex": "010004000200040003000200",
        "session": {"alive": true, "running": false, "altered": false}
      }
    }
  ],
  "steps_total": 34,
  "truncated": true,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 3,
    "stop_seq_last": 72,
    "surveyed": 14,
    "by_cause": {
      "run_to's target Draw_High_Scores_Screen": 1,
      "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told": 4,
      "the retrace the input's post ran to,": 5,
      "run_to's target Level_Write": 1,
      "run_to's target Gest_Scores": 3
    },
    "unaccounted": 56
  },
  "steps_completed": 34,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 21,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `audio_record`**: OK record: 141 frames recorded, the first whole frames past 2000 ms

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/music.wav"
}
```

```json
{
  "summary": "audio_record wav 141 frames: ELAPSED, 96288 samples at 48000 Hz at ./tmp/demos/lineup/music.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 141,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "frame": 780,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 73,
  "instruction": "<volatile>",
  "emulated_before_s": "<volatile>",
  "emulated_after_s": 11.12076996,
  "frame_before": 639,
  "frame_after": 780,
  "cycles": "<volatile>",
  "kind": "wav",
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 385196,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 96288,
  "emulated_s": "<volatile>",
  "sample_min": -19504,
  "sample_max": 18746,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**8. `audio_compare`**: OK heard: a sound, peaking at -4.51 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "<host>"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -4.51 dBFS, onset 0.0004 s, ch1 peak -4.51 dBFS, onset 0.0004 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": "<volatile>",
  "measures": [
    {
      "channel": 0,
      "peak_dbfs": -4.51,
      "rms_dbfs": -19.77,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0004,
      "clipping_run": 5,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -4.51,
      "rms_dbfs": -19.77,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0004,
      "clipping_run": 5,
      "clipped": false
    }
  ],
  "pcm_sha256": "c9d8e22394ed967ae4925d91dded07cc2b7d6984afd40f9b96d3fe85f3a451d7",
  "path": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**9. `audio_compare`**: OK exact: the recording is music.wav, sample for sample

<details><summary>call and reply</summary>

```json
{
  "method": "diff",
  "a": "./tmp/demos/lineup/music.wav",
  "b": "./demos/lineup/music.wav",
  "align": false
}
```

```json
{
  "summary": "audio_compare diff: exact, equal, envelope 1.0",
  "status": "ok",
  "exact": true,
  "snr_db": {
    "available": false,
    "why": "the two are equal after alignment: there is no error to measure the signal against"
  },
  "class": "exact",
  "envelope_correlation": 1.0,
  "onset_delta_ms": 0.0,
  "length_delta_samples": 0,
  "aligned_by_samples": 0,
  "a": "./tmp/demos/lineup/music.wav",
  "b": "./demos/lineup/music.wav",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `screen_view`**: OK screen: the board, 320x200

<details><summary>call and reply</summary>

```json
{
  "dest": "./tmp/demos/lineup/screen.png",
  "attach": false
}
```

```json
{
  "summary": "screen_view M_VGA: 320x200 at [0, 0] pixels; 1280x800 PNG x4, not inlined",
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
    "path": "<volatile>",
    "bytes": "<volatile>",
    "sha256": "<volatile>",
    "width": 1280,
    "height": 800,
    "scale": 4,
    "indexed": true,
    "inline": false,
    "not_inlined": "attach=false"
  },
  "display_start": "0h",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `close`**: OK close: closed: quit

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
