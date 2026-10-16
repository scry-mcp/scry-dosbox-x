# scry-dosbox-x

**Drive and debug a DOS program from your MCP client, live.** One DOSBox-X stays open;
you ask it things by name, stop it where you mean to, press its keys and prove they
landed, and every answer says what it examined. A question costs under a second instead
of a boot.

If you develop for DOS under DOSBox-X you know the loop: start the emulator, wait for the
guest, reach the point you care about, read one line, quit. Two questions are two boots.
This server pays that cost once, then answers, and it is built so that an autonomous
session can be left alone with it: a browser is driven by look, act, verify, and so is
this.

## What it can do

- **Hold a live machine open and answer from it.** `start` boots your conf headless (or
  in a window you place) and parks the guest at the debugger, ready. Registers, memory,
  the guest's own log, a still frame: each one is a call.
- **Read the program's own account.** A guest that writes to the Bochs `0xE9` port has a
  log, and the server filters it for you: the last lines matching a pattern, WHEN a line
  happened (already, or wait for it), what was written since the last stop, or a window
  measured on the guest's own clock.
- **Names, not addresses.** Load the symbol list your toolchain already prints (`nm`, a
  GNU `ld` map, a Borland TLINK map of either generation, an Open Watcom map) and then
  say `_engine_set_rate`, not `00AF:0017A6EC`. Breakpoints and watches are declarations
  that survive a rebuild: recompile, reload the symbols, and they re-resolve themselves.
- **Annotate the program.** A comment by symbol follows it through a rebuild, kept per conf,
  saved to and loaded from a file the project versions beside its symbol file.
- **Read the code.** `disassemble` reads code as instructions at any address, decoded on the
  host in the segment's own 16 or 32-bit width, with call targets and direct memory operands
  named from the loaded symbols. `call_stack` guesses the chain of callers of the routine a
  stop is in, walking the frame pointers and keeping only return addresses that follow a real
  call instruction, always marked heuristic.
- **See what the machine is.** `machine_map` says what the DOS machine is right now: who
  is resident and where, the kernel, the BIOS and the emulator's own blocks, the XMS and
  EMS handles, in protected mode the descriptor tables and the page mapping, and the VGA's
  state as its own listings print it. `interrupt_vectors` says which handler every
  interrupt vector points at, and whose memory it lies in.
- **Read the screen without a window.** `screen_view` gives the screen at this stop as the
  text it holds or, in the 256-colour mode, as a picture of palette indices;
  `screen_signature` folds it into one number to compare instead of reading it; `screen_wait`
  runs the machine until a string appears on the text screen, and stops there; `palette`
  gives the 256 colours of the VGA's DAC, as a table and optionally as a picture.
- **Stop where you mean to.** Run to a symbol and be told whether you arrived, stopped
  somewhere else, or are still running. Break on an interrupt, or on the program's own
  `int 3`. Break when a variable
  changes. Step one instruction at a time with every step read back. Every stop returns
  where it is, the instruction it stopped on with its nearest symbol, the registers, the
  watches you declared, which declaration produced it, and an optional summary of the log.
- **Advance it by frames, or by emulated time.** `run_for` runs the machine for a number of
  frames of the display, one vertical retrace each, or for a number of emulated milliseconds,
  and stops there with that same stop reply, the emulated clock before and after beside it.
- **Trace what it executes.** `trace` runs the machine a counted number of instructions with
  the debugger's CPU log on, hands the log over as a file, each count proved against the
  counter the debugger's register pane keeps, and says which routines ran.
- **Press its keys, move its mouse, and prove it.** `send_keys` and `send_mouse` go in
  INSIDE the machine, through a serial socket and a tiny resident stub: no window comes to
  the front and your own pointer never moves, so it runs beside you while you work. The
  mouse is placed at a screen pixel and read back. Give `expect`, a pattern only the
  program's reaction writes, and the reply says whether the program acted. A swallowed key
  is reported as a miss, never as success.
- **One call per turn, not one per step.** `perform` runs a list of operations and stops
  at the first failure with the whole account; `start(plan=...)` does it on a fresh
  session; `drive` is LOOK, ACT, VERIFY in a single round trip, with what the guest wrote
  since handed back. The server does the segment, selector and mode arithmetic so the
  caller never does.
- **Honest replies, by construction.** Every reply opens with a one-line `summary` (the
  line your client paints for the call) and closes with a `session` block carrying `altered`
  (has anything here written to the machine?). A read that could not look says so as
  `INVALID`, and a wait that expired says what it examined meanwhile. "No line matched" and
  "there was no log" are different answers here.

