# The Lists tools

<!-- scry-reference:begin perform -->
## `perform`

*Run a sequence of steps*

```text
perform(steps, settle_seconds=30.0, summaries=false)
```

Run a LIST of the server's own operations in order on the open session, in ONE round
trip, stopping at the first failure with the whole account.

Arguments: `steps`, each `{"op": <tool name>, ...its arguments}`; every tool but
`build_check`, `start`, `close`, `perform`, `drive` and `perform_export` is a step, `debug`
included. A `resume` (or a `step` that comes back running) ends the console-driven part:
after it the steps `answers_while_running` lists run at once (a `stop` ends the run), and
before any other the sequence WAITS up to `settle_seconds` for the machine to stop (0 never
waits), as a list begun running does. A `send_keys`/`send_mouse` step whose own `expect` misses
ends the list, `verdict` `TIMEOUT`.

A step's `recorded`, `{field: value}`, is what its reply must hold (a replay,
`perform_export`): else INVALID `diverged` there, with `field`, `recorded` and `got`; `held`
counts the steps that held.

Refused before the first step runs: the WHOLE list is checked (ops, argument names and
VALUES, through each tool's own checks), and the reply is INVALID with `errors` listing EVERY
refused step (`step`, `op`, `code`, `message`), nothing run. What only its step can judge (a
symbol against the table loaded by then, a file an earlier step writes, the machine's mode)
refuses at that step.

Reply: `ran` (each step's `op` and full `reply`), `steps_completed`, `held`; a step's refusal is
INVALID (`step_failed`) with `failed_at` and `failed`; once it waited, `verdict`: `TARGET`
(a list ending running adds `stopped`, the stop it was heading for) or `TIMEOUT` (the steps
after the wait unsent, a `note`); with no wait, `not_stopped` before a console step, or
`still_running`; a wait whose channel failed ends the list with its code (`session_broken`
when the emulator is gone). `start(plan=...)` runs one too.

Reference: REFERENCE.md, Sequences in one call.

| argument | type | default |
|---|---|---|
| `steps` | array of object | required |
| `settle_seconds` | number (>= 0, <= 600.0) | `30.0` |
| `summaries` | boolean | `false` |

- `summaries`: True keeps a long list readable (an argument of the call, never of a step): each step but the one the list ended on becomes a compact row (a failed one stays whole under `failed`); `ran` shows the first 24 (`truncated`, of `steps_total`), `ran_path` and `replies_path` hold all, and `stops` counts the stops.

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
        "pid": 42881,
        "conf": "$TMPDIR/dosbox-x-live-job-tcl53hm5/A/tests/guest/probe.conf",
        "conf_digest": "78bdc38f360b9b4a",
        "conf_changed_on_disk": false,
        "watched": false,
        "bound_s": 1200,
        "elapsed_s": 54.5,
        "terminal_bytes_dropped": 0,
        "drain_alive": true,
        "captures": "off",
        "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save",
        "last_stop": {
          "stop_seq": 9,
          "pc": "0814:00000130",
          "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
          "since_s": 8.5,
          "wall_at": "2026-10-24T16:10:36+00:00"
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

**A `resume` inside a sequence drains what the console steps before it left in the terminal**, so their prompt does not read as the resume's halt. Its `screen_delta` (`detail=True`) is a tail capped at 2000 characters because the repaint replays the debugger's Output pane: an earlier `breakpoint_list` shows up in it however long the machine sat quiet. That is the pane, not the log (`log` reads the log).

**A stopper that fires in a loop ends a key sequence early, and correctly**: the next key's `expect` is refused for a stopped machine. Clear it ahead of the `resume`, in the same `perform`.

**`summaries=True`** exists for size, and `stops` is the server's own count because one assembled by hand from summary lines comes out wrong.

<!-- scry-reference:begin perform_export -->
## `perform_export`

*Export the session as a replay*

```text
perform_export(dest, overwrite=false)
```

Write what this session did since its `start` to `dest` as `perform`'s own document, so an investigation becomes a bench: `uv run python -m scry_core.replay <dest>`, from this server's repository, plays it with no model and exits 0 when every step held. Answers in any state, a closed session's included.

Kept: what moved the machine, as steps, and the reads that are checks (`read_memory`,
`registers`, `screen_signature`, `golden_check`), each holding to what its reply said
(`recorded`). Dropped, each named with why: a refused call, any other read, a call that
changes nothing in the emulated machine. Cut, named: the first call no replay can place (a
release, a `stop` or `screen_wait` that ran the guest and came back stopped, or a wall-clock
bound that ended a run, whose run ends where no replay reaches; no reply; a refusal after the
guest moved; a guest found elsewhere than the call before left it; a step that wrote a file
the session named; past 5000 calls kept).

`dest` absolute or `~`-led, ending `.json`; refused if it is there unless `overwrite`. Reply: `path` (the file written), `steps`, `checks`, `dropped` (the last 40, each `call`, `op`, `why`) and `dropped_total`, `cut` (`call`, `op`, `why`, or unavailable) and `replay`, the runner's command line. `no_recording` before a `start` succeeded, after one was cancelled, or when no recorded call is a step a replay could take.

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
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1257.json"
}
```

```json
{
  "summary": "perform_export: 1 step, 0 checks, 0 dropped, cut at call 2 to $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1257.json",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1257.json",
  "steps": 1,
  "checks": 0,
  "dropped": [],
  "dropped_total": 0,
  "cut": {
    "call": 2,
    "op": "resume",
    "why": "its run was stopped by the wall clock or by the machine itself, at a place inside its frame that no replayed advance reaches"
  },
  "replay": "uv run python -m scry_core.replay $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1257.json"
}
```
<!-- scry-reference:end perform_export -->
