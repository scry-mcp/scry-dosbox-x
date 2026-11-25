# Minesweeper: the board read out of memory and cleared without a miss

<!-- demo-motion:begin -->
<p align="center"><picture><source media="(prefers-reduced-motion: reduce)" srcset="screen.png"><img src="loop.webp" alt="Minesweeper read out of memory and cleared click by click without a miss, then a mine stepped on"></picture></p>

1. `screen_map_find` names the screen the game is showing: the title.
2. `read_memory` reads the 81 bytes that say where the mines are.
3. `send_mouse` clicks a cell the memory says is safe, and the game reveals it.
4. One `perform` sends the rest of the clicks, and the board opens.
5. The explosion recorded from the emulated Sound Blaster equals `boom.wav`.

<!-- moments-ms: 1853,1838,1853,1853,1853 -->
<!-- demo-motion:end -->

`MINES.COM` is a Minesweeper this repository builds, at 800 x 600 in 256 colours. The demo
plays it with the mouse, by the names its screen map gives its buttons: a file that names the
game's controls. Then it reads where the mines are out of the game's memory, clears the board,
and steps on a mine on purpose.

## The program

The game is `mines.asm`, in this folder with the program built from it, its symbol table, its
conf and its screen map. Its header says how to build it and what it logs for a debugger.

To play it yourself: `cd demos/mines && dosbox-x -conf mines.conf`, then type `MINES`.

## Run it

```sh
uv run python demos/mines/demo.py
```

Each line it prints is one call and its check. The window opens behind the others, so the run
does not take your keyboard; `--watch` brings it in front, for when you want to watch it.

- `--binary PATH` (absolute or `~`-led) picks the DOSBox-X to start. Left out, it is
  `DOSBOX_X_BINARY`, else the `dosbox-x` on your `PATH`.
- `--display N` opens the window on that display. Left out, it opens on the main one.
- `--watch` shows the run: the window comes in front and takes your keyboard until the run ends.
- `--transcript PATH` moves the whole transcript; the run's other files go beside it.
- `--update-readme` rewrites this page's generated parts, `TRANSCRIPT.md`, `screen.png` and
  `loop.webp`, from a run where every step passed. It needs ffmpeg and `img2webp` on your
  `PATH`, and Pillow and numpy (the `decorate` extra), which draw the call captions and the pointer over the loop.

Exit codes: 0 every step passed, 1 a step failed, 2 a usage error, 3 nothing was demonstrated.
That last one is a server that did not start.

The explosion is recorded from the emulated Sound Blaster and must equal [`boom.wav`](boom.wav)
sample for sample. A change to the game's sound or timing makes that file out of date: the
run's own `run.wav`, beside its transcript, is then the one to copy over it.

Each moment is a short recording the demo takes after the call it shows, so the board that
call changed is on screen.

## Try it yourself