## Two minutes to a first answer

You need a DOSBox-X built with the debugger (most distribution builds are;
`dosbox-x -helpdebug` listing `-break-start` is the tell): the `dosbox-x` on your `PATH`,
or another build named by `DOSBOX_X_BINARY` or by `start`'s `binary`. And Python 3.11 or
newer.
The debugger wants a terminal, and the server provides one itself. `stop` reaches a running
guest through the debugger's control channel (`mcp_server`), which a current DOSBox-X has.
The saved states (`state_save`, `state_load`) need two debugger commands, `SAVESTATE` and
`LOADSTATE`, that are proposed upstream and not in a release yet: until they are, build the
`scry` branch of [Optimiza/dosbox-x](https://github.com/Optimiza/dosbox-x) (`./autogen.sh &&
./configure --enable-debug=heavy --enable-sdl2 && make`) and name it with `DOSBOX_X_BINARY`.
Absence of any of these is named by the tool that needs it, never worked around.

```sh
pip install .
claude mcp add dosbox-x -s user -- scry-dosbox-x
# or, from a checkout without installing:
claude mcp add dosbox-x -s user -- uv run --directory /path/to/scry-dosbox-x python dosbox_x_server.py
```

Then, from the client:

```
build_check()
start(conf="/path/to/proj/dev.conf", cwd="/path/to/proj",
      seconds=600, logfile="/path/to/proj/build/e9.log")
resume()                      -> {"halted": false, ...}       the guest is running
log_wait(pattern="BOOT", channel="guest", seconds=20)
                              -> {"already": true, "line": "[+  0.412] BOOT  . start",
                                  "waited_s": 0.0, "lines_total": 1, ...}
log(pattern="PERF", channel="guest", limit=5)   -> the last five PERF lines, filtered in the server
close()
```

Your conf needs `bochs debug port e9 = true` for the log to exist at all. Everything about
*your* project comes from you: the conf, the working directory, the program, where a
window goes. The server knows no project and carries no default that points anywhere.
Every path you give is absolute: `~` is not expanded and a relative path is refused, so write
the home directory out (REFERENCE.md, The session, says why).

## Demos

[`demos/bricks/`](demos/bricks/) is a Breakout-like game this repository builds, made to be
debugged: a prompt to give your MCP client, and a `demo.py` that makes the same calls and checks
every answer, from the first stop inside the program to a breakpoint on the routine every
falling brick goes through. Its README carries the transcript of a run, regenerated by the
demo itself.

## Examples

Every example below was run against a real program. Replies are abridged to the fields
that matter; the tools' own descriptions list the rest.

### Stop in a function by name, read a variable, and see what the program logged

A DJGPP program: its `nm` listing is the symbol source, and the base is read off the
running machine, so no arithmetic is needed. The trick is to load the symbols with the
guest stopped INSIDE the program, which an interrupt breakpoint gives you.

```
start(conf="/path/to/proj/conf/dev.conf", cwd="/path/to/proj",
      seconds=600, logfile="/path/to/proj/build/e9.log")
breakpoint_interrupt(number=0x21)
resume()                      -> {"halted": true, "stopped_at": {"cs": "00AF", ...}}
symbols_load(source="/path/to/proj/build/APP.SYM")
                              -> {"parsed": 9652, "kept": 7238, "loaded": 7238, "base_from": "CS", ...}
breakpoint_at(ref="_engine_set_rate")
                              -> {"stored": true, "armed": true, "entry": "BP 00AF:0017A6EC", ...}
watch_add(ref="_g_eng_rate", mode="show", length=4, fmt="u32")
breakpoint_clear(ref="BPINT 21")
resume(e9="since", e9_filter="PERF|audio")
```

The last reply is the stop itself: `stopped_at`, `registers`, `watches` with `_g_eng_rate`
already read as a `u32`, `attribution` naming `_engine_set_rate` as the declaration that
fired, and `e9` holding the lines the guest wrote between the two stops that match your
filter (`since_last_stop`, `shown`, `lines_total` for how many matched and `unfiltered` for how
many there were in all).

### The same thing in one call

```
start(conf="/path/to/proj/conf/dev.conf", cwd="/path/to/proj",
      seconds=600, logfile="/path/to/proj/build/e9.log",
      plan=[{"op": "breakpoint_interrupt", "number": 33},
            {"op": "resume"},
            {"op": "symbols_load", "source": "/path/to/proj/build/APP.SYM"},
            {"op": "breakpoint_at", "ref": "_engine_set_rate"},
            {"op": "watch_add", "ref": "_g_eng_rate", "mode": "show", "length": 4, "fmt": "u32"},
            {"op": "breakpoint_clear", "ref": "BPINT 21"},
            {"op": "resume", "e9": "since"}])
```

`plan` runs those steps on the fresh session and stops at the first failure with the
steps that ran, their replies, and the machine's state. A `resume` in the middle ends the
console part: before the next console step the sequence waits, bounded by `plan_wait`,
for the stop a breakpoint produces. The declarations persist on disk keyed by the conf, so
the next session's plan can be shorter: they re-arm on `symbols_load`.

### Press a key and prove the program took it

The program writes `key_cue_a` on its E9 port from the A-key handler and nowhere else.
That is what `expect` is for.

```
send_keys(keys=["a"], expect="key_cue_a", seconds=5)
   -> {"route": "guest", "posted": 1, "bytes": 2, "ticks": 2,
       "effect": {"checked": true, "seen": true, "expected": "key_cue_a",
                  "line": "[+ 12.407] key_cue_a ...", "seen_before_waiting": false,
                  "lines_before": 2, "waited_s": 0.3, "lines_total": 1}}
```

A modal dialog that swallowed the key comes back `INVALID` with `posted: 1` and
`effect.seen: false`: the key went in, the program did not take it, and the two are never
confused.

### Drive: look, act, verify, in one round trip

```
drive(act=[{"op": "send_keys", "keys": ["a"], "expect": "key_cue_a"},
           {"op": "send_keys", "keys": ["right", "right"]}],
      expect="cue .* set", seconds=5, pattern="cue|PERF", limit=20)
   -> {"status": "ok",
       "act": {"ran": [{"op": "send_keys", "reply": {...}}, {"op": "send_keys", "reply": {...}}],
               "completed": 2, "failed": null},
       "verify": {"checked": true, "seen": true, "line": "...", "seen_before_waiting": false,
                  "lines_before": 5, "waited_s": 0.4, "lines_total": 1},
       "looked": {"e9": {"available": true, "since_mark": 1240, "written": 37,
                         "lines_total": 25, "truncated": true,
                         "lines": [...the 20 most recent matching lines...],
                         "pattern": "cue|PERF"}}}
```

The log is marked once, before the first step. The steps run as `perform` runs them, each
`send_keys` verifying its own `expect`; then the call waits for the act's overall effect
from that same mark; then `looked.e9` is what the guest wrote since, matching `pattern` and
cut to the last `limit`, in `log`'s words. A failed step stops the act and comes back `INVALID` with the account;
so does a miss. An act that ended with the machine stopped at the debugger carries the
enriched stop in `act.stopped`.

### The input route: a conf line, then keys and the mouse

The conf's autoexec runs the shipped stub before its program (a session started with
`program` needs no line: `start` loads the stub first):

```
[autoexec]
mount g "/path/to/scry-dosbox-x/guest"
G:\INJECT.COM
APP.EXE
```

```
start(conf="/path/to/proj/conf/dev.conf", cwd="/path/to/proj",
      seconds=600, logfile="/path/to/proj/build/e9.log")
   -> {..., "input_port": 50432, "stub": "/path/to/scry-dosbox-x/guest/INJECT.COM"}
resume()
send_mouse(x=160, y=100, button="left", expect="clicked")
   -> {"route": "guest", "arrived": true,
       "pointer": {"screen": {"x": 160, "y": 100, "width": 320, "height": 200},
                   "mouse": {"x": 320, "y": 100, "max_x": 639, "max_y": 199},
                   "buttons": [], "mode": "0x13"},
       "effect": {"checked": true, "seen": true, ...}}
```

`x` and `y` are the screen's own units, as `screen_view` counts them (pixels here, mode
13h); the reply reads the pointer back, so a move that did not arrive says so.

### A real-mode program: TLINK map, load segment, run to a symbol

A 16-bit Borland program is loaded at a paragraph decided at run time, and its map prints
offsets from a frame. Reach the program's own code first, then place the map.

```
start(conf="/path/to/proj/conf/dev.conf", cwd="/path/to/proj", seconds=300)
breakpoint_interrupt(number=0x21)
resume()  ... until stopped_at.cs is the program's own segment (the loader's is different)
symbols_load(source="/path/to/proj/build/APP.MAP", base="7DF0")    # (0x0837 - 0x0058) * 16, as hex text
   -> {"parsed": 307, "loaded": 307, "overlay_idle": 80, "unreadable": 0, "base_from": "caller", ...}
