# Contributing to scry-dosbox-x

This page is for changing the server: where the code lives, which checks a change must pass,
and what proves it. What the tools promise is in [REFERENCE.md](REFERENCE.md).

## Where the code lives

- `src/scry_dosbox_x/server.py` holds the tools, and `src/scry_dosbox_x/mcp.py` the MCP server
  object, its `instructions` and the list of tools by group.
- Every other module of `src/scry_dosbox_x/` holds one concern. Its docstring opens with what
  it holds and why: read that before changing it.
- `src/scry_dosbox_x/guest/` holds the input helper the server loads into DOS (`scry.asm`, built
  to `SCRY.COM`).
- What both SCRY servers share is the scry-core package, pinned by tag in `pyproject.toml`.
  [Its module list](https://github.com/scry-mcp/scry-core/blob/main/docs/modules.md) has one
  row per module.
- `demos/` holds the demos and `tools/` the development scripts below.
- `tests/` holds the unit tests, and `tests/live/` the tests that drive a real emulator.

## The checks

```sh
uv run ruff check .
uv run mypy --strict .
uv run mypy --strict --platform win32 .
uv run pytest -q
bash .githooks/pre-commit-test.sh
```

All five pass before a change is committed. What each one proves:

- `ruff` and the first `mypy` check the code, strict, over the whole repository. A new
  directory is covered without being added anywhere.
- The second `mypy` reads the code as Windows sees it. A call Windows lacks fails on any
  computer until it is guarded by `sys.platform`.
- `pytest` runs the unit tests and checks the coverage floor in `pyproject.toml`. None of them
  starts an emulator; the checks of `tools/bench.py` itself are among them.
- The last line runs the commit hook's own cases.

The tests run with a home and a temporary folder of their own, and fail a run that leaves a
file in that home (scry-core's `private_run`). Every file the server writes follows scry-core's
[rule of file names](https://github.com/scry-mcp/scry-core/blob/main/docs/file-names.md).
`tests/conftest.py` fails a case whose files break it, except the names the debugger itself
picks (`MCPDUMP.BIN` and the like), which it lists.

On Windows the fourth command is `uv run pytest -q --no-cov`. The coverage floor is checked on
macOS only, because Windows skips the cases that need what it lacks (a FIFO, a mode bit, a
symlink).

`.github/workflows/ci.yml` runs the same checks on GitHub's Linux runners when started by hand,
with `--no-cov` and with `jscpd` installed for the hook. Without `nasm` the cases that build
the DOS test programs skip, and without `ffmpeg` the media ones; the workflow installs both.

The committed DOS test programs are built by the nasm major that
`tests/test_dosbox_x_guest.py` names. Their byte-identity cases skip under the older one Ubuntu
ships, and run on macOS and Windows.

### Running part of the tests

Every `pytest` run checks the coverage floor, which belongs to the whole repository, so a
partial run fails on it. Two traps follow from how `addopts` is written:

- `addopts` ends in a bare `--cov`, which takes the next argument as its source. So
  `uv run pytest tests/test_x.py` runs every test while looking like a one-file run.
- Narrow a run with `-o addopts=""` and the test files, or with `-k <module name> --no-cov`.
  Read it as a run that checked no floor.
- `-o addopts=` also drops the `not live` and `not window` deselections. Name test files with
  it, never a directory: `tests` would start a real emulator.

### Over ssh on Windows

The server starts DOSBox-X with no window (`-set "sdl videodriver=dummy"`), so it can be driven
over an ssh session on Windows. A venv made with a minor version has its `home` on a junction
that an elevated or ssh session cannot go through (`uv trampoline failed to spawn Python child
process`). Make it with the exact patch version, `uv venv -p <patch>`.

### A scry-core checkout

`uv run` syncs the environment before its command. So the next plain `uv run` replaces an
editable install of a scry-core checkout (`uv pip install -e ../scry-core`) with the pinned
package. The run then checks the pinned package while looking like a run on the checkout.

- Print `scry_core.__file__` from the project's Python before and after a run.
- Use `uv run --no-sync` (or `UV_NO_SYNC=1`) while the editable install is wanted, and
  reinstall it after a full run of the checks.
- Export `PYTHONPATH=<checkout>/src` for a run that must keep the checkout while another
  command syncs the environment.

## Changing a tool

A tool's reply model is its contract:

- A number whose natural notation is hex (an address, an offset, an interrupt, a port) is
  answered as `0x` text, and taken as `0x` text or an integer.
- A field every `ok` reply carries is `Required[...]` in the model.
- A field that comes only sometimes is `Annotated[T, When("words")]`, and the tool's `Reply:`
  sentence says those words beside it.
- A value that could not be read is `unavailable(why)`, never absent.

The tests refuse an `ok` reply that lacks a required field.
`tests/test_dosbox_x_reply_models.py` refuses a promised field whose condition the sentence does
not say.

A change to a tool's arguments, reply model or description changes its reference page.
`tests/test_dosbox_x_reference_pages.py` then fails, naming the tool, the page and the line.
Rewrite the pages from the code:

```sh
uv run python -m scry_core.reference scry_dosbox_x.server:REFERENCE --write
```

The examples on those pages come only from the transcript of a run against the real emulator.
Each `--mark` spells one of that computer's directories the way the committed examples do:

```sh
uv run python -m scry_core.reference scry_dosbox_x.server:REFERENCE --write \
    --examples <transcript.jsonl ...> --mark '/tmp/<the run>=$TMPDIR'
```

- A run that passes deletes its temporary folder, transcript included. Hard-link
  `transcript.jsonl` while it runs, and only one newer than the run's start.
- Mark the temporary root as well as the run's directory, with
  `--mark '<TMPDIR without its trailing slash>=$TMPDIR'`. The server's own temporary folder
  sits directly under `$TMPDIR`.
- Before the commit, search `docs/reference` for `/Users/`, `/var/folders` and `/private/var`.

### A tool that moves to another page

The reference generator rewrites only the blocks between its markers. The hand-written
paragraphs after a block belong to that tool by position, so a tool moved to another page
leaves them behind.

1. Take the text between the tool's end marker and the next begin marker, at `HEAD`.
2. Remove it from the old page and put it after the same tool's end marker on the new page.
3. Run `tests/test_dosbox_x_reference_pages.py` again.

The paragraphs of `REFERENCE.md` that name the group, and the demos' tables of tools, need the
same pass. The group of each tool both servers have is `roster.SHARED_FAMILIES` in scry-core.

## The commit hook

The commit runs scry-core's pre-commit check; `python -m scry_core.hook --help` says what it
looks at. Turn it on once per clone:

```sh
git config core.hooksPath .githooks
```

One of its checks is the share of comments and docstrings in each file's bytes. A change that
only deletes code raises that share and can fail with no comment touched. Cut a clause in the
file it names; never raise the limit.

## Tests against a real emulator

A plain `pytest` starts no emulator. The tests under `tests/live/` do:

```sh
uv run pytest -o addopts="" -m live tests/live
uv run python tests/live/run_live_pytest.py
```

The first runs them one after another. The second runs each test that opens no window as a
process of its own, several at once, and then the ones that open a window one at a time.

They run on a DOS program this repository owns, `tests/guest/probe.com`: a few bytes of
assembler that write one log line every three seconds and never exit. Half the cases are about
a program that is still running, and the other half read what a program logged.

The cases in protected mode run on a second program the repository owns, `tests/guest/dpmi.c`.
It is a DJGPP program, committed built as `dpmi.exe` with its `nm` table `dpmi.sym`, and runs
under CWSDPMI, which its own loader brings in.

### On your own program

Point the tests at your conf, and name two words your program logs: one it writes early, and one
it writes later. One case waits for something that has not happened yet, and refuses to run if
it already has.

```sh
DOSBOX_X_LIVE_CONF=/path/to/your.conf \
DOSBOX_X_LIVE_CWD=/path/to/its/dir \
DOSBOX_X_LIVE_PROGRAM=YOURAPP.EXE \
DOSBOX_X_LIVE_MARK=BOOT \
DOSBOX_X_LIVE_LATE=READY \
    uv run pytest -o addopts="" -m live tests/live
```

- Your conf needs `bochs debug port e9 = true`. Without it the port does nothing, and that
  reads as a broken session, not as a missing line; nothing checks it for you.
- `DOSBOX_X_LIVE_PROGRAM` must be at the start of a line of your `[autoexec]`, and that section
  must also have a bare `exit` line. Two cases build a variant conf by deleting those two lines.
- `DOSBOX_X_LIVE_MARK` is something your program logs early, within its first few lines.
- `DOSBOX_X_LIVE_LATE` is something it has not logged yet when the waiting case asks. A word
  that is already there makes that case INVALID, which is the correct refusal and not a pass.

### What the demos' cases need

Each demo has a case that runs it, and skips without the program it needs:

| Demo | Variable | What it names |
|---|---|---|
| Deluxe Paint (both) | `DELUXE_PAINT_DIR` | the directory holding version 1.0's `DP.EXE` |
| LineUp | `LINEUP_MSDOS_DIR` | a copy of the game's DOS version with its symbol map |
| Monkey Island | `MONKEY_ISLAND_CD` | the directory holding `monkey.cue` and its BINs |
| Speed Fight | `SPEEDF_MSDOS_DIR` | a copy of the game with `EXES/SPEEDF.EXE` and `EXES/SPEEDF.MAP` |
| ReChip! | `RECHIP_DIR` | a checkout of it after `make mcp-conf` |

Two habits keep a demo or a case the same on every computer:

- One that needs the stop where an input lands takes the stop the input itself ends at, never
  a breakpoint the click will hit. [`send_keys`' page](docs/reference/input.md) says why.
- One that records sound fixes the emulator's speed at a value the computer keeps with room to
  spare. An occasional `readback_refused` is the conf's speed first;
  [`audio_record`'s page](docs/reference/captures.md) says why.

### The live test script

`tests/live/dosbox_x_live_matrix.py` is run as a script. It tries every tool in every state of
the machine, at every edge of its arguments and across the calls that share state. Then it runs
on real DOS programs a project points it at.

- The cases are listed before anything starts, so what was planned and never reached shows at
  the end.
- Each case prints OK, FAIL, or BLOCKED with the reason it could not run.
- Every reply lands whole in a transcript whose path is printed first and again beside the
  verdict. A failed case keeps the conf and the end of the log of its session.
- It exits 0 with no FAIL, 1 with one, 3 when the run is invalid (no case ran, among others).

Its docstring has the command and the variables it reads. The ones most used:

| Variable | What it sets |
|---|---|
| `DOSBOX_X_LIVE_BENCH` | the folder of real DOS programs the program sections run |
| `DOSBOX_X_LIVE_SECTIONS` | the sections to run, by letter; `AA,` names a lone two-letter one |
| `DOSBOX_X_LIVE_JOBS` | how many sections run at once; unset, half the CPUs; `1`, one process |
| `DOSBOX_X_LIVE_DISPLAY` | the display section R's windows open on; unset, the main one |
| `SCRY_FOCUS_CONTROL` | `1` lets the focus section open a window in front and move a Space |

With `DOSBOX_X_LIVE_BENCH` unset, or a program missing from it, the case is skipped or BLOCKED
and names what is missing. So a fresh clone runs everything the repository's own programs cover.

Each part works on its own copies of the DOS programs, because the debugger writes its files
under fixed names into the emulator's working directory (`tests/live/live_private.py`).

A few cases depend on the computer:

- What opens a window (section G, the focus section O, the tests marked `windowed`) runs alone.
- The cases that capture a window as the computer shows it see it behind other windows too. On
  Windows they need the display on, because Windows draws no new frame of a window while it is
  off.
- The focus section's start in front and its Space move take your screen and keyboard: they run
  only with `SCRY_FOCUS_CONTROL=1`, on a machine nobody is using.
- The full-screen case runs before the window the focus verdict looks at. On macOS a window that
  fills the display is a Space of its own, which the watch would report as a Space moved.
- The cases that move a Space carry the `window` marker and are out of every default run.
  `SCRY_FOCUS_CONTROL=1 uv run pytest -o addopts="" -m 'live and window' tests/live` runs them.

### What a window opened behind promises

A start behind does not come to the front, so the keyboard stays where it was. That is all it
promises: the window is still there to be seen, and the computer carries the load of every
emulator the run starts.

So run the live test script in an account or on a machine nobody is working at, or at an hour
agreed with whoever is. Whether a run took the front is the focus section's verdict, read as
[scry-core's page on these tests](https://github.com/scry-mcp/scry-core/blob/main/docs/live-tests.md#showing-that-a-run-took-nobodys-focus)
says.

### What a run checks about the computer

A run refuses a computer that cannot start DOSBox-X, and proves it left none running
(`scry_core.live_host`):

- Before its first start it launches the emulator once in a form that ends by itself. If that
  does not return, the run is INVALID and starts nothing else.
- Every DOSBox-X a session starts is recorded where it is started. One still alive at the end
  is killed and fails the run by name.
- A run that passes removes its temporary folder. Any other keeps it and prints its path.

## Demos

`demos/<name>/demo.py` runs one demo end to end. With `--update-readme` it rewrites the demo's
page from a run where every step passed: the two generated blocks of its README,
`TRANSCRIPT.md`, `screen.png` and `loop.webp`.

- The steps a demo marks with an `ask` are the examples of its page, and of the README for
  Bricks.
- `loop.webp` shows the demo's moments. Each is cut from a `record` step of the run, or from
  the video of a session started with `capture_video`, by the frame the replies count.
- ffmpeg decodes the recordings and `img2webp` assembles the file; without either on the `PATH`
  the update is refused by name.
- The Monkey Island demo also writes what the README opens with: its clip, a caption and one
  step of the run as an exchange, all named in its `Lead`.
- A second run gives the same page. `loop.webp` alone may differ in its bytes.

A recording moves the game's clock on. So a demo that compares a sound sample for sample keeps
its recordings where its reference sound was made with them, or after the comparison.

The block of the README that adds the server to each client is scry-core's table of clients:

```sh
uv run python -m scry_core.install scry_dosbox_x --write
```

### Work from a saved state

A demo or an experiment that spends minutes starting a program is rerun from a state saved at
the point of interest. Call `state_write(method="save")` once; each later run starts the same
session and loads it.

Check first that what the run looks at survives a load. A state restores the program's memory
and not always the emulator's devices: Monkey Island's screen comes back striped, and its
pointer stops following the mouse driver. Memory reads, scans and anything the program computes
from its own memory are safe.

### Measuring the border and the arrow

The coloured border and the arrow that show a session is on are drawn after the frame goes to
capture. So `snapshot`, `screen_view` and the emulator's own recordings never show them; they
are measured from the computer's own screen.

- Size: `screencapture -x -o -l <window>`, with the window number from
  `scry_core.window_capture.window_of(pid)`. The title bar adds its own height.
- Timing: `ffmpeg -f avfoundation -capture_cursor 0 -pixel_format uyvy422 -framerate 60` on the
  screen, with `-c:v libx264 -crf 0`, cropped to the window's `kCGWindowBounds`.
- The arrow's fill is found by colour (R>200, 100<G<175, B<90) with the border masked, and a
  click's effect by a region the arrow never crosses.
- A look sent through `debug` is overwritten by the server's next delivery. A variant runs the
  server with `presence.LOOK` replaced before import.

Before trusting a result, run a control that must fail. Two looks that differ can otherwise
come out identical without anything saying so.

## Development scripts

`tools/bench.py` measures what a program costs to run. It takes `--conf` (the conf to measure)
and `--cwd` (the directory that conf runs in), with no default, and refuses without them.
`--json`, `--reps` and `--song` are optional.

The song, the log line it waits for and the make target it calls belong to the program it was
written for. A measurement of another program names its own.

`tools/mapsweep.py` reads real symbol maps where they live, against a manifest that says what
each one holds. It fails when the two disagree in either direction: a count that rose against
an unchanged file means the reader has begun to read something that is not a symbol.

```sh
uv run python tools/mapsweep.py --manifest <manifest>.json --root /where/those/maps/live
```

- It is run by hand, and `tests/gates-manual.txt` says why: the maps and their manifest are not
  in this repository. In every clone but one it would be INVALID.
- It covers the Borland, Open Watcom and `nm` formats on real maps. The GNU `ld` format is left
  out on purpose: the only such map is the fixture this repository builds.
- A failure means a count moved. It cannot say a count is correct: the first time a project's
  row is written, a person reads the map once and accepts what the reader says.

## Test fixtures

One file per toolchain is built here and committed under `tests/fixtures/`:

- a Borland TLINK 16-bit map with an overlay;
- an Open Watcom map over two sections;
- a DJGPP `nm` listing beside the GNU `ld` map of the same link.

`tests/test_dosbox_x_fixtures.py` reads them, so a fresh clone can check that the server reads
those formats.

The two Borland routines share their first fifteen characters on purpose: the fixture exercises
the name collision the reader resolves.

Each fixture has its generator, the source it was built from and a `build.sh` that makes it
again. Neither toolchain is in this repository; `build.sh` takes its location from an
environment variable and stops loudly without it.

## The description test

A tool's description, its arguments and the server's `instructions` are all a model has to call
the tool from. The description test gives a model only what a client delivers and checks the
calls it makes:

```sh
uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py \
    --tasks mcp_probe/tasks --check
uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py \
    --tasks mcp_probe/tasks --runs 3
```

- `--check` asks no model. It names a tool or an argument that has no task in
  `mcp_probe/tasks/`, and the commit hook runs it.
- `--runs` asks the `claude` CLI and checks each task over several runs.
  `python -m scry_core.probe --help` says how a failure is told from the model's noise.

A task the model keeps getting wrong is tolerated when the server refuses the wrong call and
says why: report it with its numbers. A client retries on a refusal, and more description text
spends the room the other tools need. Only a wrong call the server accepts with `status: ok`
is a defect.

## A file's time on Windows

Windows stamps a file's modification time from a clock that ticks coarser than `time.time()`.
A file created right after a clock read can carry a time a few milliseconds before it. So a
plain `mtime >= began` drops the first file of a run on Windows, and never fails on macOS.
