<p align="center"><img src="docs/scry-logo.png" alt="Scry" width="480"></p>

# scry-dosbox-x

**Drive and debug a DOS program from your MCP client, live.** One DOSBox-X stays open; you ask
it things by name, stop it where you mean to, press its keys and prove they landed, and every
answer says what it examined. A question costs a round trip instead of a boot.

If you develop for DOS under DOSBox-X you know the loop: start the emulator, wait for the guest,
reach the point you care about, read one line, quit. This server pays the boot once and then
answers, and it is built so that an autonomous session can be left alone with it: a browser is
driven by look, act, verify, and so is this.

## What it can do

- **Hold a live machine open.** `start` boots your conf headless (or in a window, for a run
  somebody watches) and parks the guest at the debugger. Registers, memory, the guest's
  own log, a still frame: each is one call.
- **Read the program's own account.** A guest that writes to the Bochs `0xE9` port has a log,
  filtered in the server: the last lines matching a pattern, when a line happened (or a wait
  for it), what was written since the last stop.
- **Names, not addresses.** Load the symbol list your toolchain prints (`nm`, a GNU `ld` map, a
  Borland TLINK map, an Open Watcom map) and say `_engine_set_rate`, not `00AF:0017A6EC`.
  Breakpoints, watches and comments are declarations that survive a rebuild.
- **Read the code and the machine.** `disassemble` decodes at any address in the segment's own
  width with targets named from your symbols; `call_stack` guesses the callers, marked
  heuristic; `machine_map` and `interrupt_vectors` say what the DOS machine is right now.
- **Read the screen without a window.** `screen_view` gives the screen at this stop as text or
  as a picture in any VGA mode (13h, planar 16 colours, mode X, VESA linear up to 32 bits),
  read from video memory without touching the card; `screen_signature` answers "is it the same
  screen" with one string; `screen_wait` runs until a string appears.
- **Stop where you mean to.** Run to a symbol and be told whether you arrived, stopped elsewhere
  or ran out of time; break on an interrupt, on the program's own `int 3`, when a variable
  changes, or when a register takes a value wherever the code is; step with every step read back; run by frames of the display or by emulated time.
- **Record a stretch, and watch without stopping.** `record` and `audio_record` capture the
  screen to an AVI, the sound to a WAV, the AdLib's register writes to a DRO or the MIDI bytes
  to a file, over a number of display frames, headless, each file checked before you get it. A
  count watch tallies every value a variable takes and who wrote it; a capture keeps a row, with
  the beam's line and the time, for every write or read of a byte, and never stops the machine.
- **Behind the CPU, and what DOS was asked.** `port` reads or writes an I/O port and refuses
  one no device answers; `pic` reads and drives the interrupt controllers; `a20` reads or sets
  the gate; a freeze watch pins a byte while the program runs. The `dos` log channel lists every
  DOS call with its result ("open MISSING.TXT, error 2, file not found") and who made it, and
  `guest_file` says whether the program wrote the file it was meant to leave, left it empty, or
  left the old one.
- **Press its keys, move its mouse, and prove it.** `send_keys` and `send_mouse` go in inside
  the machine, so no window comes to the front and your own pointer never moves. Give `expect`
  and the reply says whether the program acted; a swallowed key is reported as a miss.
- **One call per turn.** `perform` runs a list of operations and stops at the first failure with
  the whole account; `drive` is look, act, verify in one round trip.
- **Honest replies.** Every reply opens with a one-line `summary` and closes with a `session`
  block saying whether anything was written to the machine. "No line matched" and "there was no
  log" are different answers here.

## Two minutes to a first answer

