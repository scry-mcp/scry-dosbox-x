# Contributing to scry-dosbox-x

This is the guide for changing the server. What the tools promise is in `REFERENCE.md`; this
file says where the code lives, how to run the battery and the live tiers, and what proves a
change.

## Where the code lives

`src/scry_dosbox_x/server.py` holds the tools and `src/scry_dosbox_x/mcp.py` the MCP boundary (the
server object, its `instructions`, the roster of tools by family). Every other module in
`src/scry_dosbox_x/` holds one concern, and its docstring opens with what it holds and why: read that
before changing it. What both Scry servers share (the reply contract, the reference generator, the
demo runner, the probe, the live bench) is the scry-core package, pinned by tag in `pyproject.toml`; its README lists every module, among them `scry_core.process_tree` (ending a launched
process with everything it started), `scry_core.regpoint` (the `regpoint_hit` of a registerpoint
stop) and `scry_core.tool_replies` (the fields `screen_map_write`, `log_wait` and `comment_write`
share).
`src/scry_dosbox_x/guest/` holds the resident input stub the server loads into the guest (`scry.asm`,
built to `SCRY.COM`), `demos/` the demos, and `tools/` the development scripts below. `tests/` holds the
contract tests and `tests/live/` the tiers that drive a real emulator.

## The battery

The suite runs with a home and a temp folder of its own (scry-core's `private_run`, on in
`pyproject.toml`) and fails a run that leaves a file in that home; it stands aside when a `live`
case is selected. Every name the server writes goes through `scry_core.file_names` and follows
scry-core's [rule of file names](https://github.com/scry-mcp/scry-core/blob/main/docs/file-names.md);
`tests/conftest.py` fails a case whose files break it, except the debugger's own names it lists
(`MCPDUMP.BIN` and the like), which a new debugger-named file joins.

```sh
uv run ruff check .
uv run mypy --strict .
uv run mypy --strict --platform win32 .
uv run pytest -q
bash .githooks/pre-commit-test.sh   # the hook's own cases
```

Ruff and mypy (strict, over the whole tree) judge the code, the second mypy as Windows sees it, so
a call Windows lacks goes red on any host until it is guarded by `sys.platform`; pytest runs the
contract tests and, through `--cov`, the coverage floor in `pyproject.toml`; the last line runs the
pre-commit hook's own cases. All five green is what a change needs before it is committed.

On Windows the battery is the same, with `uv run pytest -q --no-cov`: the floor is judged on macOS
only, because Windows skips by design the cases that need what it lacks (a FIFO, a mode bit, a
symlink), and the floor counts the whole tree.

`.github/workflows/ci.yml` runs this battery on GitHub's Linux runners when started by hand, with
`--no-cov` since the floor is macOS's, plus the pre-commit's checks (which need `jscpd` on the
`PATH`, here as on a contributor's machine); the live tier stays on macOS and Windows, where an
emulator and a display are. Without `nasm` the guest-building cases skip, and without `ffmpeg` the
media ones; the workflow installs both so that a green run covers them. The committed guest binaries
are built by the nasm major `tests/test_dosbox_x_guest.py` names, so their byte-identity cases skip
under the older one Ubuntu ships, and run on macOS and Windows.

A tool's reply model is its contract. A number whose natural notation is hex (an address, an offset, an interrupt, a
port) is answered as `0x` text and taken as `0x` text or an integer. A field every `ok` reply of the tool carries is `Required[...]`
in the model; one that comes only under a condition is `Annotated[T, When("words")]`, and the
tool's `Reply:` sentence says those words beside the field; a datum that could not be read is
`unavailable(why)` and never absent. The battery refuses an `ok` reply that lacks a required field,
and `tests/test_dosbox_x_reply_models.py` refuses a promised field whose condition the sentence does not say.

