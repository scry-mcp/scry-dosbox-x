# The Lists tools

<!-- scry-reference:begin perform -->
## `perform`

*Run a sequence of steps*

```text
perform(steps=null, path="", settle_seconds=30.0, summaries=false, until_frame=0)
```

A sequence of this server's operations in one call, in order on the open session,
stopping at the first failure; `drive` is this plus a wait for a line of the E9 log.

`steps`: `{"op": <tool>, ...arguments}`, any tool but `build_check`, `start`, `close`,
`perform`, `drive`, `perform_export`. `path`: a `perform` document (absolute or `~`-led:
`.scry/perform/<name>.json`, or a file `perform_export` wrote) whose steps are replayed; give
`steps` or `path`, never both.
A `send_keys` or `send_mouse` whose `expect`
misses ends the list `TIMEOUT`. A step's `recorded` must hold, else INVALID `diverged`.
The whole list is checked first: INVALID `errors` (`step`, `op`, `code`, `message`),
nothing run. `settle_seconds` bounds each wait for a stop before a step that needs one (0:
never wait). `until_frame=F` needs `summaries=True` (a window is hundreds of steps) and a `run_for` step, and repeats the list until a stop reads frame F, within 5000 steps and 600 s; `no_channel` if there is no frame counter. Frames count since power-on. A `screen_view` step inlines its
text; its picture is written to its `path` and answers `not_inlined: nested`.

Reply: `ran`, `steps_completed`, `held`, `failed_at`, `failed` (INVALID `step_failed`),
`verdict` (once the list waited; `TARGET` adds `stopped`, `TIMEOUT` `note`), else
`still_running`; `frame_reached` (with `until_frame`).

Reference: REFERENCE.md, Sequences in one call.

| argument | type | default |
|---|---|---|
| `steps` | array of object or null | `null` |
| `path` | string | `""` |
| `settle_seconds` | number (>= 0, <= 600.0) | `30.0` |
| `summaries` | boolean | `false` |
| `until_frame` | integer | `0` |

- `summaries`: True (of the call, never of a step) makes each step but the last a compact row; `ran` shows the first 24 (`truncated`), `ran_path` and `replies_path` hold all; `stops` counts the stops.

| reply field | type |
|---|---|
| `errors` | array |
| `failed` | object |
| `field` | string |
| `got` | any |
| `ran_path` | string or object |
| `recorded` | any |
| `replies_path` | string or object |
| `steps_total` | integer |
| `still_running` | boolean |
| `stopped` | object |
| `stops` | object |
| `truncated` | boolean |
| `verdict` | string |
| `failed_at` | integer or object |
| `held` | integer |
| `ran` | array |
| `steps_completed` | integer |
| `frame_reached` | integer or object |
| `operations` | array |
| `until_frame` | integer |

Example, from a live run:

```json
{
  "steps": [
    {"op": "status"}
  ]
}
```

```json
{
  "summary": "perform: 1 of 1 step",
  "status": "ok",
  "ran": [
    {
      "op": "status",
      "reply": {
        "summary": "status: alive, stopped",
        "status": "ok",
        "pid": "<volatile>",
        "conf": "/private/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-job-<run>/A/tests/guest/probe.conf",
        "conf_digest": "78bdc38f360b9b4a",
        "bound_s": 1200,
        "elapsed_s": 5.0,
        "captures": "off",
        "state_dir": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1010-save",
        "last_stop": {
          "stop_seq": 11,
          "pc": "0814:00000130",
          "cause": "the retrace run_for ran to, at 0814:00000130",
          "since_s": 0.2,
          "wall_at": "<volatile>"
        },
        "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false},
        "cpu_mode": "real",
        "pc": "0814:00000130",
        "declarations": {"breakpoints": 0, "watches": 0, "regpoints": 0},
        "presence": {"available": false, "why": "a session started without `shared` has no window to draw on"},
        "session": {"alive": true, "running": false, "altered": true}
      }
    }
  ],
  "steps_completed": 1,
  "failed_at": {"available": false, "why": "no step failed"},
  "held": 0
}
```
<!-- scry-reference:end perform -->

**A `resume` inside a sequence is followed by asking `RUNSTATE`**, so whether it stopped again is the debugger's answer. Its `output` (`detail=True`) is what the debugger printed for `RUN`, capped at 2000 characters; the guest's own lines are the log's (`log` reads the log).