You need git, Python 3.11 or newer, [uv](https://docs.astral.sh/uv/), and a DOSBox-X built with
the debugger (`build_check` says whether yours is): the `dosbox-x` on your `PATH`, or another
named by `DOSBOX_X_BINARY` or by `start`'s `binary`. Some tools need debugger commands a
release does not carry: waiting for a stop (`run_to`, `run_for`, `trace`, `screen_wait`, a step
over, a bounded `resume`) needs `RUNSTATE`; stepping needs `STEPIN`; the saved states need
`SAVESTATE` and `LOADSTATE`; a register condition needs `BPIF`; a picture in a mode past 13h's
needs `VGAMEMDUMP`; a recording `CAPTURE`; a count or capture watch `TAP`; a port `PORTINFO`;
the DOS calls `DOSTRACE` ([Platforms](#platforms)). Name a build that carries them with
`DOSBOX_X_BINARY`. A missing piece is named by the tool that needs it, never worked around.

```sh
git clone https://github.com/scry-mcp/scry-dosbox-x
cd scry-dosbox-x
claude mcp add dosbox-x -s user -- uv run --directory "$PWD" scry-dosbox-x
```

Any other MCP client starts the same command over stdio:
`uv run --directory /path/to/scry-dosbox-x scry-dosbox-x`.

Then ask your client to `start` your conf with `conf`, `cwd` and a `logfile` for the guest's log
(your conf needs `bochs debug port e9 = true` for that log to exist). Every path you give is
absolute or starts with `~`. A session nobody watches runs headless; a watched one (`shared`) opens
DOSBox-X's window, sized by your conf. Everything about your project
comes from you; the server carries no default that points anywhere.

## Platforms

macOS and Windows. The server talks to DOSBox-X's debugger over its debugger channel on both, the
same requests and the same replies; on Windows the emulator runs in a console of its own, hidden.
Linux runs the unit tests (`.github/workflows/ci.yml`) and nothing else: no emulator has run under
the server there.

What a session can do depends on the debugger commands its build carries, and `build_check` lists
them. Any DOSBox-X with the debugger starts a session and answers every reading at the stop it
parks at. Waiting for a stop (`run_to`, `run_for`, `trace`, `screen_wait`, a step over, a bounded
`resume`) needs `RUNSTATE`, which tells whether the debugger holds the machine; stepping needs
`STEPIN`; saved states need `SAVESTATE` and `LOADSTATE`; a stop on a register condition needs
`BPIF`; the screen in a planar, unchained or linear mode needs `VGAMEMDUMP`; recording a stretch
needs `CAPTURE`; a count or capture watch needs `TAP`; a port needs `PORTINFO`; the DOS calls
need `DOSTRACE`. A tool whose command is missing says so
and does nothing ([REFERENCE.md](REFERENCE.md#debugger-commands)).

## See it run

[`demos/bricks/`](demos/bricks/) is a small game this repository builds to be debugged, and a
`demo.py` that makes the calls a model would and checks every answer, from the first stop inside
the program to a breakpoint on the routine every falling brick goes through. The calls and
replies below are the last run's, written here by the demo itself
(`uv run python demos/bricks/demo.py --update-readme`), each cut to the fields that make its
point. The demo opens a window so the game can be watched.

![Bricks in mode 13h, stopped as the ball reaches its second brick](demos/bricks/screen.png)

<!-- demo-flow:begin bricks -->
```
resume(seconds=60)
-> {
  "summary": "resume: OTHER_STOP, stopped at 08DD:00000119",
  "cause": "no declared code breakpoint at 08DD:00000119: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
  "instruction": {
    "seg_off": "08DD:00000119",
    "bytes": "CD03",
    "text": "int 3",
    "flow": "call",
    "code_bits": 16,
    "bytes_from": "memory",
    "symbol": {
      "available": false,
      "why": "no symbol table is loaded"
    },
    "delta": {
      "available": false,
      "why": "no symbol table is loaded"
    }
  }
}
```

```
symbols_load(path="/path/to/scry-dosbox-x/demos/bricks/bricks.sym", base="8dd0")
-> {
  "summary": "symbols_load: 65 loaded of 65 parsed, base 36304",
  "base": 36304
}
```

```
breakpoint_at(ref="brick_hit")
-> {
  "summary": "breakpoint_at brick_hit: armed",
  "entry": "BP 08DD:02C8"
}
```

```
resume(seconds=60)
-> {
  "summary": "resume: OTHER_STOP, stopped at 08DD:000002C8",
  "cause": "breakpoint brick_hit (by symbol) at 08DD:000002C8",
  "watches": [
    {
      "ref": "score",
      "by": "symbol",
      "mode": "show",
      "length": 2,
      "fmt": "u16",
      "state": "evaluated",
      "value": 0,
      "bytes": "0000"
    }
  ]
}
```

```
read_memory(ref="score", length=2)
-> {
  "summary": "read_memory score: 2 bytes at 08DD:00000615: 0a00",
  "hex": "0a00"
}
```

```
drive(act=[{"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10}, {"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10}, {"op": "send_keys", "keys": ["right"], "expect": "KEY R", "seconds": 10}], pattern="KEY|PLAYER")
-> {
  "looked": {
    "guest": {
      "available": true,
      "since_mark": "<volatile>",
      "lines_written": "<volatile>",
      "lines_total": "<volatile>",
      "truncated": false,
      "lines": [
        "Bochs port E9h: PLAYER",
        "Bochs port E9h: KEY R",
        "Bochs port E9h: KEY R",
        "Bochs port E9h: KEY R"
      ],
      "pattern": "KEY|PLAYER"
    }
  }
}
```

```
state_write(method="save", name="bricks")
-> {
  "name": "bricks"
}
```

```
state_write(method="load", name="bricks")
-> {
  "name": "bricks"
}
```

```
read_memory(ref="paddle_x", length=2)
-> {
  "summary": "read_memory paddle_x: 2 bytes at 08DD:0000061F: dc00",
  "hex": "dc00"
}
```
<!-- demo-flow:end bricks -->

[`demos/dpaint/`](demos/dpaint/) paints a sunset in Electronic Arts' Deluxe Paint II and
stops halfway to find with a value scan the byte where the program keeps its current colour.
[`demos/dpaint_maps/`](demos/dpaint_maps/) drives it at 640 x 480, every menu, dialog button,
tool and colour picked by a screen-map name: the Palette dialog mixing an orange, the tool in hand
read off the toolbox, and a boat lifted as a brush, flipped and stamped.

[`demos/mines/`](demos/mines/) plays a Minesweeper this repository builds at VESA 800 x 600:
every screen recognised off a screen map before a click, the mines read out of the game's memory
by symbol and the board cleared without a miss, then an explosion recorded off the Sound Blaster
and held, sample for sample, against the recording beside it.

[`demos/lineup/`](demos/lineup/) plays the PC port of *LineUp* with the same script the MAME server
plays the arcade board with: the routines and variables named off each build's own symbol map,
every screen recognised off one map signed by palette index, and the stage's music held, sample
for sample, to the Sound Blaster's own recording. It needs a copy of the game, which is not
distributed here.

## The tools

The tools by family, each with its arguments, its reply and a real example, are in the index
at the top of [REFERENCE.md](REFERENCE.md). A tool's own description, delivered to your client
at connection, is its contract.

## Going further

[REFERENCE.md](REFERENCE.md) holds what the families share (the session, what every reply
carries, names for addresses) and links each family's page, where every tool's block is
followed by why its contract is shaped that way. [CONTRIBUTING.md](CONTRIBUTING.md) is for
changing the server: its battery, its live tier and what proves a change.

## Licence

MIT. See `LICENSE`.

## Credits

Developed by Optimiza ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).
