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
  "conf_digest": "6018944893db6f81",
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

**2. `run_for`**: OK boot: booted: DOS running the game, its map placed at segment 08EB, 385 symbols

<details><summary>call and reply</summary>

```json
{
  "milliseconds": 2000,
  "seconds": 120
}
```

```json
{
  "summary": "run_for 2000 ms: ELAPSED, 140 polls, at 08EB:00001CA9",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 140,
  "pc": "08EB:00001CA9",
  "cpu_mode": "real",
  "frame": 140,
  "regs": {
    "EAX": "0x00000020",
    "EBX": "0x0000000a",
    "ECX": "0x005b0000",
    "EDX": "0x00000000",
    "ESI": "0x00001260",
    "EDI": "0x00000dfd",
    "EBP": "0x00004288",
    "ESP": "0x00004282",
    "EIP": "0x00001ca9",
    "CS": "0x08eb",
    "DS": "0x138c",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138c"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08EB:00001CA9",
  "e9": {
    "lines_total": 1,
    "truncated": false,
    "lines": ["Bochs port E9h: STUB  . scry device=present proto=7 motion=1"],
    "mark": "<volatile>"
  },
  "stop_seq": 2,
  "instruction": {
    "address": "08EB:00001CA9",
    "bytes": "833ECC0601",
    "text": "cmp word ptr [0x6cc], 1",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "Pal_Off",
    "delta": 122
  },
  "symbols_placed": {"placed": true, "path": "<volatile>", "load_segment": "08EB", "base": 36528, "loaded": 385},
  "emulated_before_s": 0.00094,
  "emulated_after_s": 2.0029089,
  "frame_before": 0,
  "frame_after": 140,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**3. `screen_map_write`**: OK map: 4 screens and 10 controls loaded

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

**4. `perform`**: OK script: 26 steps of the game's own document, 21 holding to it

<details><summary>call and reply</summary>

```json
{
  "path": "<host>",
  "summaries": true
}
```

```json
{
  "summary": "perform: 26 of 26 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "run_to",
      "reply": {
        "summary": "run_to Draw_High_Scores_Screen: TARGET at 08EB:00001DF6, control counted 1",
        "status": "ok",
        "stop_seq": 3,
        "cause": "run_to's target Draw_High_Scores_Screen at 08EB:00001DF6"
      }
    },
    {
      "step": 1,
      "op": "run_for",
      "reply": {
        "summary": "run_for 1500 ms: ELAPSED, 106 polls, at 08EB:00001CA9",
        "status": "ok",
        "stop_seq": 4,
        "cause": "the retrace run_for ran to, at 08EB:00001CA9"
      }
    },
    {
      "step": 2,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: hiscores (file), 2 controls", "status": "ok"}
    },
    {
      "step": 3,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0000", "status": "ok"}
    },
    {
      "step": 4,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 462",
        "status": "ok",
        "stop_seq": 10,
        "cause": "the retrace the input's post ran to, at F000:0000CA40"
      }
    },
    {
      "step": 5,
      "op": "run_for",
      "reply": {
        "summary": "run_for 1000 ms: ELAPSED, 71 polls, at 08EB:00001CA9",
        "status": "ok",
        "stop_seq": 11,
        "cause": "the retrace run_for ran to, at 08EB:00001CA9"
      }
    },
    {
      "step": 6,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: insert (file), 2 controls", "status": "ok"}
    },
    {
      "step": 7,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0300", "status": "ok"}
    },
    {
      "step": 8,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 539",
        "status": "ok",
        "stop_seq": 17,
        "cause": "the retrace the input's post ran to, at 08EB:00009243"
      }
    },
    {
      "step": 9,
      "op": "run_to",
      "reply": {
        "summary": "run_to Level_Write: TARGET at 08EB:000058FE, control counted 0",
        "status": "ok",
        "stop_seq": 18,
        "cause": "run_to's target Level_Write at 08EB:000058FE"
      }
    },
    {
      "step": 10,
      "op": "run_for",
      "reply": {
        "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08EB:000004AC",
        "status": "ok",
        "stop_seq": 19,
        "cause": "the retrace run_for ran to, at 08EB:000004AC"
      }
    },
    {
      "step": 11,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: level (file), 3 controls", "status": "ok"}
    },
    {
      "step": 12,
      "op": "read_memory",
      "reply": {"summary": "read_memory Credits: 2 bytes at 08EB:0000BC04: 0200", "status": "ok"}
    },
    {
      "step": 13,
      "op": "read_memory",
      "reply": {"summary": "read_memory Stage_Act: 2 bytes at 08EB:0000B0D8: 0000", "status": "ok"}
    },
    {
      "step": 14,
      "op": "run_for",
      "reply": {
        "summary": "run_for 3000 ms: ELAPSED, 211 polls, at 08EB:000086A8",
        "status": "ok",
        "stop_seq": 20,
        "cause": "the retrace run_for ran to, at 08EB:000086A8"
      }
    },
    {
      "step": 15,
      "op": "screen_map_find",
      "reply": {"summary": "screen_map_find: play (file), 3 controls", "status": "ok"}
    },
    {
      "step": 16,
      "op": "read_memory",
      "reply": {
        "summary": "read_memory Player1: 12 bytes at 08EB:0000AE32: 010003000100000003000000",
        "status": "ok"
      }
    },
    {
      "step": 17,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 16 retraces to frame 789",
        "status": "ok",
        "stop_seq": 36,
        "cause": "the retrace the input's post ran to, at 08EB:000004AC"
      }
    },
    {
      "step": 18,
      "op": "run_for",
      "reply": {
        "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08EB:000004AC",
        "status": "ok",
        "stop_seq": 37,
        "cause": "the retrace run_for ran to, at 08EB:000004AC"
      }
    },
    {
      "step": 19,
      "op": "read_memory",
      "reply": {
        "summary": "read_memory Player1: 12 bytes at 08EB:0000AE32: 010004000100000003000000",
        "status": "ok"
      }
    },
    {
      "step": 20,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 6 retraces to frame 810",
        "status": "ok",
        "stop_seq": 43,
        "cause": "the retrace the input's post ran to, at 08EB:000004AC"
      }
    },
    {
      "step": 21,
      "op": "run_for",
      "reply": {
        "summary": "run_for 200 ms: ELAPSED, 15 polls, at 08EB:00008621",
        "status": "ok",
        "stop_seq": 44,
        "cause": "the retrace run_for ran to, at 08EB:00008621"
      }
    },
    {
      "step": 22,
      "op": "read_memory",
      "reply": {
        "summary": "read_memory Player1: 12 bytes at 08EB:0000AE32: 010004000200000003000000",
        "status": "ok"
      }
    },
    {
      "step": 23,
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): posted, unverified, 16 retraces to frame 841",
        "status": "ok",
        "stop_seq": 60,
        "cause": "the retrace the input's post ran to, at 08EB:000004AC"
      }
    },
    {
      "step": 25,
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
  "steps_total": 26,
  "truncated": true,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 3,
    "stop_seq_last": 61,
    "surveyed": 14,
    "by_cause": {
      "run_to's target Draw_High_Scores_Screen": 1,
      "the retrace run_for ran to,": 7,
      "the retrace the input's post ran to,": 5,
      "run_to's target Level_Write": 1
    },
    "unaccounted": 45
  },
  "steps_completed": 26,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 21,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**5. `audio_record`**: OK record: 141 frames recorded, the first whole frames past 2000 ms

