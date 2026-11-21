# Changelog

What a client of the server notices.

## Unreleased

- The `dos` channel of `log` and `log_wait` names the INT 21h function and the DOS error of each
  call from dictionaries that cite Ralf Brown's interrupt list and DOSBox-X's source, and the
  names are fuller: `open file` where it said `open`. Every function the emulator's handler has a
  case for has a name, and so has every error code the emulator defines and every one the
  list's table gives, up to 255.
- `start` takes `overlay`, which layers the window shows over the edge: a caption naming each
  call, the keys held, the pointer, a mark while the machine is stopped and a blinking mark in
  the top right corner while `record` or `audio_record` runs, each on by default, and where the
  captions go. `start` and `status` answer `overlay` with the layers drawn and,
  for each the build cannot draw, why; `build_check` lists the layers a build draws as
  `presence_layers`. A build that draws only the edge and the pointer keeps drawing them, and one that predates
  the record mark draws every layer but that one.
- Every demo is shown moving: a `loop.webp` beside its README replaces `loop.mp4`. It holds up
  to three moments of the demo's own run, scaled up so its pixels stay sharp. A moment is cut
  from a `record` call or, in Minesweeper and the two Deluxe Paint demos, from the video of a
  session started with `capture_video`.
- The Minesweeper demo's conf no longer starts the game: `start` takes it as `program`, which
  lets the session record itself. By hand, type `MINES` at the prompt.
- The Speed Fight demo runs on to the match the game plays by itself, at a fixed speed the game
  keeps pace on. The LineUp demo fires three more shots, and the ReChip! demo films the song
  playing.
- Each demo's page offers the steps to try, each with what to ask, the call and the reply it
  got. The whole run is in `TRANSCRIPT.md`.
- The README opens with what the server lets you ask, its lead demo moving at the page's width
  and one exchange of that demo's run. Its `## Install` section has the lines to paste for ten
  MCP clients and a first question to ask.
- Takes scry-core 0.120.1.
- Each tool's reference entry opens with what the tool does and an example to try: what to ask,
  the call and the reply it got. Its arguments, what comes back, what it refuses and why follow,
  each under its own heading.
- The examples are calls of one session on Bricks, a game this repository builds. The whole
  session is `docs/reference/tour/TRANSCRIPT.md`.
- The groups of tools are renamed: Run, Breakpoints, Sequences and Project. The `instructions`,
  the reference's pages and the sections of `REFERENCE.md` carry the new names.
- A scan's summary says how many candidates are left ("3 left"). An input's says "sent, reaction
  not checked", "reaction seen" or "no reaction seen (TIMEOUT)", and so does `drive`'s.
- A summary counts frames where it counted retraces. A reply that saves a candidate for
  `promote` says "N saved for `promote`" in `kept`.
- A stop a call made itself says so in `cause`: the frame `run_for`, `record` or an input ran
  to, the step `step` made, the end of a trace's count. It used to say "no declared code
  breakpoint" whenever anything was declared.
- The `cause` of a stop nothing explains no longer names a memory watch when none is declared.
- A `step` over a call that its time limit cut says the limit stopped it. A row typed through
  `debug` that no address names (`BPINT`, `BPM`, `BPIF`) takes a stop from the call's own run.
- `start`'s description says what `front` means in its `window`: no other application's window
  covers its centre. It does not mean the window has the keyboard.
- `promote` no longer lists an exported script as unwritable when the session's `start` gave no
  `guest_files`.
- On Windows a watched `start` with `background=false` brings its window to the front once it is
  up, as the session page says. Before, the window opened behind any application that held the
  foreground.
- On Windows a watched `start` with `background=true` leaves the foreground where it was: no
  program may take it while the start launches, until the window is proved. The flag did nothing
  there.
