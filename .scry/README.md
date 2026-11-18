# `.scry/`

This repository's start profiles: how each of its test programs starts, so a session can boot one without composing `start`'s arguments by hand.

SCRY is a set of MCP servers that let an assistant run a program in an emulator and inspect it
live. This folder is what this repository keeps for it: how the program starts. Where it has
them, it also holds what its screens look like and a list of steps that drives it.

## How to start

Call the `dosbox-x` server's `start` tool with a start profile's name: `start(profile="<name>")`. An argument in the same call wins over the profile's. A profile's paths resolve against the directory holding `.scry/`, and what would be this machine's path is a [placeholder](https://github.com/scry-mcp/scry-core/blob/main/docs/store-paths.md).

## Start profiles

A start profile is a saved set of `start` arguments, so a session boots a program without composing them by hand.

- `bricks` (`start/bricks.json`): `demos/bricks/bricks.conf`, the game of the bricks demo, which breaks at its own `int 3`.
- `dpmi` (`start/dpmi.json`): `tests/guest/dpmi.conf` with `DPMI.EXE D:\DPMI.C`.
- `mines` (`start/mines.json`): `demos/mines/mines.conf`, the VBE game of the mines demo.
- `mouse` (`start/mouse.json`): `tests/guest/mouse.conf` with `MOUSE.COM`, the program the input tests run.
- `probe` (`start/probe.json`): `tests/guest/probe.conf`, the small program the tests against a real emulator run.

The screen maps this repository ships beside their demos stay there: a demo's map is part of what the demo shows.

`monkey` and `dpaint` have no start profile. Their conf is written per run from a template, and the game itself is not in this repository, so no profile could boot alone.

The test programs and the bricks demo are named through `DOSBOX_X_LIVE_GUEST_DIR` and `DOSBOX_X_LIVE_BRICKS_DIR`. A run of the tests against a real emulator copies them to a writable directory and points those variables at the copy.

The live test script exports both with this repository's own directories as their default, so a run from a clone reads the same profiles. A session that boots one outside those tests exports them too.

---

This page is rendered by the servers' `promote` from `about.json` and the files beside it; edit
those, never this page. To render it by hand, run `uv run python -m scry_core.scry_readme
<this repository>` from a scry-core checkout.