A change to a tool's arguments, reply model or description changes its reference page, and
`tests/test_dosbox_x_reference_pages.py` goes red naming the tool, the page and the line. Regenerate the pages from the
code, and the examples only from a live run's transcript (each `--mark` spells a directory of
the run's host, as the committed examples do). A green live run removes its scratch, the
transcript with it, so hard-link `transcript.jsonl` out of the run directory while the run goes,
and only one newer than the run's start, since the scratches of earlier failed runs keep their old
transcripts under the same temp root. Mark the temp root as well as the run directory: a server's
own scratch lives directly under `$TMPDIR`, so a `--mark` of the run directory alone leaves host
paths in `examples.json`; add `--mark '<TMPDIR without its trailing slash>=$TMPDIR'` and grep
`docs/reference` for `/Users/`, `/var/folders` and `/private/var` before the commit:

```sh
uv run python -m scry_core.reference scry_dosbox_x.server:REFERENCE --write
uv run python -m scry_core.reference scry_dosbox_x.server:REFERENCE --write \
    --examples <transcript.jsonl ...> --mark '/tmp/<the run>=$TMPDIR'
```

The commit itself runs scry-core's pre-commit (`python -m scry_core.hook --help` says what it checks): enable it once per clone with

```sh
git config core.hooksPath .githooks
```

Its prose check is a share of each file's bytes, so a change that only deletes code raises the
share and can go red with no comment touched: run the hook after a sweep that deletes lines, and
cut a clause in the file it names, never raise the ceiling.

These are contract tests and none of them launches an emulator: they hold the part that has to
be true before one is involved. `tools/bench.py`'s own guards are among them, because an instrument
that can lie needs validation and validation nothing executes is a comment.

Every pytest run judges the coverage floor: `--cov` is in `addopts` and the floor is
`fail_under` in `pyproject.toml`. A partial run goes red on that floor by construction, because
the floor is the whole repository's. `addopts` ends in a bare `--cov`, which takes the next
argument as its source, so `uv run pytest tests/test_x.py` runs the whole suite while looking like
a one-file run, and a `--no-cov` after the path does not help: the path was already taken. Narrow
a run with `-o addopts=""` naming the test files, or with `-k <module name> --no-cov`, and read it as a run
that judged no floor. `-o addopts=` also drops the `not live` and `not window` deselections, so it names
test files and never a directory: `tests` would start a real emulator. The live tier is deselected by default (`-m 'not live and not window'`).

`uv run` syncs the environment before its command, so an editable install of a core checkout
(`uv pip install -e ../scry-core`) is replaced by the pinned scry-core on the next plain `uv run`,
and a battery, probe or live tier then judges the pinned core while looking like a run on the
checkout. Print `scry_core.__file__` from the project's Python before and after a run, use
`uv run --no-sync` (or `UV_NO_SYNC=1`) while the editable core is wanted, reinstall it after a
full battery, and export `PYTHONPATH=<core checkout>/src` for a run that must keep the source
winning while another command syncs the environment mid-run.

The ruff and mypy configuration in `pyproject.toml` is scry-core's bar; mypy runs strict with no
path list, so a new directory is covered without being added anywhere.

## The live tier

A second tier under `tests/live/` drives a real emulator.

```sh
uv run pytest -o addopts="" -m live tests/live
```

It runs against a guest this package OWNS, `tests/guest/probe.com`, a few bytes of assembler
that write one instrumentation line every three seconds and never exit. Half these cases are
about a machine that is still RUNNING and the other half read what a guest emitted, so a tier
with no guest of its own would have to borrow one, and a borrowed guest is a dependency on
somebody else's program.

To run it against your own program instead, point it at your config and name the two tokens your
guest logs, one it writes EARLY and one it writes LATER, because one case waits for something
that has not happened yet and refuses to run if it already has:

```sh
DOSBOX_X_LIVE_CONF=/path/to/your.conf \
DOSBOX_X_LIVE_CWD=/path/to/its/dir \
DOSBOX_X_LIVE_PROGRAM=YOURAPP.EXE \
DOSBOX_X_LIVE_MARK=BOOT \
DOSBOX_X_LIVE_LATE=READY \
    uv run pytest -o addopts="" -m live tests/live
```

