# scry-dosbox-x: reference

The [README](README.md) is the front door. This page holds the index, the envelope and what every family shares: the session, what every reply carries, a cancelled call, names for addresses. Each family's tools, with the reason their contract is shaped as it is, are on their own page under `docs/reference/`.

## Index

<!-- scry-reference:begin index -->
- [Session](docs/reference/session.md): [`build_check`](docs/reference/session.md#build_check), [`start`](docs/reference/session.md#start), [`status`](docs/reference/session.md#status), [`close`](docs/reference/session.md#close)
- [Read](docs/reference/read.md): [`registers`](docs/reference/read.md#registers), [`read_memory`](docs/reference/read.md#read_memory), [`disassemble`](docs/reference/read.md#disassemble), [`call_stack`](docs/reference/read.md#call_stack), [`memdump`](docs/reference/read.md#memdump), [`find`](docs/reference/read.md#find), [`log`](docs/reference/read.md#log), [`log_wait`](docs/reference/read.md#log_wait), [`machine_map`](docs/reference/read.md#machine_map), [`interrupt_vectors`](docs/reference/read.md#interrupt_vectors), [`palette`](docs/reference/read.md#palette), [`screen_view`](docs/reference/read.md#screen_view), [`screen_signature`](docs/reference/read.md#screen_signature), [`map_find`](docs/reference/read.md#map_find), [`map_write`](docs/reference/read.md#map_write), [`debug`](docs/reference/read.md#debug)
- [Scan](docs/reference/scan.md): [`scan`](docs/reference/scan.md#scan)
- [Write](docs/reference/write.md): [`set_register`](docs/reference/write.md#set_register), [`write`](docs/reference/write.md#write)
- [Advance](docs/reference/advance.md): [`run_to`](docs/reference/advance.md#run_to), [`run_for`](docs/reference/advance.md#run_for), [`trace`](docs/reference/advance.md#trace), [`screen_wait`](docs/reference/advance.md#screen_wait), [`step`](docs/reference/advance.md#step), [`resume`](docs/reference/advance.md#resume), [`stop`](docs/reference/advance.md#stop)
- [Declarations](docs/reference/declarations.md): [`breakpoint_at`](docs/reference/declarations.md#breakpoint_at), [`breakpoint_interrupt`](docs/reference/declarations.md#breakpoint_interrupt), [`watch_add`](docs/reference/declarations.md#watch_add), [`declaration_list`](docs/reference/declarations.md#declaration_list), [`declaration_clear`](docs/reference/declarations.md#declaration_clear)
- [States](docs/reference/states.md): [`state_list`](docs/reference/states.md#state_list), [`state_write`](docs/reference/states.md#state_write)
- [Names](docs/reference/names.md): [`symbols_load`](docs/reference/names.md#symbols_load), [`symbols_find`](docs/reference/names.md#symbols_find)
- [Comments](docs/reference/comments.md): [`comment_list`](docs/reference/comments.md#comment_list), [`comment_write`](docs/reference/comments.md#comment_write)
- [Input](docs/reference/input.md): [`send_keys`](docs/reference/input.md#send_keys), [`send_mouse`](docs/reference/input.md#send_mouse), [`drive`](docs/reference/input.md#drive)
- [Captures](docs/reference/captures.md): [`captures`](docs/reference/captures.md#captures), [`capture_frame`](docs/reference/captures.md#capture_frame), [`series_capture`](docs/reference/captures.md#series_capture), [`snapshot`](docs/reference/captures.md#snapshot)
- [Files](docs/reference/files.md): [`image_compare`](docs/reference/files.md#image_compare)
- [Lists](docs/reference/lists.md): [`perform`](docs/reference/lists.md#perform), [`perform_export`](docs/reference/lists.md#perform_export)
<!-- scry-reference:end index -->

## The session

The session tools: [Session](docs/reference/session.md).

**Which DOSBox-X runs is resolved once per `start` and per `build_check`, and said**: the `binary` argument, else `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`, the first rung holding a value. A value naming no executable is refused (`bad_argument` for the argument, `host_failed` for the variable or PATH), never passed over for the next rung: a caller who named a build and got another would be measuring the wrong emulator. A failed version probe never fails the call.

**Every path you give is absolute or starts with `~`, which is expanded.** A relative path is refused because it would be judged against one directory and used in another (this server's working directory is wherever the client launched it, the emulator's is `cwd`). An optional path left empty is not given.

The SHAPE is judged before anything happens: before the session gate, and for `start` before a live session, the binary or the store is looked at. The FILESYSTEM is judged at the call: a file a tool writes has its directory there (nothing creates it) and nothing at it yet, a dangling link included, unless the tool says it replaces; a file a tool reads is a regular file there. `start` creates `captures_dir` and `state_dir` with their parents just before the emulator starts. Any other file at `logfile` is overwritten, so a log named after one of the guest's own programs replaces it. A symbol map is read leniently, because a DOS toolchain's map may carry code page 437 bytes.

**Files the debugger itself writes: it refuses rather than deleting.** `memdump`, `trace` and `interrupt_vectors` have the debugger write in the emulator's working directory, which is somebody's project. Unlinking with the error suppressed would rest the staleness guarantee on an error nobody reads: the unlink fails quietly, the debugger prints its success line anyway, and a stale file comes back with a byte count. So a file already sitting there is reported and left alone. A dangling link at the place the debugger writes is a file there too (it would write through the link, onto whatever it names). A dump that fails after the debugger wrote takes its own file away, so the next call is not refused over it.

### The presence indicator

While a session holds the window, an orange edge tells whoever sits at the host to keep their hands off: dim from `start` to `close`, bright while a call that can change the guest runs, `debug` included. It marks calls, not the machine, so a machine left running by `resume` shows the dim edge. A failure to draw it never changes another reply.

**It is drawn by the emulator, never into the evidence**: after the frame was handed to capture, so `snapshot`, `capture_frame` and `series_capture` never carry it, and `screen_view` and `screen_signature`, which read the VGA memory and the DAC, never see it. A capture is the emulated screen and nothing else.

## What every reply carries

<!-- scry-reference:begin envelope -->
| field | type |
|---|---|
| `summary` | string |
| `status` | one of `"ok"`, `"INVALID"` |
| `code` | string |
| `message` | string |
| `omitted` | array of string |
| `how` | string |
| `cancelled` | object |
| `session` | object |
| `answers_while_running` | array |
| `applied_on_stop` | object |
| `exit_code` | integer or object |
| `last_stop` | object |
| `stopped_on_its_own` | object |
<!-- scry-reference:end envelope -->

**Every reply opens with a `summary` and closes with a `session` block carrying `altered`.** Writing to a live machine is allowed, and a measurement on a forced state is not a measurement of the program; the reader three questions later has no other way to know. The first contact after a stop applies the declarations made while the guest ran, so a reader can be the call that arms a breakpoint; that write belongs to the declaring call (`pending`), and the reader says `applied_on_stop`.

**A session whose emulator died is kept until `close`**: every call that needs the machine answers `session_broken`, and `altered` survives, which a caller measuring a forced state must not lose.

**A refusal is one contract.** An INVALID carries `code`, one word from a fixed table, and `message`, flat beside the context (`last_stop`, `posted`, `route`, `failed_at`); a code outside the table or an empty message is refused where it is written. A bad argument is a refusal, not an execution failure: `isError` is for a bug. The schema is strict: a wrong type or an unknown argument name is refused as `bad_argument` naming it, and nothing is coerced (`"16"` is not 16), except that an integer stands for a number. `outputSchema` constrains no value, because any datum may come back as `unavailable(why)`.

**A value as wrong with no machine as with one is judged before the session gate**, so with no session it answers `bad_argument`, never `no_session`.

An argument held to a vocabulary lists its words as its schema's `enum`, a scalar held to a range publishes `minimum` and `maximum`. Three ranges are wider than their judge: `input_port` is also refused from 1 to 1023, `symbols_find`'s `limit` is judged on the `name` question only, and `palette`'s `first + count` may not pass 256.

**A read that found nothing says which kind of nothing.** "No line matched" is an empty list; "there is no log to match against" is `INVALID`. A caller that cannot tell them apart reports a broken instrument as a clean result.

**Reads are narrow on purpose**: what crosses back is the answer, not a haystack. Every count a reader takes has a ceiling as well as a floor, and a reply that answers less than everything carries `omitted` and `how`.

**One rule for every wait.** A wait answers a `verdict` with `status: ok`: `TARGET`, `TIMEOUT`, `OTHER_STOP` or `ELAPSED`. The bound INTERRUPTS a run (`run_to`, `run_for`, `trace`, `screen_wait`) and LEAVES running a wait that only listens (`resume`, `log_wait`, an input's `expect`, `perform`'s wait for a stop). A wait nobody asked for carries no verdict. What could not finish still refuses: `wait_stopped`, `not_settled`, `session_broken`.

**One spelling per concept, the Scry servers' own** (`ref`, `seconds`, `count`, `first`, `length`, `limit`, `dest`, `path`, `_s`, `<list>_total`). **A datum that could not be read is `{"available": false, "why": ...}` in the place its value would have taken: no reply carries a null.** A value the machine holds comes back as `0x` text at its holder's width, the spelling an argument takes back.

- `pc` is `SSSS:OOOOOOOO` with `cpu_mode` beside it: a DOS place is segmented.
- `run_for` counts frames as vertical retraces; `trace(instructions)` counts instructions run, `step(count)` steps taken.
- `snapshot` refuses a machine parked at the debugger (the guest's own stub takes the command).
- A breakpoint keeps the debugger's spelling (`target`, `controls[].at`, `entry`): it is the string `BPLIST` is matched against.

### A long wait, and a cancelled call

A call the client cancels ends at the next poll of its wait, as its own bound would have ended it, and answers nothing (the protocol sends no response to a cancelled request). The next reply, whatever tool, says once what that call left, in `cancelled` (`tool`, `after_s`, `left`, `earlier`) and in its summary. A step of a sequence is the sequence's cancel. A call cancelled while it waited for another did nothing and leaves no record. `state_write(method="save")` and `state_write(method="load")` end at the emulator's next answer: a guest they stopped is released, a save removes its file, a load counts the session altered.

Every tool ends one of three ways, and one that declares no end ends `none`:

| End | What the cancel leaves | Tools |
|---|---|---|
| `stop` | the guest back at the debugger by `BREAK`, as `stop` does (the cancelled call answers nothing, so that stop is read in the next reply's `last_stop`, its `cause` "a cancelled call's stop at SSSS:OOOOOOOO" when no declaration is at that address), or a stop it had already reached recorded as its own; a `run_to` removes the breakpoints it armed; a CPU log still open (a `trace`'s) is moved aside to `trace-cancelled-<n>.trace` in the session's captures directory (the working directory when there is none to write in) and closed | `stop`, `run_to`, `run_for`, `trace`, `screen_wait`, `perform` |
| `kill` | the emulator closed; a close cancelled half-way still finishes | `start`, `close` |
| `none` | the guest as the call found it | `build_check`, `status`, `log`, `log_wait`, `registers`, `read_memory`, `disassemble`, `call_stack`, `memdump`, `find`, `scan`, `debug`, `set_register`, `write`, `resume`, `step`, `state_write`, `snapshot`, `state_list`, `breakpoint_interrupt`, `symbols_load`, `symbols_find`, `comment_write`, `comment_list`, `machine_map`, `interrupt_vectors`, `palette`, `screen_view`, `screen_signature`, `map_write`, `map_find`, `series_capture`, `image_compare`, `breakpoint_at`, `declaration_list`, `declaration_clear`, `watch_add`, `send_keys`, `send_mouse`, `captures`, `capture_frame`, `perform_export`, `drive` |

Any other tool that meets a cancel ends `none`.

## Names for addresses

The tools: [Names](docs/reference/names.md).

`symbols_load` takes **text** a toolchain already emits and parses no binary symbol format, deliberately: put COFF in a generic debug server and it must learn TDS next, and DWARF after that. The debugger's `IV` is one address typed at a console, so it is no route for thousands of names.

**The debugger's list holds LINEAR addresses and a toolchain emits offsets**, so a base has to come from somewhere, and a default of zero is never taken: it loads without complaint and names whatever occupies low memory.

| Kind | Formats | Pass |
|---|---|---|
| Flat | `nm`, a GNU `ld` map, a REAL-MODE Borland map | `base` |
| Sectioned | a 32-bit Borland map, an Open Watcom map | `section_bases` |

**Passing both is refused**: a field that is sometimes a number and sometimes a table cannot be declared honestly. `base`, `section_bases` and `symbols_find`'s `linear` are hex text, an integer being refused.

A symbol table lists what *survived* compilation: at `-O3` an inlined `static` has no symbol, so a missing name is a fact about the build.

## Declarations

The tools: [Declarations](docs/reference/declarations.md), and the comment tools on [Comments](docs/reference/comments.md).

A ref is a **symbol or a `SEG:OFF`** everywhere, and the server works out the debugger's command
from the machine's own CPU mode (a selector in protected mode, a paragraph in real mode, `BPM` or
`BPPM` for a change-watch), so the caller says the same thing whatever the binary is. A `SEG:OFF`
is hex with or without `0x`, never signed. **An offset is as wide as the CPU mode**: 32-bit in
protected mode (a DJGPP `_main` sits past `0xFFFF`); in real mode anything past `0xFFFF` addresses
nothing and is refused rather than accepted and never firing.

One debugger row is one declaration, because a clear of either of two sharing a row would disarm
both in silence. Every arming is confirmed by **reading the debugger's list back**, never by its
acknowledgement (a repaint of an earlier one), parsed from the **last** `Breakpoint list:` of a
delta, since a delete leaves the previous populated listing on screen above the new empty one.

### What the store holds

The server stores the declaration, not the armed row: a symbol's address moves with every
recompile, the declaration does not, so each `symbols_load` re-resolves and re-arms it. A symbol
that no longer exists is KEPT, unresolved, arming nothing and losing nothing. The store is on disk,
keyed by the config file's identity, so two guests never inherit each other's declarations. Nothing
expires: a row another session left is shown as such and cleared by its `ref`, and a show watch
among the `orphan` rows is still evaluated at every stop.

### A raw `SEG:OFF` is kept per build

Over an unchanged program a raw address still names the same instruction, so it is kept whichever
session declared it, and judged by the one batch of the map that describes it: re-armed while that
batch is held unchanged, `stale` where a held batch describes the address otherwise. A relinked
build is not re-armed blind, because the address would land wherever the linker put something else;
declaring it again adopts it.

One `SEG:OFF` names another byte in the other CPU mode, so a raw row records the mode of the stop
that placed it, is judged and armed only at a stop of that mode, and is `unarmable` at the other,
its `why` naming the mode it waits for. So `start`, which parks in real mode, never re-arms a
protected-mode row (a `symbols_load` at a protected-mode stop does). A row no stop has placed is
placed by the next stop that can, and a `symbols_load` while the guest runs places nothing.

Within one session a held batch is taken as the running program, so a relinked EXE run in the same
session is not seen until the next one: batches are held in memory only. If the re-arm at `start`
cannot read the debugger's list, the session still comes up and `rearm_refused` says why.

### A comment is a declaration that stops nothing

A comment lives in the same store, under the same conf. It is never armed, never counted in
`status`'s `declarations`, never a stopper a `resume` could wait for, and neither broom touches it.
A raw comment is judged by its batch as a raw breakpoint is; a load that gives a raw row the text it
holds takes it into this session and build, which is how a `stale` row is brought back.

The tools: [Comments](docs/reference/comments.md).

## Advancing the machine

The tools: [Advance](docs/reference/advance.md).

### What a stop returns

Every stop (`resume`, `step`, `run_to`, `run_for`, `trace`, `stop`, `screen_wait`, and the tail of
a `perform`) carries the same block: `stop_seq` (the one `last_stop` names), `pc`, `cpu_mode`
(`real`, `protected`, `paged` or `VM86`, off the pane's mode word and its PAGE/NOPG mark), the
`instruction`, `regs`, the watches, `cause` and `e9`.

The `instruction` is decoded as `disassemble` decodes it. Its bytes come off the code pane the
stop's survey painted, which the debugger moves to CS:EIP when a stop lands outside it, or off one
`D` when the pane does not hold that line whole as one instruction (it decodes in its own width,
not always the segment's). The nearest symbol in protected mode costs one `SELINFO CS` and only
with a table loaded. The block is unavailable, with why, when no bytes could be read.

`cause` names the declaration whose address it stopped at (several at one address are all named),
a `run_to`'s own target, the caller's `stop`, or a retrace stop a `run_for` left armed. Else it is
an honest cannot-say: the debugger keeps no hit flag, and a memory watch stops at the instruction
that WROTE.

`e9` is the guest's E9 lines since the previous stop, bounded on every stop because each stop is
where a caller asks what the guest said. A cut block's `how` is the one way to read the rest:
`log(pattern=".", channel="guest", since_mark=<mark>, limit=<n>)`. No logfile, no lines.

### A trace says which routines ran

Every executed address is given a linear address where its mode allows one and, inside the loaded
table's span, the nearest symbol at or below it (the rule `symbols_find(linear=)` states). The table
has no sizes, so a routine's body above its highest symbol stays unplaced unless the table also
lists the data after the code, as `nm` prints a program. A `long` line says its own mode (CR0's
protection bit and VM), so each is placed by it: CS x 16 + EIP in real or virtual-8086 mode, the
base of selector CS otherwise. The other shapes do not say, so a window is read in the mode the
pane shows at its two ends: both real, every line by its paragraph; otherwise every line through
selector CS, which qualifies only as a present code descriptor at its own requested privilege, read
off one `GDT` and `LDT` listing at the stop (a session started with `logfile`). A window that
starts and stops in real mode but passes through protected mode is read by paragraphs, and a line
whose CS does not qualify gets no linear, which `note` says.

A trace whose stop never comes is interrupted where it stood, and what the log holds up to there is
collected as a stop that cut it would be; a log the machine closed first is refused, its lines not
being what ran.

### The waits are bounds

`seconds` is more than zero and at most 600, the ceiling shared by `log_wait`, the state tools and
the `expect` waits; `resume`'s `seconds` and every `settle_seconds` also take 0, meaning no wait. A
wait holds the server's lock throughout, so every other tool, `status` included, is unanswerable
until it ends; the ceiling stops one abandoned question from wedging a session.

- **An announced stop is read back before it counts**: a nudge that comes back cut means the
  machine still runs, and the wait listens on, sending nothing.
- **It hears the prompt, not only a register repaint**: the debugger repaints only the cells that
  changed, so a machine that stops again redraws its code pane while the register labels stay put.
- **It consults the emulator, and scans only what is new**, else a session that died at release
  burns the whole bound with the lock held, and each poll re-parses the whole terminal.

### While the guest runs

The debugger's console answers only while the machine is stopped. The server neither turns every
"the console cannot be asked" into an INVALID while holding the answer, nor refuses to apply what it
was asked to do while the guest ran.

- **The lists answer from what the server holds**, dated by `last_stop`, and say
  `debugger_read: false`.
- **What is asked while running is applied at the next stop**, before anything is read
  (`applied_on_stop`). A stop that happened on its own is recorded once, by the first tool that
  finds the machine at the debugger, `status` and `captures` included (`stopped_on_its_own`).
- **`status` reads `pc` off the pane**, since a command that moves CS:IP inside a stop makes no new
  stop. A reader refused because the guest runs names the tools that do answer in
  `answers_while_running`; `registers(from_last_stop=True)` hands back the stop's registers marked
  `superseded`, never as a value.

The server invents no stop and serves no cached memory as a current value: a stop comes from
something armed before the guest was released, or from `stop`, which is why the queue is drained at
the stop.

### Addresses in a reply

A segmented address is `SSSS:OOOOOOOO` (`seg_off` under its own key) and a linear one `addr`, `0x`
and eight digits, so the same place is one string. A **ref** a caller gives is matched, and a
comment stored, in the spelling its offset needs: `SSSS:OOOO` within `FFFF`, `SSSS:OOOOOOOO` past
it, upper case (`814:10b` is `0814:010B`). A row carries `addr` only where the server already knows
it, never bought with another console round trip. One spelling stays the debugger's own: a
breakpoint as `BPLIST` lists it (`run_to`'s `target`, a row's `entry`), which is what the server
matches against.

## Reading and writing

The tools: [Read](docs/reference/read.md), [Write](docs/reference/write.md) and [Scan](docs/reference/scan.md).

### The pane is the control

`disassemble` decodes on the host because the debugger has no disassembly command. The width is the
segment's own D bit, as the pane's decoder takes it: CS's, read from `Pr32`/`Pr16`, `SELINFO` or
the descriptor listing, and `code_bits_from` says which.

The pane is the control the decoder is checked against, line by line; the two may differ in
spelling alone (`jc` for `jb`, a string instruction's implicit operands, a size word, a symbol in
place of an operand). Where the pane is wrong about x86 it is
right about itself: it reads `FE /7`, which no x86 decodes, as `callback` with a word after it,
because that is how DOSBox's own code is entered from the guest; and in real mode it looks a
segment number up as a selector, so `C 0000:0000` decodes the vector table 32-bit.

## The log

`log` reads one `channel` of the logfile; the listings `machine_map`, `interrupt_vectors`, `palette` and the screen tools ask the debugger for land in the same file, among the `emulator` lines. The tools: [Read](docs/reference/read.md) (`log`, `log_wait`).

**`since_mark` asks "after Y".** A guest replaying a saved timeline writes lines identical to the ones before the load, so content cannot tell them apart and a position can. `state_write(method="load")` answers `mark`, one number per channel, all equal because one file holds them. It is a position in the file, not a moment: a line the emulator had not flushed when the load was sent lands after it.

**Only whole lines are read, from a byte offset**. A log written through stdio ends mid-line between flushes, and a reader indexing by line number consumes an index on the fragment, so the completed line is never tested. Every ending of a wait takes one last read, since a line written between the emulator check and the deadline would never be looked for.

**A wait on a machine stopped at the debugger ends at once**, refused with the position: a stopped guest writes nothing, and expiry would blame the program. The check is passive (the prompt the stop prints) and made at every poll, so a stop landing during the wait comes back as the stop, not "still running", which would have the next key refused for it.

## Sequences in one call

`perform(steps)` runs a list of the server's own operations in order and stops at the first failure with a full account; `start(plan=...)` runs the same list on the fresh session. The tools: [Lists](docs/reference/lists.md) (`perform`, `perform_export`) and [Input](docs/reference/input.md) (`drive`).

**The list is checked whole before its first step runs**, and before the session gate, so with no session a bad step answers `bad_argument` and a mistake in step 4 does not press the keys of steps 1 to 3. A step naming no operation is refused pointing at `operations`, carried once at the top level (inside `act` in a `drive`).

**The one table.** A `resume` ends the console-driven part of a sequence. After it, what answers on a running guest runs at once: the table a running-guest refusal lists in `answers_while_running`, plus the five it adds for a caller outside a list (`registers(from_last_stop=True)`, `close`, `drive`, `perform`, `perform_export`). A declaration there answers `pending` and is armed at the next stop. Whether a step stopped the machine is the session's to say, never the step's name.

**Waiting for the stop.** Before any other step (`symbols_load` included, even with a `base`) the sequence waits, bounded, for the stop a breakpoint produces. A list ending with the guest still running waits only while something declared can still produce a stop; with nothing declared it returns at once and says why. `settle_seconds` runs from 0 to 600.

Messages count steps from 1, as the progress line does; the indexes a reply carries (`failed_at`, a row's `step`, `errors`' `step`) count from 0.

## From an investigation to a bench

Every session is recorded from the `start` that succeeds and cleared by the next; `close` keeps it. `perform_export(dest)` writes it as `perform`'s own document, and the runner plays it back with no model:

```sh
uv run python -m scry_core.replay <document> [--binary PATH] [--transcript PATH]
```

It exits 0 when every step held; 1 when a step diverged or failed; 2 on a usage error; 3 when nothing was demonstrated (not a document, no `recorded` answer, a start refused, a saved state or declarations the replay lacks, a server that broke). A replay is deterministic on a conf with fixed cycles (`cycles=fixed <n>`); under `cycles=max` the guest's clock follows the host's.

A step that left the guest at a new stop holds to the `regs` its reply carries (a `state_write(method="load")` answers none, so it holds to nothing); a `debug` line is never held to its answer, which is the console's. The document ends where no replay can reach what follows: whatever ends a run stops the guest at a place no replayed advance reaches, and every later stop inherits the shift; a step that wrote a file the session named (`dest`) would find it there on replay. `needs.states` lists the saved states it loads and does not save, checked before anything plays; `needs.declarations` what the store held as the recorded `start` began, since a `start` re-arms what it finds stored for the conf. The document carries the `start`'s arguments as given, host paths included.

The tool: [Lists](docs/reference/lists.md) (`perform_export`).

## Input and the screen

Every input goes in inside the machine and nothing about the host is touched: no window comes to the front, the host pointer never moves, no Accessibility grant is asked for, and the window's scale changes nothing the guest sees. The tools: [Input](docs/reference/input.md), [Captures](docs/reference/captures.md), [Read](docs/reference/read.md) (`screen_view`, `screen_signature`, `palette`) and [Advance](docs/reference/advance.md) (`screen_wait`).

## Media files

The tools that answer about pictures follow one order: a signature or a number first ("is it the same screen" is two strings compared, never two pictures sent), the full picture last and only from a tool whose purpose is to show. Every tool that signs or compares takes a `crop`, `[x, y, width, height]` inside the picture: one that leaves it is refused, never padded, since a padded crop compares pixels nobody drew. The tools: [Captures](docs/reference/captures.md), [Files](docs/reference/files.md), [Read](docs/reference/read.md) (`screen_view`, `screen_signature`, `palette`).

**The signature** (`screen_signature`, every row of a series) is BLAKE2b with an 8-byte digest, 16 lowercase hex characters, over `scry-sig/1|<kind>|<w>x<h>|` (the crop's size) and the crop's cells row by row: `pixel` cells as RGB, `text` cells as their byte and the two colours. A text cell's colours are what its attribute resolves to: the nibble picks an Attribute Controller register (`VGA AC`), whose value, with `color-select` above it as `mode_control` bit 7 says, picks the DAC entry (with blink on, the background's fourth bit blinks and is not a colour), so a palette fade changes the signature as a character does.

## Screen maps

A screen map names an application's screens and their controls, so a caller says "the play screen" and "the court" instead of a picture and a coordinate. The file layers and the format are on [Files](docs/reference/files.md#screen-maps). The tools: [Read](docs/reference/read.md) (`map_write(method="add")`, `map_find`), [Files](docs/reference/files.md) (`map_write(method="load")`, `map_write(method="save")`), [Input](docs/reference/input.md) (`send_mouse`).

## Saved states

DOSBox-X merged SAVESTATE and LOADSTATE into its `main-ai` branch, joncampbell123/dosbox-x#6682 and #6683, not yet in `master` or a release. A build without them answers an unknown command, and both tools say so as `no_channel`, naming it. The tools: [States](docs/reference/states.md).

## The console

Everything the typed tools do goes through the debugger console, and `debug` is the raw command that hands you its paint instead. The tool: [Read](docs/reference/read.md) (`debug`).