<details><summary>call and reply</summary>

```json
{
  "frames": 141,
  "dest": "./tmp/demos/lineup/music.wav"
}
```

```json
{
  "summary": "audio_record wav 141 frames: ELAPSED, 96576 samples at 48000 Hz at ./tmp/demos/lineup/music.wav",
  "status": "ok",
  "verdict": "ELAPSED",
  "polls": 141,
  "pc": "08EB:000004AC",
  "cpu_mode": "real",
  "frame": 990,
  "regs": {
    "EAX": "0x0000ffff",
    "EBX": "0x00005e0a",
    "ECX": "0x005b0000",
    "EDX": "0x00000002",
    "ESI": "0x0000046a",
    "EDI": "0x0000faa0",
    "EBP": "0x00004288",
    "ESP": "0x00004286",
    "EIP": "0x000004ac",
    "CS": "0x08eb",
    "DS": "0x138c",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x138c"
  },
  "watches": [],
  "cause": "the retrace run_for ran to, at 08EB:000004AC",
  "e9": {"lines_total": 0, "truncated": false, "lines": [], "mark": "<volatile>"},
  "stop_seq": 62,
  "instruction": {
    "address": "08EB:000004AC",
    "bytes": "A16A12",
    "text": "mov ax, word ptr [0x126a]",
    "flow": "sequential",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "_lineup_run",
    "delta": 88
  },
  "emulated_before_s": 12.119534439999999,
  "emulated_after_s": 14.13133152,
  "frame_before": 849,
  "frame_after": 990,
  "cycles": {
    "available": false,
    "why": "the cycle count counts only what the normal core runs, and this session started on the dynamic core: start on `flags=[\"-set\", \"cpu core=normal\"]` for a count"
  },
  "kind": "wav",
  "frames": 141,
  "began": true,
  "ended": true,
  "path": "<volatile>",
  "bytes": 386348,
  "channels": 2,
  "sample_rate_hz": 48000,
  "samples": 96576,
  "emulated_s": 2.0117971,
  "sample_min": -8568,
  "sample_max": 3017,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**6. `audio_compare`**: OK heard: a sound, peaking at -11.65 dBFS

<details><summary>call and reply</summary>

```json
{
  "method": "measure",
  "path": "<host>"
}
```

```json
{
  "summary": "audio_compare measure: ch0 peak -11.65 dBFS, onset 0.0 s, ch1 peak -11.65 dBFS, onset 0.0 s",
  "status": "ok",
  "sample_rate_hz": 48000,
  "channels": 2,
  "bits": 16,
  "window": "<volatile>",
  "measures": [
    {
      "channel": 0,
      "peak_dbfs": -11.65,
      "rms_dbfs": -28.33,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 0,
      "clipped": false
    },
    {
      "channel": 1,
      "peak_dbfs": -11.65,
      "rms_dbfs": -28.33,
      "silent": false,
      "silence_spans": {
        "count": 0,
        "first": {"available": false, "why": "no silence in the window"}
      },
      "onset_s": 0.0,
      "clipping_run": 0,
      "clipped": false
    }
  ],
  "pcm_sha256": "56e09fbf4f27acceae4944debf2d03d2bb9d1fb63287118ef6980bb83d23cb19",
  "path": "<volatile>",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

**7. `audio_compare`**: OK exact: the recording is music.wav, sample for sample

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

**8. `screen_view`**: OK screen: the board, 320x200

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
    "bytes": 16447,
    "sha256": "d8086f4e5c34cdbda5c8d049be105859abd90036ed2508834e05d9318e18b3af",
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

**9. `close`**: OK close: closed: quit

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
  "conf_digest": "6018944893db6f81",
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
