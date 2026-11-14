# Changelog

What a client of the server notices.

## Unreleased

- `send_keys` and `send_mouse` while the emulator is inside a long host call (a DOS file or
  device operation it waits on) answer `delivered: false` and say the input was not sent, where
  they said whether it acted was unknown: nothing was written, so sending it again once `status`
  answers puts it in once.
- A `send_keys` or `send_mouse` cut part-way by a long host call says how many of its input
  commands were written and that a key it pressed is left down, where it said some of it may
  have gone in. The next input sends that release before its own commands and says so in
  `note`, where the key used to stay down until something else released it.
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
  a file `dest`, a `logfile` or a state's `name` given as `Shot_1.PNG` or `Boss_1` is written
  as `shot-1.png` or `boss-1.sav`, and a reply that carries the path names the file as
  written. A file `dest` or a `logfile` with no extension is refused, with no session too; a
  directory `dest` keeps its name. A state is loaded by any spelling of its name. A state or a
  screen map kept under an earlier spelling (`Boss_1.sav`, `<application>.screen-map.json`) is
  not found until its file is renamed; `state_list` says so in the row's `note`. A trace's set
  file is `<trace name>-<extension>-set.jsonl`, a screen map
  `<application>-screen-map.json`, and a comment file is advised as `<stem>-comments.tsv`.

- The descriptions say that only a watcher on a stream needs `fullscreen` (`start`), that
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
  those two arguments own are refused by name. `fullscreen` on `sdl output=surface` is refused. A windowed start is placed 40 px inside the asked display's corner, since the scry build ignores `sdl display` alone on macOS; `fullscreen` on a display other than 0 is refused there, because a start is halted at its first instruction and the window reaches full screen on another display only once the emulator runs.
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
