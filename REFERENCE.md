# scry-dosbox-x: reference

The [README](README.md) is the surface. This is the part behind each tool: what it takes,
what it refuses, what it hands back in every case, and why the contract is shaped that way.
Read the section for the family you are about to lean on.

## The session

`mode` is explicit and there is no detection behind it:

- **`headless`**: no window can open at all. This uses DOSBox-X's own
  `videodriver=dummy` setting, not the `SDL_VIDEODRIVER` environment variable and not
  `-silent` (which also hides the window but exits after `AUTOEXEC.BAT`, so it cannot
  host a session). Audio still works.
- **`shared`**: somebody is watching, and you pass the window placement flags in.

The server never computes where a window goes, and refuses a `shared` session without
flags rather than inventing a geometry. Pass them as **separate tokens**
(`["-set", "sdl display=1"]`, not one string): a `-set` pair arriving glued is an
argument DOSBox-X does not recognise, and it hangs on those rather than refusing them.

**`background` decides whether the launch takes the owner's focus**, through SDL3's
`SDL_MAC_BACKGROUND_APP` (which reaches SDL3 through the sdl2-compat layer DOSBox-X links):
`true` launches behind, `false` in front; omitted, a headless start goes behind and a shared
one in front. The hint is set or removed in the spawned environment, never inherited from
the server's, and the reply's `background` says what the process was told. A window launched
behind is still drawn where the placement flags put it.

`seconds` is a **hard bound and required**: a DOSBox-X nobody reads freezes under its
terminal, so every session carries a ceiling on its life, and `status` says how much of it is
spent. It is a backstop, not a plan: `close` is the act that ends a session.

**What else `start` takes.** `program` runs with `-c` AFTER the conf's autoexec, so that
autoexec must not `exit` or the program never runs. `plan` is a list of the server's own
operations run on the fresh session with `perform`'s vocabulary and rules, `plan_wait`
bounding each wait for a stop, and its account replaces the plain reply, with the start
facts under `start`. `state_dir` is where `state_save` writes and `state_list` reads (`save`
under `cwd` when omitted), and every session turns the emulator's save remark dialog off,
which would otherwise wait for a click nobody sends.

**Two parameters govern the tools that READ what they set up**, and neither is optional if
you want them. The rule is what is written, because a count of "which tools" goes stale:

- `logfile` is where the guest's instrumentation and the emulator's own lines are written,
  and it is what `log` and `log_wait` read. Without it, `log` has no channel and says so.
- `captures_dir` is where a video capture lands, so `captures` and `capture_frame` both
  need it, and where a `trace` with no `dest` puts its file.

`captures_dir` is NOT where a dump lands, whatever its name suggests. `memdump` names the
debugger's file itself, `MCPDUMP.BIN` in the emulator's **working directory**, because a build
whose `MEMDUMPBIN` reads an optional file name and is given none reads that name from past the
end of the line, and writes its file under a fragment of the arguments where nothing looks for
it. A build that takes no name ignores the one passed and writes its default, `MEMDUMP.BIN`,
which is collected too, from the working directory first and from the captures directory, under
both spellings, because where that default lands is one build's behaviour on one platform.

**And it REFUSES rather than deleting.** Unlinking every candidate with the error suppressed
would put the whole staleness guarantee on an error nobody reads: a read-only checkout or
another user's file, the unlink fails quietly, the debugger prints its success line anyway,
and a stale file comes back with a byte count. The first candidate is also the emulator's
**working directory**, which is somebody's project, so deleting a file of that name there is
not the tool's to do. If one is already sitting there, `memdump` says so and stops. A `dest`
directly in the working directory is refused as well (a subdirectory of it, a project's own
`TMP/`, is not), and so is one that is, or lives under, one of the debugger's file names, all
compared on the filesystem rather than on the spelling (case and a symlink name one file
by different strings): a dump collected into the directory it is collected
FROM cannot be told from the leftover this refuses, and creating one there poisons every later
dump on the session. The size it hands back is checked for EQUALITY against the length you
asked for, not merely for being non-empty. A dangling link at the place the debugger writes
is a file there too (the debugger would write through it, onto whatever it names), so it is
refused the same way, by `trace` and `interrupt_vectors` as well. And a dump that fails after
the debugger wrote takes its own file away, whichever failure it was, so the next call is not
refused over it.

**Which DOSBox-X runs is resolved once per `start` and per `build_check`, and said.** The
ladder is the `binary` argument (an absolute path), else the `DOSBOX_X_BINARY` variable, else
the `dosbox-x` the PATH finds, and the first rung holding a value is the one taken. A relative
value is `bad_argument`; one naming no executable file is `host_failed`, naming what all three
rungs held, and is never passed over for the next, because a caller who named a build and got
another would be measuring the wrong emulator. Both replies carry `binary` (absolute),
`binary_origin` (`argument`, `DOSBOX_X_BINARY` or `PATH`) and `version`: the first non-blank
line `-version` prints, or `{"available": false, "why": ...}` when it printed nothing, did not
return in 5 s or could not run. Either way the call goes on.

**`build_check` answers about the build, and refuses while a session is live.** It asks the
question a failure asks first, about the thing that matters: not whether there is a binary
but whether this build carries the DEBUGGER (`-helpdebug` listing `-break-start`), which the
whole surface rests on; a build without one starts fine and then hangs `start` until its
timeout. It is INVALID when a precondition fails: the one tool whose purpose is examining
preconditions never reports a clean result for a missing tool. And it REFUSES while a
session is live, because answering means starting a SECOND emulator: on a build without the
debugger `dosbox-x -helpdebug` is not a help listing but a full emulator for the whole bound,
since this build does not refuse an option it does not know. What it examines is a property
of the build and does not change while a session is up. `heavy_debug` says whether the build
carries the debugger's CPU log, which `trace` needs: it is read off the binary's bytes, which hold
the `LOG` family's help line only when the build is a heavy-debug one, never by typing `LOG` at a
console to see whether it answers. `false` is an answer, not a refusal: `trace` is what refuses
such a build.

**Every path you give is absolute or starts with `~`, which is expanded.** `start`'s `cwd`, `conf`,
`logfile`, `captures_dir`, `state_dir` and `binary`, `build_check`'s `binary`, `memdump`'s, `trace`'s, `snapshot`'s, `palette`'s,
`screen_view`'s, `capture_frame`'s and `series_capture`'s `dest`, `capture_frame`'s and
`series_capture`'s `source`, `symbols_load`'s `source` and `types`, and the media file tools'
paths (`a`, `b`, `manifest`, `ref`, `dir`, `checksums`) go through one judge, scry-core's. A
relative path is refused because it would be judged against one directory and used in another:
this server's own working directory is wherever the client launched it, the emulator's is `cwd`,
and a path that names one file to the judge and another to the writer is checked against the
wrong file. `~` (and `~user`) is expanded as a shell would, because it is what a person types and
no shell stands between a client and the argument; a `~user` this host does not know is refused.
A NUL or a lone surrogate is refused the same way, and
so is an empty path, except a `dest` whose default is empty, which means none.

The SHAPE is judged before anything happens: before the session gate (refused with no machine
as with one, a `perform` or `drive` list carrying one refused whole), and for `start` before a
live session, the binary or the store is looked at. A `start(plan=)` list is judged whole the
way a `perform` list is, before the emulator boots. The FILESYSTEM is judged at the call, on
the filesystem of that moment: a file a tool writes has its directory there (nothing creates
it) and nothing at it yet, a dangling link included; a file a tool reads is a regular file
there. `start` judges `cwd` as an existing directory and `logfile`'s directory as there (a
directory `start` is about to create does not count, and `logfile` may not be one of them, nor
the conf, which the emulator would overwrite with its log; a link is judged by the file it
names, and one that loops names none and is refused), then creates `captures_dir` and
`state_dir` with their parents just before the emulator starts (`host_failed` when it cannot).
Any other file already at `logfile` is overwritten, since the emulator opens its log afresh:
`start` cannot know which files the conf's `autoexec` runs, so a log named after one of the
guest's own (a program beside the conf) replaces it. A `types` file is UTF-8, refused naming
where it is not (a byte-order mark an editor wrote first is dropped); a map `source` is read
leniently, because a DOS toolchain's map may carry code page 437 bytes in a path or a comment,
and its parser counts the lines it could not read.

**Window placement.** The server never decides where a shared window goes; it takes the
`window_flags` and passes them through. A `shared` session without them is refused rather
than given a geometry the server invented, and a headless session with them is refused too:
there is no window to place.

**The emulator's own options go in `flags`, in either mode.** They are argv tokens placed
after this server's defaults, so a `-set` the caller passes for the same key wins
(`["-set", "cpu cycles=fixed 2500"]`), one token per `-set` value as for `window_flags`. What
a named argument sets is not theirs to retune: `-time-limit` is `seconds`, `sdl videodriver`
is `mode`, `log logfile` is `logfile`, and so on for the conf, the break at start, the save
directory, the program, the int 3 key, the input route and the captures. Such a flag is
refused naming its argument, because after ours it would quietly undo that argument.

**`break_on_int3=True` makes the guest's own `int 3` a stop.** It sets the emulator's `[dos]
break on int3`, and DOS arms a `BPINT 03` row in the debugger's list while it starts; from
then on an `int 3` the program executes stops at the debugger AT the trap, the stopper a TASM
program can carry itself. Two limits are the debugger's own. At the reset vector, before the BIOS
and DOS have started, there is no row and no vector, so a trap there faults instead of
stopping. And the first instruction
after a `resume` runs unchecked, because the debugger does not stop where it already is: a
trap written at the stop itself is stepped over, one instruction later it is caught.

## What every reply carries

**Every reply carries `altered`, in its `session` block, and opens with a `summary`.**
Writing to a live machine is allowed here, and a measurement taken on a forced state is not
a measurement of the program. The person reading an answer three questions later has no
other way to know. The summary is one line, first, written for a person: what was asked and
what came back, in the tool's own words, because the line a client paints for a call is the
tool's name, its arguments and its reply, and two calls of one tool are told apart only by
what is IN the reply. Every tool declares a `title`, a `readOnlyHint` and an
`idempotentHint`, false on every tool here: each one reads a machine that moves or a file
that may change, so a repeated call is never promised the same answer. One
caveat, decided on purpose: the first contact after a stop applies the declarations made
while the guest ran, so a reader can be the call that arms a breakpoint; that write belongs
to the declaring call, which said `pending`, and the reader's reply says `applied_on_stop`.

**The `session` block closes every reply**, `null` when there is no session: `pid` (the
emulator's, to read instead of hunting it), `alive`, `altered`, `conf` and `conf_digest` (the
config the session started from, and a digest of its content at start), `conf_changed_on_disk`
(`true` when that file changed since, `false` when it did not or is gone, `null` when it could
not be read), `watched` (started to be looked at, so a window was placed), `seconds_bound` and
`seconds_elapsed`, `terminal_bytes_dropped` (nonzero: a screen delta had a hole in it; it
counts the emulator's terminal, never the guest's E9 stream, which is read off the log file),
`drain_alive` and `drain_ended` (whether the terminal reader still runs, and why it stopped:
a dead reader makes every later read return nothing while `alive` still says true),
`captures` (`off`, or where a `capture_video` session records, `on, in the emulator's own
directory` when it was given no `captures_dir`) and `state_dir` (where
`state_save` writes and `state_list` reads).

**A refusal is one contract, and a class holds it.** `status` is `ok` or `INVALID`; an
INVALID carries `code`, one word from a fixed table (`no_session`, `not_stopped`,
`not_running`, `bad_argument`, `unknown_ref`, `no_channel`, `wait_stopped`, `wait_expired`,
`control_silent`, `session_broken`, `host_failed`, `step_failed`...), and `message`, the
prose, flat beside whatever context the refusal has (`last_stop`, `posted`, `route`,
`failed_at`). The table and the class live in `scry_core.reply_contract`; `NotStopped`, `E9Stopped`
and `E9Expired` fix their code in the constructor, so a site cannot raise one under another
word, and a code outside the table, an empty message or a retired spelling (`reason`) is
refused where it is written, as a programmer's error, so a malformed refusal never reaches a
caller looking like a verdict. Rows and sub-objects keep their own `why` beside their
`state`: that is a row's prose, not a refusal. A bad argument is a refusal too, not an
execution failure: the SDK's `isError` is for a bug, and "I could not look" is a verdict. An
argument of the wrong TYPE (a list where an integer is due) never reaches a tool: the schema
refuses it first, and the refusal comes back in this same envelope as `bad_argument`, naming
the argument. The schema is STRICT: nothing is coerced (`"16"` is not 16, a list sent as a
JSON string is a string), except that an integer stands for a number, and an argument name
the tool does not take is refused the same way, never dropped. A value as wrong with no
machine as with one is refused before the session gate, so with no session it answers
`bad_argument`, never `no_session`: a state's name, a scan's operator and a negative value, a register
value wider than its register or negative, a scan's length in whole cells, a search's length,
a declaration's ref in the shape its family takes (a breakpoint is never declared through a
pointer, `[g_p]` included), a watch's length, a key name, `resume`'s `seconds`, a wait's
bound, and every step of a `perform`, `drive` or `start(plan=)` list (its op, its argument
names and values).

**A read that found nothing says which kind of nothing.** "No line matched" is an answer and
comes back as an empty list. "There is no log to match against" is `INVALID`. A caller that
cannot tell those apart reports a broken instrument as a clean result.

**A session it cannot reproduce is refused, before the process exists.** An unreadable
config, a watched session with no placement flags, a session with no bound: all refused up
front. A guarantee that leaves alive what it just declared invalid is not a guarantee.

**Reads are narrow on purpose.** `log` filters in the server and hands back matching lines,
with `lines_total` reporting how many matched rather than how many came back; `memdump` writes
to disk and hands back a path. What crosses back to you should be the answer, not a haystack
with the answer in it. Every count a reader takes has a ceiling as well as a floor (`log` at
400 lines, `symbols_find` at 50 names): a limit with no top is the haystack with a number on
it, and the answer above the ceiling is a narrower pattern or name.

`debug` answers in the debugger's raw screen text; `resume` and `breakpoint_interrupt` answer
in parsed fields and add the repaint only with `detail=True` (and only `breakpoint_interrupt`'s
fresh arm types anything to repaint). Wherever a repaint comes back it is capped and SAYS so:
`screen_chars` is how much the screen produced and `clipped` is whether what came back is all
of it. No command this debugger has reaches the cap on a stopped machine, so `clipped` is a
headroom declaration rather than a live hazard; a caller quoting a delta without reading it
would still be quoting a sample as a result the day one does clip.