run_to(ref="ATTRACT_RUN", control="MAIN_LOOP", seconds=60)
   -> {"arrived": true, "stopped_at": {"cs": "0837", "eip": "00000599", "mode": "Real"},
       "breakpoint_removed": true, "bound_expired": false, "control": {...}, ...}
```

In real mode the same byte has many spellings (`07DF:0599` and `0837:0041` are one
address), and arrival is judged on the linear address, whatever paragraph the program's
`CS` happens to hold when it stops. The breakpoint `run_to` armed is removed once it has
arrived; one it could not arrive at is left armed and the reply says so.

### A window on the guest's clock

A guest that stamps its lines has a clock the server can cut on. Lend the stamp as a
regex with one group and ask for the last N seconds of log at every stop:

```
run_to(ref="_engine_set_rate", control="_vbl_handler", seconds=30, e9="seconds:2",
       e9_stamp="\\[\\+\\s*(\\d+\\.\\d+)\\]", e9_filter="PERF")
   -> {..., "e9": {"lines": [...], "shown": 3, "now": 14.207, "window_s": 2, "unstamped": 0,
                "lines_total": 412, "filter": "PERF"}}
```

"Now" is the latest stamp in the log; a line without a stamp is counted, never placed;
the mode without a stamp is refused before the machine moves.

### Wait for a line, then take a still

```
start(conf="/path/to/proj/conf/dev.conf", cwd="/path/to/proj",
      seconds=120, logfile="/path/to/proj/build/e9.log",
      capture_video=True, program="APP.EXE", captures_dir="/path/to/proj/build/captures")
