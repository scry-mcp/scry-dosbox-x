# Changelog

What a client of the server notices.

## Unreleased

- Takes scry-core 0.118.3.
- `run_to`'s `cut_by_other_stop` refusal says what to do next, as scry-mame's does: `cause` names
  what stopped the run, and a watch is passed with `disarm_watches=true`.
- `promote` refuses a `start` profile or a `perform` document holding a `${...}` that is no
  placeholder, typed text included, where it wrote a store file `perform(path=)` refused.
- A DJGPP program's table given to `start(symbols=)` is placed at the first stop in its own 32-bit
  code, where a stop in the DPMI host's 16-bit code placed it at the host's base, and every
  symbol read through it (`read_memory` of a variable, a stop's `symbol`) answered another
  place.
- `build_check` lists `record` and `audio_record` among what a build without `RUNSTATE` cannot
  serve: their retraces run as `run_for` runs them.
- `scan` no longer lists a `survivors` reply field: it never sent one.
- The live tier reads its bench only from `DOSBOX_X_LIVE_BENCH`: unset, every program on the bench
  is BLOCKED naming the variable, where it fell back to a directory of the developer's home.
- `symbols_load`'s `base` and `section_bases` and `symbols_find`'s `linear` take an address as
  `0x` text or an integer, as every other address; bare hex digits (`8000`) are refused, since
  they read either way.
- `debug` writes an output past 4000 characters whole to a file in the session's scratch and
  answers its first line as a preview, with `output_chars` and `output_path`, where it kept only
  the last 4000 characters.
- `run_to` and `run_for` take `disarm_watches`: the change watches' rows leave the debugger for
  the pass and come back at its stop, and the reply names them in `disarmed_watches`, with
  `not_rearmed` (and why) for one that could not come back.
- `breakpoint_at` takes `role="control"`: the place is stored and counted by every `run_to`
  beside the run's own `control`, held in the debugger only while a run counts it, so it never
  stops `resume`, `run_for` or a wait (an `on_breakpoint` wait on it is refused). Its
  reply, and each breakpoint row of `declaration_list`, carry `role`.
- `role` is on every `breakpoint_at` reply and every breakpoint row, so a demo transcript that
  declares a stop shows `role: "stop"`; the bricks and mines demos pass their table's `base` as
  `0x` text.
- A pattern or an `expect` that does not compile is refused naming the argument
  (`pattern='(' does not compile: ...`), where it said only that it was not a usable pattern.
- `read_memory` and `scan` no longer list a `rows` reply field, nor `write` a `written` one: no
  tool ever sent them. `read_memory`, `disassemble`, `find`, `memdump` and `write` declare the
  `ref` every `ok` reply of theirs echoes, and `scan` on `start`.
- `debug`'s summary counts the characters of a short output too, where it read "None chars".
- `run_to` refused before the release because the debugger did not list one of its breakpoints
  takes out every row it armed, where they stayed and stopped the next `resume`.
- A control declared with `breakpoint_at(role="control")` is counted by `run_to` only where a stop
  row would be armed (placed in this mode, not stale over another build), where it counted hits
  at another byte or refused the run.
- A `perform` document a store holds is replayed with its placeholders resolved, `${state}`
  naming the session's scratch: its steps ran with `${root}` in their paths and were refused.
- A `drive` refused before its act ran carries `looked` as `{"guest": ...}`, the shape of
  every other `drive` reply, where it carried a bare `unavailable` block.
- The descriptions say what the tools already did: `memdump`, `trace`, `snapshot`,
  `audio_record` and `machine_map` take a `~`-led `dest`, `log` refuses an empty `pattern`,
  `state_list` rows carry `name` and `path`, and `screen_wait`'s schema lists the `palette` it
  takes.
- A stop at the boot sector (0000:7C00) after a conf's `boot` gives the guest OS's boot as its
  `cause`, where it said no declaration could explain it; `resume`'s reference says a second
  `resume` lets the guest OS run.
- The Monkey Island demo starts DOSBox-X in its run's directory and mounts C: there by a
  relative name, so its loop and screen are the same wherever the repository is cloned.
- `screen_wait` refuses a watch that follows a pointer saying its firing "cannot be told from
  another stop", where it said "from a retrace".
- `start` refused for a `profile` no directory above holds carries `searched`, the directories
  it walked, the `cwd` hint included.
- scry-core 0.115.0 pinned: the at-stop wait's refusals and note, its reply fields and their
  sentence, and what a `start` or a map's `add` keeps for `promote` are the same code on both
  servers.
- A file written at a path you name (`dest` of `memdump`, `trace`, `snapshot`, `record`,
  `audio_record`, `comment_write`, `palette`, `screen_view` and `capture_frame`) takes the name
  every file the server writes takes, lowercase words joined by hyphens with one extension:
  `Shot_1.PNG` is written as `shot-1.png`, and a name with no extension is refused before the
  machine is asked, as is a `%` in `capture_frame`'s `dest`, since no numbering pattern is
  expanded. The reply's path names the file written, and its `note` says so whenever
  the name is not the one you gave, on these tools and on `machine_map`, `screen_map_write`,
  `perform_export` and `start`'s `logfile`. `start` answers `logfile` when given one.
- scry-core 0.114.0 pinned: it words the one sentence a reply's `note` gives when a file is
  written under another name than the one given.
- scry-core 0.113.0 pinned: on the Mac a window placed to fit a display's usable area sees a
  Dock or menu bar that showed, hid or moved within a few seconds, where it kept the first area
  it read for the life of the server.
- The ReChip! demo's three stops the host places leave their `note` out of the transcript, which
  the server adds only when a stop landed in a ROM handler, so two runs write one transcript.
- scry-core 0.112.0 pinned: the probe resolves `{tmp}` and `{anchor}` in a task file, so a
  task set spelled through them is judged the same on Windows as on the Mac.
- The probe's task file and its captures spell a path through `{tmp}` and `{anchor}`, so
  `probe --check`, the hook and the suite's task and capture checks judge the same tasks on
  Windows, where `/tmp/x` is relative and every such task was refused.
- scry-core 0.111.2 pinned: the pre-commit hook starts the `jscpd.cmd` npm installs on Windows,
  so the hook's cases run there; `DOSBOX_X_LIVE_SECTIONS=AA` (letters that spell section AA) and
  a value that names no section (`,`) are refused at INVALID, where the first ran section A and
  the second every section.
- On a debugger channel that went silent, the window's presence edge no longer sends its first
  version request either: a reply waited one bound less for it.
- A `screen_wait` judged on a watch that never fired, on a dynamic core, no longer says a code
  breakpoint is declared when none is: the caveat about a core passing one over comes only with
  a declared code breakpoint.
- A map `screen_map_write` loaded names the entry it was read from, so an `add` after the
  load updates that map in the store it came from, as the `promote` description says,
  where it was kept as a new map of the current `start`'s repository.
- `window`'s `front` is said as it is computed: on screen, with no other application's
  window over its centre.
- After a release no answer confirmed, a reply on a channel silent through a long host call
  waits the channel's bound once, where its `session` block asked `RUNSTATE` again and
  waited a second bound; a `step` with no stop says it is running only when it is.
- `screen_wait`'s description no longer says a wait on a declared stop runs on the normal
  core (it runs on any), and `start` says `symbols_placed` carries `load_segment` in real
  mode only.
- On the pinned scry-core (`pyproject.toml`), `screen_wait`'s description gives `condition`
  a register of the stopped cpu, never a register this server refuses.
- Inside a long host call each call answers `host_failed` after the debugger channel's bound
  once, where the presence edge's own delivery held the channel for a bound in front of
  nearly every call and doubled it; the edge waits for the channel to answer again.
- `state_write(method="load")` of a state saved in another program than the one running (at
  the stop before DOS boots, none is) answers `needs_call`, naming the program to run first,
  and leaves the session unaltered, where it answered `unexpected_answer` and marked it
  altered though the emulator replaced nothing.
- A `send_keys` or `send_mouse` cut part-way while paying the releases an earlier cut send
  owed counts only the keys still down, where it also counted those whose release had just
  gone in.
- A steered `send_mouse` summary, inside `perform(summaries=true)` too, says "program's pointer
  at" with the place `arrived` judged, and the driver's place beside it when the two differ,
  where it said "pointer at" with the driver's place alone.
- A steered `send_mouse` whose move leaves the guest in a mode this server does not map says
  so in `pointer.program` (unavailable, no ratio to nudge by), where the block was missing.
- A steered `send_mouse` after a pointer move the steering did not send (`units="mouse"`, a
  move while the guest ran, a drag's end) first waits, a retrace at a time and up to the
  bound its reads already use, for the program to take that move, where it read the
  program's pointer at once and could find it where the move had not yet carried it: on the
  place, it sent nothing and left the pointer to land elsewhere. With no such move behind it,
  nothing waits.
- On the pinned scry-core (`pyproject.toml`), `promote` writes an entry only into the store of
  the repository it was learned in (the one whose store a call read it from, else the current
  `start`'s: its profile's, else the one its guest runs in), so a session that ran programs of
  two repositories never files one
  in the other's and the server's own directory never lends its store. An entry whose
  repository holds no store is `unwritable` in a review and refused in an approval, naming the
  `root` to pass; the `kept` line names each such repository; a call writes one store; with
  `root`, a candidate kept in another repository says `from`.
- A `start` refused before it launches (a session already live) leaves the live session's guest
  as it was, so the next map `add` is still named after the program on its screen.
- `send_keys` and `send_mouse` while the emulator is inside a long host call (a DOS file or
  device operation it waits on) answer `delivered: false` and say the input was not sent, where
  they said whether it acted was unknown: nothing was written, so sending it again once `status`
  answers puts it in once.
- A `send_keys` or `send_mouse` cut part-way by a long host call says how many of its input
  commands were written and that a key it pressed is left down, where it said some of it may
  have gone in. The next input sends that release before its own commands and says so in
  `note`, where the key used to stay down until something else released it.
- `log_wait` during a long host call keeps its bound (plus at most one debugger request's),
  reports in `waited_s` the time it took, and no longer says the machine is still running when
  nothing answered that question.
- A steered `send_mouse` whose program pointer is on the place answers `arrived: true` wherever
  the driver sits: a program that adds the driver's motion to a pointer of its own takes a
  click where that pointer is, so moves that answered `arrived: false` with a note about the
  driver disagreeing now answer true. The note and the false answer remain for one case, a
  driver range that changed during the move without the steering changing it; a range the
  program sets on the click itself no longer counts.
- A steered `send_mouse` whose program pointer is already on the place sends no move, and its
  reply carries no `motion`: a click after a hover on the same control moved the driver to the
  place's middle, which carried the program's pointer off it, and the nudge back left the
  driver further from the pointer over a walk of such calls.
- `start`'s `plan` and `drive`'s `act` say what a step looks like, `{"op": <tool>, ...arguments}`,
  in the words `perform` uses: a first call no longer guesses the key and meets a refusal asking
  for `op`.
- A steered `send_mouse` learns the ratio between the driver and the program's pointer from the
  motion the driver made, not from what was asked of it: a nudge the driver's edge cut short
  taught a ratio that grew with every nudge at the edge, so the round after the corner sweep
  swung the pointer from edge to edge and ended `arrived: false`. It now lands on the place.
- A `send_mouse` steered by a map's `pointer` reads the program's pointer only once the program
  has taken each move: a program that reads the mouse once a pass of its own loop shows a move
  some retraces late, and a read before then made a nudge look like a pointer that stopped, so
  the steering swept the corners and ended `arrived: false` with a `reach` the pointer never
  had. Such a move now arrives; its `polls` include the retraces it waited.
- `start(symbols=, base_from="program")` on a DJGPP program places its symbols at the program's
  own DPMI selector, not the DOS load segment: the go32 stub lives in the load segment while the
  protected-mode code runs off the selector, so a breakpoint armed on such a symbol now fires
  where the code runs instead of landing on a dead address.
- A refused `record` or `audio_record` removes its file: a capture the server rejects (a short
  WAV, a header that disagrees with its file, a truncated stream) no longer stays in the capture
  folder, so a repository's folder does not fill with files no run owns.
- `log` on a running guest says when lines may still be in flight: the emulator flushes its log
  in its own time, so a line the guest has just written may not be in the file yet, and its
  absence from the reply is not proof it was never written.
- `start(profile=...)` with no `cwd` says so plainly: a named profile not found above the
  server's directory is refused with `cwd` named as the way to point the server at the
  repository that holds the recipe, instead of only the directories it searched.
- `send_keys` takes `shift`, `ctrl` and `alt` (and `control`, `option`) as keys: with `action`
  `down` and `up` a modifier can be held on its own, where `modifiers` needed a real key beside
  it, so holding one keeps a program from going idle without holding a key the program may map.
- A new tool, `wait`, lets a running guest play for `seconds` and answers `waited_s` and where it
  is, without releasing or stopping it: its expiry is the answer, never a failure, and a stop
  during the wait (a breakpoint) comes back as the stop reply. A stopped machine is refused as
  `not_running`.
- `log` and `log_wait` say when the logfile lost lines it once held: a capture could eat the
  guest's lines, and the next `log` answered none as if the program never wrote them. Once, the
  `note` gives the file's size now and the size it had.
- `close`, `status` and the `session_broken` reply tell the server's own kill of the emulator
  from one sent from outside, and for an outside one name the macOS memory manager and its
  report directory, where a guest it killed read as a crash of the guest.
- A `send_keys` with `expect` that does not see its pattern, when it is the session's first,
  adds to `verify.note` that the guest may drop a first key while it settles: send it once more
  before hunting for a modal that is not there.
- `log` and `log_wait` read the logfile without asking the debugger channel first, so they answer
  while the guest sits in one long host call (a DOS call over a large folder) instead of
  `host_failed`; a `host_failed` reply names that as the likely cause, so `send_keys` and
  `perform` say why the debugger did not answer.
- `session.running` says the truth about the guest, never a guess: past a `run_for`, `run_to` or
  `resume` whose release no answer confirmed, it re-reads the machine, so a caller is told `false`
  when it stopped and `unavailable` when it still cannot be read.
- Every tool that writes a file honours the `dest` a caller names, `_` and capitals kept, and its
  reply's `path` is that name: `screen_view`, `snapshot`, `palette`, `record`, `audio_record`,
  `memdump`, `trace`, `capture_frame` and `comment_write`; the file-name rule is of the names a
  server makes up, not of a caller's own path.
- The demos ship a loop: each demo's `loop.mp4` sits beside its `screen.png`, recorded by the
  runner after the step that takes the still.
- On the pinned scry-core (`pyproject.toml`), which carries the window every demo asks of
  its `start`.

- On the pinned scry-core (`pyproject.toml`), whose demo runner fails a loop a bound or a
  stop cut.

- On the pinned scry-core (`pyproject.toml`), whose demo runner reports the stop that ends
  a loop as the host's too.

- On the pinned scry-core (`pyproject.toml`), whose demo runner reports a loop's own timing
  as the host's, so a demo's two runs give one transcript.

- On the pinned scry-core (`pyproject.toml`), whose demo runner takes `--display`, so a
  demo can be recorded on one of the host's own displays.

- On the pinned scry-core (`pyproject.toml`), which renders a repository's `.scry/README.md` from
  one template and holds the `record` text both servers answer.
- On the pinned scry-core (`pyproject.toml`), whose `record` words say what a bound does when its
  release answers, so a server that answers `ended: false` over a capture it could not turn off
  is not contradicted.
- On the pinned scry-core (`pyproject.toml`), whose demo runner records a demo's loop and
  converts it to its `loop.mp4` beside the capture.
- `record` with an empty `dest` writes into the session's scratch and answers its `path`;
  `frames` under 2 and a `dest` whose suffix is not `.avi` are refused.
- A `promote` that names `root` no longer fails when the working directory is gone.
- A guest whose conf's path holds a space keeps its own name, not the first word of the path.
- An approved `promote` into a repository with no `.scry/` also writes its `about.json` and
  `README.md`: `dry_run` lists what it would create in `would_create`, the approval says what it
  created in `created`. A reply that kept something for `promote` says when there is no `.scry/`
  above the project, and how to see what an approval would create.
- Interrupts and offsets read as a programmer writes them: `breakpoint_interrupt` and
  `interrupt_vectors` take `number` and `ah` as `0x` hex (`"0x21"`) as well as integers, and
  each vector's `number` answers as `0x21`, not 33; `symbols_find` takes `offset` as `0x` hex
  and answers every `offset` in hex; `symbols_load` answers `base`, `limit` and `descriptor` in
  hex, and `unavailable` where no descriptor was read, not -1, as does the `base` of a stop's
  `symbols_placed`. The Monkey Island demo skips its
  intro again, by Escapes sent at the game's own ticks.
- On macOS the server reads the screens from a child process when it places a window, so it is
  no longer held as an application and Activity Monitor cannot show it as not responding.
- Every demo arrives by the program's own code or screen, never by a fixed time: MINES runs to
  its loop after each click; LineUp stops at its first DOS call, waits for each screen at the
  frame after its tick and reads each move once taken; Speed Fight stops at its first VESA
  call and runs to its title, on the normal core and a fixed clock; the Deluxe Paint demos
  wait for each screen on their map, and the maps demo holds the palette's arrow until a
  watch sees the colour at its top. A transcript hides what the host decides (the window, the place a
  retrace stop lands on, a derived conf's digest).
- `screen_wait` takes `on_breakpoint` or `on_watch`: the screen is judged only at the frame's
  end after a firing of that declared breakpoint or change watch, never by sampling, and a
  `condition` filters the firings first. The reply counts `firings` and `frames_examined` in
  place of `polls`; a row that never fires is `never_fired`, and such a wait is cut, not
  replayed, by `perform_export`. `changed` waits for a mapped screen other than the one shown
  at the start.
- The files the server writes are named in lowercase words joined by hyphens, with one
  extension ([the rule](https://github.com/scry-mcp/scry-core/blob/main/docs/file-names.md)):
  a `logfile` or a state's `name` given as `Run_1.LOG` or `Boss_1` is written as `run-1.log`
  or `boss-1.sav`, and a reply that carries the path names the file as written. A `logfile`
  with no extension is refused, with no session too; a directory `dest` keeps its name. A state is loaded by any spelling of its name. A state or a
  screen map kept under an earlier spelling (`Boss_1.sav`, `<application>.screen-map.json`) is
  not found until its file is renamed; `state_list` says so in the row's `note`. A trace's set
  file is `<trace name>-<extension>-set.jsonl`, a screen map
  `<application>-screen-map.json`, and a comment file is advised as `<stem>-comments.tsv`.

- The descriptions say that `fullscreen` captures the mouse, so the guest pointer no longer
  follows the host cursor (`start`), that
  `detail` adds the debugger's own text while the E9 lines come in the stop reply's `e9`
  (`resume`), what `control` holds and that `gdt` and `ldt` are read by default in protected
  mode (`machine_map`), and that a step's `recorded` is `{field: value}` of its reply
  (`perform`).
- A `logfile` that is the `captures_dir` or the `state_dir` in another case (`Out.D`, where the
  log is written as `out.d`) is refused, as one spelled the same is.
- A `promote` review lists apart, in `unwritable` with its reason, each entry it cannot write,
  and shows the rest.
- `close` no longer names an entry the store already holds as it is.
- `promote` also looks for the store from a recipe's `conf`.
- `stop(until="protected")`: a stop that lands in a BIOS handler, in real mode, runs on in short
  slices until one lands in protected mode, also from a stop already held; `runs_to_protected`
  says how many it took and `cpu_mode` where it ended. A real-mode refusal and a stop in the
  ROM name it. While it walks it reports which run it is on, and a cancel ends it between two
  runs with the machine stopped.
- `promote`: a map or a script learned from a loaded recipe looks for the store from that
  recipe.
- `start` through an app bundle runs in the right working directory: a relative mount in the
  conf named the wrong one.

It needs the scry-core that serves `scry_core.window`, `recording.read_document` and
`recording.steps_to_replay`, not an older one: the tag pinned in `pyproject.toml` is the
floor.

- `perform` takes `path`: a `perform` document (`.scry/perform/<name>.json`, or a file
  `perform_export` wrote) whose steps are replayed on the session; `steps` and `path` are
  refused together, and a document whose version this server does not read is refused by
  name.
- `start` and `build_check` on Windows read the build's `version` from the executable's version resource instead of
  running `-version`, which opens a console and waits for a key there: a `start` no longer waits for the probe's
  bound and the reply carries the version.
- `close` on Windows asks the emulator to quit through its debugger channel before terminating it, as SIGTERM does
  elsewhere: a healthy session now ends `ended_by: quit` with exit code 0, and `killed` means it did not leave.
- The descriptions of `build_check` and `start` name `session_live`, `registers` names `no_stop` and `snapshot` names
  `wait_expired`, the codes they answer; the README says how to watch a session, and `start`'s page says who mounts
  the stub and what a repository's conf must drop.
- `send_keys` takes `action`: `down` holds the modifiers and presses the keys, `up` releases them, and `press` (the
  default) taps them as before, so a program that reads the keyboard state can be tested with a key held (no repeats of its own: each is a further `down`). `send_mouse`
  takes `action="triple"`, three clicks a tick apart, and the range widening of a program's pointer measures a
  sweep that a screen edge clamped from a shorter distance, so `pointer.mouse.max_*` no longer comes out several
  times too large. `perform`'s description says a `screen_view` step answers its picture as `not_inlined: nested`.
- `window` says why a size reads `matches: false` while the guest has never run (the emulator takes the size at its
  first video mode) and what to do: `resume` and read again.
- `flags` takes a `-set` as `key=value` with no section too, as DOSBox-X does, and refuses a key the server owns in that
  spelling (`break on int3=false`, `integration device=false`, `debugger headless=false`); a `-set` with no `=`, the
  value after a space included, is refused because DOSBox-X ignores it. `symbols_find` by `linear` in a section the
  table lacks answers `unknown_ref`, a real-mode base off a paragraph keeps its low bits, a conf's
  `windowresolution=desktop` or `original` is no longer overridden by the fitted size, and a quoted `mount` path with
  a space is read.
- `screen_map_write` takes `method="pointer"` and `pointer={"x": ref, "y": ref, "bytes": 2}`: the program's own
  pointer declared by a call instead of by editing the saved map; `save` keeps it and a `load` replaces it.
- `build_check` answers `debugger_commands_missing`: each debugger command the build lacks, with the tools it
  takes away (a build without `RUNSTATE` lists `run_to`, `run_for`, `trace`, `screen_wait` and the rest); it is
  omitted when the build has every command.
- The `session` block carries `program` once the program the guest was running is gone: `exited`, or `fault` with
  the message DJGPP left on the text screen quoted from there (it never reaches the E9 log). It is read at the
  stops that answer a call, from DOS's current process. A wait that expired opens its `note` with that, or with
  the fact that the guest wrote no line in the wait, instead of leaving the cause among a list of guesses.
  A `run_to` whose control stayed silent, and a wait refused with `wait_stopped`, open their `message` with it too,
  since a gone program is why.
- `send_mouse`: naming an `action` with no `button` presses the left one (a `click` used to press nothing; with
  neither, the pointer only moves); a screen-unit move that no program pointer judged answers `driver_arrived` (where
  the driver is), not `arrived`; and when a program's pointer can only follow the driver over a range smaller than its
  screen (Allegro's default DOS mouse: 640 x 200 for a 1024 x 768 screen) the range is widened once, by a new stub
  command (protocol 7: a conf that mounts an older `SCRY.COM` is refused), and `range_widened` is in the `session`
  block of every reply from then on. A `perform` list that ends on a missed `expect` quotes that step's own reply in
  its `note`.
- `start` notes a stub the conf runs off a mounted drive that speaks another protocol than the server, instead of
  leaving it to the first key or mouse call; the `send_mouse` summary says when the driver's range was widened.
- `symbols_load` takes a selector as `base_from` (four hex digits, `00AF` for a DJGPP program under CWSDPMI): the
  debugger reads its descriptor in any CPU mode, so a table can be loaded, and `send_mouse` can steer the program's
  pointer, at a real-mode stop without waiting for a protected-mode one.
- `send_mouse` steers a protected-mode program's own pointer from the real-mode stop its retrace ends on: a build
  whose debugger has the new `MEMDUMPLIN` (a read by linear address, through the page tables of CR3 with paging on or
  off) places the map's pointer symbols as the table's base plus their offset, when the table was loaded at a
  protected-mode stop from a register. `start`'s `debugger_commands` lists it. Without it, or with a table whose
  base was given by hand or taken from the program's load segment, the call is refused as before.
- A steered `send_mouse` places the program's pointer again at every stop it reads from, so a retrace stop in
  real mode after a nudge no longer fails on the selector placed at the first one. When the pointer does not
  arrive after the sweep, `pointer.program.reach` gives the span it took at the driver's two corners: a program
  can show the driver's range on a window of its screen, and an aim outside it cannot be reached.
- The `send_mouse` summary says `no button pressed` when the call named no `button`, so a move whose check
  saw no effect is not read as a click that failed. A symbol that folds past the first megabyte at a
  real-mode stop is refused saying that no `SEG:OFF` reaches it there either (the debugger wraps a
  real-mode offset to 16 bits) and to arm or read it at a protected-mode stop; it used to advise an
  explicit `SEG:OFF`, which is refused too.

- `start` takes `size` (`WIDTHxHEIGHT` in the host's unit), sent to the emulator as `sdl windowresolution`
  (logical pixels where DOSBox-X is not DPI aware: from 200 % on Windows with the conf's default `dpi aware`,
  at any scale with `dpi aware=false` or `-nodpiaware`; real pixels with `true`; points on macOS).
  Without it a watched window keeps the size the conf states, else is the largest 4:3 one the display's
  usable area holds where the conf's `sdl output` takes a size (every OpenGL output and Direct3D; an
  unset `output` on macOS and Windows). `size` is refused beside `fullscreen`, beyond the usable area with its
  frame and under an `output` that ignores it, and `window` judges a stated size. A `-set` of
  `sdl windowresolution` in `flags` is now refused naming `size`, no longer "the conf decides".
- A `start` refused with `window_not_visible` leaves its session live with the `presence` it was
  asked for drawn, so `window(front=true)` brings forward a window that carries it.

- `start` takes `display` (the OS's index, the main display when omitted) and `fullscreen`, and a
  watched start answers `window`, proved in the host's window list; a window that never appears on
  the asked display is `window_not_visible`. `SCRY_EMULATOR_ARGS` is gone, and `flags` setting what
  those two arguments own are refused by name. `fullscreen` on `sdl output=surface` is refused. A windowed start is placed 40 px inside the asked display's corner, since DOSBox-X ignores `sdl display` alone on macOS; `fullscreen` on a display other than 0 is refused there, because a start is halted at its first instruction and the window reaches full screen on another display only once the emulator runs.
- A new tool, `window`, answers where the window is at any time, and with `front=true` brings it
  in front of what covers it. Without `front` it answers the window
  wherever the owner put it, another display included. A `front` that fails on a session
  started with `background=true` names that as what may keep it behind and what to do.
- The cases that move the owner's Space carry the `window` marker and are out of every default run.
- `symbols_load`'s summary says whether the table was checked against a build beside it, and against which
  executable, so a table nothing could check no longer reads like a proved one.
- A second `symbols_load` answers `loaded` with what that load put in, the count that can be judged
  against `parsed` and `table_total`; `debugger_holds` carries every row the debugger still holds,
  since `LV` appends, and comes only when it is larger.
- A stored declaration whose name no loaded table resolves says in its row why, and what would
  place it, instead of reading as a symbol this build lost.
- The `session` block carries `image_changed_on_disk` once the executable a loaded table was checked
  against is written again, which is a relink under a live session; `status` says it on its line.
- A `stop` that lands inside the ROM says so in its `note`, with the address, and says that
  `run_for` or `resume` leaves it while `step` stays in the handler.
- `start` takes `profile`: the name of a `.scry/start/<name>.json` a repository declares, or a
  path to one. Its keys are `start`'s own arguments and fill only what the call does not give,
  every path resolved against the directory holding `.scry/`; the reply's `profile` block names
  the file and what it filled. `conf`, `cwd` and `session_seconds` are optional now, so a
  profile can carry them, and one neither the call nor a profile gives is refused by name.

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