**A reply that answers less than everything says so.** Where the whole answer is larger than
the question usually asked (`machine_map`'s sections, the repaints above), the default reply
answers that question and carries `omitted`, the names it left out, and `how`, the argument
that brings them; a reply that left nothing out carries neither, except a `machine_map` whose
lists were cut, whose `how` says how to have every row. `how` in a `stop` or `close` reply is
another word: how that stop or end came about.

### A long wait, and a cancelled call

A wait that can run for seconds reports its progress about once a second, as MCP progress
notifications a client paints in the call's row: the frames or milliseconds done of those
asked, a count it is waiting on, or the seconds of the bound when time is all there is. A step
of `perform` or `drive` reports through the sequence's own line,
`perform step 2 of 5 (run_for): ...`, so the line never goes back.

A call the client cancels ends at the next poll of its wait, the way its own bound would have
ended it, and answers nothing: the protocol sends no response to a cancelled request. A tool
with no wait of its own (a read, a single console command) runs to its end first. `state_save` and
`state_load` wait on the emulator's answer and end at its next poll as their bound would: a guest
they stopped is released, a save removes its file (one the emulator finishes after the cancel
can still appear, as after a save its bound ended), a load counts the session altered. The next reply, whatever tool it
is, says once what that call left (a step of a sequence is the sequence's cancel): in `cancelled` (`tool`, `after_s`, `left`, one of `stopped`,
`running`, `closed` or `unknown`, and `earlier`, the cancelled calls before it that no reply
reported) and in its summary, `after a cancelled run_for (stopped): ...`. A call cancelled while
it waited for another to finish did nothing, and leaves no record.

A call that had finished its work when the cancel arrived is recorded the same way, with no
end applied, and what its reply carried (a stop it found, what a stop applied) is said by the
next reply instead. A cancel that arrives after the server's last look, while the reply is on
its way, is not seen.

Every tool ends one of three ways, and one that declares no end ends `none`:

| End | What the cancel leaves | Tools |
|---|---|---|
| `stop` | the guest back at the debugger by `BREAK`, as `stop` does, or a stop it had already reached recorded as its own; a `run_to` removes the breakpoints it armed; a CPU log still open (a `trace`'s) is moved aside to `trace-cancelled-<n>.trace` in the session's captures directory (the working directory when there is none to write in) and closed | `stop`, `run_to`, `run_for`, `trace`, `screen_wait`, `perform` |
| `kill` | the emulator closed; a close cancelled half-way still finishes | `start`, `close` |
| `none` | the guest as the call found it | `build_check`, `status`, `log`, `log_wait`, `registers`, `read_memory`, `disassemble`, `call_stack`, `memdump`, `find`, `scan_start`, `scan_filter`, `scan_clear`, `debug`, `set_register`, `write`, `resume`, `step`, `state_save`, `state_load`, `snapshot`, `state_list`, `breakpoint_interrupt`, `symbols_load`, `symbols_find`, `comment_add`, `comment_list`, `comment_delete`, `comment_save`, `comment_load`, `machine_map`, `interrupt_vectors`, `palette`, `screen_view`, `screen_signature`, `series_capture`, `image_diff`, `series_diff`, `region_track`, `golden_check`, `breakpoint_at`, `breakpoint_list`, `breakpoint_clear`, `watch_add`, `watch_list`, `watch_clear`, `send_keys`, `send_mouse`, `captures`, `capture_frame`, `perform_export`, `drive` |

Any other tool that meets a cancel ends `none`.

## Names for addresses

The debugger *does* have a symbol facility (`IV` names an address, `SV` saves the list, `LV`
loads one) and no route for getting nine thousand names in: `IV` is one address typed at a
console, and it uppercases what you type, so a C symbol table cannot be entered that way
even with patience.

`symbols_load` takes **text**: `nm` output, a GNU `ld` link map, or the `Publics by ...`
section of a Borland TLINK/TASM map, **both generations of that one**, the real-mode
`SEG:OFFS` rows and the 32-bit `SECTION:OFFSET` rows, which are resolved against the section
table printed in the same file. It parses no binaries, deliberately: put COFF in a generic
debug server and it must learn TDS next, and DWARF after that. Every DOS toolchain emits one
of these from a tool that already knows its own format.

**The debugger's own file format is documented nowhere**, so it was opened and read: a `u16`
count, then that many records of a 16-byte NUL-padded name and a `u32` **linear** address.
`IV 1234:5678` stores `0x000179B8`, which is `0x12340 + 0x5678`.

Three things that decides, none of them optional:

- **The address is LINEAR and a toolchain emits offsets**, so a base has to come from
  somewhere. It is read off the running machine with `SELINFO`, because under a DPMI host
  the program's selector base is decided at load time. **In real mode there are no
  descriptors**, and what `SELINFO` prints there is no answer (inside a program, no descriptor
  line at all; at the reset vector, an all-zero one), so `symbols_load` reads the mode off the
  register pane and refuses a flat map with no `base` before asking, naming `base` as the
  remedy, rather than taking anything as base 0, which would place every symbol at its raw
  offset and load perfectly cleanly. An all-zero descriptor met in protected mode (a selector
  nothing has set up) is refused for the same reason. Pass `base` yourself to override, as hex
  text (`"8000"` for load segment 0x0800); `section_bases` takes hex text too, and an integer
  is refused in both, so no caller has to convert hex to decimal.
- **The name field is 16 bytes, so 15 usable characters**, and a real C symbol table has
  many names longer than that; truncating them blindly collapses a good fraction of the
  table onto colliding names. So a collision keeps *all* its members and shortens them for an
  index (`__poly_scan~00`), the ledger of taken names is GLOBAL rather than per-group (a
  per-group ledger leaves symbols carrying another symbol's name), and the reply says how
  many were truncated and how many renamed. **Read `renamed`, not `truncated_names`**:
  `truncated_names` counts names longer than the field, and a name that FITTED is mutilated
  too when it has to carry a `~n`. And a name that fits AND is unique is reserved before any
  index is handed out, because one pass in input order gives a real `...~0` name to somebody
  else's address. `symbols_find` answers from the full untruncated table, held in the server;
  asked by `linear`, it takes the address as hex text (`"0x56DF24"`), as `symbols_load` takes
  its bases.
- **`unreadable` is how many lines matched neither format**, and it is reported beside the
  buckets rather than inside them. `parsed` counts what was RECOGNISED, so without it a file
  half of which the parser could not read produces a plan whose every count adds up. `nm -C`
  is the ordinary way to hit it: a demangled C++ name holds spaces.
- **`overlay_idle` is how many of the loaded symbols carry the linker's `idle` mark.** They
  are **loaded**, not filtered: a real map can carry the mark on a quarter of its rows, and
  dropping that much of a table is the worse failure of the two. So it is a number to read
  rather than a filter, and `symbols_find` answers `idle` for the one name you asked about,
  which a total cannot. It is a **subset of `kept`**, not a bucket beside it, so it does not
  enter the sum that accounts for `parsed`; folded in, it would double-count and refuse every
  map carrying the mark. It is 0 for `nm` output and for a GNU map: neither format has the
  concept. What the mark MEANS is an open question: it was read as a public living in an
  overlay the linker had not made resident, and real artefacts contradict that from both
  directions (a map with no overlay segments carrying the mark, and a map built with an
  overlay marking the resident publics). No replacement explanation is offered; the mark is
  read, carried and counted, and the field's name inherits the refuted reading, which is
  flagged where it is defined.
- **A 32-bit Borland row is a SECTION INDEX and an offset inside it**, not a paragraph and an
  offset, so `seg * 16` would invent an address rather than read one, and the file carries NO
  flat address anywhere. The vendor's documentation suggests otherwise, that the section
  table's `Start` column is a full address (`0001:00401000`), so `base = 0` would be right and
  the map would place itself; the artefacts contradict it. Every `Start` offset in an ILINK32
  map's table is zero, an Open Watcom map's first two sections both start at zero too, so the
  sections OVERLAP, and under a flat model they all fold onto ONE address space with hundreds
  of symbols plausible and on top of one another. The bases live in the LINKED IMAGE (a
  DOS/4GW `LE` object table, a PE section table), which this server does not read, so a
  sectioned map takes `section_bases`, a base per section index, and `base` beside it is
  refused. Eight hex digits with no table that positions the section stays a refusal, and a
  short offset in a file that DOES carry a section table is refused rather than folded,
  because that file has said its left column is an index. What is deleted is the assumption,
  not the possibility that some linker prints a full address there: one file cannot
  establish that.
- **A 32-bit Borland map describes a Win32 program, and this server debugs DOS.** It is read
  anyway, deliberately: it reads without losing a row, and a DOS program in the same format
  would be read by the same code. What it does NOT give you is a program you can then stop
  in, so if you load one and every breakpoint refuses, that is the reason and not a defect.
- **`LV` appends**, so loading twice leaves both lists and `loaded` exceeds `kept`.
- **A second load ADDS to the first on this side too**, which is what loading in narrow
  batches needs: the table answered from here ACCUMULATES with the debugger's, so a symbol
  placed by an earlier batch keeps its row and a breakpoint armed on it stays resolved, and a
  name loaded again takes the newer row. The one thing that does not carry over is a load that
  MOVES the program: this table holds offsets and the base places them, so a different `base`
  or different section bases REPLACE the table, because carrying the old offsets across would
  re-place them at addresses nobody measured. `table_mode` says which of the two happened and
  `table_total` how many symbols the table now holds. On a replace the two counts part
  company: `table_total` is what this side answers from, while `loaded` is the debugger's own
  holding, and since `LV` never forgets, the debugger still carries the previous base's rows
  under their old names, invisible to `symbols_find` and not clearable by name from here;
  `close` and a fresh `start` is what empties them.
- **`excluded_unplaceable` counts symbols whose value is not an address** (`nm`'s `C`,
  `A`/`a` and `N` rows), excluded whatever `keep_noise` says, since no base can place them.
- **With an explicit `base` the load works while the guest RUNS**: the table is held at once,
  so `symbols_find` answers, and the debugger's list is loaded at the next stop together with
  the re-arm, which the reply says as `pending: true`. Without one the base has to be measured
  off the machine FIRST (`SELINFO`), so a running machine is refused one step earlier, in the
  descriptor's words; with one, the refusal is the load's own, before any file is written.
- **Two limits, declared rather than guarded.** A base belongs to a loaded PROGRAM, and a
  guest that exits one program and runs another at a different base within one session is not
  re-measured: load again, minding that `LV` appends. And a load that gets past `LV` and then
  fails leaves the debugger holding the list while the reply is INVALID and the previous table
  stays; retrying is safe for this side's answers and adds a second copy to the debugger's
  pane.

`loaded` is read back out of the debugger with `SV` rather than taken from its `ok`, because
**a `SV`/`LV` filename is silently cut to twelve characters and reported `ok` for whatever
was used**. The two files this uses live in the emulator's working directory, the only place
a twelve-character name can reach; an existing file of either name is refused rather than
overwritten, and both are removed on the way out.

**Two kinds of map, two ways of saying where the program was loaded.** A toolchain emits
OFFSETS and the debugger's list holds LINEAR addresses, so something has to supply the
difference:

| Kind | Formats | Pass |
|---|---|---|
| Flat | `nm`, a GNU `ld` map, a REAL-MODE Borland map | `base` |
| Sectioned | a 32-bit Borland map, an Open Watcom map | `section_bases` |

**Passing both is REFUSED.** A field that is sometimes a number and sometimes a table cannot
be declared honestly, and which one won would be exactly the thing nobody notices getting
wrong. Passing neither is refused for a sectioned map, and for a flat one in real mode; a flat
map in protected mode measures its base off the selector `base_from` names (`CS` by default).
What is never taken is a default of zero: it encodes a file that is well formed, loads
without complaint, and names whatever occupies low memory. A symbol therefore keeps
its section, and placement happens once, afterwards, from that table; a flat format is the
degenerate case, one section, one base, and placement stops being a side effect of reading
and becomes a step that DEMANDS its bases.

**A file most of which was discarded is refused.** `parse` returns how many rows it could not
read, and a symbol section that lost MORE rows than it kept is refused: a reading that
discarded more than it understood is not a reading of that file. It binds the anchored
readers only, and that is the load-bearing half: for those, an unreadable row is a line
INSIDE a symbol section that LOOKS like a row, so every one is a symbol lost; for the flat
readers it counts every line that did not match, and a GNU `ld` map is MOSTLY not symbols by
construction, so one ratio over both would refuse every GNU map ever written. The `idle`
mark is matched PER FORMAT and each declaration carries its own spelling (TLINK 16-bit writes
`idle`, ILINK32 writes `Idle`): a case-insensitive match would quietly accept a spelling
neither linker produces.

Producing the text is your build's job, and it has to be *your* toolchain's `nm` rather than
the host's. Write to a temporary and move it, because `>` truncates before `nm` runs: an
`nm` that dies part way replaces a good symbol file with a partial one, and that partial
file is what the debugger is then told to trust.

```make
symbols:
	@$(XPREFIX)nm build/APP.EXE > $@.tmp || { rm -f $@.tmp; exit 3; }
	@grep -qE '^[0-9a-f]+ [A-Za-z] ' $@.tmp || { rm -f $@.tmp; exit 3; }
	@mv $@.tmp build/APP.SYM
```

Mind what a symbol table is: a list of what *survived* compilation. At `-O3` a `static`
function is inlined and has no symbol at all, so a name missing there is a fact about the
build and not about the source.

## Declarations

`breakpoint_at`, `watch_add`, `run_to` and the readers take a **symbol or a `SEG:OFF`**
indifferently, and the server works out the debugger's command from the machine's own CPU
mode: a selector in protected mode, a paragraph in real mode, `BPM` or `BPPM` for a
change-watch. The caller says the same thing whatever the binary is.

One debugger row is one declaration: a second ref on an address another breakpoint or watch
of the store already holds is refused, naming the ref that holds it, because two
declarations sharing one row would be disarmed together by a clear of either, in silence.

What the server STORES is the declaration, not the armed row. A symbol's address moves every
time you recompile; the declaration does not, so on every `symbols_load` each one is
re-resolved against the new map and re-armed, and the reply names them (`rearmed_refs`). A
symbol that no longer exists (the compiler inlined it, or you removed it for now) is KEPT,
unresolved, and `breakpoint_list` says so: it arms nothing and it is lost nothing. The store
is on disk, keyed by the config file's identity, so it survives closing the emulator and
restarting the client, and two different guests never inherit each other's breakpoints.
Re-declaring something already stored is a no-op that says `already_stored`, so a
declaration script survives being re-run.

**Every declaration knows when and by which session it was made**, and the clear tools take
exactly the `ref` the declaring reply carried (`breakpoint_interrupt(0x21, ah=0x4B)` answers
`ref: "BPINT 21 AH=4B"`, and that is the string that clears it). An interrupt breakpoint is
stored under its `BPINT` spelling rather than cleared through the console's index, which
deletes whichever row sits there at the time, and re-arming one is a no-op checked against
the live list, because `BPINT` sent twice stacks a second row that a later clear leaves
behind as `foreign`. A `ref` that matches nothing is refused, naming what the store holds,
because a zero in green is how a wrongly spelt ref leaves a breakpoint armed. **A raw
`SEG:OFF` is kept per BUILD**, whichever session declared it, because over an unchanged program
it still names the same instruction. It is judged by the one batch of the map that describes its
address (the batch whose lowest and highest entries enclose it, the latest loaded where several
do): re-armed after a `symbols_load` while that batch is held unchanged, whatever was loaded
beside or after it since the last replace; `stale` where a held batch describes the address
otherwise (a relinked map, the map at another base); and, where no batch describes it, judged by
the conf only when it was declared with no map describing it, so one declared before any map is
re-armed at `start`, and one declared under a map waits for that map's load and is `stale`
under any other, its address described or not (the map at a base past it, relinked shorter or
longer). One declared where its place is not known while a map is held (a protected-mode
offset past FFFF at a real-mode stop) takes the batch that describes it when a later load of its
session places it; with no such load it is `stale` in every later session, at `start` too, and
is never re-armed blind. It also records the cpu mode of the stop that placed it, real or
protected, because one `SEG:OFF` names another byte in the other mode: it is judged and armed
only at a stop of that mode, and at a stop of the other it is `unarmable`, its `why` naming the
mode it waits for, so `start`, which parks in real mode, never re-arms a protected-mode one (a
`symbols_load` at a protected-mode stop does). A comment file's row takes the mode of the first
stop that places it, so a protected-mode program's file is loaded at a protected-mode stop.
Within one session a held batch is taken as the running program, so a guest that exits
and runs a relinked EXE inside the same session is not seen until the next session, which judges
its rows against the map it loads. The store keeps each batch its rows name once, beside them,
and drops it with the last row that names it. If
the re-arm at `start` cannot read the debugger's list, the session still comes up and the
reply says why in `rearm_refused`. One declared over another build is kept but never re-armed:
it re-resolves against nothing, and re-armed blind on a relinked program it lands wherever the
linker put something else, so it is listed `stale` with its `origin` and `created_at`, and
declaring it again adopts it. A symbol re-resolves whichever session declared it; that is what
it is for. `breakpoint_clear()` with an empty `ref` (its default) remains the broom for the
breakpoints of a store you do not recognise, and `watch_clear()` is the other broom (a `null`
`ref` is the schema's refusal): each sweeps its own family,
never the other's, and the two together empty the store. A
declaration written by a store from before origins were kept is listed `orphan`, with the
`ref` that clears it, and a show watch among them is still evaluated at every stop until it
is cleared or re-declared.

**A watch has two halves, and one address may not be both.** A show watch (`mode="show"`) arms NOTHING:
it is a plain memory read at every stop, rendered in its declared width and format, and it is at
most 128 bytes: a region is `memdump`'s job. A change-watch arms a trap byte, and the debugger
never takes a watch away, so the read would return the trap as program bytes. A row a store
holds under the retired mode `read` is read as `show`, and written so at the next write.

A change watch (`watch_add` with `mode="change"`) breaks when memory **changes**, the
debugger's own wording, and the thing most likely to be misread: a read never fires it, and
neither does a write storing the value already there. Arming it eats the
selector-versus-segment choice by reading the CPU mode off the machine (`BPM` in real mode,
`BPPM` in protected), because the same sixteen bits mean different things in each, the
debugger accepts either without comment, and the mode changes underneath a caller as their
program boots. **`BPLM` is deliberately not offered**: it watches a LINEAR address, and a DPMI
program runs **paged**, so the frame named belongs to whoever holds it at that instant; a
static in a DJGPP binary watched that way fires on unrelated code during boot and never on
the application. Break-on-change is real mode's today: under a DJGPP program's paging a
`BPPM` change-watch fires on the paging host and not on the program, so in protected mode it
is armed and the reply says its firing is not to be trusted (`caveat`), the honest limit
rather than a silent wrong stop.

**And what `BPLIST` prints is not what you send, nor is it uniform**, which is why a fixture
authored from the same belief as the code cannot catch a wrong spelling here:

```
BPM  0040:006C   ->  00. BPMEM 0040:006C (00)        offset %04X, keyword gains MEM
BPPM 00AF:6024   ->  00. BPPM 00AF:00006024 (00)     offset %08X, keyword does not
BPLM 000B8000    ->  00. BPLM 000B8000 (00)
```

Every arming here is confirmed by **reading the debugger's list back**, never by believing
the acknowledgement: the Output pane is a scrolling log, so `DEBUG: Set breakpoint at ...`
can be a repaint of an earlier one. That is also why the list is parsed from the **last**
`Breakpoint list:` in a delta: after a delete, the previous populated listing is still on
screen above the new empty one.

**A watch reached through a pointer.** `ref` takes `[base]`, `[base]+0x28`, `[base]-0x4` or
`base->field`, with `base` a symbol or a `SEG:OFF` holding the pointer: the pointer is read
there as a NEAR pointer in the base's own segment, at the width its type declares
(`ptr16{...}`/`ptr32{...}` in the `types` file, which also names what it points at so `->`
knows the field's offset and format; a class after the width, `ptr16@CODE`, is part of the
grammar for a machine relocated by class, parsed here and applied to nothing) or else the
cpu mode's (four bytes protected, two real), the offset added, and the watch placed at the
result; the reply's `pointer` block says through what. It is re-resolved at every stop,
because the pointer can move: a change watch is moved with it (`moved: {from, to}` on that
stop), and a null pointer is the state `null_pointer`, never a watch at zero. A base the
table lacks is refused naming what it most likely is, a stack local, which has no stable
address to start from.

**A comment is a declaration that stops nothing.** `comment_add` puts a line of text on a
place, by symbol or by `SEG:OFF`, in the same store and under the same conf as the breakpoints,
with the same `created_at` and `origin`; it is never armed (the debugger has no comment of its
own), never counted in `status`'s `declarations`, never a stopper a `resume` could wait for,
and neither broom touches it. The place is the LINEAR address: a symbol's is the one
`symbols_find` gives, a `SEG:OFF` is read in the mode the machine is in (a paragraph in real
mode, the selector's base in protected mode, its offset held to the selector's limit), so a
comment meant to survive a mode switch is made by symbol. One comment per place: a second
`comment_add` on the same byte, in any spelling, replaces the text and keeps the held row's
`ref`, so a comment made by symbol keeps following the symbol. Its state is read when it is
listed: `resolved` with its `linear`; `unresolved`, a name this table lacks, kept for the next
build; `ambiguous`; `stale`, a raw address not known to be this build's, still listed where it
points. A raw comment is judged by the one batch that describes its address, as a raw breakpoint
is: this build's while that batch is held unchanged, `stale` where a held batch describes the
address otherwise, `stale` where none does and its map is not held (at the next park as
well), and judged by the conf only when no map described it as it was placed (a row placed
before any map, or loaded where its place is not known while a map is held, takes the batch
that describes it when its session loads one, a store that cannot take that write making the
load `host_failed` with the row held in memory, and the second kind is `stale` in a later
session that no such load reached, its `why` saying so; a row an earlier session placed with no map
is `stale` once a batch describes it, its `why` saying no build beyond the conf was recorded; a
row stored without its conf is `stale` at the park, its `why` saying so). A load that gives a
raw row the text it holds takes it into this session and the batch that describes it, which is
how a `stale` row is brought back.
`unarmable`, a place that cannot be worked out now (a selector whose base needs the logfile,
a protected-mode address while the guest runs, or a raw address a load kept that this stop's
mode cannot place). Comments a rebuild or a load brought to one place are all kept, and a call
reaches the one whose ref it spells.

**The comment file** is how a project keeps its comments: `comment_save(dest=)` writes them,
`comment_load(source=)` reads them, both absolute paths, and the convention is
`<symbol file stem>.comments.tsv` beside the symbol file. Line 1 is exactly
`# comments v1: ref<TAB>cpu<TAB>created_at<TAB>text`; every other line is those four fields, the
text last and the rest of the line, so nothing is quoted or escaped; rows are sorted, so
`git diff` shows exactly the comments that changed. The `cpu` column is the format's and is
written empty here, one processor; a file that fills it is refused. There is no build column: a
raw address is trusted for the build it is loaded into. A load is all or nothing: a line the
format refuses or one address in two spellings refuses the whole file. Which refs alias one
byte, and whether a raw one lands at all, depends on the table and the mode of the stop, so a
file is refused for neither: a file saved before `symbols_load`, or on a running guest, can hold
two rows a later stop places at one byte, and both are kept and named in `note` (a save refuses
them until one is deleted); a row saved in protected mode is past FFFF at the real-mode park
every session starts at, and a real-mode `0000:` row names the null selector in protected mode,
so such a row is kept `unarmable`, named in `note`, and placed at a stop whose mode holds it; so
is a row past its selector's limit, until a stop's descriptor reaches it, and each row's `why`
names the stop it waits for (`comment_add` still refuses that address, since a call is answered
at this stop). Where the store and the file disagree, the file wins and the store's old row
comes back whole in `replaced_comments`; a row whose text the store already holds counts in
`unchanged_total`, and when it was placed in another build it is brought to this one, its ref
and stamp kept, whether this stop lists it `stale` or cannot place it yet; rows only the store
holds stay. A save replaces only a comment file, and names in `dropped_comments` what the
replaced file held that the store does not.

## Advancing the machine

`step(count=1, mode="into")` is the debugger's F11, or F10 with `mode="over"`. It refuses on a machine that is not stopped (a
keystroke to a running guest is swallowed with no error anywhere) and it **re-establishes
the position after every key** rather than sending `count` of them and reporting `count`.
That is not caution: stepping OVER a `CALL` is run-until-it-returns, so a call that never
returns leaves the machine running and the rest of the keystrokes go nowhere. `completed` is
what happened; `running` says why it stopped short. `moved` is asked per step and `stalled`
counts the ones that did not change position, because comparing only the endpoints answers
wrong on a two-instruction loop (`L: nop` / `jmp L`): it comes back where it started, so two
steps that both moved read as a swallowed key. About a second and a half per step, which is
the settle on the repaint that proves it landed. So `count` is 1 to 64 (`STEP_MAX`), a cost
bound and not a safety one: past it the question is `run_to`, which pays the settle once.

`run_to` takes a symbol or a `SEG:OFF` (`ref`, the one spelling the whole surface uses), arms
a breakpoint there, resumes, and separates three outcomes that are easy to conflate: it
**arrived** (the same linear byte in real mode, whatever paragraph spelt it, since the CPU
stops with the program's own CS:IP); it stopped **somewhere else** (another breakpoint got
there first, which is ordinary and is not an arrival); or the bound expired and the machine
is **still running**. It removes the breakpoint it created once it has arrived (`BP` is
persistent, so a leftover would silently stop the next `resume`), and it looks the index up
again to do it, because `BPDEL` renumbers.

**A `control` turns a silence into a measurement.** `run_to(ref=..., control=...)` arms a
second breakpoint at a place known to be HOT, releases the machine again each time it fires,
and reports `control: {at, hits, removed}`. A bound that expires with ZERO hits is then
INVALID rather than "it did not arrive": neither breakpoint fired, so nothing was proved
about the target, which is exactly the shape of the ROM breakpoint below. The control is
removed on every stopped outcome, since nobody asked to keep it, and each hit costs a
position read (a console round trip), so a control that fires a few times a run is the right
one. The control is REQUIRED (the schema refuses a call without one, and an empty one is
none): a cold target beside a hot control fires the control and never
the target, and with the roles swapped the target arrives, which is the difference between a
measurement and a silence.

**`run_for(frames=N)` advances by frames of the display, and a frame is one vertical
retrace.** Each is the debugger's `VRT` (run, then stop at the next retrace), sent as a release
and heard by the prompt the way `run_to` hears its stop, so a frame costs the retrace and one
read of the terminal, never a settle; the last comes back with the full stop reply. A DOS
machine keeps no frame counter a server could read, so N counts retraces from wherever the call
starts, and `frame_before` and `frame_after` are null. How far the machine went is the register
pane's own emulated clock, `pfi=` in milliseconds, read off the survey before the first frame and
the stop reply's after the last (`emulated_before_s`, `emulated_after_s`); a clock that did not
move over the run is `no_progress`. `cycles` is null with `cycles_why`: the pane's `cc=` counts cycles only on
the normal core, and which core runs is not something the server can read. The `verdict` is
`ELAPSED` when the run ran its course, `OTHER_STOP` when a declared code breakpoint stopped the
machine first (named by `attribution`), and `TIMEOUT` when the bound expired; `polls` counts the
`VRT`s a stop answered, the cut one included.

**`run_for(milliseconds=N)` counts the same clock instead of the frames.** It runs retrace by
retrace, surveying each stop for the clock, until it has risen at least N milliseconds, so an
`ELAPSED` stop is the first retrace at or past the mark: the granularity is one frame, and
`emulated_before_s` and `emulated_after_s` say what landed. Every frame then costs a survey as
well as the retrace, and `seconds` still bounds the run, so a long stretch of emulated time
wants a bound to match or it ends `TIMEOUT`. A retrace that did not move the clock ends it
`no_progress`; a repaint that painted no clock is read again at the next frame; and a pane with
no clock before the first frame is refused `unexpected_answer` before anything runs. Exactly
one of `frames` and `milliseconds` is above zero.

**A `VRT` a breakpoint cuts stays armed in the debugger**, and the next release stops at the next
retrace. So an `OTHER_STOP` says `retrace_pending: true`, and the first stop a later `resume` or
`run_to` makes that no declaration explains carries `retrace_pending: true` in its `attribution`,
with a `why` naming that retrace as the likeliest cause; a step, a `stop` or a `run_to` that
arrived is its caller's own stop and leaves it armed. Two limits the `note` states when they
apply: on a dynamic core a code breakpoint armed after its code already ran under a retrace run
can fail to cut the frames after it, while `run_to` and `resume` honour it, so an `ELAPSED` with
one declared does not prove its address was not reached; and a change-watch or an interrupt
breakpoint cannot be told from a retrace (there is no hit flag), so its stop counts as a frame.
A `TIMEOUT` reached between frames is at rest and surveyed; one that expires while a `VRT` is out
leaves the machine RUNNING with the retrace pending, as `run_to`'s still-running outcome leaves
it: `log_wait` or the next console tool meets it at the retrace.

**`trace(instructions=N)` runs the machine N instructions with the debugger's CPU log on, and
the log is the instrument.** The `LOG` family writes one line per instruction with the state
before it runs, in the four `shape`s: `normal` (`LOG`: the disassembly and the registers),
`short` (`LOGS`), `long` (`LOGL`: adds the emulated time, VM and CR0) and `cs_ip` (`LOGC`: the
address alone). The debugger reads its count in hex and writes, as its last line, the
instruction it stops at, logged and not executed, so the call sends `N + 1` in hex and an
`ELAPSED` file holds `N + 1` lines. The working directory is only the file's passing place,
because the debugger writes nowhere else: the file moves to `dest` (absolute, its directory
there, the file not, and not directly in the working directory), or to the next free
`trace-<n>.trace` in the session's captures directory, which has to exist (the working directory
itself when it is the captures directory: that name is the call's own, never the debugger's); a
`LOGCPU.TXT` already in the working directory is somebody's, refused and never read or deleted. A
working directory the emulator cannot write is refused `no_channel` before anything is typed,
because there the debugger answers the log's command `not recognized` (The console says what that
leaves); refused the file all the same, the trace answers `host_failed` when the `logfile` says
so, and `close` is the way out. What ran before a
stop is not read back: the debugger's `HEAVYLOG` keeps a ring of recent instructions but writes it
only when the emulator exits, so it is answered by a trace forward from an earlier stop.

**A trace proves its own count, because the line count is an instruction count only on the
normal core.** A dynamic core calls the log at the boundaries of the blocks it translated, and
the server cannot read which core runs, so the register pane's `cc=` counter, which on the normal
core moves by one per instruction (read across its 32-bit wrap), has to have moved by the
instructions the file says executed. A mismatch is refused `no_channel` with the file kept at its
path, and a session to trace in is one started with `flags=["-set", "cpu core=normal"]`. A stop
that comes first (a declared breakpoint or watch, an interrupt breakpoint, a retrace `run_for`
left pending) ends the run `OTHER_STOP` with the log still open: the file moves first, then
`LOGC 0` closes the log, executing nothing. An interrupt breakpoint stops inside its INT, after
the counter took it and before it ran, so a cut run may count one more than it executed. The log
writes each line before the breakpoints are checked, so a trace started on a code breakpoint's
address, or on an interrupt breakpoint's INT, stops there again with nothing executed, which its
`note` says. The machine can close the log itself (the BIOS's power-on self test does, so a trace
from the reset park meets it), and the debugger then writes `cpu log LOGCPU.TXT stopped` to the
session's `logfile`. With a stop after that, the trace is refused `readback_refused`, the lines
kept, because they are not what ran; so is an empty log, and a close that does not answer
(`closed: false`, the log possibly still open at its path). The bound expiring answers
`wait_expired` with `running: true` and a `trace` of `path` and `closed`. A log still running
stops the machine at its count, and the next trace refuses while that file sits in the working
directory, and once it is gone closes the log before opening its own. One the machine closed
during the wait never reaches its count: the reply has `closed: true` when the logfile says so,
and then only a declared breakpoint, `stop` or `close` ends the run. `closed: false`
says no such close was seen, which promises no stop: without a `logfile` the two cannot be told
apart, and the reply says so.

**A trace says which routines ran.** Every executed address is given a linear address where
its mode allows one and, inside the loaded table's span, the nearest symbol at or below it: the
rule `symbols_find(linear=)` states, by bisection over the table sorted once. The table has no
sizes, so the span ends at its highest symbol and a routine's body above that stays unplaced (a
table that also lists the data after the code, as `nm` prints a program, covers it). A `long`
line says its own mode (CR0's protection bit and VM), so each is placed by it: CS x 16 + EIP in
real or virtual-8086 mode, the base of selector CS otherwise. The other shapes do not say, so a
window is read in the mode the pane shows at its two ends: both real, every line by its
paragraph; otherwise every line through selector CS, which qualifies only as a present code
descriptor at its own requested privilege (a conforming one entered from a lower privilege does
not), read off one `GDT` and `LDT` listing at the stop, which needs a session started with
`logfile`. Those are the limits of the shapes that do not say: a window that starts and stops in
real mode but switches to protected mode in between is read by paragraphs, and a real-mode
segment that also reads as a qualifying selector is placed through it; a line whose CS does not
qualify gets no linear and `note` says so. A stop the pane names `VM86` (virtual-8086 mode) is
no mode the survey reads, so a trace is refused at one before its log opens, and one that ends
at one comes back `unexpected_answer` with the path of its log, that stop not surveyed. `long`
places every line by its own mode. `symbols` has a row per routine
(`symbol`, its own `linear`, `addresses`, `instructions`, and the lowest and highest address
executed inside as `first` and `last`), ascending; the reply carries the lowest-addressed rows,
`symbols_total` counts them all and `symbols_truncated` says when some are left out. `unplaced`
counts the executed addresses no symbol places. The set file beside the log
(`<path>.set.jsonl`, refused like the log if it is already there) has one JSON line per executed
address (`addr` as the log prints it, `linear`, `symbol`, `delta`, `count`), ascending by linear,
those without one last; one the host refuses part-way is removed and `note` says so. Every
linear is eight upper-case hex digits. With no table loaded nothing is named and `note` says so.

**The waits are bounds**: `run_to`'s, `run_for`'s and `trace`'s `seconds` is more than zero and at
most 600 (`RUN_TO_MAX`), the ceiling `log_wait`, the state tools and the `expect` waits share. A wait
holds the server's lock for its whole duration, so every other tool, `status` included, is
unanswerable until it ends; the ceiling is what stops one abandoned question from wedging a
session. Two waits are not held to it: `resume`'s `seconds` and `start`'s `plan_wait`.

**`resume` sends F5 once and says whether the machine left the debugger**: `halted` is `true`
when it is already back, and the reply is then the full stop; `false` when it runs. With
`seconds` it waits that long for a stop, listening for the prompt as `run_to` does, and when
the bound expires comes back with `halted: false`, `waited_s` and a `note` saying it is still
running, and leaves it running; the default `0` comes back at once, and a negative one is
refused, as is a malformed `e9` argument, both before any session is asked for. A guest
already running is then refused `not_stopped`, because an F5 there
does nothing and an `ok` would read like a release. Nothing has to be declared before a
`resume`: `stop` brings a running guest back, headless or windowed.

**`stop` breaks in through the debugger channel**, upstream's `mcp_server`: every session listens
on a local port the kernel picks and passes it as `-set "dosbox mcp_server=<port>"`, the emulator
dials it at start, and `stop` sends `BREAK` down it. The emulator polls the channel from a timer
tick, so it answers while the guest runs, and the debugger's prompt on the terminal is what says
the machine is back (`waited_s`). No window, no menu and no focus are involved, so `stop` works
on a headless session as on a windowed one. A build without the channel (one that predates it
upstream, or one built without the debugger) never dials, and `stop` is then `no_channel`, naming it; the
`-set` key is the session's own, so a caller's `flags` may not carry it.

**The outcome is read from `arrived` and `running`, never from `bound_expired` alone.** That
flag is the wait's own measurement, whether the loop gave up on the clock, and it is on every
reply rather than on the one branch that needed it: the position is read after the loop
ends, so a machine can be found at rest, at the target or elsewhere, with the flag true.
Where it earns its place is splitting the still-running outcome, which has two causes that
want different next moves: the clock ran out with nothing happening, or the debugger
announced a stop, the loop left early, and the nudge that followed came back cut. One note
for both would contradict itself in one object: "the bound expired" beside a `waited_s` of
nothing.

**The wait hears a stop by the prompt, not only by a register repaint.** The debugger is an
ncurses screen that repaints only the cells that changed, so a machine that stops again
redraws its code pane while the register labels stay put and are never sent. A wait that
listens to the pane alone sits out its whole bound over a machine that stopped within
milliseconds; the wait returns on the prompt, and a stop elsewhere that did outlast the
bound says so in its note.

**The wait consults the emulator, and scans only what is new.** Without the first, a session
that died the instant the machine was released burns the whole bound with the server's lock
held, so `status` cannot even be asked. Without the second, re-parsing the whole accumulated
terminal every poll is quadratic in the length of the wait. It keeps a bounded carry from
the previous read, because a read is cut wherever the pipe happened to be and a register can
arrive split across two of them.

**A CODE BREAKPOINT IN ROM IS ACKNOWLEDGED AND NEVER FIRES**, and it is documented nowhere:
`BP F000:E05B` and `BP F000:C9B0` are both accepted, both appear in `BPLIST`, and neither
stops a machine that provably executes them (the reset vector jumps to the first, which jumps
to the second); the same command at a RAM address fires first time. Two controls rule out
the obvious explanations: it is **not** the dynamic core (a `core=normal` run behaves
identically) and **not** a missing feature (`HEAVYLOG` is in the binary, so heavy debugging
is compiled in). The likely mechanism is that a breakpoint is armed by writing a trap byte
into memory and a write to ROM is absorbed, but that is an explanation, not a measurement,
because the arming happens after the machine is released and cannot be observed from a
stopped debugger. For the same reason this cannot be detected in advance, so it is named in
`run_to`'s non-arrival note, where the caller is already asking why.

**AN OFFSET IS AS WIDE AS THE CPU MODE.** Clamping `run_to` to 16 bits would refuse
essentially every interesting protected-mode address: a DJGPP `_main` sits well past
`0xFFFF`. The debugger takes a 32-bit offset and lists it: `BP 0087:00012345` comes back as
`BP 0087:12345`, which also shows the list prints a *minimum* of four hex digits rather than
exactly four. In real mode anything past `0xFFFF` addresses nothing, so that is refused
instead of being accepted and never firing.

**What a stop returns.** Every stop (`resume`, `step`, `run_to`, `run_for`, `trace`, and the tail of a
`perform`) carries its number `stop_seq` (the one `last_stop` names), where it stopped, the
`instruction` it stopped on (decoded as `disassemble` decodes it, its bytes taken off the code
pane the stop's own survey painted, which the debugger moves to CS:EIP whenever a stop lands
outside it, or off one `D` when the pane does not hold that line whole as one instruction (it
decodes in its own width, which is not always the segment's), with its nearest symbol, which
in protected mode costs one `SELINFO CS` and only with a table loaded; null with
`instruction_why` when no bytes could be read or they start no instruction), the registers,
the show watches already evaluated (each with `state: "evaluated"`), an ATTRIBUTION to the declaration whose address it stopped
at (or an honest cannot-say: the
debugger keeps no hit flag, and a memory watch stops at the instruction that WROTE), and an
E9 summary, `e9`, that is OFF by default with the count and how to turn it on, because the
guest's log can blow up a conversation: `lines_total` lines matched the filter, `unfiltered`
were logged in all, `shown` came back in `lines`. Every stop but `trace`, which takes no `e9`,
leaves it off and names `log` in `how`, turns it on with `e9="all"`, `"lines:N"` or `"since"` (the previous stop) plus
a filter; and `"seconds:N"` when the caller lends `e9_stamp`, a regex with one group
capturing each line's own time, because this server knows no clock of its own on the log
and a guest that stamps its lines (a monotonic guest clock) is the only honest one. The
window is then cut on the guest's clock, "now" being the latest stamp in the log, and a line
without a stamp is counted rather than placed.

**While the guest runs.** The debugger's console answers only while the machine is stopped,
and on macOS nothing can break a running guest in (dosbox-x #4026). Those two facts are the
emulator's. The server's part is not to turn every "the console cannot be asked" into an
INVALID while holding the answer, and to apply what it was asked to do while the guest ran.
The running-guest contract, in three parts:

- **The lists answer from what the server holds.** `breakpoint_list` and `watch_list` on a
  running guest return the declarations with the state the last stop's survey saw, say
  `debugger_read: false`, and date the answer with `last_stop` (the last stop's `stop_seq`, `at`,
  `attribution`, `since_s`, and `clock`, the host's UTC time, to the second, at which the stop
  was recorded). Stopped, they read the debugger and say `debugger_read: true`.
  Before any stop, `last_stop` is null and a symbol's state is `unarmable`.
- **What is asked while running is applied at the next stop.** `breakpoint_at` and a
  change-`watch_add` answer `state: pending`; `breakpoint_clear`/`watch_clear` drop the
  declaration now and queue the debugger's row (`pending_disarm`); `symbols_load` with an
  explicit base parses and holds the table at once (`symbols_find` answers) and loads the
  debugger at the stop (`pending: true`). The next stop applies all of it before reading
  anything and says so in `applied_on_stop` (`armed`, `disarmed`, `symbols_loaded`, and
  `still_pending` for what could not be applied). A stop that happened on its own, during a
  wait or a key, is recorded by the first tool that finds the machine at the debugger,
  `status` and `captures` included: that reply says `stopped_on_its_own` (its `stop_seq`,
  `at` and attribution), once, and carries the same `applied_on_stop` block when something
  was pending. `status` counts what is pending.
- **`last_stop`, wherever it helps.** `status` carries the last stop, and beside it `pc` and
  `cpu_mode` (`real`, `protected` or `paged`, from the register pane's mode word and its
  `PAGE`/`NOPG` mark) of the stop the machine is IN, null with `cpu_mode_why` in three
  cases: while it runs (or is gone), since the pane is read off a stopped machine; when the
  stop it is in was not readable yet (a cut pane, and `last_stop` is then the one before it);
  and when the pane named a mode that does not place it as real, protected or paged.
  `declarations` counts this server's own
  (`breakpoints`, interrupts among them, and `watches`) in any state, the rows its `_list`
  tools return, on a running machine too; a reader refused because
  the guest runs (`registers`, `read_memory`, `memdump`, `step`, `debug`, and `resume` itself,
  whose F5 would do nothing there and whose `ok` would read like a release) carries it too, with
  `answers_while_running` naming the tools that do answer; `registers(from_last_stop=True)`
  hands back the registers as they were at that stop, marked `stale`, never as a value.

What it does not do: invent a stop, or serve cached memory as a current value. A stop still
has to come from something armed before the guest was released, which is why the pending
queue is drained at the stop and not before. `resume`'s own pre-check reads what the
debugger has armed as well as what the store declared, so the target breakpoint a `run_to`
left armed after stopping elsewhere counts as something that can stop the machine.

**`RUNWATCH` ships no tool.** The debugger has it (resume the machine while going on painting
its state) and it is the obvious way to watch a program move. It is a hose: it resumes and
repaints without pause, filling a settle window many times over, and writing `RUNWATCH` a
second time does not turn it off, so the session that tries it has to be abandoned, which is
why `debug` refuses it (The console). A tool with no way back leaves the caller holding a
wedged session and a terminal nobody can read, so it is recorded as a finding rather than
delivered. Anyone picking it up again needs to
find the OFF switch first.

## Reading and writing

`read_memory` hands back ROWS rather than a screen. This debugger paints its Output log BELOW
its Data view, so a positional cut of the terminal's tail can fall inside the eight rows, and
a read of one address comes back beginning at another with the reply saying `ok`. It reduces
by MEANING and refuses when the address asked for is not among the rows it found; for an
exact number of bytes, `memdump`.

**`memdump` past offset 0xFFFF reads the memory really there, or refuses.** The debugger reads
each byte of a dump at its own segmented address, which wraps a 16-bit segment's offset at 64
KiB and gives a byte past a protected-mode descriptor's limit no address, writing a zero, and
both come back with a success line and the length asked. So a range inside offsets 0 to 0xFFFF
is one command: a 16-bit and a 32-bit segment address it alike, and its limit is not judged
there (past it the debugger reads zeros). A longer one in real mode is read in windows that
each sit inside one segment's 64 KiB, joined in order, up to `FFFF:FFFF`, the last byte a
real-mode address names, and refused past it. A longer one in protected mode reads the
selector's descriptor off the `GDT` or `LDT` listing, so it needs `logfile` (`no_channel`
without) and costs those listings, and is refused on a 16-bit segment, past the limit, or for
a selector with no descriptor, rather than handed back with a wrapped copy or zeros in it. The
selector in `CS` is judged the same way, although the debugger reads it through its cached base
and no limit. A v86 stop, which the pane names `VM86`, is not a mode the stop survey reads, so
a range past 0xFFFF there is refused with it. `find` takes the same route, and in real mode
names a hit past offset 0xFFFF from its own paragraph, since an offset that large addresses
nothing there.

**And where the read boundary falls does not decide what comes back.** An escape sequence
can straddle two reads of the terminal, so the head is held and prepended to the next one
rather than being stripped as text, INCLUDING when the head starts at offset zero, precisely
when the head is all there is to hold: the same escape split three ways (whole in one read;
split with text before it; split with the escape as the first byte) has to yield the same
row, or a fragment stripped alone injects its final byte into the row's hex. The hold is
bounded by LENGTH, because an unterminated OSC matches from the first byte of every later
read and an unbounded hold would swallow the stream and go blind while reporting nothing
wrong.

`write` and `set_register` READ BACK what landed (`readback`, `verified`) and mark the session
altered for good: a write into ROM is taken and changes nothing, which the readback says.
A register is read back where the pane paints it and at its own width: a 32-bit name as its
whole register, a segment register under its own name, and a 16-bit name (`ax` .. `sp`, `ip`)
as the low half of its 32-bit register, because the pane shows `EAX` and never `AX`.
Compared whole, `ax` would read `verified: false` for a write that landed whenever the high
half was not zero. A value wider than the register, or negative, is refused before anything
is sent, naming the width, so `altered` does not move for it.

`find(data_hex, ref, length)` takes the pattern first; `ref` and `length` are required,
because there is no default range to search. It dumps
the range by `memdump`'s route into a scratch file of the call's own and searches it exactly,
because the debugger has no pattern search; the scanner family (`scan_start`, `scan_filter`,
`scan_clear`) is the debugger's own `MEMFIND`/`MEMS`, one scan at a time (a `length` of whole
cells of its `width`, and a filter `value` no wider than the cell of a scan `scan_start`
opened, both refused
before the debugger is asked), paged by the
debugger and turned with a bare ENTER because a command typed while a page waits is eaten
one keystroke per page. With no `value`, a filter compares each cell with what it held when
the scan OPENED, not at the previous filter: `!` keeps the cells that changed since then,
`=` those that did not, and a cell changed once and left alone keeps passing `!`. Every
filter reply says `hits_total` and `truncated`: above `limit` survivors, 40 unless asked
for up to 400, `hits` is empty and the listing is never typed (`find` keeps its highest
400 instead), and `iterations`, which the debugger prints on every filter but the one that
closes the scan; there the server answers its own count, or `null` with why when `debug`
touched the scan.

**`disassemble` decodes on the host, because the debugger has no disassembly command.** Its
code pane decodes what it shows (`C seg:off` moves it), one screen of lines with the bytes glued
to the text; a listing of any length is read by `memdump`'s route into a scratch file of the
call's own, `length` plus the longest x86 instruction so the last line completes (in a 32-bit
segment the few of those past offset `FFFF` come off one `D`, never past the selector's limit,
so a listing that ends below it needs no `logfile`), and decoded by capstone. The width is the
segment's own D bit, as the pane's decoder takes it: real mode is 16-bit; in protected mode the
register pane's `Pr32` or `Pr16` is CS's, `SELINFO` prints it for a selector another segment
register holds (the fourth of the five digits under `parbg`), and the `GDT` or `LDT` listing for
one no register holds, which needs `logfile`. `code_bits_from` says which.
A 16-bit segment ends at offset `FFFF` and IP wraps there, so a `length` that runs
past it is refused, naming the most bytes from that address. `flow` comes from the decoder's
instruction groups, not from its text: an interrupt is a `call` (it hands control to a handler
the way a call does), `loop` and the conditional jumps are `branch`es. With a table loaded, `resolved` names what the decoder's
operand details say is DIRECT: a call or branch target (near, in the line's own segment; far,
in the segment its pointer names) and a memory operand with no base and no index, placed under
the segment register it is read through (an override, else DS) at its value at this stop,
because that register is what the CPU will use; a row outside the table's span has `symbol`
null, and one that could not be placed (a register the pane did not show, a selector with no
descriptor) has `linear` null and says `why`. The pane is the control the decoder is tested against, line by line (address, length,
bytes, mnemonic, and operand by operand the numbers and registers), and where the two differ
only in spelling (`jc` for `jb`, the implicit operands of a string instruction, a size word, a
loaded symbol in place of an operand) the tests record it with its opcode. Where the pane is
wrong about x86 it is right about itself: it reads `FE /7`, which no x86 decodes, as `callback`
with a word after it, because that is how DOSBox's own code is entered from the guest; and in
real mode it looks a segment number up as a selector, so `C 0000:0000` decodes the vector table
32-bit.

