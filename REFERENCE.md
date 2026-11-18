# scry-dosbox-x: reference

This page is for a rule that several tools share. It holds the list of tools, the fields every reply carries, and those rules.

Each tool has its own entry, with arguments, reply and example, on its family's page under `docs/reference/`; a family is a group of tools. To install, see the [README](README.md).

## Index

<!-- scry-reference:begin index -->
- [Session](docs/reference/session.md): Checking the DOSBox-X build, starting a session, asking what state it is in, finding its window and ending it. [`build_check`](docs/reference/session.md#build_check), [`start`](docs/reference/session.md#start), [`status`](docs/reference/session.md#status), [`window`](docs/reference/session.md#window), [`close`](docs/reference/session.md#close)
- [Machine](docs/reference/machine.md): What the DOS machine holds at a stop (memory blocks, drivers, interrupt vectors) and what the program and the emulator write to the log. [`machine_map`](docs/reference/machine.md#machine_map), [`interrupt_vectors`](docs/reference/machine.md#interrupt_vectors), [`log`](docs/reference/machine.md#log), [`log_wait`](docs/reference/machine.md#log_wait)
- [Read](docs/reference/read.md): Reading what the stopped program holds: memory, registers, code, and which of its screens is showing. [`registers`](docs/reference/read.md#registers), [`read_memory`](docs/reference/read.md#read_memory), [`disassemble`](docs/reference/read.md#disassemble), [`call_stack`](docs/reference/read.md#call_stack), [`memdump`](docs/reference/read.md#memdump), [`find`](docs/reference/read.md#find), [`screen_map_find`](docs/reference/read.md#screen_map_find), [`screen_map_write`](docs/reference/read.md#screen_map_write)
- [Screen](docs/reference/screen.md): Reading what the screen shows at a stop: its text or its picture, its colours, and a short hash of it. [`palette`](docs/reference/screen.md#palette), [`screen_view`](docs/reference/screen.md#screen_view), [`screen_signature`](docs/reference/screen.md#screen_signature)
- [Scan](docs/reference/scan.md): Finding the address of a value nobody has named yet. [`scan`](docs/reference/scan.md#scan)
- [Write](docs/reference/write.md): Changing the machine: memory, a register, and any command the debugger takes. [`set_register`](docs/reference/write.md#set_register), [`write`](docs/reference/write.md#write), [`debug`](docs/reference/write.md#debug)
- [Hardware](docs/reference/hardware.md): The hardware behind the cpu: I/O ports, the interrupt controllers and the A20 line. [`port`](docs/reference/hardware.md#port), [`pic`](docs/reference/hardware.md#pic), [`a20`](docs/reference/hardware.md#a20)
- [Run](docs/reference/run.md): The tools that let the program run and stop it again. [`run_to`](docs/reference/run.md#run_to), [`run_for`](docs/reference/run.md#run_for), [`trace`](docs/reference/run.md#trace), [`screen_wait`](docs/reference/run.md#screen_wait), [`step`](docs/reference/run.md#step), [`resume`](docs/reference/run.md#resume), [`wait`](docs/reference/run.md#wait), [`stop`](docs/reference/run.md#stop)
- [Breakpoints](docs/reference/breakpoints.md): Breakpoints and watches the server saves by name and sets again in later sessions. [`breakpoint_at`](docs/reference/breakpoints.md#breakpoint_at), [`breakpoint_interrupt`](docs/reference/breakpoints.md#breakpoint_interrupt), [`regpoint_add`](docs/reference/breakpoints.md#regpoint_add), [`watch_add`](docs/reference/breakpoints.md#watch_add), [`declaration_list`](docs/reference/breakpoints.md#declaration_list), [`declaration_clear`](docs/reference/breakpoints.md#declaration_clear)
- [States](docs/reference/states.md): Saved states: the whole emulated machine written to a file, listed, and loaded back. [`state_list`](docs/reference/states.md#state_list), [`state_write`](docs/reference/states.md#state_write)
- [Names](docs/reference/names.md): Symbol names for addresses: load your program's symbol table, then look up a name or an address in it. [`symbols_load`](docs/reference/names.md#symbols_load), [`symbols_find`](docs/reference/names.md#symbols_find)
- [Comments](docs/reference/comments.md): Notes on addresses of the program, saved with the breakpoints and shown in the disassembly. [`comment_list`](docs/reference/comments.md#comment_list), [`comment_write`](docs/reference/comments.md#comment_write)
- [Input](docs/reference/input.md): Sending keys, mouse buttons and pointer moves to the DOS program, and checking that it reacted. [`send_keys`](docs/reference/input.md#send_keys), [`send_mouse`](docs/reference/input.md#send_mouse)
- [Captures](docs/reference/captures.md): Saving the screen and the sound to files: a still, a series of frames, a video, a recording, and the list of them. [`captures`](docs/reference/captures.md#captures), [`capture_frame`](docs/reference/captures.md#capture_frame), [`series_capture`](docs/reference/captures.md#series_capture), [`snapshot`](docs/reference/captures.md#snapshot), [`record`](docs/reference/captures.md#record), [`audio_record`](docs/reference/captures.md#audio_record)
- [Files](docs/reference/files.md): Comparing pictures and recordings on disk, in numbers, and checking a file the DOS program wrote. [`image_compare`](docs/reference/files.md#image_compare), [`audio_compare`](docs/reference/files.md#audio_compare), [`guest_file`](docs/reference/files.md#guest_file)
- [Sequences](docs/reference/sequences.md): Running several calls as one: a list of steps, an input with its check, and a session written as a replay script. [`perform`](docs/reference/sequences.md#perform), [`perform_export`](docs/reference/sequences.md#perform_export), [`drive`](docs/reference/sequences.md#drive)
- [Project](docs/reference/project.md): Saving what a session learned into the repository's `.scry/` folder, after a review. [`promote`](docs/reference/project.md#promote)
<!-- scry-reference:end index -->

## The session

A session is one DOSBox-X that `start` launches, stopped at its debugger, and the server keeps until `close`.

- **One call at a time.** Calls take turns: a second one waits for the first.
- **Which DOSBox-X runs.** `start` and `build_check` use `binary`, else the `DOSBOX_X_BINARY` variable, else the `dosbox-x` on your `PATH`: the first of these that is set. A value that names no executable is refused, never skipped: you would be measuring another emulator.
- **Paths.** A path argument is absolute or starts with `~`; a relative one is refused, because the server and the emulator run in different folders. An optional path left empty counts as not given.
- **When a path is checked.** Its form is checked before anything else happens. The file itself is checked at the call: a file a tool writes needs its folder to exist and nothing at its name, a dangling link included.
- **The server's end.** However the server stops, its emulator stops too: on Windows the system ends it, elsewhere a watchdog process listed as `scry-dosbox-x-guardian`. The emulator also ends when `start`'s `session_seconds` run out.
- **A dead emulator.** The session is kept until `close`. Every call that needs the machine answers `session_broken`, and `altered` is not lost.

### Files the debugger writes

`memdump`, `trace` and `interrupt_vectors` have the debugger write a file in the emulator's working folder, which is your project. A file already there is reported and left alone, never deleted, and a dangling link counts as a file. A dump that fails after the debugger wrote removes its own file.

### The orange edge of the window

While a session is live the emulator's window has an orange edge, so a person at the computer knows it is in use. It is bright while a call that can change the program is in progress, and dim otherwise, even over a program `resume` left running. Once `send_mouse` has moved the program's pointer, an orange pointer marks it.

The emulator draws both after a frame is handed to capture, so no capture shows them and no tool that reads the screen sees them.

The tools: [Session](docs/reference/session.md).

## What every reply carries

Every reply has the same outer fields, whichever tool answers, so you read any answer the same way.

<!-- scry-reference:begin envelope -->
- `summary` (string)
- `status` (one of `"ok"`, `"INVALID"`)
- `code` (string)
- `message` (string)
- `omitted` (array of string)
- `how` (string)
- `note` (string)
- `cancelled` (object)
- `session` (object)
- `answers_while_running` (array)
- `exit_code` (integer or object)
- `last_stop` (object)
- `stopped_on_its_own` (object)
- `applied_on_stop` (object)
- `symbols_placed` (object)
<!-- scry-reference:end envelope -->

What each one is for:

- `summary`: one line saying what happened.
- `status`: `ok`, or `INVALID` for a refusal.
- `code`, `message`: a refusal's word, from a fixed list, and its reason.
- `omitted`, `how`: fields left out to keep the reply short, and the call that returns them.
- `note`: what the other fields do not say; absent when there is nothing to add.
- `session`, `cancelled`: described below.
- `answers_while_running`: on a refusal because the program runs, the tools that still answer.
- `last_stop`: the last stop the server saw.
- `stopped_on_its_own`: the program stopped while no call waited; said once, by the next reply.
- `exit_code`: the emulator's, when it ended during the session.
- `applied_on_stop`: what you asked for while the program ran, applied now that it stopped.
- `symbols_placed`: said once, at the stop where the symbol table given to `start` got its addresses.

### The `session` block

`session` closes every reply. It says `alive` (the emulator is up), `running` (the program runs, not stopped at the debugger) and `altered`.

**`altered` says something wrote to the machine.** A write is allowed, and every later reply then says `altered: true`: a measurement on a forced value does not describe the program's own run. On a DOSBox-X built without heavy debugging, a code breakpoint is an `INT 3` byte in memory, so setting one counts.

**`running` is never a guess.** When a `resume` got no answer, the server reads the state again. If that fails too, `running` is `{"available": false, "why": "..."}`, never `true` for a stopped machine.

A warning appears only while it holds:

- `program`: the program `start` launched has ended, until it runs again. `state` is `exited` or `fault`, and `fault` quotes the screen. A wait that then expires opens its `note` with it.
- `range_widened`: `send_mouse` widened the mouse driver's range to reach the whole screen.
- `conf_changed_on_disk`, `image_changed_on_disk`: the config file, or the executable its symbols were loaded for, changed after the session read it.
- `output_bytes_dropped`: the emulator printed more than the server keeps.

### A refusal

A refused call answers `status: INVALID` with `code` and `message`, and its context in plain fields beside them, such as `last_stop`.

- The schema refuses a wrong type as `bad_argument`, and an unknown argument name too. Nothing is converted: `"16"` is not 16.
- A fixed list of words or a range is published in the schema as `enum`, `minimum` and `maximum`.
- A value that is wrong with or without a machine is refused `bad_argument` even with no session, never `no_session`.
- Finding nothing is not a refusal. "No line matched" is an empty list; "there is no log to search" is `INVALID`.
- A refusal is a normal reply: MCP's `isError` is for a failure of the server itself.

A field that could not be read is `{"available": false, "why": "..."}` where its value would be; no reply carries a null. Every tool publishes its reply's shape as `outputSchema`, and its description says when a field comes only in some cases.

### One name for each thing

- `ref` is an address: a symbol or a `SEG:OFF`.
- `seconds` is the real time a call may wait, `count` how many, `first` from where, `length` how many bytes, `limit` how many rows come back.
- `dest` is the file a call writes and `path` the file it reads.
- `_s` ends a name in seconds, and `<list>_total` is how many a list holds, listed or not.
- A value the machine holds comes back as `0x` text at its width, the spelling an argument takes back.

### How a wait ends

A tool that waits answers `status: ok` with a `verdict`:

- `TARGET`: what it waited for happened.
- `ELAPSED`: the emulated time you asked for passed.
- `TIMEOUT`: `seconds` ran out. `run_to`, `run_for`, `trace` and `screen_wait` then stop the program. `resume`, `log_wait`, an input's `expect` and a sequence's wait for a stop leave it running.
- `OTHER_STOP`: a stop the call did not ask for ended it.

A call that could not finish is a refusal with no `verdict`: `wait_stopped`, `not_settled` or `session_broken`.

`seconds` is more than zero and at most 600. `resume`'s `seconds` and every `settle_seconds`, a sequence's wait for a stop, also take 0: no wait. The ceiling is there because no other tool answers during a wait, `status` included.

### A long wait, and a cancelled call

A long wait reports progress about once a second, as MCP progress notifications.

**A cancelled call answers nothing**, since the protocol sends no response to one. It ends at the next check of its wait, as its own time limit would end it. Cancelling a step cancels its whole sequence.

**The next reply says what it left**, once, in `summary` and in `cancelled`: `tool`, `after_s`, `left` and `earlier`, the cancelled calls not yet reported. A call cancelled while it waited its turn did nothing and leaves no record.

| End | What the cancel leaves | Tools |
|---|---|---|
| `stop` | The program stopped by `BREAK`, as `stop` leaves it, and read in the next reply's `last_stop`. A `run_to` removes its own breakpoints. A `trace`'s open CPU log is closed and kept as `trace-cancelled-<n>.trace` in the captures folder, else the working folder. | `stop`, `run_to`, `run_for`, `trace`, `screen_wait`, `record`, `audio_record`, `perform` |
| `kill` | The emulator closed. A `close` cancelled half-way still finishes. | `start`, `close` |
| `none` | The program as the call found it. | `build_check`, `status`, `log`, `log_wait`, `registers`, `read_memory`, `disassemble`, `call_stack`, `memdump`, `find`, `scan`, `debug`, `set_register`, `write`, `resume`, `wait`, `step`, `state_write`, `snapshot`, `state_list`, `breakpoint_interrupt`, `regpoint_add`, `symbols_load`, `symbols_find`, `comment_write`, `comment_list`, `machine_map`, `interrupt_vectors`, `palette`, `screen_view`, `screen_signature`, `screen_map_write`, `screen_map_find`, `series_capture`, `image_compare`, `audio_compare`, `breakpoint_at`, `declaration_list`, `declaration_clear`, `watch_add`, `send_keys`, `send_mouse`, `captures`, `capture_frame`, `perform_export`, `drive`, `port`, `pic`, `a20`, `guest_file`, `window`, `promote` |

Two tools of the last row still do something. A cancelled `state_write` ends at the emulator's next answer: a save removes its file, and a load counts as a write. Input sent to a stopped machine runs it frame by frame, and a cancel leaves it stopped with the input sent so far in.

The tools: every one in the [Index](#index).

## Names for addresses

An address argument, `ref` in most tools, is a symbol of your program or a `SEG:OFF`, whatever mode the CPU is in.

- **You say the same thing in real and protected mode.** The server reads the CPU mode and gives the debugger the kind of segment that mode uses. A `SEG:OFF` is hex, with or without `0x`, and takes no sign.
- **An offset is as wide as the CPU mode**: 32 bits in protected mode. In real mode an offset past `0xFFFF` addresses nothing and is refused.
- **Symbols come from `symbols_load`**, or `start`'s `symbols`. It reads text a toolchain already writes, such as an `nm` listing or a linker map, and no binary symbol format.
- **A symbol table needs a base.** The debugger holds linear addresses and a toolchain writes offsets. A base of zero is never assumed: it would name whatever sits in low memory.
- **A base is an address**: `0x` text or an integer, like `symbols_find`'s `linear`. Bare hex digits are refused.
- **A name is found whatever its case**, and a saved breakpoint keeps the `ref` as you typed it. A name two symbols share is refused as ambiguous.
- **A missing name is a fact about the build.** A function the compiler inlined has no symbol.

### Addresses in a reply

A segmented address is `SSSS:OOOOOOOO`, under `seg_off`, or `address` in a stop's `instruction`. A linear one is `addr`: `0x` and eight digits. `pc` is segmented, with `cpu_mode` beside it.

A `ref` you give is matched and saved in upper case, as `SSSS:OOOO` up to `FFFF` and `SSSS:OOOOOOOO` past it: `814:10b` is `0814:010B`. One spelling stays the debugger's own, a breakpoint as its `BPLIST` shows it: `run_to`'s `target`, a row's `entry`.

The tools: [Names](docs/reference/names.md).

## Breakpoints and watches

The server saves each breakpoint, watch and registerpoint as you asked for it, and sets it again in later sessions.

A registerpoint is a stop when a condition on the registers comes true.

- **What is saved is what you asked for, not the debugger's row.** A symbol's address moves with every rebuild, so each `symbols_load` looks it up again and sets it. The tools call a saved one a declaration.
- **A symbol that no longer exists is kept**, as `unresolved`, and its row says why.
- **Each one is confirmed by reading the debugger's `BPLIST` back**, not by its acknowledgement. One debugger row is one saved breakpoint.
- **A comment is saved beside them and stops nothing.** It is never set, never counted in `status`'s `declarations`, and clearing breakpoints leaves it.

### What is saved between sessions

- **One file per program**, found by the config file and the name of the program run under it. Two programs never get each other's breakpoints.
- **Nothing expires.** A row another session left is shown as such, and cleared by its `ref`.
- **A raw `SEG:OFF` belongs to one build.** It is set again while the loaded symbol table still describes that address the same way, and is `stale` otherwise. Saving it again takes it over.
- **A raw `SEG:OFF` belongs to one CPU mode**, that of the stop where it was set. At a stop of the other mode it is `unarmable`, and `why` names the mode it waits for.
- **`start` stops in real mode**, so it sets no protected-mode row; a `symbols_load` at a protected-mode stop does. If `start` cannot read the debugger's list, the session still starts and `rearm_refused` says why.
- **A relinked program run in the same session is not noticed** until the next one: a loaded symbol table is taken as the running program.

The tools: [Breakpoints](docs/reference/breakpoints.md), [Comments](docs/reference/comments.md).

## Running and stopping

The program is either stopped at the debugger or running, and the debugger reads the machine only while it is stopped.

`start` leaves it stopped. A running program stops at a breakpoint set before it was resumed, or at `stop`. The server invents no stop, and never gives memory it read earlier as a current value.

**While it runs, a tool that reads the machine refuses** `not_stopped`, with `last_stop` and `answers_while_running`. These answer:

- every tool of Breakpoints, States, Input, Files, Sequences and Project;
- `status`, `window`, `close`, `log`, `log_wait`, `wait`, `stop`, `symbols_find`, `comment_list`, `captures`, `capture_frame`, `series_capture`, `snapshot`;
- `comment_write(method="save")`, `screen_map_write` with `load`, `save` or `pointer`, and `registers(from_last_stop=True)`.

**What you ask for while it runs is applied at the next stop**, before anything is read. Until then a breakpoint answers `pending`, and the lists answer from what the server holds, with `debugger_read: false`. The reply that meets the stop says `applied_on_stop`.

**A stop nobody waited for is reported once**, in `stopped_on_its_own`, by the first tool that finds the program stopped.

### What a stop returns

Every reply that ends at a stop carries the same readings:

- `stop_seq`: the number of this stop, the one `last_stop` names.
- `pc` and `cpu_mode`: `real`, `protected`, `paged` or `VM86`.
- `frame`: display frames since power-on.
- `instruction`: the instruction at `pc`, decoded as `disassemble` decodes it, with the comment saved there.
- `regs` and `watches`: the registers, and the value of each watch.
- `cause`: what stopped the program.
- `e9`: the lines the program wrote to port `0xE9`, a debug port a DOS program can log to, since the last stop.

`cause` names the saved breakpoint at that address, the registerpoint, a `run_to`'s own target, your `stop`, or the time limit or frame a run ended at. Otherwise it says it cannot tell: a debugger row has no hit flag, and a memory watch stops at the instruction that wrote.

`e9` is cut to a limit, and its `how` gives the `log` call that reads the rest. Without `start`'s `logfile` there are no lines.

### A trace says which routines ran

`trace` gives each executed address a linear address, where the CPU mode allows one, and the nearest symbol at or below it. The symbol table has no sizes. So code above the last symbol gets no name, unless the table also lists the data after the code, as `nm` does.

A log line that says its own CPU mode is read in that mode. The others are read in the mode the stop shows at both ends of the trace. A line whose code segment cannot be read gets no linear address, and `note` says so.

A trace whose stop never comes is interrupted where it stood, and what its log holds up to there is returned. A log the machine closed first is refused, since its lines are not what ran.

The tools: [Run](docs/reference/run.md).

## Reading and writing

A tool that reads needs the program stopped and answers narrowly, so what comes back is the answer and little else.

- **Every count has a ceiling.** A reply that leaves something out says so in `omitted`, and `how` gives the call that returns it.
- **For a value, use `registers`, `read_memory`, `memdump` or `log`.** `debug`, the raw debugger command, is the last resort.
- **A write sets `altered`**, as [What every reply carries](#what-every-reply-carries) explains.
- **A file's name is written by [one rule](https://github.com/scry-mcp/scry-core/blob/main/docs/file-names.md)**: `Shot_1.PNG` becomes `shot-1.png`, and a name with no extension is refused. The reply's path is the file as written, with a `note` when the name changed. A folder `dest` keeps its name.

The tools: [Read](docs/reference/read.md), [Write](docs/reference/write.md), [Scan](docs/reference/scan.md), and `machine_map` and `interrupt_vectors` on [Machine](docs/reference/machine.md).

## The log

`log` and `log_wait` search one log of the session by pattern: what the program wrote, what the emulator wrote, or the DOS calls the program made.

- **`channel` picks the log.** `guest` is the lines the program wrote to port `0xE9`, `emulator` the emulator's own, and `all` both, from `start`'s `logfile`. `dos` is every INT 21h with its result, on a session started with `dos_calls`.
- **`since_mark` reads only what follows a position.** After a saved state is loaded the program writes the same lines again, so only a position tells old from new. A state load answers it as `mark`.
- **A `mark` is a byte position in the file, not a moment.** A line the emulator had not written out when the load was sent lands after it. `dos` takes none.
- **Only whole lines are read.** A line still being written is read once it is complete, and a wait takes one last read before it ends.
- **A wait on a stopped program ends at once**, refused `wait_stopped`, because a stopped program writes nothing. A stop during the wait comes back as the stop.

The tools: [Machine](docs/reference/machine.md) for `log` and `log_wait`.

## The machine's hardware

`port`, `pic` and `a20` type the debugger's own `IN` and `OUT`, `PIC` and `A20` commands, to read and drive the hardware under a program.

- **A port no device answers is refused, not read.** The emulator would answer such a read with all ones, which looks like a device that answered `0xFF`.
- **Every port access sets `altered`, a read too**: reading a port is a bus cycle the device sees.
- **The timer is IRQ 0**, so `pic(method="raise", irq=0)` runs its handler on demand.

The tools: [Hardware](docs/reference/hardware.md).

## Files inside DOS

A DOS program hands a result back as a file on a mounted drive, and the server tells you whether this run wrote it.

`start(guest_files=[...])` notes each file's size, time and hash before the emulator boots, and `guest_file` and `close` then say what the program left. A file from an earlier run passes any "is it there" test, so one that did not change is `unchanged` and refused. Only new bytes or a new time make it `written`.

The check reads your computer's file. A file the program still holds open may lack its bytes, because the emulator keeps them until DOS closes it.

The tools: [Files](docs/reference/files.md) for `guest_file`.

## Several calls as one

`perform` runs a list of calls in order as one call, and `drive` runs one and then waits for a line of the program's log.

- **The whole list is checked before its first step runs**, even with no session. A mistake in step 4 does not press the keys of steps 1 to 3. `start(plan=...)` runs such a list on the new session.
- **After a `resume` step, the steps that answer on a running program run at once.** A breakpoint set there answers `pending` and is set at the next stop.
- **Before any other step the sequence waits for the stop**, up to `settle_seconds`. A list that ends with the program running waits only while a saved breakpoint can still stop it.
- **Messages count steps from 1**; the indexes in a reply, `failed_at` and each `step`, count from 0.

The tools: [Sequences](docs/reference/sequences.md).

## From a session to a test that replays itself

A session can be written out as a list of steps and played back later with no model, as a test.

Every session is recorded from the `start` that succeeds; the next `start` clears the recording and `close` keeps it. `perform_export` writes it as a document, and this command replays it from this repository:

```sh
uv run python -m scry_core.replay <document> [--binary PATH] [--transcript PATH]
```

- Exit 0: every step gave its recorded values again.
- Exit 1: a step failed or gave other values.
- Exit 2: the command line was wrong.
- Exit 3: nothing was shown. No step has recorded values, the `start` was refused, the server broke, or a saved state or breakpoint the document needs is missing.

A step that left the program at a new stop is compared by its `regs` and its `frame`. A replay gives the same values on a config with fixed cycles, `cycles=fixed <n>`; under `cycles=max` the program's clock follows your computer's. The document carries `start`'s arguments as given, your paths included.

The tools: [Sequences](docs/reference/sequences.md).

## The `.scry/` folder

A repository can keep how a session starts on its program in a `.scry/` folder it tracks, so a session gives only what belongs to its own run.

- `.scry/start/`: start profiles, each a saved set of `start` arguments, for `start(profile=...)`.
- `.scry/maps/`: screen maps, for `screen_map_write(method="load")`.
- `.scry/perform/`: saved step lists, for `perform(path=...)`.

**A session writes nothing there by itself.** It saves what it learned as drafts; `promote` shows them for review and writes the ones you approve. Paths in these files use placeholders, by [this rule](https://github.com/scry-mcp/scry-core/blob/main/docs/store-paths.md), so a file reads the same on any computer.

**Each draft belongs to one repository**: the one a call read it from, else the one of the current `start`. That is its profile's repository, or the one its program runs in, by `cwd` or else the `conf`'s folder. Without `root`, `promote` writes a draft only there, never into another repository or the server's own clone.

The tools: [Project](docs/reference/project.md).

## Input and the screen

Input goes in inside the emulated machine and the screen is read from its video memory, so neither depends on your window, keyboard or mouse.

- **Nothing on your computer is touched.** No window comes to the front, your pointer never moves, no accessibility permission is asked for, and the window's scale changes nothing the program sees.
- **Reading the screen never changes it.** The tools read video memory and the palette, and touch no register, latch or frame timing.
- **`record` and `audio_record` capture between two stops**, through the debugger's `CAPTURE` command, so no window or menu is involved either.

The tools: [Input](docs/reference/input.md), [Captures](docs/reference/captures.md), [Screen](docs/reference/screen.md), and `screen_wait` on [Run](docs/reference/run.md).

## Media files

The tools that answer about pictures and sound give the cheapest answer that settles the question.

A fingerprint or a number comes first: "is it the same screen" is two strings compared, never two pictures sent. The whole picture comes last, only from a tool made to show one. A sound is never sent, only its measures.

A tool that fingerprints or compares a picture takes a `crop`, `[x, y, width, height]`. One that leaves the picture is refused, never padded, since padding compares pixels nobody drew. A recording is cut by a `window` in seconds instead.

The tools: [Captures](docs/reference/captures.md), [Files](docs/reference/files.md), [Screen](docs/reference/screen.md).

## Screen maps

A screen map is a file that names a program's screens and the areas of each, so you say "the play screen" instead of a picture and a coordinate.

Its format is on the Read page.

The tools: [Read](docs/reference/read.md) for `screen_map_find` and `screen_map_write`, [Input](docs/reference/input.md) for `send_mouse`.

## Saved states

A saved state needs the debugger commands `SAVESTATE` and `LOADSTATE`, which a build may lack.

On a build without them both methods of `state_write` are refused `no_channel`, naming the command. [Debugger commands](#debugger-commands) lists what each command gives.

The tools: [States](docs/reference/states.md).

## The debugger connection

Every reading and every command goes to DOSBox-X's debugger over one connection, a request at a time, and the debugger's screen is never read.

- **The config setting is `[dosbox] mcp_server`.** A build whose debugger can run with no screen, `[dosbox] debugger headless`, is started that way. Another gets a terminal nobody reads on macOS, or a hidden console on Windows.
- **A reply longer than the connection keeps is refused**, never read as whole.
- **`debug` is the raw command**, and returns the lines it printed.

### Debugger commands

Some tools need a debugger command a build may lack. `build_check` and `start` list the ones a build has, in `debugger_commands`. A tool that needs a missing one is refused `no_channel`, naming it, before anything acts.

| Command | What it gives | Needed by |
|---|---|---|
| `RUNSTATE` | Whether the program is stopped, and the frame count behind each stop's `frame` and `perform`'s `until_frame` | `run_to`, `run_for`, `trace`, `screen_wait`, `record`, `audio_record`, `step(mode="over")`, `resume` with `seconds`, input to a stopped machine, any reading after a `resume` |
| `STEPIN` | One instruction run | `step` |
| `SAVESTATE`, `LOADSTATE` | A saved state | `state_write` |
| `PRESENCE` | The orange edge | the edge itself |
| `BPIF` | A stop on a register condition | `regpoint_add` |
| `VGAMEMDUMP` | Video memory as the card holds it | `screen_view`, `screen_signature` in a planar, unchained or linear mode |
| `CAPTURE` | A sound or video capture between stops | `record`, `audio_record` |
| `TAP` | Reads and writes logged without stopping | `watch_add` with `mode` `count` or `capture` |
| `PORTINFO` | Which accesses of a port reach a device | `port` |
| `DOSTRACE` | Every INT 21h, into a file | `log` and `log_wait` on `dos`, `start(dos_calls=True)` |
| `PIC`, `A20` | The interrupt controllers, the A20 line | `pic`, `a20` |
| `MEMDUMPLIN` | Memory by linear address | reads by linear address, `send_mouse` in protected mode |

Without `RUNSTATE` a session still starts. Every reading answers at the stop `start` leaves, and input, breakpoints and `snapshot` work. `resume` with no `seconds` lets the program run, saying nothing will tell when it stops; `stop` brings it back.

The tools: [Write](docs/reference/write.md) for `debug`, [Session](docs/reference/session.md) for `build_check`.