resume()
log_wait(pattern="READY", channel="guest", seconds=30)     -> {"already": false, "waited_s": 2.1, "line": "...", ...}
captures()                               -> {"captures": [{"path": ".../app_000.avi", "frames": 143, ...}]}
capture_frame(at=140, dest="/path/to/proj/build/captures/ready.png")
```

The video is DOSBox-X's own recording and needs no keypress; the still is an extraction
from it (`ffmpeg`), because the emulator's screenshot is a mapper action with no
non-interactive trigger. Two capture files is the normal case: the recording restarts
when the guest changes video mode.

## The tools

Everything about *your* project comes from you: the config file, the working
directory, the program to run, and where a window should go. The server knows no
project and carries no default that points anywhere in particular.

| tool | what it does |
|---|---|
| `start` | opens a session and stops it at the debugger, ready to be asked things, behind your own windows unless you ask otherwise; `flags` carries the emulator's own options in either mode, and `break_on_int3` makes the guest's own `int 3` a stop |
| `status` | is it up, how much of its bound is SPENT, and whether it has been written to; where it is stopped, in which cpu mode, and how many declarations it holds; a stop the guest reached on its own that no tool has seen yet is recorded here and said in `stopped_on_its_own` |
| `close` | ends it deliberately, and says how: `quit` on the first signal, which is the normal ending because `start` turns the emulator's quit warning off; `killed` only when the signal was ignored |
| `build_check` | what the server can see of its own preconditions, `heavy_debug` among them: whether the build carries the CPU log `trace` needs |
| `symbols_load` | a toolchain's TEXT symbol list into the debugger, so addresses carry names |
| `symbols_find` | look one up: by name, or by where you have stopped (`linear` as hex text) |
| `comment_add` | a comment on a place, by symbol (it follows the symbol through a rebuild) or by `SEG:OFF`; one per place, so another spelling of the same byte replaces its text |
| `comment_list` | every comment with where it lands now (`linear`) and its state; answers on a running guest too |
| `comment_delete` | one comment, by its ref or by any spelling of its place |
| `comment_save` | every comment to a comment file (`dest`, absolute), the record a project versions beside its symbol file |
| `comment_load` | a comment file into the store, all or nothing; where the two disagree, the file wins |
| `machine_map` | what the DOS machine is at this stop, one section per debugger listing (the MCB chain, devices, kernel, BIOS, XMS and EMS, the cpu, the VGA's state as `vga` and, in protected mode, the descriptor tables and paging); a section the debugger cannot list yet is absent, with why. Needs a session started with `logfile` |
| `interrupt_vectors` | `(number=None)`: the vector table, each handler with the block of the MCB chain, the kernel or the BIOS that holds it and, inside the loaded table's span, its symbol; in protected mode the IDT, placed through the GDT, the LDT and the pages. A program's or a TSR's hook shows as the block it lies in. The blocks, and in protected mode the descriptor tables, need a session started with `logfile`; the debugger's file is written into the working directory and removed |
| `breakpoint_at` | a code breakpoint by SYMBOL or by `SEG:OFF`, stored as a declaration that survives a rebuild; a raw-address breakpoint is re-armed at the next session only over the same build FINGERPRINT (the conf and, once a map is loaded, every name the table holds with its linear address, hashed), whoever declared it, and listed `stale` over another |
| `breakpoint_list` | every declaration with its state: armed, unresolved, gone, or a foreign row the store never put there |
| `breakpoint_clear` | one declaration by ref, or all of them; never touches watches, never deletes a foreign row |
| `breakpoint_interrupt` | breaks on an interrupt |
| `watch_add` | N bytes at a name, shown at every stop (`mode="show"`) or breaking when they change (`mode="change"`); the bytes read as a FORMAT of the value grammar: a scalar (`u16`, N of them by `length`), an array (`u16[8]`), a string (`char[16]`) or a struct (`{x:i16,y:i16,flags:u8}`), a sized format implying its length, and a symbol typed by the `types` file `symbols_load` takes reading as its type with no format named |
| `watch_list` | the watch declarations and their state |
| `watch_clear` | one watch by ref, or all; never touches breakpoints |
| `step` | `(count=1, mode="into")`: one instruction at a time, into or over, with every step READ BACK rather than counted out |
| `run_to` | run until a SYMBOL or a `SEG:OFF`, and say where it really stopped: arrived, stopped elsewhere, or still running; the `control` is REQUIRED (a second `ref` known to be hot), so a bound that expires is a measurement and not a silence; it reports its progress while it waits, as do `run_for`, `trace`, `log_wait`, `perform`'s wait for a stop, `drive`, the wait for `expect` in `send_keys` and `send_mouse`, `start` waiting for the debugger prompt, `close` waiting for the emulator to leave |
| `run_for` | `(frames=N)` or `(milliseconds=N)`: run for N frames of the display, one vertical retrace each, or retrace by retrace until the emulated clock has risen N ms, and stop there with the full stop reply; `verdict` says whether the run ran its course (`ELAPSED`), a declared breakpoint stopped it first (`OTHER_STOP`, saying the retrace it leaves pending), or the bound expired (`TIMEOUT`), and the pane's emulated clock says how far it went |
| `trace` | `(instructions=N, shape="normal", dest="")`: run N instructions with the debugger's CPU log on, one line each (`normal`, `short`, `long` or `cs_ip`), and stop with the full stop reply, the log moved to `dest` or to the next `trace-<n>.trace` in the captures directory; the count is proved against the pane's `cc=` counter, which only the normal core keeps in step, and `verdict` is `ELAPSED` or `OTHER_STOP` as for `run_for`; the executed addresses are joined to the loaded symbols, the routines in `symbols` (the lowest-addressed ones, `symbols_total` counting them all) and every address in a set file beside the log |
| `resume` | lets the machine run, and says whether it actually left the debugger: `halted` plus, when it did stop again, `stopped_at`; with `seconds` it waits that long for a stop, listening for the prompt as `run_to` does, and leaves the machine running when the bound expires; nothing has to be declared first, since `stop` brings it back |
| `stop` | brings a RUNNING guest back to the debugger and surveys the stop, headless or windowed, by sending `BREAK` down the emulator's own debugger channel (upstream's `mcp_server`, which the session sets to a port of its own): no window, no menu, no focus taken |
| `registers` | the register pane, as a mapping |
| `disassemble` | code at an address as instructions, decoded on the host in the segment's own width, each line's `flow`, and with symbols loaded the direct targets and memory operands named (`resolved`) |
| `call_stack` | the callers of the routine the stop is in, a heuristic: the frame chain walked, each return kept only where a call instruction ends at it, and why the walk ended |
| `set_register` | writes a register, reads it back (`readback`, `verified`), and marks the session altered, for good |
| `read_memory` | `length` bytes at an address as `hex`, read off the data-view **rows** the debugger printed and returned beside them; INVALID unless that address is among the rows, and above what the rows hold the answer is `memdump` |
| `write` | bytes at a symbol or a `SEG:OFF`, read back (`readback`, `verified`), marking the session altered; a write into ROM is taken and changes nothing, which the readback says |
| `memdump` | `(ref, length, dest)`: memory to a **file**, returning its path; past offset 0xFFFF it reads the memory really there or refuses |
| `find` | `(data_hex, ref, length)`: every address in the range holding the bytes (`hits`, `hits_total`, `truncated`); the debugger has no pattern search, so the range is dumped by `memdump`'s route into a scratch file of the call's own and searched exactly |
| `scan_start` / `scan_filter` / `scan_clear` | the debugger's own value scanner (`MEMFIND` / `MEMS`), for a program with no map: open a range at a cell width, filter it by an operator against a value or, with no value, against what each cell held when the scan opened (`!` keeps the cells that changed, `=` those that did not), read the survivors with their current values, cancel it. ONE scan at a time, held by the debugger: a second `scan_start` is refused in its words. The listing is paged by the debugger and the tool turns the pages with a bare ENTER, because a command typed while a page waits is eaten one keystroke per page |
| `log` | one `channel` of the log, filtered **in the server** by a pattern: `guest` is the program's own 0xE9 instrumentation, `emulator` DOSBox-X's own lines, `all` the file in order with every line tagged; `labels=True` counts the first word of each line |
| `log_wait` | WHEN a line of a channel happened: it answers at once if it already has, and waits if it has not |
| `perform` | a LIST of the server's own operations, checked WHOLE before the first step runs (every refused step listed, nothing run) and then run in order, stopping at the first failure; `summaries=True` cuts every step but the last to its summary line, writes them all to two files and counts the stops |
| `drive` | LOOK, ACT, VERIFY in one call: mark the log, run input steps, wait for the expected reaction, hand back what the guest wrote since; `summaries=True` as in `perform` |
| `send_keys` | keystrokes into the RUNNING guest, verified against the program's own reaction with `expect` |
| `send_mouse` | the guest's pointer placed at a screen pixel and read back, and its buttons clicked, double-clicked or held, verified the same way |
| `captures` | the video captures this session recorded, and what is in them |
| `capture_frame` | one still image out of a capture, returning its path. Always a **PNG**, whatever `dest` is called; a `dest` already there is refused, never deleted |
| `snapshot` | one still of the RUNNING screen, taken inside the guest on any session, confirmed by the new `.png` under the captures directory and moved to `dest` when given |
| `screen_signature` | one number for what is on screen (CRC-32 over the mode, the size, every byte the screen is drawn from and the DAC), to compare instead of reading it; the modes `screen_view` reads. Needs a session started with `logfile` |
| `palette` | `(first=0, count=0, dest="")`: the 256 colours of the VGA's DAC at this stop, as `#rrggbb` and as the six-bit `rgb` the debugger prints; with `dest`, also an indexed PNG of them, one square per entry. Needs a session started with `logfile` |
| `screen_view` | `(dest="")`: what the screen shows at this stop, read from video memory: a text mode as its rows of text with the cursor, the chained 256-colour mode (13h's) as an indexed PNG at `dest`; any other mode is refused naming `capture_frame`. Needs a session started with `logfile` |
| `screen_wait` | `(text, seconds=30)`: runs the machine retrace by retrace until `text` is inside one row of the text screen, and stops there with the stop's registers and attribution; a string already on screen is answered at once (`already`), the machine not moved; a frame that is not text is no match. Needs a session started with `logfile` |
| `state_save` | the machine under a NAME, as `<state_dir>/<name>.sav`, by the debugger's own `SAVESTATE` sent down the debugger channel: no window, no menu, no focus taken. A running guest is stopped for it and released again (`paused`); the file is read back for what it says about itself. Never overwrites; alters nothing. Needs a DOSBox-X that carries the command (see Saved states below) |
| `state_load` | the named state, by the debugger's own `LOADSTATE`, as `state_save` saves; a running guest is stopped for it and released again, a parked one stays parked at the loaded position. A state of another DOSBox-X version, program, memory size or machine type is refused, never asked about. Marks the session altered |
| `state_list` | every state under the session's `state_dir` with the members its ZIP carries (version, program, machine, memory size, stamp), read without loading; no window needed, works while the guest runs |
| `debug` | one command to the debugger console |

## Going further

Every tool's own description, delivered to your client at connection, is its contract. The
WHY behind each contract, what each tool refuses and what it hands back in every case, the
symbol formats, the running-guest rules and how to run the tests are in
[`REFERENCE.md`](REFERENCE.md), one section per family in the order above.

## Licence

MIT. See `LICENSE`.

## Credits

Developed by Optimiza ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).