**`call_stack` is a guess and says so.** A DOS program keeps no call stack anyone can read: the
CPU pushes a return address and moves on. What compilers leave is a frame chain, BP pointing at
the caller's saved BP with the return address one slot above (C's `push bp; mov bp, sp`,
Borland's `enter`), so the walk follows BP and, before trusting a return address, checks that
the bytes ending at it decode as one call instruction, near or far (the far one's segment is the
next slot up). That check is what turns a stack full of stale words into a chain: a word that
merely looks like a code address follows no call. At a routine's first instruction the frame
does not exist yet, and at its `ret` it is gone, so the caller is read off SP (`via` `entry`),
an offset past `FFFF` of a 16-bit stack wrapping to its start as SP does. A
return is named by the routine its call is in, since a call that ends a routine returns to the
first byte of the next. A routine compiled without a
frame pointer is invisible: the walk names its caller's caller in its place, or stops. The walk
ends at a zero or non-rising saved BP, a frame past the stack segment, a return no call precedes
(not listed), a return outside the loaded table (listed, then the end), or its bound, and
`ended_why` says which. Its reads are the data view's, each `D` reused while it covers the next.

**`machine_map` is the machine as the debugger lists it, read off the logfile.** By default it
reads the DOS machine and the cpu (`mcbs`, `devs`, `kern`, `xms`, `ems`, `ems_pages`,
`emu_mem`, `machine`, `cpu`, and `gdt`/`ldt` in protected mode), and leaves `bios_mem`,
`callbacks`, `vga` and `paging` unread, naming those this mode has in `omitted`. `sections`
names the ones to read instead, and only those listings are typed, plus `CPU`, which says the
mode; `dest` writes every section read whole, lists uncut, as JSON. Each
section is one debugger command and keeps its listing's words: `DOS MCBS` gives `mcbs`, `DOS DEVS`
`devs`, `DOS KERN` `kern`, `DOS XMS` `xms`, `DOS EMS` `ems` and `ems_pages`, `BIOS MEM`
`bios_mem`, `CALLBACKS` `callbacks`, `EMU MEM` `emu_mem`, `EMU MACHINE` `machine` and `CPU`
`cpu`, each field named by its column. The rows come from the session's logfile and never
from the screen: the debugger writes a listing there with its columns intact, while the
repaint draws the columns with cursor moves the escape strip removes, so on the screen a
segment and a size run together. A session started without `logfile` is refused
`no_channel`. A listing longer than the Output pane pages, and the pager eats every key it
is given, a command included; so the reader answers it with `Q` alone, which prints the rest
of the listing and empties the input line, and an input line still holding text after that
is refused `unexpected_answer`, because the next command would be appended to it rather
than run.

