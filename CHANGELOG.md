# Changelog

What a client of the server notices.

## Unreleased

It needs the scry-core that serves `scry_core.window`, not an older one: the tag pinned in
`pyproject.toml` is the floor.

- The `session` block carries `program` once the program the guest was running is gone: `exited`, or `fault` with
  the message DJGPP left on the text screen quoted from there (it never reaches the E9 log). It is read at the
  stops that answer a call, from DOS's current process. A wait that expired opens its `note` with that, or with
  the fact that the guest wrote no line in the wait, instead of leaving the cause among a list of guesses.
- `send_mouse` steers a protected-mode program's own pointer from the real-mode stop its retrace ends on: a build
  whose debugger has the new `MEMDUMPLIN` (a read by linear address, through the page tables of CR3 with paging on or
  off) places the map's pointer symbols as the table's base plus their offset, when the table was loaded at a
  protected-mode stop from a register or with a `base`. `start`'s `debugger_commands` lists it. Without it, or with
  a table measured from the program's load segment, the call is refused as before.
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
