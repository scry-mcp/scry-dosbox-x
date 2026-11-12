---
paths:
  - "demos/**"
---

# The demos are deterministic

A published demo runs on hosts of very different speed and load, so no step depends on either.
A step that needs the program to have reached a place gets there by a control, the first of
these the program offers:

1. a symbol (`run_to`), a breakpoint or a watch on a variable;
2. what the program writes about itself (`log_wait`, or an input's `expect` on its log line);
3. `screen_wait` judged only at a declared stop (`on_breakpoint`, `on_watch`, with a
   `condition` to filter the firings);
4. `screen_wait` sampling retraces (or `run_to` an unanchored screen, which samples too), only
   when the program has no symbols, no log and no place that runs once per change (a polling
   loop), or when a judgement at the place would cost a stop each across a long wait the program
   paces by something else (a CD track that plays only while the machine runs), and the demo says
   why where it does it.

A fixed `run_for` shows time passing on a program locked to the retrace, or is an input's own
duration; it never arrives. A value a demo waits for (a colour at its top, a player in a column)
is a watch or a `condition`, never a duration that happens to be long enough on this host.

- **The program's conf is not the demo's clock.** A conf that keeps the dynamic core passes over
  code breakpoints, and one at `cycles=max` hands the guest as many cycles as the host has. A demo
  that arms a code breakpoint or waits on the screen runs on the normal core and a fixed `cycles`,
  set by its own conf or by flags its `start` passes (`-set cpu core=normal`); one that only
  waits on the program's log needs neither.
- **What the host decides is declared volatile, each key with its true reason**: the window, the
  instruction a retrace stop lands on (the cycles drift by a few between hosts), a derived conf's
  digest that carries the host's paths, a key's clock stamp on a running program. A value the demo
  checks or shows is never hidden.
- **A picture is the same picture when its pixels are**: each host's zlib writes other bytes, so
  the committed `screen.png` is judged by its pixels and a transcript hides a picture's `bytes` and
  `sha256`. A recording that differs by platform has its own reference under the same name
  (`win32/music.wav`), its path declared a host argument so the transcript reads the same.
- **A changed demo is proved twice on each host it runs on**: the same normalised transcript both
  runs, the same pixels, and across hosts only what is declared. A second run that differs means
  the demo is not deterministic yet, never a flake to rerun.