**Which sections exist depends on the mode, and an absent one says why.** `cpu_mode` is read
off the `CPU` listing's cr0. In real mode the descriptor lists `gdt` and `ldt` are absent,
because there the debugger reads the interrupt vector table as descriptors (the `cpu` section's
own `gdt` and `ldt` are the table registers, present in every mode); in protected mode they
come back with their empty slots dropped. `paging` is absent with paging off, and with it on
comes back as runs of pages contiguous in linear and physical memory with the same flags, `d`
and `a`, so expanding a run page by page gives the listing back. A section whose listing the
debugger refused (before DOS has booted: `Cannot enumerate MCB list while DOS kernel is
inactive.`), printed nothing for, or printed a line no known shape matches is ABSENT rather
than partial, and `coverage_note` quotes the sentence or the line: a chain with one block
skipped would read as the whole chain. A free block keeps the stale name DOS leaves in it,
and its `psp_seg` of `0000` is what says it is free. A listing with a heading and no row,
`xms` on a machine with no handle, is an empty list and not an absent section; the MCB chain
is the exception, since DOS always holds a block of its own, and the debugger walks each
chain by the sizes: every block after a chain's first starts right past the one above it (its
header paragraph and its size), and `END OF CHAIN` sits right past the last. A chain that
lists no block, breaks that walk (a block missing between two others or at the end) or stops
before its `END OF CHAIN` line is a cut chain, and `mcbs` is absent; a chain's first block
has nothing in the listing to check it against. Every list section is cut at the ceiling
`log`'s lines take, and the reply says so: `counts` holds each section's full length,
`truncated` whether any list was cut, and `sources` the command behind each section present.
Every call reads live, one console command per listing (two when it pages), so it answers for
this stop and costs a settle per command. The last section, `vga`, is the VGA's state, what the
screen is being drawn from: `VGA MODE`, `CRTC`, `SEQ`, `GC`, `AC`, `DAC` and `DRAW` under
`mode`, `crtc`, `seq`, `gc`, `ac`, `dac` and `draw`, each the listing's own `key=value` words
with `-` as `_` and the text it printed, the AC's sixteen palette registers as a list; one
listing it cannot read makes the whole section absent, quoted, like any other.