Your config needs `bochs debug port e9 = true`; without it the port is inert and the
instrumentation goes nowhere, which reads as a broken session rather than a missing line.
Nothing checks that for you. Three more things the overrides expect:

- `DOSBOX_X_LIVE_PROGRAM` must appear at the START of a line in your `[autoexec]`, and that
  section must also carry a bare `exit` line. Two cases build a variant config by deleting
  exactly those two lines, and skip if they cannot find one of each.
- `DOSBOX_X_LIVE_MARK` has to be something your guest logs EARLY, within the first handful of
  instrumentation lines.
- `DOSBOX_X_LIVE_LATE` has to be something it logs LATER and has NOT logged yet when the waiting
  case asks. A token that is already there makes that case report INVALID, which is the correct
  refusal and not a pass.

The cases that open a watched window open it as `start` does, on the display they ask for
(`display`, on [`start`'s page](docs/reference/session.md#start)). The cases that move the
owner's Space carry the `window` marker and are out of every default run: `SCRY_FOCUS_CONTROL=1
uv run pytest -o addopts="" -m 'live and window' tests/live` runs them (scry-core's README,
*On-demand tiers*). A demo or a live cell that needs the stop where an input lands takes the
input's own post as the stop, never a breakpoint the click itself will hit inside a step that
must answer ok (the read-back follows the button by a BIOS tick, `send_keys`' page says why);
one that records sound takes a clock the host holds with room to spare (an intermittent
`readback_refused` is the conf's clock first, `audio_record`'s page says why). The Deluxe Paint demos' cases also need `DELUXE_PAINT_DIR`, the directory holding version 1.0's
`DP.EXE` (the demos refuse any other build); this repository carries none of the program, and
without it they skip. The LineUp demo's case needs `LINEUP_MSDOS_DIR`, a copy of the game's PC port
with its symbol map, and skips the same way. The Monkey Island demo's case needs `MONKEY_ISLAND_CD`,
the directory holding the 1992 Enhanced CD's `monkey.cue` and its BINs, and skips the same way.
The Speed Fight demo's case needs `SPEEDF_MSDOS_DIR`, a copy of the game's PC port with its blessed
`EXES/SPEEDF.EXE` and `EXES/SPEEDF.MAP`, and the ReChip! demo's case `RECHIP_DIR`, a checkout of it
after `make mcp-conf`; each skips the same way.

**The matrix.** Around those cases sits `tests/live/dosbox_x_live_matrix.py`, run as a script
rather than collected: every tool in every machine state, at every argument edge, across the
calls that share state, then on real DOS programs a project points it at. Its cells are declared
before anything boots, so what was planned and never reached shows at the end. Each cell prints
OK, FAIL, or BLOCKED with the reason it could not run; every reply lands whole in a transcript
whose path it prints first and again beside the verdict, and a failed cell keeps the conf and the
log tail of the session live at the time. It exits 0 with no FAIL, 1 with one, 3 when the run is
invalid (no cell ran among them). Its docstring holds the command and the variables it reads.

**Parts run side by side.** The matrix runs each section (a letter; a name of two letters, once the alphabet runs out, is chosen with commas, `AA,` for a lone one), and
`tests/live/run_live_pytest.py` each windowless live test (the `windowed` ones follow one at a
time), as a process of its own, as many at once as `DOSBOX_X_LIVE_JOBS` says (unset, half the host's CPUs; `1`, one after another in one process),
merged from the summaries they declare through `scry_core.live_pool`.

```sh
uv run python tests/live/run_live_pytest.py
```

**What a run behind guarantees.** Every start of the matrix but the focus gate's own start in
front is behind, and a start behind does not come to the front, so the keyboard stays where it
was. That is all it promises: its window is still there to be seen, and the host carries the
load of every emulator the run starts, several at once. So a start behind is never the reason a
run is safe beside somebody working: the matrix runs in an account or on a machine nobody is
working at, or at an hour agreed with whoever is, and what says whether a run took the front is
section O's verdict, read as scry-core's README says (*Focus watch*).

What opens a window (section G, the focus gate's O, the `windowed` tests) runs alone. The focus
gate's start in front and its Space move take the desk of whoever is working, so they run only
with `SCRY_FOCUS_CONTROL=1` on an idle machine; unset, those cells are BLOCKED naming the variable
and the verdict says it is unproven. The full-screen cell runs beside them, before the window the
verdict judges: on macOS a window filling the display is a Space of its own, which the watch
would report as a Space nobody moved. Each part
works on copies of its own of the guests, because the debugger writes its files
under fixed names into the emulator's working directory (`tests/live/live_private.py`).

## The guests the live tier runs

The protected-mode cases need no other project: they run on a second guest the package owns,
`tests/guest/dpmi.c`, a DJGPP program built into the committed `dpmi.exe` and its `nm` table
`dpmi.sym`, under the DPMI host DOSBox-X provides, CWSDPMI, which the program's stub loads
resident.

The real-mode cases and the matrix's program sections run programs this repository does not
carry. Where one is not there, its case is skipped or its cells are BLOCKED naming what is
missing, so a fresh clone runs everything the package's own guests cover.

## What a live run guards

Both tiers refuse a host that cannot start DOSBox-X, and prove they left none running. Before its
first start a run launches the emulator once in a form that ends by itself; one that does not
return is INVALID naming the host, and nothing else is launched. Every DOSBox-X a session starts
is recorded where it is spawned, and at the end of the run one still alive is killed and FAILS
the run by name. A green run removes its scratch, its jobs' with it; a red, INVALID or broken one
keeps it and prints its path (`scry_core.live_host`).

## Development scripts

`demos/<name>/demo.py` runs one demo end to end; with `--update-readme` it rewrites the demo's
guide from a run where every step passed: the transcript block in its README, `TRANSCRIPT.md`,
`screen.png` and `loop.mp4` (the loop is recorded right after the step that takes the still).
Converting the loop needs `ffmpeg` on the `PATH`; without it a demo that declares a loop ends
INVALID and writes no loop.

`tools/bench.py` measures a program's cost. It takes `--conf` (the config file to measure) and `--cwd`
(the directory that config runs in) as required flags, with no default, and refuses without them,
naming the flags. `--json`, `--reps` and `--song` are optional. The song, the boot marker it
waits for and the make target of its batch cost belong to the program it was written for, so a
bench of another program names its own.

**Iterate from a saved state, not from the demo's start.** A demo or an experiment that spends
minutes booting a program before it reaches the thing under work is rerun from a state saved at
that point: `state_write(method="save")` once, then each run starts the same session and
`state_write(method="load")`. Check first that what the run judges survives a load, because a
state restores the guest's memory and not always the emulator's devices: a program whose video
memory or mouse driver the load leaves wrong (Monkey Island's screen comes back striped and its
pointer stops following the driver) cannot be judged from one. Memory reads, scans and anything
the program computes from its own memory can.

**The presence overlay is measured off the host screen.** The edge and the arrow are drawn after
the frame goes to capture, so `snapshot`, `screen_view` and the emulator's own recordings never
show them. Their size is read off `screencapture -x -o -l <window>` (the window number from
`scry_core.window_capture.window_of(pid)`; the title bar adds its own height on top), their timing
off `ffmpeg -f avfoundation -capture_cursor 0 -pixel_format uyvy422 -framerate 60 -i "<screen>:none"`
with `-c:v libx264 -crf 0`, cropped to the window's `kCGWindowBounds`. The arrow's fill is found
by colour (R>200, 100<G<175, B<90) with the edge band masked, and a click's effect by a region the
arrow never crosses. A look sent through `debug` is overwritten by the server's next delivery, so
a variant runs the server with `presence.LOOK` replaced before import. Validate the instrument
with a control that must come out red before reading a green: look variants that differ can
otherwise come out identical without anything saying so.

## Fixtures and the sweep off the commit path

One artefact per toolchain is BUILT HERE and committed under `tests/fixtures/`: a Borland TLINK
16-bit map with an overlay in it, an Open Watcom map spanning two sections, and a DJGPP `nm`
listing beside the GNU `ld` map from the same link. The two Borland residents share their first
fifteen characters on purpose, so the fixture exercises the collision the disambiguator exists
for. `tests/test_dosbox_x_fixtures.py` reads them, so the claim "this reads those formats" is
something a fresh clone can check.

Each ships with its generator, the source it was built from and a `build.sh` that re-makes it: a
captured artefact whose recipe is lost cannot be re-captured, and a discrepancy in how it was
transcribed can then never be settled. Neither toolchain is vendored here; `build.sh` takes its
location in an environment variable and stops loudly rather than quietly building with something
else.

`tools/mapsweep.py` reads REAL maps where they live, against a manifest that says what each one holds,
and goes red when the two part company in either direction: a count that ROSE against an
unchanged file means the reader has begun reading something that is not a symbol.

```sh
uv run python tools/mapsweep.py --manifest <manifest>.json --root /where/those/maps/live
```

It is manual and declared as such in `tests/gates-manual.txt`, with the reason: the material is
not in this repository and is not versioned here, nor is the manifest, which names it and so is
kept with it. On the commit path the sweep would be INVALID in every
clone but one, and a gate that is almost always invalid is one people learn to ignore. It covers
the Borland, Open Watcom and `nm` formats on real material; the GNU `ld` map is absent on
purpose, because the only one is the fixture this package generated, which lives inside the
repository, and the sweep is for material that does not.

What a red means: a count MOVED. What it cannot say is that a count is CORRECT: the first time a
project's row is written, whatever the reader says becomes the expectation, and closing that is
reading the map, by a person, once, exactly as blessing any golden is.

## Proving a change

A change to a tool's description, arguments or `instructions` is probed: the probe hands a model
only what a client delivers and checks that it calls the tool as the contract says. The
pre-commit runs its `--check`, which asks no model and names a tool or argument with no task in
`mcp_probe/tasks/`; a real run asks the `claude` CLI and judges each task over several runs:

```sh
uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py --tasks mcp_probe/tasks --check
uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py --tasks mcp_probe/tasks --runs 3
```

`python -m scry_core.probe --help` says how a failure is told from the model's noise. A task the
probe's model keeps getting wrong, where the server refuses the wrong call naming why, is accepted
residual and reported with its numbers: a client retries on a refusal, and more description text
for that task spends the cap the others need. Only a wrong call the server accepts with
`status: ok` is a defect.

The reference generator rewrites only the blocks between its markers, and the hand-written
paragraphs after a block belong to that tool by position. A tool moved to another family page
leaves them on the old page: take the text between its end marker and the next begin marker at
HEAD, remove it from the old page (it occurs once) and put it after the same tool's end marker on
the new page, then rerun the drift test. The `REFERENCE.md` prose that names the family and the
demos' family tables need the same sweep; the family of each shared tool is
`roster.SHARED_FAMILIES` in scry-core.

Windows stamps a file's mtime from a clock that ticks coarser than `time.time()`, so a file
created right after a clock read can carry an mtime a few milliseconds before it, and a plain
`mtime >= began` drops the first file of a run on Windows while never failing on macOS.
`MTIME_TICK_S` in `src/scry_dosbox_x/recordings.py` is the slack, bounded from the other side by
the gap between two calls, which is always longer. Prove a change there with a test that adds a
few milliseconds to the clock, never with a sleep, and give any step that compares file times
against the process's clock a Windows pass: its first sign is a test that passes and fails with
no change of code.
