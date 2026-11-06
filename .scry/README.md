# `.scry/`: this repository's run recipes

What this repository declares about how its guests run, so a session can boot one without
composing `start`'s arguments by hand. The server reads it; nothing here is written by a tool.

    .scry/
      README.md             this page
      start/<name>.json     a run recipe: `start`'s arguments, in the `scry-start/1` format

`maps/` and `perform/` hold a screen map and a `perform` document when this repository has one.
The maps this repository ships beside their demos stay there: a demo's map is part of what the
demo shows.

## The recipes

| name | boots |
| --- | --- |
| `probe` | `tests/guest/probe.conf`, the small guest the live tier owns |
| `mouse` | `tests/guest/mouse.conf` with `MOUSE.COM`, the input guest |
| `dpmi` | `tests/guest/dpmi.conf` with `DPMI.EXE D:\DPMI.C` |
| `bricks` | `demos/bricks/bricks.conf`, the int 3 guest of the bricks demo |
| `mines` | `demos/mines/mines.conf`, the VBE guest of the mines demo |

`lineup`, `monkey` and `dpaint` have no recipe: their conf is written per run from a template
whose values are the game's own directory, a disc image or the run's C: drive, and the game
itself is not in this repository. A recipe that cannot boot alone is not a recipe.

## How a path is written

Every recipe resolves against one base, the directory holding `.scry/`, so a relative path is
relative to this repository. What a tracked file must not carry, a host path, is written as a
placeholder:

- `${root}`: this repository.
- `${home}`: the user's home.
- `${state}`: the session's scratch directory.
- `${env:NAME}`: an environment variable, refused by name when it is unset.

The guests and the bricks demo are named through `DOSBOX_X_LIVE_GUEST_DIR` and
`DOSBOX_X_LIVE_BRICKS_DIR` because a live run copies them to a writable directory and points
those variables at the copy. The matrix exports them with this repository's own directories as
their default, so a run from a clone reads the same recipes. A session booting a recipe outside
the harness exports them too.

## The caller wins

A recipe fills only what the call does not give, so `start(profile="mouse", shared=True)` keeps
`shared` from the call and takes the rest from `mouse.json`. The reply's `profile` block names
the file and every key it supplied.

## What stays out

A recipe declares how a program starts: paths, arguments, how long a session lives. What the
program's trace means (which stop serves a case, how a key is spelled, what a screen delta
proves) stays in this repository's rules and its tests, because only this repository holds the
gate that keeps it true.