**`interrupt_vectors` is the vector table, each handler with the block that holds it.** The
table is the file the debugger's `INTVEC` writes: in real mode the table at `0000:0000`, in
protected mode the IDT, whose entries are selector pairs. The server names that file
`MCPIVT.TXT` in the emulator's working directory, reads it and removes it whatever happens,
and one already sitting there, a dangling link included, is refused and left alone, because
it is somebody else's.
`number` is an integer, 0 to 255, and narrows the reply to one vector (`bad_argument`
outside, before anything is typed; `not_stopped` on a running guest). Each vector's `linear`
is `segment*16+offset` in real mode, and in protected mode the base of the descriptor its
selector names in `gdt` or `ldt` plus the offset; with paging on, the block that holds it is
matched on the address that linear maps to through the page runs. The row of `mcbs`, `kern`
or `bios_mem` whose bytes hold it comes back under that section's own name (first match in
that order), which answers which program or resident hooked a vector without comparing
against an earlier table: a table taken at `start` is all zeros, since the park comes before
DOS fills it. A free block holds a vector under its stale name and its `notes`, which is
what a vector left pointing into freed memory looks like. `symbol` is given only between the
loaded table's lowest and highest symbol, so past either end no name is invented; inside, the
nearest symbol at or below comes with its `delta`. Without `logfile` the table comes back
and no vector has a holder; in protected mode none has a `linear` or a `symbol` either,
because the descriptor tables are listings too. `coverage_note` says why for every vector it
could not place.

## The log

`log` reads one `channel` of the logfile, filtered **in the server**: `guest` is the program's
own 0xE9 instrumentation, `emulator` DOSBox-X's own lines, `all` the file in order with every
line tagged; the listings `machine_map`, `interrupt_vectors`, `palette` and the screen tools ask
the debugger for land in the same file, among the `emulator` lines. `log_wait` is the waiting form, and its two
semantics in one tool are the design rather than a convenience. Between launching the emulator
and asking, the thing you are waiting for **may already have gone past**; a tool that only
waited would sit out its whole bound and then report that it never happened, which is false and
costs exactly the length of the bound. So `log_wait` reads what the log already holds first and
waits only if it must; `already` tells you which of the two answers you got, because one is
history and the other is something you were present for.

It returns the **first** match (the question is "when did it happen"; `lines_total` says how many
there were, so a caller who wanted the latest knows to use `log`, which keeps the newest).
`waited_s` is measured, and is `0.0` exactly when it had already happened.

**Each refusal takes one last read of the log first.** The loop asks whether the emulator is
still there BEFORE it reads and leaves on the deadline AFTER it, so a line written in either
of those gaps (between the final poll and the death, or between the final poll and the
clock) would otherwise never be looked for at all. That is the canonical wait: for a guest's
**exit trace**, which is written on its way out.

**Only one of `log`'s three refusals survives here**, and that is deliberate: a session with
no logfile has no channel and waiting cannot create one, but a log that does not exist YET
and a log with no instrumentation IN it are the ordinary state of a guest that has just been
resumed. Refusing on all three makes the tool unable to wait for the guest's **first** trace.
Those two states are reported in the expiry instead, where they are an answer about the
window.

**A wait on a machine stopped at the debugger ends at once**, refused with the position: a
stopped guest writes nothing, so a wait for it cannot end, and its expiry would blame the
program. What the log already holds is still answered first, stopped or not, and the check is
passive (the prompt the stop prints), never a console round trip. `send_keys` with `expect`
and `drive` wait the same way and refuse the same way.

**And the check is made at every poll AND at the expiry**, so a stop that lands DURING the
wait (a breakpoint armed before the post, firing after it) comes back as the stop, with
`last_stop`, never as "still running". Otherwise a miss says "the emulator is still running"
about a machine the debugger has held for seconds, and the next key is refused for exactly
that: the prompt of that stop is consumed as the reply to a command typed at the running
guest, nothing counts it, and every passive look afterwards finds an empty terminal. The
prompt is counted wherever it is read, and the pre-check is the passive one, which also stops
costing every key the settle of a nudge nobody answers.

**A bound that expires is INVALID, never an empty answer**, and the refusal names what it
examined: how many instrumentation lines arrived DURING the wait, how many are in the log
altogether, and for how long it watched. Those first two are different facts, and reporting
the second under the first's name makes a wait in which nothing happened, on a log carrying
thousands of earlier traces, say that thousands of lines went past, which anyone diagnosing
a silent guest reads as a live channel.

