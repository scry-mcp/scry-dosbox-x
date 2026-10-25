# The Lists tools

<!-- scry-reference:begin perform -->
## `perform`

*Run a sequence of steps*

```text
perform(steps, settle_seconds=30.0, summaries=false)
```

Run this server's operations in order on the open session, stopping at the first
failure.

`steps`: `{"op": <tool>, ...arguments}`, any tool but `build_check`, `start`, `close`,
`perform`, `drive`, `perform_export`. A `send_keys` or `send_mouse` whose `expect`
misses ends the list `TIMEOUT`. A step's `recorded` must hold, else INVALID `diverged`.
The whole list is checked first: INVALID `errors` (`step`, `op`, `code`, `message`),
nothing run. `settle_seconds` bounds each wait for a stop before a step that needs one (0:
never wait).

Reply: `ran`, `steps_completed`, `held`, `failed_at`, `failed` (INVALID `step_failed`),
`verdict` (`TARGET` adds `stopped`, `TIMEOUT` `note`), else `still_running`.

Reference: REFERENCE.md, Sequences in one call.

| argument | type | default |
|---|---|---|
| `steps` | array of object | required |
| `settle_seconds` | number (>= 0, <= 600.0) | `30.0` |
| `summaries` | boolean | `false` |

- `summaries`: True (of the call, never of a step) makes each step but the last a compact row; `ran` shows the first 24 (`truncated`), `ran_path` and `replies_path` hold all; `stops` counts the stops.

| reply field | type |
|---|---|
| `errors` | array |
| `failed` | object |
| `failed_at` | integer or object |
| `field` | string |
| `got` | any |
| `held` | integer |
| `note` | string |
| `ran` | array |
| `ran_path` | string or object |
| `recorded` | any |
| `replies_path` | string or object |
| `steps_completed` | integer |
| `steps_total` | integer |
| `still_running` | boolean |
| `stopped` | object |
| `stops` | object |
| `truncated` | boolean |
| `verdict` | string |
| `operations` | array |

Example, from a live run:

```json
{
  "steps": [
    {
      "op": "status"
    }
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
        "pid": 44567,
        "conf": "/path/to/scry-dosbox-x/tests/guest/probe.conf",
        "conf_digest": "78bdc38f360b9b4a",
        "bound_s": 1200,
        "elapsed_s": 12.4,
        "captures": "off",
        "state_dir": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n632-save",
        "last_stop": {
          "stop_seq": 9,
          "pc": "0814:00000130",
          "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
          "since_s": 1.0,
          "wall_at": "2026-10-25T21:14:23+00:00"
        },
        "pending": {
          "arm": [],
          "disarm": 0,
          "symbols_load": false,
          "base_remeasure": false
        },
        "cpu_mode": "real",
        "pc": "0814:00000130",
        "declarations": {
          "breakpoints": 0,
          "watches": 0
        },
        "presence": {
          "available": false,
          "why": "a session started without `shared` has no window to draw on"
        },
        "session": {
          "alive": true,
          "running": false,
          "altered": true
        }
      }
    }
  ],
  "steps_completed": 1,
  "failed_at": {
    "available": false,
    "why": "no step failed"
  },
  "held": 0
}
```
<!-- scry-reference:end perform -->

**A `resume` inside a sequence is followed by asking `RUNSTATE`**, so whether it stopped again is the debugger's answer. Its `output` (`detail=True`) is what the debugger printed for `RUN`, capped at 2000 characters; the guest's own lines are the log's (`log` reads the log).

**A stopper that fires in a loop ends a key sequence early, and correctly**: the next key's `expect` is refused for a stopped machine. Clear it ahead of the `resume`, in the same `perform`.

**`summaries=True`** exists for size, and `stops` is the server's own count because one assembled by hand from summary lines comes out wrong.

After a `resume`, only the ops `answers_while_running` lists go on at once, and before any other the list waits up to `settle_seconds` for a stop. `start(plan=...)` also runs a list. A `step` that comes back running ends the console-driven part like a `resume`, and a `stop` ends the run. A `resume` inside a sequence drains what the console steps before it left in the terminal, so their prompt does not read as the resume's halt. A stopper that fires in a loop ends a key sequence early, and correctly, because the next key's `expect` is refused for a stopped machine: clear it ahead of the `resume`, in the same `perform`. `settle_seconds` 0 never waits. What only a step can judge (a symbol against the table loaded by then, a file an earlier step writes, the machine's mode) refuses at that step; the list check covers ops, argument names and values through each tool's own checks. `summaries` exists for size, and `stops` is the server's own count because one assembled by hand from summary lines comes out wrong. A wait whose channel failed ends the list with its code (`session_broken` when the emulator is gone). `ran` carries each step's `op` and full `reply`; `held` counts the steps that held their `recorded`; `not_stopped` is the answer before a console step when nothing waited. Refused steps in `errors` each carry `step`, `op`, `code` and `message`.

<!-- scry-reference:begin perform_export -->
## `perform_export`

*Export the session as a replay*

```text
perform_export(dest, overwrite=false)
```

Write the session's calls since `start` to `dest` as a `perform` document.

Kept: moving calls and checks (`read_memory`, `registers`, `screen_signature`, `map_find`,
`image_compare(method="golden")`), each held to its `recorded` reply. Other calls drop;
the first no replay can place, or past 5000, cuts the rest.

`dest` (`.json`) is refused if present unless `overwrite`. Reply: `path`, `steps`,
`checks`, `dropped`, `dropped_total`, `cut`, `replay`; `no_recording` if empty.

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

Example, from a live run:

```json
{
  "dest": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n1257.json"
}
```

```json
{
  "summary": "perform_export: 1 step, 0 checks, 0 dropped, cut at call 2 to $TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n1257.json",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n1257.json",
  "steps": 1,
  "checks": 0,
  "dropped": [],
  "dropped_total": 0,
  "cut": {
    "call": 2,
    "op": "resume",
    "why": "its run was stopped by the wall clock or by the machine itself, at a place inside its frame that no replayed advance reaches"
  },
  "replay": "uv run python -m scry_core.replay $TMPDIR/dosbox-x-live-matrix-3da5a8d2baff/n1257.json"
}
```
<!-- scry-reference:end perform_export -->

A release, a `stop` or `screen_wait` that ran the guest and came back stopped, or a wall-clock bound that ended a run, ends the document because the run ends where no replay reaches. Also cut: a call with no reply, a refusal after the guest moved, a guest found elsewhere than the call before left it, a step that wrote a file the session named. Dropped: a refused call, any other read, a call that changes nothing in the emulated machine. The replay is `uv run python -m scry_core.replay <dest>`, from this server's repository, and exits 0 when every step held. `dropped` shows the last 40 rows (`call`, `op`, `why`); `cut` is unavailable when nothing was cut; `no_recording` also covers a cancelled `start`. Dropped and cut calls are each named with a `why`.
