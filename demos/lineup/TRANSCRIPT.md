Every call of the run with its reply, in order: 24 calls. `<volatile>` stands for a value that changes from run to run, and `<host>` for one this host decides.

**1. `start`**: OK start: shared DOSBox-X, parked at the debugger before DOS boots

<details><summary>call and reply</summary>

```json
{
  "shared": true,
  "background": true,
  "display": "<host>",
  "profile": "<host>",
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
  "background": true,
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
    "checked": {
      "available": false,
      "why": "the table carries no symbol kinds (a link map lists none), so its code symbols cannot be told from the rest"
    }
  },
  "kept": "1 saved for `promote`",
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
  "number": "0x21",
  "ah": "0x62"
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
  "names": [
    {
      "field": "given.number",
      "number": "0x21/0x62",
      "kind": "call",
      "name": "get psp",
      "id": "ibm-pc:call:0x21/0x62"
    }
  ],
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
  "symbols_placed": {"placed": true, "path": "<volatile>", "load_segment": "08EB", "base": "0x00008eb0", "loaded": 385},
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
      "frame_before": 1,
      "frame_after": 352,
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
      "frame_before": 352,
      "frame_after": 352,
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 2,
      "op": "screen_wait",
      "frame_before": 352,
      "frame_after": 355,
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
      "frame_before": 355,
      "frame_after": 355,
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 4,
      "op": "screen_map_find",
      "frame_before": 355,
      "frame_after": 355,
      "reply": {"summary": "screen_map_find: hiscores (file), 2 controls", "status": "ok"}
    },
    {
      "step": 5,
      "op": "read_memory",
      "frame_before": 355,
      "frame_after": 355,
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0000", "status": "ok"}
    },
    {
      "step": 6,
      "op": "send_keys",
      "frame_before": 355,
      "frame_after": 361,
      "reply": {
        "summary": "send_keys (guest): sent, reaction not checked, 6 frames to frame 361",
        "status": "ok",
        "stop_seq": 10,
        "cause": "<volatile>"
      }
    },
    {
      "step": 7,
      "op": "breakpoint_at",
      "frame_before": 361,
      "frame_after": 361,
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 8,
      "op": "screen_wait",
      "frame_before": 361,
      "frame_after": 362,
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
      "frame_before": 362,
      "frame_after": 362,
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 10,
      "op": "screen_map_find",
      "frame_before": 362,
      "frame_after": 362,
      "reply": {"summary": "screen_map_find: insert (file), 2 controls", "status": "ok"}
    },
    {
      "step": 11,
      "op": "read_memory",
      "frame_before": 362,
      "frame_after": 362,
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0300", "status": "ok"}
    },
    {
      "step": 12,
      "op": "send_keys",
      "frame_before": 362,
      "frame_after": 371,
      "reply": {
        "summary": "send_keys (guest): sent, reaction not checked, 9 frames to frame 371",
        "status": "ok",
        "stop_seq": 20,
        "cause": "<volatile>"
      }
    },
    {
      "step": 13,
      "op": "run_to",
      "frame_before": 371,
      "frame_after": 380,
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
      "frame_before": 380,
      "frame_after": 380,
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 15,
      "op": "screen_wait",
      "frame_before": 380,
      "frame_after": 382,
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
      "frame_before": 382,
      "frame_after": 382,
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 17,
      "op": "screen_map_find",
      "frame_before": 382,
      "frame_after": 382,
      "reply": {"summary": "screen_map_find: level (file), 3 controls", "status": "ok"}
    },
    {
      "step": 18,
      "op": "read_memory",
      "frame_before": 382,
      "frame_after": 382,
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0200", "status": "ok"}
    },
    {
      "step": 19,
      "op": "read_memory",
      "frame_before": 382,
      "frame_after": 382,
      "reply": {"summary": "read_memory Stage_Act: 2 bytes at 08EB:0000B0D8: 0000", "status": "ok"}
    },
    {
      "step": 20,
      "op": "breakpoint_at",
      "frame_before": 382,
      "frame_after": 382,
      "reply": {"summary": "breakpoint_at Check_Money100: armed", "status": "ok"}
    },
    {
      "step": 21,
      "op": "screen_wait",
      "frame_before": 382,
      "frame_after": 592,
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
      "frame_before": 592,
      "frame_after": 592,
      "reply": {"summary": "declaration_clear breakpoint all: 1 cleared", "status": "ok"}
    },
    {
      "step": 23,
      "op": "screen_map_find",
      "frame_before": 592,
      "frame_after": 592,
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
        "names": [
          {"field": "given.ref", "number": "0x00013ce2", "kind": "symbol", "name": "Player1"}
        ],
        "session": {"alive": true, "running": false, "altered": false}
      },
      "frame_before": 639,
      "frame_after": 639
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
      "no declared code breakpoint, and the debugger does not say which row stopped the machine, so what made this stop cannot be told": 4,
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
  "emulated_after_s": "<volatile>",
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
  "b": "<host>",
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
  "b": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**10. `send_keys`**: OK fire again: UP pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "down"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 6 frames to frame 786",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 79,
  "frame": 786,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**11. `record`**: OK second shot: recorded 141 frames in ./tmp/demos/lineup/second-shot.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/second-shot.avi",
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
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**12. `send_keys`**: OK fire again: let go: the key let go

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "up"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 6 frames to frame 933",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 86,
  "frame": 933,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**13. `send_keys`**: OK right again: RIGHT pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["right"]
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 20 frames to frame 953",
  "status": "ok",
  "keys": ["right"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 4,
  "frames": 4,
  "polls": 20,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 106,
  "frame": 953,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**14. `run_to`**: OK moved again: the move taken

<details><summary>call and reply</summary>

```json
{
  "ref": "Gest_Scores",
  "control": "Check_Money25",
  "seconds": 120
}
```

```json
{
  "summary": "run_to Gest_Scores: TARGET at 08EB:00000E42, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08EB:0E42",
  "ref": "Gest_Scores",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "Check_Money25", "at": "08EB:19DC", "hits_in_run": 0, "removed": true}
  ],
  "frame": 953,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 107,
  "instruction": "<volatile>",
  "names": [
    {"field": "given.ref", "number": "0x00009cf2", "kind": "symbol", "name": "Gest_Scores"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**15. `send_keys`**: OK fire from there: UP pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "down"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 10 frames to frame 963",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 10,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 117,
  "frame": 963,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**16. `record`**: OK third shot: recorded 141 frames in ./tmp/demos/lineup/third-shot.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/third-shot.avi",
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
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**17. `send_keys`**: OK fire from there: let go: the key let go

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "up"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 6 frames to frame 1110",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 124,
  "frame": 1110,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**18. `send_keys`**: OK colour again: FIRE1 pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["space"]
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 10 frames to frame 1120",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 10,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 134,
  "frame": 1120,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**19. `run_to`**: OK raised again: the colour taken

<details><summary>call and reply</summary>

```json
{
  "ref": "Gest_Scores",
  "control": "Check_Money25",
  "seconds": 120
}
```

```json
{
  "summary": "run_to Gest_Scores: TARGET at 08EB:00000E42, control counted 1",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08EB:0E42",
  "ref": "Gest_Scores",
  "pc": "<volatile>",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 1,
  "controls": [
    {"ref": "Check_Money25", "at": "08EB:19DC", "hits_in_run": 1, "removed": true}
  ],
  "frame": 1121,
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 135,
  "instruction": "<volatile>",
  "names": [
    {"field": "given.ref", "number": "0x00009cf2", "kind": "symbol", "name": "Gest_Scores"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**20. `send_keys`**: OK fire that colour: UP pressed

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "down"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 9 frames to frame 1130",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 9,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 144,
  "frame": 1130,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**21. `record`**: OK fourth shot: recorded 141 frames in ./tmp/demos/lineup/fourth-shot.avi

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/fourth-shot.avi",
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
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": "<volatile>",
  "avi_frames": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**22. `send_keys`**: OK fire that colour: let go: the key let go

<details><summary>call and reply</summary>

```json
{
  "keys": ["up"],
  "action": "up"
}
```

```json
{
  "summary": "send_keys (guest): sent, reaction not checked, 6 frames to frame 1277",
  "status": "ok",
  "keys": ["up"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
  "polls": 6,
  "pc": "<volatile>",
  "cpu_mode": "real",
  "stop_seq": 151,
  "frame": 1277,
  "instruction": "<volatile>",
  "regs": "<volatile>",
  "watches": [],
  "cause": "<volatile>",
  "e9": {"lines_total": "<volatile>", "truncated": false, "lines": [], "mark": "<volatile>"},
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**23. `screen_view`**: OK screen: the board, 320x200

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

**24. `close`**: OK close: closed: quit

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