**It reads only what is NEW, from a byte offset, and only whole lines.** A log written
through ordinary stdio ends mid-line between flushes, the steady state while a writer is
producing, and a reader that splits the file by lines and indexes by line NUMBER hands back
a fragment that consumed an index and matched the E9 prefix, with its payload missing; when
the rest arrives the count does not grow, so the completed line is **never tested**. Reading
from an offset also bounds the cost: re-reading the whole file at every poll is quadratic in
the length of the wait, with the server's lock held, growing as the log grows underneath it.
"Wait for X" answered with "no lines" cannot be told from "there was no channel to match
against", and those are different facts about the world.

**What you can do with the moment is narrower than it looks**, and it is said out loud here
because the alternative is finding out after a run you cannot repeat. A guest writing traces
is a guest that is **running**, so ordinarily the machine is still running when this returns
from a wait, and this debugger's console does not accept commands then, which every reader
here demonstrates by refusing. **So you ordinarily cannot arm a breakpoint at the moment you
were just handed**, and you should ASK rather than assume: a breakpoint armed earlier can
fire between the line being written and the poll that read it, and this reply carries no
`running` field to tell you. The reason is the **console**, not dosbox-x #4026: that issue is
about breaking IN with a host keypress, a different path, and one `breakpoint_interrupt`
demonstrably works around.

So what the moment is for: choosing an address to `run_to` or `watch_add` on the **next**
run, armed before the machine is released. It is also the timestamp you would need to find
the frame in a video capture, but nothing here maps a guest timestamp to a frame index, so
that is something you can do by hand, not something this does.

There is also no breakpoint on the log itself, and that is not an oversight in this server:
**not one of this debugger's breakpoint commands acts on a port, an I/O access or a log
message.** The nearest thing to "stop when the guest logs this" is a change watch on the
variable whose change produces the line.

## Sequences in one call

`perform(steps)` runs a list of the server's OWN operations by name
(`{"op": "breakpoint_at", "ref": "_uicue_apply"}`, `{"op": "resume"}`, ...) in order, and
STOPS at the first failure with a full account: the steps that ran with their replies, which
one failed and why, and the machine's state. `start(plan=...)` runs the same list on the
fresh session.

**The list is checked whole before its first step runs**, and not only for shape: every
step's operation, argument names and argument VALUES go through the same checks each tool
runs first on its own (a key name no route knows, a pattern that does not compile, a step
count past the ceiling, a wait that is not a bound, a raw address that does not parse, an
argument of the wrong type, a required argument missing). A batch with a mistake in step 3
does not press the keys of steps 0 to 2 and then stop: the reply is INVALID with `errors`
listing every refused step, `ran` is empty, and the caller fixes the batch once. What only
its step can judge still refuses there, with `failed_at` and `ran` as the honest account: a
symbol name against the table loaded by then (`symbols_load` may be an earlier step of the
same list), a file an earlier step writes, and anything that needs the machine. `debug` is a
step like any other tool, and the last resort inside a list as outside one.

Every tool but `build_check`, `start`, `close`, `perform`, `drive` and `perform_export` is a
step, read off the
server's own registry. A `resume` ends the console-driven part of a sequence. After it, what
answers on a RUNNING guest runs at once: the one table a running-guest refusal lists in
`answers_while_running` (`status`, the log, `symbols_find`, the input, the captures, the
saved states, the snapshot, `stop`, the declarations, `comment_list` and `comment_save`),
the five it adds for a caller
outside a list (`registers(from_last_stop=True)`, `close`, `drive`, `perform`, `perform_export`)
apart. A
declaration there answers `pending` while the guest runs and is armed at the next stop, as the
same call made outside a sequence does, instead of waiting for a stop first; a `stop` brings
the machine back, and whether a step stopped it is the session's to say, never the step's
name. Before any other step (`registers`, and `symbols_load` even with a `base`, which it
could take on a running guest outside a list) the sequence waits, bounded, for the stop a
breakpoint produces. If the list ends with the step that released the machine, the reply
carries the enriched stop it was heading for, and so it does when the last step met a stop (a
`stop`, or a breakpoint that fired while a declaration or a key went in); if it ends in a
running-guest step with the guest still running, the tail waits only while something declared
can still produce a stop (a breakpoint, an interrupt, a change-watch), and with nothing
declared it returns at once, still running, and says why. `wait` runs from 0, which never
waits, to 600 (`RUN_TO_MAX`), and `drive` takes the same `wait`.

A `resume` inside a sequence drains what the console steps before it left in the terminal as
the key goes out, so their prompt does not read as the resume's halt. What the drain does NOT
change is the listing you will see in the resume's `screen_delta` (`detail=True`): the F5's own
repaint carries the debugger's Output pane, which replays the last console output, so a
`breakpoint_list` typed before the key shows up in it as "Breakpoint list:" however long the
machine sat quiet. That is the pane, not a leak, and it is why `screen_delta` is a POSITIONAL
tail capped at its last 2000 characters, `clipped` saying when (a running guest painting its
log pane reaches the cap inside the settle, and that tail is the log PANE as the debugger
paints it, not the log: `log` reads the log), for reading an immediate stop and never for
counting anything.

**A stopper that fires in a LOOP ends a key sequence early, and correctly.** A breakpoint on
something the program does every cycle (a seek on each A-B wrap, say) stops the machine
again at the next pass, and the `expect` of the next key is then refused for a stopped
machine: the right answer, and not the one you wanted half-way through a confirm dialog.
Clear what fires in a loop (`breakpoint_clear` of that ref, or bare) ahead of the `resume`
that releases the machine, in the same `perform`, before a sequence of keys that has to run
to its end.

**`summaries=True` keeps a long list readable.** Every step but the last one that ran
becomes a compact row: its `step` index, its `op`, and its reply cut to `summary`, `status`,
a stop's `stop_seq` and `attribution`, and `stopped_on_its_own` when the step found one. A
list that fails keeps every step before the failure compact and the failing reply whole under
`failed`. `ran` shows the first `ROWS_SHOWN` (24) rows and the kept step, with `steps_total`
and `truncated`; every compact row goes to `ran_path` and every full reply to
`replies_path`, JSON Lines in this server's own scratch directory (never the session's
`cwd`), numbered per call, both or neither. `stops` is the server's count of the stops it
numbered during the call: the range (`stop_seq_first`, `stop_seq_last`), how many the replies
`surveyed`, a count per attribution in `by_how` (`unattributed` for a stop no declaration
accounts for), and `unaccounted`, the stops numbered that no reply surveyed. `drive` takes
the same switch for its act. The reason is size: a run of stops each carrying its registers,
watches and log crosses what a client keeps in line, and a count assembled by hand from
summary lines is the number that comes out wrong.

**The loop: `drive`.** An autonomous session steps a program the way a browser is driven:
look, act, verify, and go again. `drive(act=[...], expect=..., pattern=..., limit=N)` is that
loop's one turn. The E9 log is MARKED before the first step; the steps run exactly as
`perform` runs them (each `send_keys`/`send_mouse` with its own `expect` if it has one); with
`expect` the call then waits for a NEW matching line from the mark, so the act as a whole is
verified and a miss comes back INVALID with the account of what ran (and when the act ended
with the machine stopped at the debugger, the log is read once instead of waited on, because
a stopped guest cannot write); and `looked.e9` is what the guest wrote since the mark,
matching `pattern` and cut to the last `limit`, with the counts that say what was cut
(`lines_total`, `truncated`), in `log`'s own words. An act
that ended at a stop carries the enriched stop reply in `act.stopped`, as `perform`'s tail
hands it over. A verification that read from the top of the log would find the cue that
fired ten seconds ago, and a look taken before the act would be the previous act's: the one
mark, taken before anything moves, is what makes both honest. A screen is not part of the
look: the still needs a recording and `ffmpeg`, and `capture_frame` offers it on its own.

## From an investigation to a bench

Every session is recorded from the `start` that succeeds, and cleared by the next one; `close`
keeps it. `perform_export(path)` writes it as `perform`'s own document, and the runner plays it
back with no model, from this repository:

```sh
uv run python -m scry_core.replay <document> [--binary PATH] [--transcript PATH]
```

It exits 0 when every step held, 1 when a step diverged or failed in the server's own words (or
`perform`'s `held`, the steps it held to their `recorded` answer, is not the document's count), 2
on a usage error, and 3 when nothing was demonstrated: a document that is not one or holds no
step with a `recorded` answer, a start the server refused, a saved state it loads and the server
lacks, declarations the replay's store holds unlike the recorded start's, and a server that
broke (did not start, died or timed out mid-call, answered an error result, refused the list
whole). The whole transcript goes to `tmp/replays/<document stem>/transcript.md`. A replay is deterministic on a conf with a fixed
cycle count (`cycles=fixed <n>`); under `cycles=max` the guest's own clock follows the host's.

What the export keeps is what moved the machine and what was checked:

| A call of | Becomes |
|---|---|
| a tool that changes the machine or what the next call acts on (`write`, `set_register`, `run_to`, `run_for`, `step`, `trace`, `state_save`, `state_load`, `symbols_load`, a declaration...) | a step; one that left the guest at a new stop holds to the `registers` its reply carries (a `state_load` answers none, so it holds to nothing) |
| a `debug` line | a step whose answer is never held to: what a typed command printed is the console's; one that moved the guest holds to its stop like any advance |
| `read_memory` | a check of `hex` |
| `registers` | a check of `registers` |
| `screen_signature` | a check of `signature` |
| `golden_check` | a check of `matched`, `differing`, `missing` and `extra` |
| any other read, `snapshot`, `capture_frame`, `series_capture`, `memdump`, `comment_*`, the scan, `machine_map`, `interrupt_vectors`, `palette`, `screen_view` | dropped, named in the reply with why; one that moved the guest is kept as a step |
| a call the server refused | dropped, named; one that moved the guest first ends the document |
| a release (a `resume`), a `stop` or `screen_wait` that ran the guest and came back stopped (at a breakpoint or a found text included), a call whose wall-clock bound ended it (`TIMEOUT`), one that ended with no reply | the end of the document: the reply's `cut` names it and why. Whatever ends such a run stops the guest at a place no replayed advance reaches, and every stop after it inherits the shift |
| a call that found the guest elsewhere than the call before it left it | the end of the document, named: the motion happened outside every recorded call |
| a kept step that wrote a file the session named (`dest`) | the end of the document, named: a replay finds the file there and the step refuses it |

`perform` and `drive` are recorded as their steps, and the steps of a `start`'s `plan` after the
start. A step's check is `"recorded": {<field>: <value>}` inside it, and `perform` holds the
step's own reply to it: a mismatch is INVALID `diverged` at that step, with `field`, `recorded`
and `got`, the list stopping there. A caller keys on `failed_at`, which a failed step and a
diverged one both carry; the code says which (the machine differs, not the step). `held` counts
the steps that matched. The document names the server's entry file (`entry`, here
`dosbox_x_server.py`). Its `needs.states` lists the saved states it loads and does not save,
which the runner checks against `state_list` before it plays anything; `needs.declarations` the
breakpoints, interrupts and watches the store held as the recorded `start` began, which the
runner holds the replay's `breakpoint_list` and `watch_list` to. A recording keeps at most 5000
calls, counted over the calls the export keeps, past which the export says it is cut there. The
document carries the `start`'s arguments as given, host paths included; `--binary` replaces the
emulator's.

What a replay cannot hold to, it says at the step rather than passing over it. The `start` re-arms
the declarations it finds stored for the conf, as any start does, which is why the runner checks
them first. A session meant for a bench keeps its states in a directory of its own and leaves
`dest` empty. A `golden_check` over files a dropped
call wrote (a `snapshot`, a `series_capture` and its manifest) is dropped too: the replay would
not write them, so it would hold to the session's own.

## Input and the screen

