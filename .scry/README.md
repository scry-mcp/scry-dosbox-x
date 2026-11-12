# `.scry/`

This repository's run recipes: what it declares about how its guests run, so a session can boot one without composing `start`'s arguments by hand.

SCRY is a set of MCP servers that let an assistant run a program in an emulator and inspect it
live. This folder is what this repository declares for it: how the program starts and, where it
has them, what its screens look like and a session that drives it.

## How to start

Call the `dosbox-x` server's `start` tool with a recipe's name: `start(profile="<name>")`. An argument in the same call wins over the recipe's. A recipe's paths resolve against the directory holding `.scry/`, and what would be this machine's path is a [placeholder](https://github.com/scry-mcp/scry-core/blob/main/docs/store-paths.md).

## Recipes

A recipe is the arguments of `start`, so a session boots a program without composing them by hand.

- `bricks` (`start/bricks.json`): `demos/bricks/bricks.conf`, the int 3 guest of the bricks demo.
- `dpmi` (`start/dpmi.json`): `tests/guest/dpmi.conf` with `DPMI.EXE D:\DPMI.C`.
- `mines` (`start/mines.json`): `demos/mines/mines.conf`, the VBE guest of the mines demo.
- `mouse` (`start/mouse.json`): `tests/guest/mouse.conf` with `MOUSE.COM`, the input guest.
- `probe` (`start/probe.json`): `tests/guest/probe.conf`, the small guest the live tier owns.

The maps this repository ships beside their demos stay there: a demo's map is part of what the demo shows.

`monkey` and `dpaint` have no recipe: their conf is written per run from a template whose values are the game's own directory, a disc image or the run's C: drive, and the game itself is not in this repository. A recipe that cannot boot alone is not a recipe.

The guests and the bricks demo are named through `DOSBOX_X_LIVE_GUEST_DIR` and `DOSBOX_X_LIVE_BRICKS_DIR` because a live run copies them to a writable directory and points those variables at the copy. The matrix exports them with this repository's own directories as their default, so a run from a clone reads the same recipes. A session booting a recipe outside the harness exports them too.

---

This page is rendered by the servers' `promote` from `about.json` and the files beside it; edit
those, never this page. To render it by hand, run `uv run python -m scry_core.scry_readme
<this repository>` from a scry-core checkout.