**`until_frame=F` is a window, not a count.** The list repeats until a step's stop reads frame F or later, counted since power-on, and ends right after that step, even mid-list; so it needs a `run_for` step and `summaries`. A frame the stopped machine already stands at or past is refused before anything runs; on a running machine the first stop starts the window, and one already past F is refused as nothing walked. A stop with no `frame` ends the list (`unexpected_answer`), since nothing then says whether the window is over; the bounds are its steps and its seconds, and reaching neither F nor an error is a `TIMEOUT` naming the last frame read. An export keeps the steps the window ran, never the `until_frame`, because each lap's stop is held to its own `recorded`.

**`summaries=True`** exists for size, and `stops` is the server's own count because one assembled by hand from summary lines comes out wrong.

After a `resume`, only the ops `answers_while_running` lists go on at once, and before any other the list waits up to `settle_seconds` for a stop. `start(plan=...)` also runs a list. A `step` that comes back running ends the console-driven part like a `resume`, and a `stop` ends the run. A `resume` inside a sequence drains what the console steps before it left in the terminal, so their prompt does not read as the resume's halt. `settle_seconds` 0 never waits. What only a step can judge (a symbol against the table loaded by then, a file an earlier step writes, the machine's mode) refuses at that step; the list check covers ops, argument names and values through each tool's own checks. A wait whose channel failed ends the list with its code (`session_broken` when the emulator is gone). `ran` carries each step's `op` and full `reply`; `held` counts the steps that held their `recorded`; `not_stopped` is the answer before a console step when nothing waited. Refused steps in `errors` each carry `step`, `op`, `code` and `message`.

<!-- scry-reference:begin perform_export -->
## `perform_export`

*Export the session as a replay*

```text
perform_export(dest, overwrite=false)
```

Write the session's calls since `start` to `dest` as a `perform` document.

Kept: moving calls and checks (`read_memory`, `registers`, `screen_signature`,
`screen_map_find`, `guest_file`, `image_compare(method="golden")`), each held to its
`recorded` reply. Other calls drop; the first no replay can place, or past 5000, cuts
the rest.

`dest` (`.json`) is refused if present unless `overwrite`. Reply: `path`, `steps`,
`checks`, `dropped`, `dropped_total`, `cut`, `replay`, and `kept` when the document is kept
for `promote`; `no_recording` if empty.

Reference: REFERENCE.md, From an investigation to a bench.

| argument | type | default |
|---|---|---|
| `dest` | string | required |
| `overwrite` | boolean | `false` |

| reply field | type |
|---|---|
| `checks` | integer |
| `cut` | object |
| `dropped` | array |
| `dropped_total` | integer |
| `path` | string |
| `replay` | string |
| `steps` | integer |
| `kept` | string |

Example, from a live run:

```json
{
  "dest": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1869.json"
}
```

```json
{
  "summary": "perform_export: 1 step, 0 checks, 0 dropped, cut at call 2 to /var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1869.json",
  "status": "ok",
  "path": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1869.json",
  "steps": 1,
  "checks": 0,
  "dropped": [],
  "dropped_total": 0,
  "cut": {
    "call": 2,
    "op": "resume",
    "why": "its run was stopped by the wall clock or by the machine itself, at a place inside its frame that no replayed advance reaches; it stopped inside frame 0, the one it began in"
  },
  "replay": "uv run python -m scry_core.replay /var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1869.json"
}
```
<!-- scry-reference:end perform_export -->

A release, a `stop` that ran the guest and came back stopped, or a wall-clock bound that ended a run (a `screen_wait` that timed out among them), ends the document because the run ends where no replay reaches; on a build that counts frames its `why` says how many frames the run took, and that `run_for` with that count replays it up to the start of the frame it stopped in. A `screen_wait` that found its text is the `run_for` of as many frames as it polled, a step a replay reaches; one that moved nothing is dropped. A `send_keys` or `send_mouse` to a stopped machine is a step: it runs by retraces to a stop a replay reaches, and holds to its registers and frame. Also cut: a call with no reply, a refusal after the guest moved, a guest found elsewhere than the call before left it, a step that wrote a file the session named. Dropped: a refused call, any other read, a call that changes nothing in the emulated machine. The replay is `uv run python -m scry_core.replay <dest>`, from this server's repository, and exits 0 when every step held. `dropped` shows the last 40 rows (`call`, `op`, `why`); `cut` is unavailable when nothing was cut; `no_recording` also covers a cancelled `start`. Dropped and cut calls are each named with a `why`.