Every input goes in INSIDE the machine, and nothing about the host is touched: no window
comes to the front, the host pointer never moves, no Accessibility grant is asked for, and
the window's scale changes nothing the guest sees. The emulator's COM1 is a TCP client of a
port the session listens on (`serial1=nullmodem server:127.0.0.1 port:N transparent:1`;
`start`'s `input_port`, 1024 to 65535, or a free port when it is omitted; transparent, so a
byte 0xFF is data) and DOSBox-X's integration device is switched on (`integration
device=true`), both as `-set` overrides the conf need not carry; the emulator dials before the
guest runs an instruction. A tiny
resident stub, `guest/INJECT.COM` (its source is beside it, and its header is the protocol),
takes ONE command off the socket on every timer tick and carries it out in the guest: a scan
byte into the emulated 8042, a mouse button into the device's button register, the pointer
placed with INT 33h, a report of where the pointer is, a screenshot through the device's
capture trigger. One command per tick is the 8042's own pace (the stub's header says why).

What the conf owes this route is ONE line: its autoexec runs the stub before the program
(mount the package's `guest/` directory, or copy the COM next to the program). A session
started with `program` needs none: `start` loads the stub with two `-c` commands of its own
ahead of the program's (why a conf that runs its own program needs the line is under *The
session*, `program`). A conf that runs the stub AND a `program` session end with one copy: the
second says `STUB  . inject already resident` and leaves. The stub says `STUB  . inject
device=present proto=2` on the E9 when the device answered, and exits saying `absent` when
it did not; the first input reads that line off the log and refuses (`no_channel`, naming
the fix) when it is missing, when the device is absent, or when the stub speaks another
protocol, because an older stub reads every byte as a scan code and a mouse command would
arrive as keystrokes. A session with no `logfile` has no line to read: keys go out on the
conf's word, and the mouse, which reads its pointer back through the log, is refused. A conf
that configures `serial1` itself loses it to the route. The session listens on the port before
the emulator exists and holds it, so nothing can take it between the pick and the emulator's
dial; a port something else already holds is refused before the emulator exists.

**Keys.** `send_keys` composes scan code set 1 on the host, makes, breaks and the E0 prefix
of an extended key, with `modifiers` (`shift`, `ctrl`, `alt`) held across the keys; a DOS
keyboard has no command key, and `cmd` is refused by name. At most 64 keys a call: every
scan byte waits a timer tick under the session's lock. The reply says `route: "guest"` with
`posted` (keys), `bytes` and `ticks` (scan bytes). A key sent to a machine stopped at the
debugger is refused, because the bytes would land, unannounced, at the next resume.

**An input that went in is not one the program took, and `expect` is how you tell them
apart.** A modal popup can capture the cue key while the post succeeds. So give `expect` a
pattern over the guest's E9 log that only the program's REACTION writes, and the tool marks the log before
the post, posts, and waits up to `seconds` for a NEW matching line. `effect.seen: true` with
the line means the program acted; a miss is INVALID, still reporting the post, because a
swallowed key and a key never sent are different facts. The pattern is matched against what
the program LITERALLY writes, so read its log once before choosing one: a program that logs
`key down x mods=4` for alt+x and `key down SPACE` for the space bar is telling you the case
it uses. Only an expired wait is the program's miss. A machine that STOPPED at the debugger
while the wait looked is a miss too, but one that names the stop
(`effect.stopped_during_wait`, `last_stop` with the address and the declaration it is
attributed to) and where an undelivered key waits: the serial buffer, landing at the next
resume. Whether the key landed BEFORE the stop is the guest's log's to say, not the reply's
(a key can go in and its own reaction produce the stop), so `log` since the post is the
judge, and the reply says how many lines were on disk while it looked (`lines_on_disk`,
`waited_s`), the emulator flushing its log in its own time. A machine already at the
debugger BEFORE the post is refused: a key posted to a stopped machine waits where nothing
measures it. A reaction the guest logged just before the stop is still found:
every refusal from inside the wait takes one last look at the log first. An emulator that
died or a log that shrank underneath the wait come back as `effect.checked: false` with the
wait's own words, never as "the program swallowed it". Without `expect` the reply says
`effect.checked: false` in so many words: what went in is known, what the program did is not, and
`seconds` with no `expect` is refused rather than ignored. A program that writes no
instrumentation gives this nothing to confirm against, and that limit is stated rather than
papered over. What the mark cannot bracket is the post itself (one command per tick): a line the
guest writes in that window is served, with `effect.seen_before_waiting: true` and
`waited_s: 0.0` as the tell, and `lines_before` says how many lines the guest wrote between
the mark and the reaction. The field is not called `already`: that reads as "it had happened
before the key was sent", and it would say so about reactions stamped after their posts.

Timing is coarse: an input lands "now", a tick at a time. For a key that must arrive at a
precise guest instant, stop there first (`run_to`, a change-watch), send, then `resume`: the
debugger provides the WHEN and the stub provides the key.

**The mouse: a position, set and read back.** `send_mouse` takes a move (`x`, `y`), a
`button` (`left`, `right`, `middle`) with an `action` (`click`, `double`, `down`, `up`), or
both, the move first. Coordinates are in `units`: `screen` by default, the units
`screen_view` counts in (character cells in a text mode, pixels in a graphics one), or
`mouse`, the DOS driver's own coordinates. Every call asks the stub where the pointer is
BEFORE (the driver's range and the BIOS mode, which turn screen units into the driver's) and
AFTER (where it went), and the reply carries the read-back: `pointer.screen` with `x`, `y`,
`width` and `height`, `pointer.mouse` with the driver's `x`, `y`, `max_x`, `max_y`, the
buttons held, the mode. `arrived` says the read-back is where the call asked; when it is not,
`asked` beside it says where it was asked, in the driver's coordinates, because a text mode
places the pointer on its cell and a
program's own range (INT 33h AX=07h/08h) clamps it, and the reply reports the guest's answer
rather than rounding it away.

Why the pointer is SET rather than moved: the device's motion registers feed DOSBox-X's
relative motion, which the driver scales by its mickey ratio and sensitivity, so one delta
lands at a different guest distance per mode and per axis. INT 33h AX=04h puts the driver's
pointer where it is asked. `screen` units know the standard BIOS modes (text, as many cells as
the driver's range holds at eight units a cell, so 80 by 25 or 80 by 50; 320x200, 640x200,
640x350, 640x480); in any other mode (VESA, a custom one) they are refused
naming the mode, and `units="mouse"` reaches it in the driver's coordinates. A target off
the screen or outside the driver's range is refused before anything is sent, as is a session
without a `logfile` (the read-back goes through it). A double click is two clicks a tick
apart, which is what a DOS program timing its own double click sees; a drag is `down`, a
move, `up`. What the route does NOT reach: a mouse driver loaded inside the guest, a program
reading the PS/2 port directly, and a program that reads the driver's motion counters (INT
33h AX=0Bh): setting the pointer produces no motion, and DOSBox-X counts motion only while the
host mouse is captured. The stub's own report line is never served as the program's reaction
to `expect`.

**Capturing what the screen shows: both halves, and they are not symmetric.** Start the
session with `capture_video=True`, a `program` for the recorder to wrap, and a `captures_dir`
to write into. Then:

- **The video** is DOSBox-X's own doing (`DX-CAPTURE /V`) and needs no keypress. `captures`
  hands back the files with their frame counts.
- **A still** of the running screen is `snapshot`: the stub writes the integration device's
  capture trigger and the emulator writes the PNG, on any session with a `logfile`, headless
  included (its command is a scan code to an older stub, so the log's announce has to say
  which stub is resident). A still
  out of a recording is an **extraction** from the video, via `capture_frame`, which needs
  `ffmpeg`, whose absence the tool names rather than working around.

Two capture files is the normal case, not a fault: the recording restarts when the guest
changes video mode, so a program that boots in text and then goes graphical leaves a small
first file and the real one after it. `captures` returns them largest last, and that is the
order `capture_frame` defaults to.

**`complete: false` is information, not damage.** It means the recording was never finalised,
which happens when the program under capture runs forever or the session is closed
underneath it. A frame comes out of an unindexed capture perfectly well.

**The still is always a PNG, whatever `dest` is called**, because inferring the encoder from
the extension hands back a frameless video container as a still: asked for a frame past the
end with a `.mp4` destination, ffmpeg writes a small container with no frame in it and exits
0. And a `%` anywhere in `dest`, parent directories included, is refused: the image muxer
reads the whole path as a numbering template, so what ffmpeg opens is a path the caller never
named. The refusal is broader than the hazard on purpose, because that direction fails
loudly and the other fails silently.

**And a `dest` already there is refused, never deleted.** A tool that unlinks `dest` before
asking ffmpeg for the frame leaves the caller's file gone when the frame is past the end of
the capture (ffmpeg writes nothing and exits zero) and the reply INVALID about the frame. The
same holds for `memdump`: a `dest` that exists is refused before the debugger is asked
anything, so nothing of the caller's is overwritten and no dump is left behind.

**One constraint on your config:** `program` is passed with `-c`, and `-c` runs **after** the
config's `[autoexec]` section. A config whose autoexec ends in `exit` quits the emulator
before that command is ever reached, so `program` needs one that mounts what it needs and
does not run-and-exit. `captures` says this when nothing appears, because the symptom is an
empty directory and the cause is elsewhere.

**`palette` is the DAC as the debugger lists it, never a picture of the screen.** `VGA DAC`
gives its width and mask (`bits`, `pel_mask`), `VGA DACPAL` its 256 entries, read off the
logfile like `machine_map`'s listings, so it needs a `logfile` and a stopped machine and alters
nothing. `rgb` is each entry as printed, three six-bit components; `colors` widens each to
eight bits by repeating its two top bits below (`2a` is `aa`, `3f` is `ff`), which is how the
emulator renders them: a plain shift leaves the brightest entry short of white. A DAC in any
other width is refused rather than widened by a rule written for six bits. The entries are
always drawn too, as an indexed PNG whose pixels are the entries' own indices into the DAC,
sixteen squares a row, so the index is the data and the colour a view of it, and the picture is
attached (*Media files*); `dest` is absolute, in a directory that exists, and never written over.

**`screen_view` reads the screen from video memory, where the `VGA` listings say it lies.** `VGA
MODE` says which mode it is, and only two families are read: a text mode, decoded to its characters,
and the chained 256-colour mode (13h's), decoded to a picture of palette indices. Every other mode
is refused `no_channel`, naming its word: in a planar or unchained mode the CPU window answers one
plane per read and choosing the plane writes a Graphics Controller register; a linear frame buffer
lies past what the debugger's segmented dump reaches in real mode; and the image of what was
displayed in any of them is `capture_frame`. The shape comes from the listings' own words: a text
screen's columns are the draw state's `blocks` and a 256-colour screen's its `width`, a row is the
draw state's `addrline-total` of its scan lines (the CRTC's cell height, doubled when it
double-scans, as INT 10h's 200-line text does), the display start goes to bytes by the mode's
`addr-shift`, and the window (`B8000`, `B0000` or `A0000`) by the Graphics Controller's memory map
select. A layout the bytes cannot be read straight from, a logical row wider than the screen, a
split screen or panning, is refused rather than read wrong, and so is a screen that would run past
its window. Text rows are the character bytes as code page 437 draws them, the control bytes as
their glyphs (`01` is `☺`) and `00` as a space, with trailing blanks dropped; the cursor is
`[column, row]` from the start, null when hidden or off the screen. The 256-colour picture is an
indexed PNG whose pixels are the bytes the guest wrote and whose PLTE is the DAC, widened as
`palette` widens it, so each pixel, doubled each way as the emulator renders 13h, equals the
emulator's own capture of that frame; it is attached, enlarged as *Media files* says. A `crop`
reads part of the screen in its own units: characters in a text mode (the rows cut to it and
the cursor counted from its corner, null outside it), pixels in 256 colours.

**In protected mode the screen is read through a data segment that covers it.** A linear
address is only the screen if it maps to it, so the bytes are dumped through the lowest present
data segment of the GDT, then of the LDT, whose base and limit cover them, and with paging on
only when every page of them maps to the same physical address; none qualifying is
`no_channel`. A virtual-8086 task reads through the paragraph, as its own segments do. Each call
reads the four listings that place the screen (`VGA MODE` first), `CPU` (and in protected mode
`GDT` and `LDT`, and `PAGING` with paging on), one dump, and in 256 colours `VGA DAC` and
`VGA DACPAL`, a console round trip each.

**`screen_signature` is one string for the same screen**, or for a `crop` of it, by the
definition in *Media files*: each cell in the colour it is shown in. A text cell is its code
page 437 byte and the colours its attribute resolves to: the attribute's nibble picks an
Attribute Controller palette register (`VGA AC`), whose value, with `color-select` above it as
`mode_control` bit 7 says, picks the DAC entry; with blink on, the background's fourth bit
blinks and is not a colour. A 256-colour pixel is its DAC colour. So a palette fade changes it
as surely as a character does, two screens that look the same have one signature, and the
cursor is not part of it. It reads what `screen_view` reads in either family and, in both,
the DAC, with `VGA AC` in a text mode; it refuses what `screen_view` refuses.

**`screen_wait` runs the machine until a string is on the text screen, and stops there.** It
is `run_for`'s retrace (`VRT`, the stop heard by the prompt) with the screen read at each stop:
`VGA MODE` for the mode word and the display start, `VGA DRAW` for the size it renders, `VGA GC`
for where the page lies (the monochrome mode moves it and changes neither of the other two),
`CPU` for how it is reached, and one dump, five console round trips a frame, so a string far
ahead is reached faster with `run_for` first. `VGA CRTC` is read once, as it places only the
cursor, and the descriptor tables are re-read only when the cpu mode, or whether a virtual-8086
task runs, changes, since a guest can enter protected mode under an unchanged text screen. The
text, up to 132 characters code page 437 draws, is matched literally and case-sensitive inside
one row as `screen_view` reads it, so a text ending in a blank is refused (a row is read without
its trailing blanks); a frame not in a text mode is no match. A string already on screen is
answered at once without moving the machine. Windowed or headless, the route is the same, so the
reply names none.

**How a wait ends.** `seconds` counts from once the first read of the screen is done, so a short
bound still reaches the first frame, and it is read before each retrace, so a frame's read and
the stop reply under way when it passes are finished. A declared code breakpoint that stops the
machine first ends the wait `wait_stopped`, its retrace left pending as `run_for` leaves it; a
change-watch or an interrupt breakpoint cannot be told from a retrace, and a `note` says so. The
bound ends it `wait_expired`, with the rows of the last text page read and `running: true` when
a `VRT` is still out; a frame laid out in a way the reader refuses ends it with that
`no_channel`. Whichever way it ends at a stop of its own (found, cut, expired at a retrace,
refused), it records that stop as every stop tool does, and carries its `stop_seq`; a stop whose
survey comes back cut is not recorded, and the reply carries `enrichment` (`available: false`
and why) instead, a find keeping its `point` and `line`. A wait whose bound passed before its
first `VRT` typed nothing, so the record, and a retrace an earlier run left armed, stay as they
were.

## Media files

The tools that answer about pictures follow one order, so a reply is the cheapest thing that
answers the question: a signature or a number first ("is it the same screen" is two strings
compared, never two pictures sent); the full picture last, and only from a tool whose purpose
is to show (`screen_view` in 256 colours, `palette`); and a reply that answers with numbers
names what it compared, over which region, and its path. Every tool that signs or compares the
screen or a series takes a `crop`, `[x, y, width, height]` inside the picture: one that leaves
it is refused with the picture's size, never padded, since a padded crop compares pixels
nobody drew.

**The signature** (`screen_signature`, every row of a series) is BLAKE2b with an 8-byte digest,
16 lowercase hex characters, over `scry-sig/1|<kind>|<w>x<h>|` (the crop's size) and the crop's
cells row by row: `pixel` cells as RGB, `text` cells as their byte and the two colours above.

**The picture attached.** A view answers with ONE PNG, written to the session's scratch (or to
`dest`: `close` deletes the scratch, so a picture meant to outlive the session takes one),
named in the reply's `image` (`path`, `sha256`, `bytes`, `width`, `height`, `scale`, `indexed`,
`inline`) and attached after the JSON, read back from the file and hashed again, when the model
can see it as it is. Past a side of 1568 px, or past 1568 tiles of 28 px, the API resamples a
picture, and a resampled picture of pixel art is a plausible wrong one; such a picture is
written and not attached, `not_inlined` says why, and the caller asks for a `crop` or a smaller
`scale`. Inside the ceiling a picture is enlarged by an integer factor, nearest neighbour, so
each pixel is a square of one colour (`scale=0`, the default, is the largest factor up to 8
that fits: a 320x200 screen comes out 1280x800). Anthropic's own guidance is to send an image
already inside the model's limits so nothing is resampled on the way, to crop or zoom for fine
detail, not to go below about 960x540 for screen work, and to start at 1280x720
(Anthropic, *Best practices for computer and browser use*; the limits and the cost of an
image, `ceil(w/28) x ceil(h/28)` tokens, are in Anthropic's API documentation, *Vision*); an integer enlargement
also makes pixel art more legible to a vision model, since smaller patches relative to the
content raise its accuracy
([Wang et al., *Scaling Laws in Patchification*, arXiv:2502.03738](https://arxiv.org/abs/2502.03738)).

**`series_capture`** turns frames of the session's video capture into PNGs beside one
`scry-series/1` manifest (`server`, `source`, `crop`, a row per frame `{frame, path, sha256,
bytes, signature}`). DOS has no frame counter a stop can read, so the frames are the AVI's own,
numbered from 0 by the file's index, and the reply says so (`frame_source`). One ffmpeg pass
keeps them: a `select` over the frame numbers, a `crop` filter judged against the size the
AVI's header declares, RGB rows with no prediction, and each PNG read back for its signature and
hash. With `dest` the series outlives `close`; without it, it lives in the scratch and goes
with it.

**The file tools** (`image_diff`, `series_diff`, `region_track`, `golden_check`) read files and
touch no machine, so they answer with the guest running or with none, and their body and text
come from scry-core, the package this server pins; `region_track` writes one file, the whole
track as JSON, beside the manifest. Every series and golden comparison carries its control,
because a result that cannot come out the other way is no result: a series whose frames never
change says nothing about another (`control_silent` naming it), two series with no frame in
common compare nothing, a region whose measure never moves was missed, and goldens whose names
meet no file examined nothing. Reading a manifest hashes every file it lists, so a frame changed
since it was written is refused rather than trusted.

## Saved states

`state_save` and `state_load` are the debugger's own commands, `SAVESTATE <file>` and `LOADSTATE
<file>`, sent down the debugger channel `stop` uses: no window, no menu, no dialog and no focus
taken, headless or windowed, and the reply says whether the emulator acted. Those two commands are
proposed upstream and not in a release yet; a build without them answers an unknown command, and
both tools say so as `no_channel`, naming the command the build lacks. They need the debugger
STOPPED: while the guest runs, the channel is served from a timer tick handler, and loading a state
there would replace the tick handlers the timer is walking. So a running guest is stopped for the
command (`stop`'s `BREAK`) and released again, and the reply's `paused` says it happened; a parked
one stays parked, at the loaded machine's position after a load. The command is the confirmation: a
refusal of its own (a state of another DOSBox-X version, program, memory size or machine type is
refused, never asked about) is `unexpected_answer` quoting it, and the emulator's log says why. The
state is `<name>.sav` under the session's `state_dir`, written there directly and read back for
what it says about itself; `state_list` reads every state's ZIP members (version, program, machine,
memory size, stamp) without loading, needs no window, and answers while the guest runs. A save
never overwrites and alters nothing; a load marks the session altered, because it replaces the
machine. A name is letters, digits, `_` and `-`, starting with a letter or a digit, at most 64 of
them, and not digits only: the emulator's own slot files are `<n>.sav` in the same directory.

## The console

`debug` sends one command to the debugger console and hands back the screen delta it
produced, capped and saying so (`screen_chars`, `clipped`). It needs the machine stopped,
like every reader: the console answers only then. A mutating command counts as a write and
marks the session altered. Everything the typed tools do goes through this same console,
which is why they exist: they parse what the console paints, read the lists back and refuse
a shape they were not captured answering, where a raw command hands you the paint.

**A command that lets the guest run is refused before it is typed.** `VRT`, `RUNWATCH`, `INT`
and the `LOG` family (`LOG`, `LOGS`, `LOGL`, `LOGC`), matched on the first word in any case,
leave the debugger without the session knowing, so `last_stop` and `status` would go on naming
the stop before them. They are refused `bad_argument`, with or without a session, naming the
tool that reports the stop it reaches: `run_for(frames=1)` for `VRT`, `trace` for the `LOG`
family, `resume` with a breakpoint where the machine should stop for the other two. `INTT`,
`TIMERIRQ` and `HEAVYLOG` stay at the debugger and go through. A command carrying
a control character is refused too: a line break would type a second command past that check,
and an escape is a key.

**A command the console does not recognise stays on its input line**, `VGA` with no
subcommand among them: the console answers `not recognized` and keeps the text, the next command
is typed onto it and fails too, and so does every one after, until the session is closed. The
typed tools never send one; a `debug` with one poisons the console for them.

## Development

The server is carved along the seams the work has: a tool's CONTRACT (the docstring the
client reads) sits with its registration in `dosbox_x_server.py`, and its body sits in the
module that owns that kind of work, so a capability is born in its own unit rather than
added to one file.

- **`dosbox_summaries.py`**: the one line each tool's reply opens with, one function per tool,
  and the line a refusal gets instead.
- **`dosbox_x_server.py`**: the tools, each registered with its `summary`: the session's
  lifecycle (`start`, `status`, `close`, `build_check`) and the readers and advances that are
  one console call each.
- **`dosbox_mcp.py`**: the MCP boundary every tool is wrapped in: the server object and its
  `instructions`, the lock over the one machine, the decorator that registers a tool, and this
  server's hooks into `scry_core.boundary` (how a body is called and which errors are answers,
  how a cancelled call ends, the reply a call the schema refused gets); the core closes every
  reply (`summary` first, `session` last, composed after the body).
- **`dosbox_binary.py`**: which DOSBox-X `start` and `build_check` run, by the ladder *The
  session* sets out, and the build's own version line.
- **`dosbox_state.py`**: what the server holds between calls (the session, the symbol table,
  the declaration store, the last stop, what waits for the next one) and the envelope every
  reply carries.
- **`dosbox_checks.py`**: the table of which argument each tool judges BEFORE the session
  gate, one function per rule owned by the module that does the work, read by the surface and
  by the batch executor alike.
- **`dosbox_placement.py`**: a name or a `SEG:OFF` to the address the debugger wants, in this
  machine's mode; `symbols_load` and `symbols_find`.
- **`dosbox_arming.py`**: declarations meeting the machine: arming, reading the list back,
  evaluating watches at a stop, attributing a stop, draining what was asked while the guest
  ran; the six declaring tools and `breakpoint_interrupt`.
- **`dosbox_running.py`**: a stop the guest reached on its own, the first contact after it,
  and the one survey a stop reply is built from, with its E9 block.
- **`dosbox_inputs.py`**: the two routes a key takes and the one the mouse takes, and the
  proof the guest reacted; `send_keys` and `send_mouse`.
- **`dosbox_captures.py`**: the video the emulator recorded, and a still out of it.
- **`dosbox_media.py`**: `series_capture`, frames out of a video capture as a series.
- **`dosbox_find.py`**: the exact byte search and the debugger's own scanner.
- **`dosbox_disasm.py`**: x86 decoded on the host by capstone, the one module that imports it:
  bytes, an address and a code size in, each instruction's text, `flow` and direct operands out.
- **`dosbox_code.py`**: code read off the machine: the code pane parsed, the width and base of a
  segment at a stop, `disassemble` and the operands it names, the instruction every stop
  carries, and `call_stack`'s walk.
- **`dosbox_machine.py`**: the debugger's listings parsed, `machine_map` assembled from them
  by mode, and the vector table placed in them.
- **`dosbox_sequence.py`**: the executor behind `perform`, `start(plan=)` and `drive`.
- **`dosbox_comments.py`**: where a comment lands now and the one-per-place rule; the five
  comment tools.
- **`dosbox_comment_file.py`**: the comment file read and written: its header, its rules for a
  ref, a stamp and a text, and nothing that needs the machine.
- **`dosbox_session.py`**: one live session and the emulator's terminal it drives.
- **`dosbox_launch.py`**: what a session is launched with, judged, and the command line built from
  it; **`dosbox_console.py`**: the console's grammar, the pane and the replies parsed;
  **`dosbox_logs.py`**: the log's channels and filters; **`dosbox_collect.py`**: the files the
  emulator wrote, collected to where they were asked for.
- **`dosbox_symbols.py`**, **`dosbox_declarations.py`**: the symbol formats, the store.
- **`scry_core.reply_contract`**, **`scry_core.value_format`**,
  **`scry_core.strict_arguments`**: the refusal contract, the watch value grammar and the strict
  schema, held once in the `scry-core` package both Scry servers pin.

### Tests

```sh
uv run pytest tests       # installs the package and its dev tools first
```

They are contract tests and none of them launches an emulator: what they hold is the part
that has to be true before one is involved. `bench.py`'s own guards are among them, because
an instrument that can lie needs validation and validation nothing executes is a comment. A
second tier under `tests/live/` does drive a real emulator, and it needs nothing from you:

```sh
uv run pytest tests/live -m live
```

**It runs against a guest this package OWNS**, `tests/guest/probe.com`, a few bytes of
assembler that write one instrumentation line every three seconds and never exit. That is
not a toy: half these cases are about a machine that is still RUNNING, and the other half
read what a guest emitted, so a tier with no guest of its own has to borrow one, and a
borrowed guest is a dependency on somebody else's program.

**To run it against your own program instead**, point it at your config and name the two
tokens your guest logs, one it writes EARLY and one it writes LATER, because one case waits
for something that has not happened yet and refuses to run if it already has:

```sh
DOSBOX_X_LIVE_CONF=/path/to/your.conf \
DOSBOX_X_LIVE_CWD=/path/to/its/dir \
DOSBOX_X_LIVE_PROGRAM=YOURAPP.EXE \
DOSBOX_X_LIVE_MARK=BOOT \
DOSBOX_X_LIVE_LATE=READY \
    uv run pytest tests/live -m live