[Add the server to your client](../../README.md#install) and ask it to start DOSBox-X on `demos/mines/mines.conf` with `MINES.COM` as its program, run to
the program's own `int 3` and load `mines.sym` there. Each of these is a step of
the demo, in the order the demo makes them.

<!-- demo-transcript:begin -->
### 1. Run to a routine by its name

Ask:

> Run the game until it reaches `main_loop`.

Call:

```text
run_to(ref="main_loop", control="retrace", seconds=60)
```

Reply, 2 of 19 fields:

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "verdict": "TARGET"
}
```

`TARGET` means the run stopped at `main_loop`, where the game goes once its title is drawn. So the screen read next is whole on any computer.

<details><summary>The whole reply</summary>

```json
{
  "summary": "run_to main_loop: TARGET at 08DF:00000131, control counted 0",
  "status": "ok",
  "verdict": "TARGET",
  "target": "08DF:0131",
  "ref": "main_loop",
  "pc": "08DF:00000131",
  "cpu_mode": "real",
  "target_disarmed": true,
  "control_hits": 0,
  "controls": [
    {"ref": "retrace", "at": "08DF:0DFF", "hits_in_run": 0, "removed": true}
  ],
  "frame": 2,
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x0002010f",
    "ECX": "0x00000148",
    "EDX": "0x00000180",
    "ESI": "0x000017d5",
    "EDI": "0x00001835",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffe",
    "EIP": "0x00000131",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0x08df",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "watches": [],
  "cause": "run_to's target main_loop at 08DF:00000131",
  "e9": {"lines_total": 1, "truncated": false, "lines": ["Bochs port E9h: TITLE"], "mark": "<volatile>"},
  "stop_seq": 3,
  "instruction": {
    "address": "08DF:00000131",
    "bytes": "E8CB0C",
    "text": "call 0xdff",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": "main_loop",
    "delta": 0
  },
  "names": [
    {"field": "given.ref", "number": "0x00008f21", "kind": "symbol", "name": "main_loop"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

### 2. Read the board out of memory

Ask:

> Read the 81 bytes at `mines`, the game's own table of where the mines are.

Call:

```text
read_memory(ref="mines", length=81)
```

Reply, 2 of 8 fields:

```json
{
  "summary": "read_memory mines: 81 bytes at 08DF:00001030: 00000001000000 ... (202 characters)",
  "length": 81
}
```

`mines` is a symbol of the build, one byte per cell. Where the mines are is data the server can read and a player cannot.

<details><summary>The whole reply</summary>

```json
{
  "summary": "read_memory mines: 81 bytes at 08DF:00001030: 00000001000000000000000100010000000001000000000000000000000000000000000000000000000000000000000000010000000000000000000100000100... (17 more bytes in `hex`)",
  "status": "ok",
  "ref": "mines",
  "seg_off": "08DF:00001030",
  "length": 81,
  "hex": "000000010000000000000001000100000000010000000000000000000000000000000000000000000000000000000000000100000000000000000001000001000001000000000000010000010000000000",
  "names": [
    {"field": "given.ref", "number": "0x00009e20", "kind": "symbol", "name": "mines"}
  ],
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

### 3. Clear the board in one call

Ask:

> Open every safe cell with as few clicks as the game's flood fill allows, waiting for the game to log each reveal.

Call:

```text
perform(steps=[… 18 items], summaries=…)
```

Reply, 2 of 12 fields:

```json
{
  "summary": "perform: 18 of 18 steps",
  "steps_completed": 18
}
```

Each click waits for the line the game logs when it reveals that cell, so a click that missed fails at once. `perform` sends them all as one call.

<details><summary>The whole reply</summary>

```json
{
  "summary": "perform: 18 of 18 steps",
  "status": "ok",
  "ran": [
    {
      "step": 0,
      "op": "send_mouse",
      "frame_before": 534,
      "frame_after": 555,
      "reply": {
        "summary": "send_mouse: pointer at 352,204, program's own pointer not read; reaction seen, 21 frames to frame 555",
        "status": "ok",
        "stop_seq": 172,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 1,
      "op": "send_mouse",
      "frame_before": 555,
      "frame_after": 580,
      "reply": {
        "summary": "send_mouse: pointer at 400,204, program's own pointer not read; reaction seen, 25 frames to frame 580",
        "status": "ok",
        "stop_seq": 197,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 2,
      "op": "send_mouse",
      "frame_before": 580,
      "frame_after": 605,
      "reply": {
        "summary": "send_mouse: pointer at 424,204, program's own pointer not read; reaction seen, 25 frames to frame 605",
        "status": "ok",
        "stop_seq": 222,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 3,
      "op": "send_mouse",
      "frame_before": 605,
      "frame_after": 630,
      "reply": {
        "summary": "send_mouse: pointer at 448,204, program's own pointer not read; reaction seen, 25 frames to frame 630",
        "status": "ok",
        "stop_seq": 247,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 4,
      "op": "send_mouse",
      "frame_before": 630,
      "frame_after": 655,
      "reply": {
        "summary": "send_mouse: pointer at 376,228, program's own pointer not read; reaction seen, 25 frames to frame 655",
        "status": "ok",
        "stop_seq": 272,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 5,
      "op": "send_mouse",
      "frame_before": 655,
      "frame_after": 680,
      "reply": {
        "summary": "send_mouse: pointer at 400,348, program's own pointer not read; reaction seen, 25 frames to frame 680",
        "status": "ok",
        "stop_seq": 297,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 6,
      "op": "send_mouse",
      "frame_before": 680,
      "frame_after": 705,
      "reply": {
        "summary": "send_mouse: pointer at 448,348, program's own pointer not read; reaction seen, 25 frames to frame 705",
        "status": "ok",
        "stop_seq": 322,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 7,
      "op": "send_mouse",
      "frame_before": 705,
      "frame_after": 730,
      "reply": {
        "summary": "send_mouse: pointer at 472,348, program's own pointer not read; reaction seen, 25 frames to frame 730",
        "status": "ok",
        "stop_seq": 347,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 8,
      "op": "send_mouse",
      "frame_before": 730,
      "frame_after": 755,
      "reply": {
        "summary": "send_mouse: pointer at 376,372, program's own pointer not read; reaction seen, 25 frames to frame 755",
        "status": "ok",
        "stop_seq": 372,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 9,
      "op": "send_mouse",
      "frame_before": 755,
      "frame_after": 780,
      "reply": {
        "summary": "send_mouse: pointer at 400,372, program's own pointer not read; reaction seen, 25 frames to frame 780",
        "status": "ok",
        "stop_seq": 397,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 10,
      "op": "send_mouse",
      "frame_before": 780,
      "frame_after": 805,
      "reply": {
        "summary": "send_mouse: pointer at 424,372, program's own pointer not read; reaction seen, 25 frames to frame 805",
        "status": "ok",
        "stop_seq": 422,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 11,
      "op": "send_mouse",
      "frame_before": 805,
      "frame_after": 830,
      "reply": {
        "summary": "send_mouse: pointer at 448,372, program's own pointer not read; reaction seen, 25 frames to frame 830",
        "status": "ok",
        "stop_seq": 447,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 12,
      "op": "send_mouse",
      "frame_before": 830,
      "frame_after": 855,
      "reply": {
        "summary": "send_mouse: pointer at 472,372, program's own pointer not read; reaction seen, 25 frames to frame 855",
        "status": "ok",
        "stop_seq": 472,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 13,
      "op": "send_mouse",
      "frame_before": 855,
      "frame_after": 880,
      "reply": {
        "summary": "send_mouse: pointer at 496,372, program's own pointer not read; reaction seen, 25 frames to frame 880",
        "status": "ok",
        "stop_seq": 497,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 14,
      "op": "send_mouse",
      "frame_before": 880,
      "frame_after": 905,
      "reply": {
        "summary": "send_mouse: pointer at 328,396, program's own pointer not read; reaction seen, 25 frames to frame 905",
        "status": "ok",
        "stop_seq": 522,
        "cause": "no declared code breakpoint at 08DF:00000E07, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 15,
      "op": "send_mouse",
      "frame_before": 905,
      "frame_after": 930,
      "reply": {
        "summary": "send_mouse: pointer at 352,396, program's own pointer not read; reaction seen, 25 frames to frame 930",
        "status": "ok",
        "stop_seq": 547,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 16,
      "op": "send_mouse",
      "frame_before": 930,
      "frame_after": 955,
      "reply": {
        "summary": "send_mouse: pointer at 400,396, program's own pointer not read; reaction seen, 25 frames to frame 955",
        "status": "ok",
        "stop_seq": 572,
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told"
      }
    },
    {
      "step": 17,
      "op": "send_mouse",
      "reply": {
        "summary": "send_mouse: pointer at 424,396, program's own pointer not read; reaction seen, 25 frames to frame 980",
        "status": "ok",
        "x": 424,
        "y": 396,
        "units": "screen",
        "button": "left",
        "action": "click",
        "route": "guest",
        "pointer": {
          "screen": {"x": 424, "y": 396, "width": 800, "height": 600},
          "mouse": {"x": 424, "y": 396, "max_x": 799, "max_y": 599},
          "buttons": [],
          "bios_mode": "0x6b",
          "vbe_mode": "0x103"
        },
        "driver_arrived": true,
        "polls": 25,
        "pc": "08DF:00000E08",
        "cpu_mode": "real",
        "stop_seq": 597,
        "frame": 980,
        "instruction": {
          "address": "08DF:00000E08",
          "bytes": "A808",
          "text": "test al, 8",
          "flow": "sequential",
          "code_bits": 16,
          "bytes_from": "memory",
          "symbol": "retrace",
          "delta": 9
        },
        "regs": {
          "EAX": "0x00000004",
          "EBX": "0x00000000",
          "ECX": "0x00000160",
          "EDX": "0x000003da",
          "ESI": "0x000017d5",
          "EDI": "0x00000fc4",
          "EBP": "0x0000091c",
          "ESP": "0x0000fffc",
          "EIP": "0x00000e08",
          "CS": "0x08df",
          "DS": "0x08df",
          "ES": "0x08df",
          "FS": "0x0000",
          "GS": "0x0000",
          "SS": "0x08df"
        },
        "watches": [],
        "cause": "no declared code breakpoint at 08DF:00000E08, and the debugger does not say which row stopped the machine, so what made this stop cannot be told",
        "e9": {
          "lines_total": 2,
          "truncated": false,
          "lines": ["Bochs port E9h: REVEAL 8 5 4", "Bochs port E9h: WIN"],
          "mark": "<volatile>"
        },
        "motion": true,
        "verify": {
          "checked": true,
          "seen": true,
          "expected": "REVEAL 8 5 ",
          "verdict": "TARGET",
          "line": "Bochs port E9h: REVEAL 8 5 4",
          "seen_before_waiting": true,
          "lines_before": 0,
          "waited_s": "<volatile>",
          "lines_total": 1
        },
        "session": {"alive": true, "running": false, "altered": false}
      },
      "frame_before": 955,
      "frame_after": 980
    }
  ],
  "steps_total": 18,
  "truncated": false,
  "ran_path": "<volatile>",
  "replies_path": "<volatile>",
  "stops": {
    "stop_seq_first": 152,
    "stop_seq_last": 597,
    "surveyed": 18,
    "by_cause": {
      "no declared code breakpoint, and the debugger does not say which row stopped the machine, so what made this stop cannot be told": 18
    },
    "unaccounted": 428
  },
  "steps_completed": 18,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0,
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>

### 4. Compare a sound with its reference

Ask:

> Compare the explosion you recorded with `boom.wav`, sample by sample.

Call:

```text
audio_compare(method="diff", a="./tmp/demos/mines/run.wav", b="./demos/mines/boom.wav", align=false)
```

Reply, 2 of 12 fields:

```json
{
  "summary": "audio_compare diff: exact, equal, envelope 1.0",
  "exact": true
}
```

`exact` is true only when every sample is equal. The recording comes from the emulated Sound Blaster's digital output, not from the speakers.

<details><summary>The whole reply</summary>

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
  "a": "<volatile>",
  "b": "./demos/mines/boom.wav",
  "session": {"alive": true, "running": false, "altered": false}
}
```

</details>
<!-- demo-transcript:end -->

<details><summary>The whole demo as one prompt</summary>

1. Start DOSBox-X windowed on `demos/mines/mines.conf` with `MINES.COM` as its program,
   recording its own video, stopping at the program's own `int 3`, with the log in a file.
2. Run to that `int 3`, load `mines.sym` at the segment it stopped in, and load the screen map
   `mines-screen-map.json` beside the conf.
3. Run to `main_loop` and tell me which screen this is; click its start, run to `main_loop`
   again and tell me again.
4. Open the Game menu by name, run to `main_loop`, check it is the menu, pick Beginner and run
   to `main_loop`.
5. Read the board's size, where its mines are and the pixel of its top-left corner, all by
   symbol.
6. Flag two of the mines with the right button, then open every safe cell and show me the game
   says WIN.
7. Move the pointer off the board, tell me which screen this is, show it to me and run 240
   frames.
8. Click OK, run to `main_loop`, read the new board's mines and click on the first one until
   the game logs BOOM.
9. Record 45 frames of sound from there, measure them and compare them with `boom.wav` without
   aligning.
10. Move the pointer away, tell me which screen this is, and close.

</details>

## Tools this demo uses

| Group | Tools |
|---|---|
| [Session](../../docs/reference/session.md) | `start`, `close` |
| [Run](../../docs/reference/run.md) | `resume`, `run_to`, `run_for` |
| [Names](../../docs/reference/names.md) | `symbols_load` |
| [Read](../../docs/reference/read.md) | `screen_map_write`, `screen_map_find`, `read_memory` |
| [Input](../../docs/reference/input.md) | `send_mouse` |
| [Sequences](../../docs/reference/sequences.md) | `perform` |
| [Machine](../../docs/reference/machine.md) | `log` |
| [Files](../../docs/reference/files.md) | `audio_compare` |
| [Screen](../../docs/reference/screen.md) | `screen_view` |
| [Captures](../../docs/reference/captures.md) | `audio_record` |

Each group is a page of the reference. Some of the names need a word:

- Run: the tools that let the program run and stop it again.
- Sequences: the tools that run several calls as one.
- Machine: the program's log and the map of what DOS loaded.
- Names: the tool that loads a symbol table.

## The transcript

[TRANSCRIPT.md](TRANSCRIPT.md) has every call of the run with its reply. Process ids, ports,
wall-clock times and temporary paths read `<volatile>` there, because they change from run to
run.
