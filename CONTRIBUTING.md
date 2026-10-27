# Contributing to scry-dosbox-x

This is the guide for changing the server. What the tools promise is in `REFERENCE.md`; this
file says where the code lives, how to run the battery and the live tiers, and what proves a
change.

## Where the code lives

`dosbox_x_server.py` holds the tools and `dosbox_mcp.py` the MCP boundary (the server object, its
`instructions`, the roster of tools by family). Each `dosbox_*.py` holds one concern, and its
docstring opens with what it holds and why: read that before changing it. What both Scry servers
share (the reply contract, the reference generator, the demo runner, the probe, the live bench)
is the scry-core package, pinned by tag in `pyproject.toml`. `guest/` holds the resident input stub the server loads into the guest (`scry.asm`, built to `SCRY.COM`), `demos/` the demo game, and `bench.py` and `mapsweep.py` are the development scripts below. `tests/` holds the
contract tests and `tests/live/` the tiers that drive a real emulator.

## The battery

```sh
uv run ruff check .
uv run mypy --strict .
uv run mypy --strict --platform win32 .
uv run pytest -q
bash .githooks/pre-commit.test.sh   # the hook's own cases
```

Ruff and mypy (strict, over the whole tree) judge the code, the second mypy as Windows sees it, so
a call Windows lacks goes red on any host until it is guarded by `sys.platform`; pytest runs the
contract tests and, through `--cov`, the coverage floor in `pyproject.toml`; the last line runs the
pre-commit hook's own cases. All five green is what a change needs before it is committed.

On Windows the battery is the same, with `uv run pytest -q --no-cov`: the floor is judged on macOS
only, because Windows skips by design the cases that need what it lacks (a FIFO, a mode bit, a
symlink), and the floor counts the whole tree.

A change to a tool's arguments, reply model or description changes its reference page, and
`tests/test_dosbox_x_reference_pages.py` goes red naming the tool, the page and the line. Regenerate the pages from the
code, and the examples only from a live run's transcript (each `--mark` spells a directory of
the run's host, as the committed examples do):

```sh
uv run python -m scry_core.reference dosbox_x_server:REFERENCE --write
uv run python -m scry_core.reference dosbox_x_server:REFERENCE --write \
    --examples <transcript.jsonl ...> --mark '/tmp/<the run>=$TMPDIR'
```

The commit itself runs scry-core's pre-commit (`python -m scry_core.hook --help` says what it checks): enable it once per clone with

```sh
git config core.hooksPath .githooks
```

These are contract tests and none of them launches an emulator: they hold the part that has to
be true before one is involved. `bench.py`'s own guards are among them, because an instrument
that can lie needs validation and validation nothing executes is a comment.

Every pytest run judges the coverage floor: `--cov` is in `addopts` and the floor is
`fail_under` in `pyproject.toml`. A partial run goes red on that floor by construction, because
the floor is the whole repository's, so for a single file add `--no-cov` and read it as a run
that judged no floor. The live tier is deselected by default (`-m 'not live'`).

The ruff and mypy configuration in `pyproject.toml` is scry-core's bar; mypy runs strict with no
path list, so a new directory is covered without being added anywhere.

## The live tier

A second tier under `tests/live/` drives a real emulator.

```sh
uv run pytest tests/live -m live
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
    uv run pytest tests/live -m live
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

`WINDOW_APP` names the placement helper the cases that open a watched window ask, as `start`
does; its runs go to the display `WINDOW_SHARED_DISPLAY` names, the secondary when unset, so they
stay off the one somebody works on. Without it those cases skip: where a window goes is not this
package's decision.

**The matrix.** Around those cases sits `tests/live/dosbox_x_live_matrix.py`, run as a script
rather than collected: every tool in every machine state, at every argument edge, across the
calls that share state, then on real DOS programs a project points it at. Its cells are declared
before anything boots, so what was planned and never reached shows at the end. Each cell prints
OK, FAIL, or BLOCKED with the reason it could not run; every reply lands whole in a transcript
whose path it prints first and again beside the verdict, and a failed cell keeps the conf and the
log tail of the session live at the time. It exits 0 with no FAIL, 1 with one, 3 when the run is
invalid (no cell ran among them). Its docstring holds the command and the variables it reads.

**Parts run side by side.** The matrix runs each section letter, and
`tests/live/run_live_pytest.py` each live test, as a process of its own, as many at once as
`DOSBOX_X_LIVE_JOBS` says (unset, half the host's CPUs; `1`, one after another in one process),
merged from the summaries they declare through `scry_core.live_pool`.

```sh
uv run python tests/live/run_live_pytest.py
```

What opens a window (section G, the focus gate's O, the `windowed` tests) runs alone. Each part
works on copies of its own of the guests and the bench, because the debugger writes its files
under fixed names into the emulator's working directory (`tests/live/live_private.py`).

## The bench the live tier reads

The protected-mode cases need no other project: they run on a second guest the package owns,
`tests/guest/dpmi.c`, a DJGPP program built into the committed `dpmi.exe` and its `nm` table
`dpmi.sym`, under the DPMI host DOSBox-X provides, CWSDPMI, which the program's stub loads
resident.

The real-mode cases and the matrix's program sections run `dos-real16` and `dos-real16-alt` from
a bench: copies of each program, its map, the data it opens and its project's own run conf,
pinned by hash in the bench's own `bench.json`, with an `identity.json` beside it that says which
files, launch line, memory-block name and E9 line each program's label stands for (its keys:
`IDENTITY_KEYS` in `tests/live/bench_programs.py`). Neither file is tracked, because both name
the programs; the tracked live code names only the labels. The bench is the directory
`DOSBOX_X_LIVE_BENCH` names, else `.local/share/scry-bench/dosbox-x` under your home directory.

```sh
uv run python -m scry_core.live_bench fill --bench <bench> --from <source_repo>=<checkout>
uv run python -m scry_core.live_bench check --bench <bench>
```

`fill` copies the files from their checkouts and `check` says whether they still match. The
session conf is derived from the pinned run conf at run time. A case whose identity is
incomplete or whose copies are absent or wrong is skipped, or its cells BLOCKED, naming what is
wrong.

## What a live run guards

Both tiers refuse a host that cannot start DOSBox-X, and prove they left none running. Before its
first start a run launches the emulator once in a form that ends by itself; one that does not
return is INVALID naming the host, and nothing else is launched. Every DOSBox-X a session starts
is recorded where it is spawned, and at the end of the run one still alive is killed and FAILS
the run by name. A green run removes its scratch, its jobs' with it; a red, INVALID or broken one
keeps it and prints its path (`scry_core.live_host`).

## Development scripts

`bench.py` measures a program's cost. It takes `--conf` (the config file to measure) and `--cwd`
(the directory that config runs in) as required flags, with no default, and refuses without them,
naming the flags. `--json`, `--reps` and `--song` are optional. The song, the boot marker it
waits for and the make target of its batch cost belong to the program it was written for, so a
bench of another program names its own.

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

`mapsweep.py` reads REAL maps where they live, against a manifest that says what each one holds,
and goes red when the two part company in either direction: a count that ROSE against an
unchanged file means the reader has begun reading something that is not a symbol.

```sh
uv run python mapsweep.py --manifest <bench>/real-maps.json --root /where/those/maps/live
```

It is manual and declared as such in `tests/gates-manual.txt`, with the reason: the material is
not in this repository and is not versioned here, nor is the manifest, which names it and so
lives in the bench beside `bench.json`. On the commit path the sweep would be INVALID in every
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

`python -m scry_core.probe --help` says how a failure is told from the model's noise.