- `stop(until="protected")` with `start(symbols=)`'s DJGPP table held runs on until a stop in
  the program's own 32-bit code. Before, a stop in the DPMI host's 16-bit protected code ended
  it, and the program's symbols were unknown there. A run that gives up says it did not reach
  the program's code, where it said protected mode while `cpu_mode` said protected.
- `stop` on a machine that stopped by itself puts `start(symbols=)`'s held table at the stop, as
  any stop reply does, and says `symbols_placed`. Before, the table stayed held until the next
  stop.
- `run_to`'s `cut_by_other_stop` refusal says what to do next: `cause` names what stopped the
  run, and a watch is passed with `disarm_watches=true`.
- `promote` refuses a `start` profile or a `perform` document holding a `${...}` that is no
  placeholder, typed text included. Before, it wrote a file into `.scry/` that `perform(path=)`
  then refused.
- A DJGPP program's table given to `start(symbols=)` is put at the first stop in its own 32-bit
  code. Before, a stop in the DPMI host's 16-bit code put it at the host's base. Every symbol
  read through it (`read_memory` of a variable, a stop's `symbol`) then answered another
  address.
- `build_check` lists `record` and `audio_record` among what a build without `RUNSTATE` cannot
  serve: their retraces run as `run_for` runs them.
- `scan` no longer lists a `survivors` reply field: it never sent one.
- `symbols_load`'s `base` and `section_bases` and `symbols_find`'s `linear` take an address as
  `0x` text or an integer, as every other address. Bare hex digits (`8000`) are refused, since
  they read either way.
- `debug` writes an output past 4000 characters whole to a file in the session's temporary
  folder and answers its first line as a preview, with `output_chars` and `output_path`. Before,
  it kept only the last 4000 characters.
- `run_to` and `run_for` take `disarm_watches`: the change watches' rows leave the debugger for
  the pass and come back at its stop. The reply names them in `disarmed_watches`, with
  `not_rearmed` (and why) for one that could not come back.
- `breakpoint_at` takes `role="control"`: the address is saved and counted by every `run_to`
  beside the run's own `control`. It is held in the debugger only while a run counts it, so it
  never stops `resume`, `run_for` or a wait (an `on_breakpoint` wait on it is refused). Its
  reply, and each breakpoint row of `declaration_list`, carry `role`.
- A pattern or an `expect` that does not compile is refused naming the argument (`pattern='('
  does not compile: ...`). Before, the refusal said only that it was not a usable pattern.
- `read_memory` and `scan` no longer list a `rows` reply field, nor `write` a `written` one: no
  tool ever sent them. `read_memory`, `disassemble`, `find`, `memdump` and `write` declare the
  `ref` every `ok` reply of theirs echoes, and `scan` on `start`.
- `debug`'s summary counts the characters of a short output too. It used to read "None chars".
- A `run_to` refused before the resume because the debugger did not list one of its breakpoints
  now takes out every row it armed. Before, they stayed and stopped the next `resume`.
- A control declared with `breakpoint_at(role="control")` is counted by `run_to` only where a
  stop row would be armed (set in this mode, not stale over another build). Before, it counted
  hits at another byte or refused the run.
- A `perform` document saved in `.scry/` is replayed with its placeholders resolved, `${state}`
  naming the session's temporary folder. Before, its steps ran with `${root}` in their paths and
  were refused.
- A `drive` refused before its act ran carries `looked` as `{"guest": ...}`, the shape of every
  other `drive` reply. Before, it carried a bare `unavailable` block.
- The descriptions say what the tools already did. `memdump`, `trace`, `snapshot`,
  `audio_record` and `machine_map` take a `~`-led `dest`, and `log` refuses an empty `pattern`.
  `state_list` rows carry `name` and `path`, and `screen_wait`'s schema lists the `palette` it
  takes.
- A stop at the boot sector (0000:7C00) after a conf's `boot` gives the DOS system's boot as its
  `cause`. Before, it said no declaration could explain it. `resume`'s reference says a second
  `resume` lets the DOS system run.
- The Monkey Island demo starts DOSBox-X in its run's directory and mounts C: there by a
  relative name. Its clip and screen are the same wherever the repository is cloned.
- `screen_wait` refuses a watch that follows a pointer saying its firing "cannot be told from
  another stop". Before, it said "from a retrace".
- `start` refused for a `profile` no directory above holds carries `searched`, the directories
  it looked in, the `cwd` hint included.
- A file written at a path you name takes the name every file the server writes takes: lowercase
  words joined by hyphens with one extension. `Shot_1.PNG` is written as `shot-1.png`. This
  covers `dest` of `memdump`, `trace`, `snapshot`, `record`, `audio_record`, `comment_write`,
  `palette`, `screen_view` and `capture_frame`.
- A `dest` with no extension is refused before the machine is asked, as is a `%` in
  `capture_frame`'s `dest`, since no numbering pattern is expanded. The reply's path names the
  file written, and its `note` says so whenever the name is not the one you gave.
- That `note` also appears on `machine_map`, `screen_map_write`, `perform_export` and `start`'s
  `logfile`. `start` answers `logfile` when given one.
- On the Mac a window sized to fit a display's usable area sees a Dock or menu bar that showed,
  hid or moved within a few seconds. Before, it kept the first area it read for the life of the
  server.
- The ReChip! demo's three stops that the host picks leave their `note` out of the transcript.
  The server adds that `note` only when a stop landed in a ROM handler, so two runs write one
  transcript.
- On a debugger connection that went silent, the window's presence edge no longer sends its
  first version request either: a reply waited one time limit less for it.
- A `screen_wait` on a watch that never fired, on a dynamic core, no longer says a code
  breakpoint is declared when none is. The caveat about a core passing one over comes only with
  a declared code breakpoint.
- A map `screen_map_write` loaded names the entry it was read from. An `add` after the load then
  updates that map in the `.scry/` folder it came from, as the `promote` description says.
  Before, it was kept as a new map of the current `start`'s repository.
- `window`'s `front` is said as it is computed: on screen, with no other application's window
  over its centre.
- After a resume no answer confirmed, a reply on a connection silent through a long host call
  waits the connection's time limit once. Before, its `session` block asked `RUNSTATE` again and
  waited a second limit. A `step` with no stop says it is running only when it is.
- `screen_wait`'s description no longer says a wait on a declared stop runs on the normal core
  (it runs on any), and `start` says `symbols_placed` carries `load_segment` in real mode only.
- `screen_wait`'s description gives `condition` a register of the stopped cpu, never a register
  this server refuses.
- Inside a long host call each call answers `host_failed` after the debugger connection's time
  limit once. Before, the window's presence edge held the connection for a limit in front of
  nearly every call and doubled it. The edge now waits for the connection to answer again.
- `state_write(method="load")` of a state saved in another program than the one running (at the
  stop before DOS boots, none is) answers `needs_call`, naming the program to run first. It
  leaves the session unaltered. Before, it answered `unexpected_answer` and marked the session
  altered though the emulator replaced nothing.
- A `send_keys` or `send_mouse` cut part-way while sending the key-ups an earlier cut send owed
  counts only the keys still down. Before, it also counted those whose key-up had just gone in.
- A pointer-following `send_mouse` summary, inside `perform(summaries=true)` too, says
  "program's pointer at" with the address `arrived` checked, and the driver's address beside it
  when the two differ. Before, it said "pointer at" with the driver's address alone.
- A pointer-following `send_mouse` whose move leaves the program in a mode this server does not
  map says so in `pointer.program` (unavailable, no ratio to correct by). Before, the block was
  missing.
- A pointer-following `send_mouse` first waits for the program to take a move it did not send
  itself (`units="mouse"`, a move while the program ran, a drag's end). It waits a retrace at a
  time, up to the limit its reads already use. Before, it read the pointer at once and could
  send nothing while the pointer landed elsewhere.
- `promote` writes an entry only into the `.scry/` folder of the repository it was learned in.
  That is the one a call read it from, else the current `start`'s (its profile's, else the one
  its program runs in).
- A session that ran programs of two repositories never files an entry in the other's `.scry/`
  folder, and the server's own directory never lends its folder.
- An entry whose repository has no `.scry/` folder is `unwritable` in a review and refused in an
  approval, naming the `root` to pass. The `kept` line names each such repository, a call writes
  one `.scry/` folder, and with `root` a candidate kept in another repository says `from`.
- A `start` refused before it launches (a session already live) leaves the live session's
  program as it was. The next map `add` is still named after the program on its screen.
- `send_keys` and `send_mouse` while the emulator is inside a long host call (a DOS file or
  device operation it waits on) answer `delivered: false` and say the input was not sent.
  Before, they said whether it acted was unknown. Nothing was written, so sending it again once
  `status` answers puts it in once.
- A `send_keys` or `send_mouse` cut part-way by a long host call says how many of its input
  commands were written and that a key it pressed is left down. Before, it said some of it may
  have gone in. The next input sends that key's release first and says so in `note`; the key
  used to stay down.
- `log_wait` during a long host call keeps its time limit (plus at most one debugger request's)
  and reports in `waited_s` the time it took. It no longer says the machine is still running
  when nothing answered that question.
- A pointer-following `send_mouse` whose program pointer is on the address answers `arrived:
  true` wherever the driver sits. A program that adds the driver's motion to a pointer of its
  own takes a click where that pointer is. Moves that answered `arrived: false` with a note
  about the driver disagreeing now answer true.
- The note and the false answer remain for one case: a driver range that changed during the move
  without the steering changing it. A range the program sets on the click itself no longer
  counts.
- A pointer-following `send_mouse` whose program pointer is already on the address sends no
  move, and its reply carries no `motion`. Before, a click after a hover on the same control
  moved the driver to the middle and carried the pointer off it. The correction then left the
  driver further from the pointer over a series of such calls.
- `start`'s `plan` and `drive`'s `act` say what a step looks like, `{"op": <tool>,
  ...arguments}`, in the words `perform` uses. A first call no longer guesses the key and meets
  a refusal asking for `op`.
- A pointer-following `send_mouse` learns the ratio between the driver and the program's pointer
  from the motion the driver made, not from what was asked of it. Before, a correction the
  driver's edge cut short taught a ratio that grew at every edge hit, and the pointer swung from
  edge to edge and ended `arrived: false`. It now lands on the address.
- A `send_mouse` that follows a map's `pointer` reads the program's pointer only once the
  program has taken each move. Before, a program that reads the mouse once per loop pass showed
  a move some retraces late, and the call ended `arrived: false` with a `reach` the pointer
  never had. Such a move now arrives; its `polls` include the retraces it waited.
- `start(symbols=, base_from="program")` on a DJGPP program puts its symbols at the program's
  own DPMI selector, not the DOS load segment. The protected-mode code runs off the selector, so
  a breakpoint armed on such a symbol now fires where the code runs instead of landing on a dead
  address.
- A refused `record` or `audio_record` removes its file. A capture the server rejects (a short
  WAV, a header that disagrees with its file, a truncated stream) no longer stays in the capture
  folder.
- `log` on a running program says when lines may still be in flight. The emulator flushes its
  log in its own time, so a line the program has just written may not be in the file yet.
- `start(profile=...)` with no `cwd` says so plainly. A named profile not found above the
  server's directory is refused with `cwd` named as the way to point the server at the
  repository that holds the start profile. Before, the refusal gave only the directories
  searched.
- `send_keys` takes `shift`, `ctrl` and `alt` (and `control`, `option`) as keys. With `action`
  `down` and `up` a modifier can be held on its own, where `modifiers` needed a real key beside
  it. Holding one keeps a program from going idle without holding a key the program may map.
- A new tool, `wait`, lets a running program play for `seconds` and answers `waited_s` and where
  it is, without resuming or stopping it. Its expiry is the answer, never a failure, and a stop
  during the wait (a breakpoint) comes back as the stop reply. A stopped machine is refused as
  `not_running`.
- `log` and `log_wait` say when the logfile lost lines it once held. A capture could eat the
  program's lines, and the next `log` answered none as if the program never wrote them. Once,
  the `note` gives the file's size now and the size it had.
- `close`, `status` and the `session_broken` reply tell the server's own kill of the emulator
  from one sent from outside. For an outside one they name the macOS memory manager and its
  report directory. Before, a program it killed read as a crash of the program.
- A `send_keys` with `expect` that does not see its pattern, when it is the session's first,
  adds to `verify.note` that the program may drop a first key while it settles. Send it once
  more before hunting for a modal that is not there.
- `log` and `log_wait` read the logfile without asking the debugger connection first. They
  answer while the program sits in one long host call (a DOS call over a large folder), where
  they answered `host_failed`. A `host_failed` reply names that as the likely cause, so
  `send_keys` and `perform` say why the debugger did not answer.
- `session.running` says the truth about the program, never a guess. Past a `run_for`, `run_to`
  or `resume` whose resume no answer confirmed, it re-reads the machine. A caller is told
  `false` when it stopped and `unavailable` when it still cannot be read.
- `record` with an empty `dest` writes into the session's temporary folder and answers its
  `path`. `frames` under 2 and a `dest` whose suffix is not `.avi` are refused.
- A `promote` that names `root` no longer fails when the working directory is gone.
- A program whose conf's path holds a space keeps its own name, not the first word of the path.
- An approved `promote` into a repository with no `.scry/` also writes its `about.json` and
  `README.md`. `dry_run` lists what it would create in `would_create`, and the approval says
  what it created in `created`. A reply that kept something for `promote` says when there is no
  `.scry/` above the project, and how to see what an approval would create.
- `breakpoint_interrupt` and `interrupt_vectors` take `number` and `ah` as `0x` hex (`"0x21"`)
  as well as integers, and each vector's `number` answers as `0x21`, not 33. `symbols_find`
  takes `offset` as `0x` hex and answers every `offset` in hex.
- `symbols_load` answers `base`, `limit` and `descriptor` in hex, and `unavailable` where no
  descriptor was read, not -1, as does the `base` of a stop's `symbols_placed`. The Monkey
  Island demo skips its intro again, by Escapes sent at the game's own ticks.
- On macOS the server reads the screens from a child process when it sizes a window. It is no
  longer held as an application, so Activity Monitor cannot show it as not responding.
- Every demo arrives by the program's own code or screen, never by a fixed time. MINES runs to
  its loop after each click, and LineUp stops at its first DOS call and reads each move once
  taken. Speed Fight stops at its first VESA call and runs to its title, on the normal core and
  a fixed clock.
- The Deluxe Paint demos wait for each screen on their map, and the maps demo holds the
  palette's arrow until a watch sees the colour at its top. A transcript hides what the host
  decides: the window, the address a retrace stop lands on, a derived conf's digest.
- `screen_wait` takes `on_breakpoint` or `on_watch`: the screen is checked only at the frame's
  end after a firing of that declared breakpoint or change watch. It is never sampled, and a
  `condition` filters the firings first.
- That wait's reply counts `firings` and `frames_examined` in place of `polls`. A row that never
  fires is `never_fired`.
- `perform_export` cuts such a wait instead of replaying it.
- `screen_wait`'s `changed` waits for a mapped screen other than the one shown at the start.
- The files the server writes are named in lowercase words joined by hyphens, with one extension
  ([the rule](https://github.com/scry-mcp/scry-core/blob/main/docs/file-names.md)). A `logfile`
  or a state's `name` given as `Run_1.LOG` or `Boss_1` is written as `run-1.log` or
  `boss-1.sav`, and a reply that carries the path names the file as written.
- A `logfile` with no extension is refused, with no session too. A directory `dest` keeps its
  name, and a state is loaded by any spelling of its name.
- A state or a screen map kept under an earlier spelling (`Boss_1.sav`,
  `<application>.screen-map.json`) is not found until its file is renamed. `state_list` says so
  in the row's `note`.
- A trace's set file is `<trace name>-<extension>-set.jsonl`, a screen map
  `<application>-screen-map.json`, and a comment file is advised as `<stem>-comments.tsv`.
- The descriptions say that `fullscreen` captures the mouse, so the program's pointer no longer
  follows the host cursor (`start`). They also say that `detail` adds the debugger's own text
  while the E9 lines come in the stop reply's `e9` (`resume`).
- The descriptions say what `control` holds and that `gdt` and `ldt` are read by default in
  protected mode (`machine_map`), and that a step's `recorded` is `{field: value}` of its reply
  (`perform`).
- A `logfile` that is the `captures_dir` or the `state_dir` in another case (`Out.D`, where the
  log is written as `out.d`) is refused, as one spelled the same is.
- A `promote` review lists apart, in `unwritable` with its reason, each entry it cannot write,
  and shows the rest.
- `close` no longer names an entry the `.scry/` folder already holds as it is.
- `promote` also looks for the `.scry/` folder from a start profile's `conf`.
- `stop(until="protected")`: a stop that lands in a BIOS handler, in real mode, runs on in short
  slices until one lands in protected mode, also from a stop already held. `runs_to_protected`
  says how many it took and `cpu_mode` where it ended. A real-mode refusal and a stop in the ROM
  name it.
- While `stop(until="protected")` runs on, it reports which run it is on, and a cancel ends it
  between two runs with the machine stopped.
- `promote`: a map or a script learned from a loaded start profile looks for the `.scry/` folder
  from that profile.
- `start` through an app bundle runs in the right working directory. Before, a relative mount in
  the conf named the wrong one.
- `perform` takes `path`: a `perform` document (`.scry/perform/<name>.json`, or a file
  `perform_export` wrote) whose steps are replayed on the session. `steps` and `path` are
  refused together, and a document whose version this server does not read is refused by name.
- `start` and `build_check` on Windows read the build's `version` from the executable's version
  resource instead of running `-version`, which opens a console and waits for a key there. A
  `start` no longer waits for the version check's time limit, and the reply carries the version.
- `close` on Windows asks the emulator to quit through its debugger connection before
  terminating it, as SIGTERM does elsewhere. A healthy session now ends `ended_by: quit` with
  exit code 0, and `killed` means it did not leave.
- The descriptions of `build_check` and `start` name `session_live`, `registers` names `no_stop`
  and `snapshot` names `wait_expired`, the codes they answer. The README says how to watch a
  session, and `start`'s page says who mounts the input helper inside DOS and what a
  repository's conf must drop.
- `send_keys` takes `action`: `down` holds the modifiers and presses the keys, `up` releases
  them, and `press` (the default) taps them as before. A program that reads the keyboard state
  can be tested with a key held (no repeats of its own: each is a further `down`).
- `send_mouse` takes `action="triple"`, three clicks a tick apart. The range widening of a
  program's pointer measures a move that a screen edge clamped from a shorter distance, so
  `pointer.mouse.max_*` no longer comes out several times too large.
- `perform`'s description says a `screen_view` step answers its picture as `not_inlined:
  nested`.
- `window` says why a size reads `matches: false` while the program has never run (the emulator
  takes the size at its first video mode). It also says what to do: `resume` and read again.
- `flags` takes a `-set` as `key=value` with no section too, as DOSBox-X does. It refuses a key
  the server owns in that spelling (`break on int3=false`, `integration device=false`, `debugger
  headless=false`). A `-set` with no `=`, the value after a space included, is refused because
  DOSBox-X ignores it.
- `symbols_find` by `linear` in a section the table lacks answers `unknown_ref`, and a real-mode
  base off a paragraph keeps its low bits. A conf's `windowresolution=desktop` or `original` is
  no longer overridden by the fitted size, and a quoted `mount` path with a space is read.
- `screen_map_write` takes `method="pointer"` and `pointer={"x": ref, "y": ref, "bytes": 2}`:
  the program's own pointer declared by a call instead of by editing the saved map. `save` keeps
  it and a `load` replaces it.
- `build_check` answers `debugger_commands_missing`: each debugger command the build lacks, with
  the tools it takes away (a build without `RUNSTATE` lists `run_to`, `run_for`, `trace`,
  `screen_wait` and the rest). It is omitted when the build has every command.
- The `session` block carries `program` once the program the machine was running is gone. It is
  `exited`, or `fault` with the message DJGPP left on the text screen (it never reaches the E9
  log). It is read at the stops that answer a call, from DOS's current process.
- A wait that expired opens its `note` with that, or with the fact that the program wrote no
  line, instead of leaving the cause among a list of guesses. A `run_to` whose control stayed
  silent opens its `message` with it too, as does a wait refused with `wait_stopped`.
- `send_mouse`: naming an `action` with no `button` presses the left one (a `click` used to
  press nothing; with neither, the pointer only moves). A screen-unit move that no program
  pointer checked answers `driver_arrived` (where the driver is), not `arrived`.
- When a program's pointer follows the driver over a range smaller than its screen, `send_mouse`
  widens the range once, by a new input-helper command (protocol 7). One case is Allegro's
  default DOS mouse: 640 x 200 for a 1024 x 768 screen. A conf that mounts an older `SCRY.COM`
  is refused.
- `range_widened` is in the `session` block of every reply once the range is widened.
- A `perform` list that ends on a missed `expect` quotes that step's own reply in its `note`.
- `start` notes an input helper the conf runs off a mounted drive that speaks another protocol
  than the server, instead of leaving it to the first key or mouse call. The `send_mouse`
  summary says when the driver's range was widened.
- `symbols_load` takes a selector as `base_from` (four hex digits, `00AF` for a DJGPP program
  under CWSDPMI). The debugger reads its descriptor in any CPU mode. A table can be loaded, and
  `send_mouse` can follow the program's pointer, at a real-mode stop without waiting for a
  protected-mode one.
- `send_mouse` follows a protected-mode program's own pointer from the real-mode stop its
  retrace ends on. A build whose debugger has the new `MEMDUMPLIN` puts the map's pointer
  symbols at the table's base plus their offset. It needs a table loaded at a protected-mode
  stop from a register, and `start`'s `debugger_commands` lists it.
- Without `MEMDUMPLIN`, or with a table whose base was given by hand or taken from the program's
  load segment, the steering call is refused as before.
- A pointer-following `send_mouse` resolves the program's pointer again at every stop it reads
  from. A retrace stop in real mode after a correction no longer fails on the selector set at
  the first stop.
- When the pointer does not arrive after the corner moves, `pointer.program.reach` gives the
  span it took at the driver's two corners. A program can show the driver's range on a window of
  its screen, and an aim outside it cannot be reached.
- The `send_mouse` summary says `no button pressed` when the call named no `button`, so a move
  whose check saw no effect is not read as a click that failed.
- A symbol that folds past the first megabyte at a real-mode stop is refused. The refusal says
  that no `SEG:OFF` reaches it there either (the debugger wraps a real-mode offset to 16 bits)
  and to arm or read it at a protected-mode stop. It used to advise an explicit `SEG:OFF`, which
  is refused too.
- `start` takes `size` (`WIDTHxHEIGHT` in the host's unit), sent to the emulator as `sdl
  windowresolution`. The unit is logical pixels where DOSBox-X is not DPI aware: from 200 % on
  Windows with the conf's default `dpi aware`, at any scale with `dpi aware=false` or
  `-nodpiaware`. It is real pixels with `true`, and points on macOS.
- Without `size`, a watched window keeps the size the conf states. Where the conf's `sdl output`
  takes a size, it is the largest 4:3 one the display's usable area holds (every OpenGL output
  and Direct3D; an unset `output` on macOS and Windows).
- `size` is refused beside `fullscreen`, beyond the usable area with its frame and under an
  `output` that ignores it, and `window` checks a stated size. A `-set` of `sdl
  windowresolution` in `flags` is now refused naming `size`, no longer "the conf decides".
- A `start` refused with `window_not_visible` leaves its session live with the `presence` it was
  asked for drawn, so `window(front=true)` brings forward a window that carries it.
- `start` takes `display` (the OS's index, the main display when omitted) and `fullscreen`, and
  a watched start answers `window`, proved in the host's window list. A window that never
  appears on the asked display is `window_not_visible`.
- `SCRY_EMULATOR_ARGS` is gone, and `flags` setting what `display` and `fullscreen` own are
  refused by name. `fullscreen` on `sdl output=surface` is refused.
- A windowed start opens 40 px inside the asked display's corner, since DOSBox-X ignores `sdl
  display` alone on macOS. `fullscreen` on a display other than 0 is refused there. A start is
  halted at its first instruction, and the window reaches full screen on another display only
  once the emulator runs.
- A new tool, `window`, answers where the window is at any time, and with `front=true` brings it
  in front of what covers it. Without `front` it answers the window wherever you put it, another
  display included.
- A `front` that fails on a session started with `background=true` names that as what may keep
  it behind and what to do.
- `symbols_load`'s summary says whether the table was checked against a build beside it, and
  against which executable, so a table nothing could check no longer reads like a proved one.
- A second `symbols_load` answers `loaded` with what that load put in, the count that can be
  compared with `parsed` and `table_total`. `debugger_holds` carries every row the debugger
  still holds, since `LV` appends, and comes only when it is larger.
- A saved declaration whose name no loaded table resolves says in its row why, and what would
  resolve it, instead of reading as a symbol this build lost.
- The `session` block carries `image_changed_on_disk` once the executable a loaded table was
  checked against is written again, which is a relink under a live session. `status` says it on
  its line.
- A `stop` that lands inside the ROM says so in its `note`, with the address, and says that
  `run_for` or `resume` leaves it while `step` stays in the handler.
- `start` takes `profile`: the name of a `.scry/start/<name>.json` a repository keeps, or a path
  to one. Its keys are `start`'s own arguments and fill only what the call does not give, every
  path resolved against the directory holding `.scry/`. The reply's `profile` block names the
  file and what it filled.
- `conf`, `cwd` and `session_seconds` are optional now, so a start profile can carry them. One
  that neither the call nor a profile gives is refused by name.

## 0.1.0

First release. It needs scry-core 0.80.0.

- Numbers sent to the debugger no longer collide with its names: `disassemble` with a length that
  reads as a flag or a register (`length=160` among them) answers instead of `readback_refused`,
  and a loaded symbol named like hex digits no longer shadows an offset or a segment.
- The DOS call trace is held in a window of the newest calls, so a chatty program cannot grow the
  server without bound; `log` and `log_wait` on the `dos` channel report `calls_dropped`.
- `regpoint_hit` rides every stop reply a registerpoint ends (`resume`, `run_for`, `send_keys`,
  a `perform` row, a refused wait) with the same common fields as the other server's.
- A symbol name the table gives twice is refused as `ambiguous_ref` naming each address; a re-armed
  tap or a pointer base that is ambiguous says so rather than `unknown_ref`.
- `status` with no session omits `presence`; `close` with no session says `pid` and `exit_code`
  are unavailable; symbol prefix matches come back in a stable order.
- `Look` keeps the fields both servers share; the guest pointer is the server's own `pointer`.