<!-- scry-reference:begin drive -->
## `drive`

*Drive an input and verify it*

```text
drive(act, expect="", seconds=null, pattern=".", limit=40, settle_seconds=30.0, summaries=false)
```

A sequence that also waits for a line of the E9 log; with no line to wait for, `perform`
is the call. Marks the E9 log, runs `act` (steps in `perform`'s
vocabulary), then with `expect` waits up to `seconds` (default 5, at most
600) for a new matching line. Needs a `logfile`.

`pattern` and `limit` only filter the lines shown; `settle_seconds` is the call's, as in
`perform`. Refused: `seconds` without `expect`.

Reply: `act` (`ran`, `steps_completed`, `failed_at`), `verify` (`verdict` `TARGET` or
`TIMEOUT`, `seen`, `line`; `checked: false`), `looked.guest` (`lines`, `truncated`).
INVALID with the same fields on `step_failed`, `wait_stopped`, or the act's own refusal.
No screen: use `capture_frame`.

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `act` | array of object | required |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |
| `pattern` | string | `"."` |
| `limit` | integer (>= 1, <= 400) | `40` |
| `settle_seconds` | number (>= 0, <= 600.0) | `30.0` |
| `summaries` | boolean | `false` |

- `summaries`: True (of the call, never of a step) makes each step but the last a compact row; `ran` shows the first 24 (`truncated`), `ran_path` and `replies_path` hold all; `stops` counts the stops.

| reply field | type |
|---|---|
| `act` | object |
| `looked` | object |
| `operations` | array |
| `verify` | object |

Example, from a live run:

```json
{
  "act": [
    {"op": "status"}
  ]
}
```

```json
{
  "summary": "drive: no expectation",
  "status": "ok",
  "act": {
    "ran": [
      {
        "op": "status",
        "reply": {
          "summary": "status: alive, stopped",
          "status": "ok",
          "pid": "<volatile>",
          "conf": "/private/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-job-<run>/A/tests/guest/probe.conf",
          "conf_digest": "78bdc38f360b9b4a",
          "bound_s": 1200,
          "elapsed_s": 5.0,
          "captures": "off",
          "state_dir": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/jobs-scratch/A/n1010-save",
          "last_stop": {
            "stop_seq": 11,
            "pc": "0814:00000130",
            "cause": "the retrace run_for ran to, at 0814:00000130",
            "since_s": 0.2,
            "wall_at": "<volatile>"
          },
          "pending": {"arm": [], "disarm": 0, "symbols_load": false, "base_remeasure": false},
          "cpu_mode": "real",
          "pc": "0814:00000130",
          "declarations": {"breakpoints": 0, "watches": 0, "regpoints": 0},
          "presence": {"available": false, "why": "a session started without `shared` has no window to draw on"},
          "session": {"alive": true, "running": false, "altered": true}
        }
      }
    ],
    "steps_completed": 1,
    "failed_at": {"available": false, "why": "no step failed"},
    "held": 0
  },
  "verify": {
    "checked": false,
    "why": "no `expect` given; the act's own steps carried whatever verification they asked for"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": 60541,
      "lines_written": 0,
      "lines_total": 0,
      "truncated": false,
      "lines": [],
      "pattern": "."
    }
  }
}
```
<!-- scry-reference:end drive -->

The log is marked once, before anything moves, because that one mark keeps both halves honest: a verification reading from the top would find the cue that fired ten seconds ago. A screen is not part of the look: a still needs a recording and `ffmpeg`, and `capture_frame` offers it on its own.

A stopped guest cannot write, so an act that ended stopped has the log read once, not waited on. `checked` is whether a check ran at all and `seen` whether the line arrived; neither is `verified`, which everywhere else means a readback equal to what was sent. `verify` also carries `waited_s`, `seen_before_waiting`, `lines_before`, `lines_total`, and on a `TIMEOUT` `arrived_during` and `note`; `why` explains `checked: false`, and `available: false` means the act timed out. `looked.guest` also carries `lines_written`, `lines_total`, `since_mark`, `pattern`. The act's own INVALID codes (`not_stopped`, `session_broken`, `diverged`) pass through.