```

Your config needs `bochs debug port e9 = true`; without it the port is inert and the
instrumentation goes nowhere, which reads as a broken session rather than a missing line.
Nothing checks that for you.

Three more things the overrides expect, none of them guessable:

- `DOSBOX_X_LIVE_PROGRAM` must appear at the START of a line in your `[autoexec]`, and that
  section must also carry a bare `exit` line. Two cases build a variant config by deleting
  exactly those two lines, and skip if they cannot find one of each.
- `DOSBOX_X_LIVE_MARK` has to be something your guest logs EARLY, within the first handful
  of instrumentation lines.
- `DOSBOX_X_LIVE_LATE` has to be something it logs LATER and has NOT logged yet when the
  waiting case asks. A token that is already there makes that case report INVALID, which is
  the correct refusal and not a pass.

A sixth variable, `DOSBOX_X_LIVE_WINDOW_FLAGS`, carries the placement flags for the one case
that opens a watched window (newline-separated, because a `-set` pair contains a space).
Without it that case skips: where a window goes is not this package's decision.

**The live tiers need no other project.** The protected-mode cases run on a second guest the
package owns, `tests/guest/dpmi.c`, a DJGPP program built into the committed `dpmi.exe` and
its `nm` table `dpmi.sym`, under the DPMI host DOSBox-X provides. The real-mode cases and the
matrix's program sections run dos-real16 and dos-real16-alt from a bench: copies of each program, its
map, the data it opens and its project's own run conf, under `DOSBOX_X_LIVE_BENCH`
(`~/.local/share/scry-bench/dosbox-x` when unset), pinned by hash in the bench's own
`bench.json`, with an `identity.json` beside it that says which files, launch line, memory-block
name and E9 line each program's label stands for (its keys: `IDENTITY_KEYS` in
`tests/live/bench_programs.py`). Neither is tracked, because both name the
programs; the tracked live code names only the labels. `uv run python -m scry_core.live_bench
fill --bench <bench> --from <source_repo>=<checkout>` copies them from their checkouts and `check
--bench <bench>` says whether they still match; the session conf is derived from the pinned run conf at run time, and a case
whose identity is incomplete or whose copies are absent or wrong is skipped, or its cells
BLOCKED, naming what is wrong.

**Around those cases sits a matrix**, `tests/live/dosbox_x_live_matrix.py`, run as a script
rather than collected: every tool in every machine state, at every argument edge, across the
calls that share state, then on real DOS programs a project points it at. Its cells are declared
before anything boots, so what was planned and never reached shows at the end; each prints OK,
FAIL, or BLOCKED with the reason it could not run, every reply lands whole in a transcript whose
path it prints first and again beside the verdict, and a failed cell keeps the conf and the log
tail of the session live at the time. It exits 0 with no FAIL, 1 with one, 3 when the run is
invalid (no cell ran among them). What each word means, the variables it reads and the command
are in its own docstring.

**Both tiers run their parts side by side.** The matrix runs each section letter, and
`tests/live/run_live_pytest.py` each live test, as a process of its own, as many at once as
`DOSBOX_X_LIVE_JOBS` says (unset, half the host's CPUs; `1`, one after another in one process),
merged from the summaries they declare through `scry_core.live_pool`. What opens a window
(section G, the focus gate's O, the `windowed` tests) runs alone. Each part works on
copies of its own of the guests and the bench, because the debugger writes its files under
fixed names into the emulator's working directory (`tests/live/live_private.py`).

**Both tiers refuse a host that cannot start DOSBox-X, and prove they left none running.**
Before its first start a run launches the emulator once in a form that ends by itself; one that
does not return is INVALID naming the host, and nothing else is launched. Every DOSBox-X a
session starts is recorded where it is spawned, and at the end of the run one still alive is
killed and FAILS the run by name. A green run removes its scratch, its jobs' with it; a red,
INVALID or broken one keeps it and prints its path (`scry_core.live_host`).

`bench.py` needs the same two things, and it takes them as FLAGS: `--conf` and `--cwd`,
beside the `--json`, `--reps` and `--song` its parser already had. It measures YOUR
program, so it has no default to fall back on and refuses without them, naming the
flags; two equally required inputs arriving through a different door than the other
three is an incoherence, not a need.

### The fixtures, and the sweep that is not on the commit path

**One artefact per toolchain is BUILT HERE and committed**, under `tests/fixtures/`: a
Borland TLINK 16-bit map with an overlay in it, an Open Watcom map spanning two sections,
and a DJGPP `nm` listing beside the GNU `ld` map from the same link. The two Borland
residents share their first fifteen characters on purpose, so the fixture really exercises
the collision the disambiguator exists for. `tests/test_dosbox_x_fixtures.py` reads them,
so the claim "this reads those formats" is something a fresh clone can check rather than
something you have to take on trust.

**Each ships with its generator**, the source it was built from and a `build.sh` that
re-makes it. A captured artefact whose recipe is lost cannot be re-captured, and a
discrepancy in how it was transcribed can then never be settled by anybody. Neither
toolchain is vendored here; `build.sh` takes its location in an environment variable and
stops loudly rather than quietly building with something else.

**`mapsweep.py` reads REAL maps where they live**, against a manifest that says what each one
holds, and goes red when the two part company in either direction: a count that ROSE against
an unchanged file means the reader has begun reading something that is not a symbol.

```sh
uv run python mapsweep.py --manifest <bench>/real-maps.json --root /where/those/maps/live
```

It is **manual and declared as such** in `tests/gates-manual.txt`, with the reason: the
material is not in this repository and is not versioned here, nor is the manifest, which names
it and so lives in the bench beside `bench.json`; on the commit path the sweep would be INVALID
in every clone but the author's, and a gate that is almost always invalid is one
people learn to ignore. It covers the Borland, Open Watcom and `nm` formats on real material;
the GNU `ld` map is deliberately absent, because the only one is the fixture this package
generated, which lives INSIDE the repository, and the sweep is for material that does not.
What it can say is that a count MOVED, which is what it is for. It cannot say a count is
CORRECT: the first time a project's row is written, whatever the reader says becomes the
expectation, and closing that is reading the map, by a person, once, exactly as blessing any
golden is.

### Proving a change

The session that edits this server cannot exercise its change through it: a running server
answers from the state it was launched with. A change is proved out of process, with a stdio
client in a fresh process binding the server from the files as they stand and calling a
fixed sequence, and the verdict block it prints says of every reply whether the first key is
`summary` and the last is `session`.
