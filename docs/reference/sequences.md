# The Sequences tools

These tools run other tools of this server for you. `perform` runs a list of steps in one call, and `drive` runs a list and then checks that the program reacted. `perform_export` writes the session so far as a script that replays with no model.

A step is a tool call written as an object, such as `{"op": "run_for", "frames": 2}`. Every tool can be a step except `build_check`, `start`, `close`, `window`, `promote` and the three on this page. `start(plan=...)` runs the same kind of list on the session it opens.

<!-- scry-reference:begin perform -->
## `perform`

Run a list of this server's tools in one call, in order, stopping at the first step that fails.

```text
perform(steps=null, path="", settle_seconds=30.0, summaries=false, until_frame=0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, while it runs with the mouse moving the paddle.

Ask:

> Give the paddle back to the keyboard with M, then serve with the space bar, checking the game logged each key.

Call:

```text
perform(
    steps=[{"op": "send_keys", "keys": ["m"], "expect": "MOUSE OFF$", "seconds": 10}, "… 1 more"])
```

Reply, 5 of 8 fields:

```json
{
  "summary": "perform: 2 of 2 steps, still running",
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "still_running": true,
  "held": 0
}
```

Both steps ran and none failed. `still_running` says the list ended with the game running and waited for no stop; `held` is 0 because no step carried `recorded` values.

<details><summary>The whole reply</summary>

```json
{
  "summary": "perform: 2 of 2 steps, still running",
  "status": "ok",
  "ran": [
    {
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): reaction seen",
        "status": "ok",
        "keys": ["m"],
        "modifiers": [],
        "route": "guest",
        "posted": 1,
        "bytes": 2,
        "frames": 2,
        "frame_before": 330,
        "frame_after": 337,
        "verify": {
          "checked": true,
          "seen": true,
          "expected": "MOUSE OFF$",
          "verdict": "TARGET",
          "line": "Bochs port E9h: MOUSE OFF",
          "seen_before_waiting": "<volatile>",
          "lines_before": "<volatile>",
          "waited_s": "<volatile>",
          "lines_total": "<volatile>"
        },
        "session": {"alive": true, "running": true, "altered": true}
      },
      "frame_before": 330,
      "frame_after": 337
    },
    {
      "op": "send_keys",
      "reply": {
        "summary": "send_keys (guest): reaction seen",
        "status": "ok",
        "keys": ["space"],
        "modifiers": [],
        "route": "guest",
        "posted": 1,
        "bytes": 2,
        "frames": 2,
        "frame_before": 337,
        "frame_after": 347,
        "verify": {
          "checked": true,
          "seen": true,
          "expected": "SERVE$",
          "verdict": "TARGET",
          "line": "Bochs port E9h: SERVE",
          "seen_before_waiting": "<volatile>",
          "lines_before": "<volatile>",
          "waited_s": "<volatile>",
          "lines_total": "<volatile>"
        },
        "session": {"alive": true, "running": true, "altered": true}
      },
      "frame_before": 337,
      "frame_after": 347
    }
  ],
  "steps_completed": 2,
  "failed_at": {"available": false, "why": "no step failed"},
  "still_running": true,
  "note": "the sequence ended with the machine running after a step that answers on a running machine, and nothing declared can stop it (no breakpoint, no interrupt breakpoint, no change watch), so no stop was waited for; declare one, or end the list  ... (301 characters)",
  "held": 0
}
```

</details>

### Arguments

- `steps` (array of object, optional): The list to run: each step is `{"op": <tool>, ...}` with that tool's own arguments. Give this or `path`, never both.
- `path` (string, default `""`): A saved step list to replay in place of `steps`: a file under `.scry/perform/` or one `perform_export` wrote. Absolute, or starting with `~`.
- `settle_seconds` (number (>= 0, <= 600.0), default `30.0`): How long each wait for a stop may take, before a step that needs one: 0 to 600 seconds. 0 never waits; left out, 30.
- `summaries` (boolean, default `false`): `true` cuts each step's reply but the last to a short row and writes the full replies to a file. Left out, every reply comes back whole.
- `until_frame` (integer, default `0`): A frame number, counted since power-on: the list repeats until a stop reads that frame. Needs `summaries` and a `run_for` step; left at 0, the list runs once.

### What comes back

- `ran`: One row per step that ran: its `op` and its full `reply`. With `summaries` a row adds its `step`, and `ran_path` and `replies_path` hold them all.
- `held`: How many steps carried `recorded`, the values a replayed step must give again, and gave them. 0 when no step carried any.
- `failed_at`: The step that failed, counted from 0, with its `op` and `reply` in `failed`. When none failed it is `available: false` with a `why`.
- `errors`: Every step refused before anything ran, each with its `step`, `op`, `code` and `message`.
- `verdict`: Comes once the list waited for a stop: `TARGET` with the stop in `stopped`, or `TIMEOUT` with a `note`. A list that waited for none says `still_running`.
- `stops`: With `summaries`, the server's own count of the stops: `stop_seq_first`, `stop_seq_last`, `surveyed` (how many a reply described), `by_cause` and `unaccounted`.

<details><summary>All 20 reply fields</summary>

- `errors` (array)
- `failed` (object)
- `field` (string)
- `got` (any)
- `ran_path` (string or object)
- `recorded` (any)
- `replies_path` (string or object)
- `steps_total` (integer)
- `still_running` (boolean)
- `stopped` (object)
- `stops` (object)
- `truncated` (boolean)
- `verdict` (string)
- `failed_at` (integer or object)
- `held` (integer)
- `ran` (array)
- `steps_completed` (integer)
- `frame_reached` (integer or object)
- `operations` (array)
- `until_frame` (integer)

</details>

### What it refuses

- A step that names no tool, an argument its tool does not take or a value it refuses. Nothing runs, and `operations` lists the tools a step may name (`bad_argument`).
- Both `steps` and `path`, neither, or an empty list (`bad_argument`).
- A step that answers INVALID: the list ends there (`step_failed`).
- A step whose reply differs from its `recorded` values; the reply names the `field`, the `recorded` value and what it `got` (`diverged`).
- A step that needs the program stopped while it still runs and `settle_seconds` is 0 (`not_stopped`).
- `until_frame` without `summaries`, without a `run_for` step, or at a frame the program has already reached (`bad_argument`).
- `until_frame` on a build whose `RUNSTATE` prints no `frames=`, so there is no frame to count (`no_channel`).
- A stop that reads no frame under `until_frame`, since nothing then says whether the frame came (`unexpected_answer`).
- The emulator gone before a step could run (`session_broken`).

### Why it works this way

The whole list is checked before its first step runs, so a refusal never arrives after earlier steps changed the machine. What only a running step can know refuses at that step: a symbol against the table loaded by then, a file an earlier step writes, the cpu's mode.

A step that needs the program stopped waits up to `settle_seconds` for the stop. A wait that runs out ends the list `TIMEOUT`: the steps after it were built on what it waited for. So does a step whose own wait missed: a `log_wait` or `screen_wait` that timed out, a `send_keys` or `send_mouse` whose `expect` never came.

A step may carry `recorded`, a `{field: value}` object of its own reply, and a reply with other values ends the list. That turns a list into a test, and `perform_export` writes such lists from a session.

<details><summary>More on why</summary>

`until_frame` counts what happens before a frame when nobody can know how many steps that takes. Every stop a watch makes takes a step without moving the frame, so a list sized by guessing ends short, with a smaller count that looks right.

The call ends right after the first step whose stop reads the frame, even mid-list, and `frame_reached` says which. It needs a `run_for` step because `run_for` carries on past a watch's stop, where `run_to` and `step` end at the first.

On a running program the first stop starts the count. Running out of steps or seconds is a `TIMEOUT` that names the last frame read. An exported script keeps the steps the repetitions ran, never the `until_frame`.

With `summaries`, `steps_total` counts the rows and `truncated` says the reply shows fewer. Read `stops` for a count and `ran_path` for the whole table: a count made by hand from cut rows comes out wrong and looks right.

After a `resume` step the server asks the debugger's `RUNSTATE` whether the program stopped again, so a stop is never guessed from a step's name. A `step` that comes back with the program running counts as a `resume`, and a `stop` step ends the run.

A `screen_view` step returns its text in the reply and writes its picture to its `path`, answering `not_inlined: nested`.

**Steps on a running program**

- A step from the list a `not_stopped` refusal names in `answers_while_running` runs on a running program. Any other waits for a stop, `symbols_load` included even with a `base`.
- That list also names tools that are no step: `close`, `drive`, `perform`, `perform_export`, `window` and `promote`.
- A list that ends with the program running after such a step, with nothing declared that could stop it, returns at once and its `note` says why.
- `operations`, the tools a step may name, comes once at the top of the reply, inside `act` in a `drive`.

</details>

### Related tools

- [`drive`](#drive)
- [`perform_export`](#perform_export)
- [`run_for`](run.md#run_for)
- [`log_wait`](machine.md#log_wait)
- [`screen_wait`](run.md#screen_wait)
- [`start`](session.md#start)

<details><summary>The contract your client receives</summary>

```text
A sequence of this server's operations in one call, in order on the open session,
stopping at the first failure; `drive` is this plus a wait for a line of the E9 log.

`steps`: `{"op": <tool>, ...arguments}`, any tool but `build_check`, `start`, `close`,
`perform`, `drive`, `perform_export`, `window`, `promote`. `path`: a `perform` document (absolute or `~`-led:
`.scry/perform/<name>.json`, or a file `perform_export` wrote) whose steps are replayed; give
`steps` or `path`, never both.
A `send_keys` or `send_mouse` whose `expect`
misses ends the list `TIMEOUT`. A step's `recorded`, `{field: value}` of its
own reply, must hold, else INVALID `diverged`.
The whole list is checked first: INVALID `errors` (`step`, `op`, `code`, `message`),
nothing run. `settle_seconds` bounds each wait for a stop before a step that needs one (0:
never wait). `until_frame=F` needs `summaries=True` (a window is hundreds of steps) and a `run_for` step, and repeats the list until a stop reads frame F, within 5000 steps and 600 s; `no_channel` if there is no frame counter. Frames count since power-on. A `screen_view` step inlines its
text; its picture is written to its `path` and answers `not_inlined: nested`.

Reply: `ran`, `steps_completed`, `held`, `failed_at`, `failed` (INVALID `step_failed`),
`verdict` (once the list waited; `TARGET` adds `stopped`, `TIMEOUT` `note`), else
`still_running`; `frame_reached` (with `until_frame`).

Reference: REFERENCE.md, Several calls as one.

summaries: True (of the call, never of a step) makes each step but the last a compact row; `ran` shows the first 24 (`truncated`), `ran_path` and `replies_path` hold all; `stops` counts the stops.
```

</details>
<!-- scry-reference:end perform -->

<!-- scry-reference:begin perform_export -->
## `perform_export`

Write the session's calls since `start` as a script that replays them and checks their answers, with no model.

```text
perform_export(dest, overwrite=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, in a session that ran to the first brick hit, forced a register and stepped.

Ask:

> Save what we did in this session as a script that replays and checks it without you.

Call:

```text
perform_export(dest="./tmp/demos/tour/files/session.json")
```

Reply, 6 of 10 fields:

```json
{
  "path": "./tmp/demos/tour/files/session.json",
  "steps": 15,
  "checks": 4,
  "dropped_total": 14,
  "cut": {"available": false, "why": "the recording kept every call a replay takes"},
  "kept": "2 saved for `promote`"
}
```

Fifteen calls replay, four of them as checks, and 13 calls were left out. `cut` is unavailable because nothing ended the script early; `kept` says the script is now a candidate for `promote`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "perform_export: 15 steps, 4 checks, 14 dropped to ./tmp/demos/tour/files/session.json",
  "status": "ok",
  "path": "./tmp/demos/tour/files/session.json",
  "steps": 15,
  "checks": 4,
  "dropped": [
    {"call": 1, "op": "status", "why": "a read the export does not check"},
    {"call": 5, "op": "machine_map", "why": "it changes nothing in the emulated machine"},
    {"call": 7, "op": "symbols_find", "why": "a read the export does not check"},
    {"call": 8, "op": "interrupt_vectors", "why": "it changes nothing in the emulated machine"},
    {"call": 9, "op": "screen_view", "why": "it changes nothing in the emulated machine"},
    {"call": 10, "op": "palette", "why": "it changes nothing in the emulated machine"},
    "... 8 more"
  ],
  "dropped_total": 14,
  "cut": {"available": false, "why": "the recording kept every call a replay takes"},
  "replay": "uv run python -m scry_core.replay ./tmp/demos/tour/files/session.json",
  "kept": "2 saved for `promote`"
}
```

</details>

### Arguments

- `dest` (string, required): The `.json` file to write: absolute, or starting with `~`. Refused when it exists, unless `overwrite`.
- `overwrite` (boolean, default `false`): `true` replaces a `dest` that is already there. Left out, an existing file is refused.

### What comes back

- `steps`: How many calls the script replays; `path` is the file written.
- `checks`: How many of them compare a reading with its `recorded` values, the answer the session got.
- `dropped`: The last 40 calls left out (reads the script does not check, refused calls, calls that change nothing), each with its `call`, `op` and `why`; `dropped_total` counts all.
- `cut`: The call the script ends before, with its `call`, `op` and `why`. It is `available: false` when every call a replay can run was kept.
- `replay`: The command that [replays the script](../../REFERENCE.md#from-a-session-to-a-test-that-replays-itself), run from this server's repository. It exits 0 when every step gave its `recorded` values again.
- `kept`: Says the script was saved as a candidate for `promote`: it reads "N saved for `promote`", and names a repository that has no `.scry/` folder yet.

<details><summary>All 8 reply fields</summary>

- `checks` (integer)
- `cut` (object)
- `dropped` (array)
- `dropped_total` (integer)
- `path` (string)
- `replay` (string)
- `steps` (integer)
- `kept` (string)

</details>

### What it refuses

- A `dest` that does not end in `.json`, is a directory, or exists without `overwrite` (`bad_argument`).
- No `start` that succeeded, one that was cancelled, or no call left that a replay could run (`no_recording`).

### Why it works this way

The script keeps the calls that move the program and a few readings as checks, each with the answer it got as `recorded`. A call that left the program at a new stop is checked on that stop's `regs` and `frame`.

The script ends at the first call no replay can reach. A `resume`, or a run that the clock or a `stop` ended, stops the cpu at a point inside its frame that no replayed run reaches. Every later stop would inherit the shift.

So move with `run_for`, `run_to` and `step`, which stop at the same point on every run, and keep `resume` for the end. Leave the `dest` of a step that writes a file empty: a file the session named is still there on replay, and the step is refused.

<details><summary>More on why</summary>

When the frames are known, `cut` says how many the run took, and a `run_for` of that many replays it up to that frame's start. The script also ends at a call with no reply, a refusal after the program moved, and a program found elsewhere than the call before left it.

A `screen_wait` that found its text becomes a `run_for` of as many frames as it polled, which a replay reaches. A `send_keys` or `send_mouse` to a stopped program is kept as a step: it runs frame by frame to a stop a replay reaches.

- A `debug` command the script keeps is never checked against its answer, and a `state_write(method="load")` is checked against nothing either.
- The file names what a replay needs: `needs.states`, the saved states it loads and does not save itself.
- And `needs.declarations`: the breakpoints and watches saved when the recorded `start` began, so a replay under others says so before it plays.

</details>

### Related tools

- [`perform`](#perform)
- [`promote`](project.md#promote)
- [`run_for`](run.md#run_for)
- [`run_to`](run.md#run_to)
- [`step`](run.md#step)
- [`state_write`](states.md#state_write)

<details><summary>The contract your client receives</summary>

```text
Write the session's calls since `start` to `dest` as a `perform` document.

Kept: moving calls and checks (`read_memory`, `registers`, `screen_signature`,
`screen_map_find`, `guest_file`, `image_compare(method="golden")`), each held to its
`recorded` reply. Other calls drop; the first no replay can place, or past 5000, cuts
the rest.

`dest` (`.json`) is refused if present unless `overwrite`. Reply: `path`, `steps`,
`checks`, `dropped`, `dropped_total`, `cut`, `replay`, and `kept` when the document is kept
for `promote`; `no_recording` if empty.

Reference: REFERENCE.md, From a session to a test that replays itself.
```

</details>
<!-- scry-reference:end perform_export -->

<!-- scry-reference:begin drive -->
## `drive`

Send an input as a list of steps, then check the program reacted by waiting for a new line in the log.

```text
drive(act, expect="", seconds=null, pattern=".", limit=40, settle_seconds=30.0, summaries=false)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, while it runs, in a session started with a `logfile`.

Ask:

> Press M and check the game handed the paddle to the mouse: wait for its MOUSE ON line.

Call:

```text
drive(act=[{"op": "send_keys", "keys": ["m"]}], expect="MOUSE ON$", seconds=10)
```

Reply, 2 of 5 fields:

```json
{
  "summary": "drive: reaction seen",
  "status": "ok"
}
```

The summary says a new log line matched `expect` after the key went in. The line itself is under `verify` in the whole reply, with the lines `looked` kept.

<details><summary>The whole reply</summary>

```json
{
  "summary": "drive: reaction seen",
  "status": "ok",
  "act": {
    "ran": [
      {
        "op": "send_keys",
        "reply": {
          "summary": "send_keys (guest): sent, reaction not checked",
          "status": "ok",
          "keys": ["m"],
          "modifiers": [],
          "route": "guest",
          "posted": 1,
          "bytes": 2,
          "frames": 2,
          "frame_before": 264,
          "frame_after": 272,
          "verify": {
            "checked": false,
            "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
          },
          "session": {"alive": true, "running": true, "altered": true}
        },
        "frame_before": 264,
        "frame_after": 272
      }
    ],
    "steps_completed": 1,
    "failed_at": {"available": false, "why": "no step failed"},
    "still_running": true,
    "note": "the act ended with the machine running; `drive`'s wait for `expect` is the wait",
    "held": 0
  },
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MOUSE ON$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MOUSE ON",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": "<volatile>",
      "lines_written": "<volatile>",
      "lines_total": "<volatile>",
      "truncated": false,
      "lines": ["Bochs port E9h: MOUSE ON"],
      "pattern": "."
    }
  }
}
```

</details>

### Arguments

- `act` (array of object, required): The steps to run, in the shape `perform` takes: `{"op": <tool>, ...}`. Required, and never empty.
- `expect` (string, default `""`): A regular expression: the log line that shows the program reacted, waited for after the steps. Left out, nothing is checked and `verify` says `checked: false`.
- `seconds` (number (> 0, <= 600.0), optional): How long to wait for the `expect` line. Left out, 5 seconds; given without `expect`, the call is refused.
- `pattern` (string, default `"."`): A regular expression that picks which new log lines `looked` shows. It changes nothing in the check; left out, every line.
- `limit` (integer (>= 1, <= 400), default `40`): How many of those lines `looked` shows, the newest: 1 to 400. Left out, 40.
- `settle_seconds` (number (>= 0, <= 600.0), default `30.0`): As in `perform`. With `expect`, the last step's stop is not waited for: waiting for the line is the wait.
- `summaries` (boolean, default `false`): As in `perform`: `true` cuts each step's reply but the last to a short row.

### What comes back

- `act`: What the steps did, in the fields of a `perform` reply: `ran`, `steps_completed`, `failed_at` and the rest.
- `verify`: The check: `checked` says whether one ran and `seen` whether the line came, with the `line`, the `verdict` (`TARGET` or `TIMEOUT`) and `waited_s`.
- `looked`: Under `guest`, the newest `lines` the program wrote since the steps began that match `pattern`, with `lines_total` and `truncated`.

<details><summary>All 4 reply fields</summary>

- `act` (object)
- `looked` (object)
- `operations` (array)
- `verify` (object)

</details>

### What it refuses

- `seconds` without `expect`, or an empty `act` (`bad_argument`).
- A bad step or argument in `act`, before anything runs; `operations` lists the tools a step may name (`bad_argument`).
- A session started without a `logfile`, which leaves no log to read (`no_channel`).
- A step that answers INVALID (`step_failed`).
- The program stopped at the debugger without the line: a stopped program writes nothing more. The reply adds `last_stop` (`wait_stopped`).
- A refusal of the steps themselves comes back with its own code, such as `not_stopped`, `session_broken` or `diverged`.

### Why it works this way

The log is marked once, before the first step, so a line written before the input is never taken for a reaction.

The log is the program's own: the lines it writes to port E9, kept in the session's `logfile`. Steps that end with the program stopped get one read of it, not a wait; `send_keys` and `send_mouse` with `expect` do wait, frame by frame.

`checked` says a check ran and `seen` that the line came; neither is `verified`, which elsewhere means a value read back equal to the one sent. A still of the screen needs a recording and `ffmpeg`, so `capture_frame` takes it.

<details><summary>More on why</summary>

`verify` also carries `expected`, `seen_before_waiting`, `lines_before` and `lines_total`; on a `TIMEOUT`, `arrived_during`, `lines_examined` and a `note`; after a stop, `stopped_during_wait` and `lines_on_disk`. `why` explains `checked: false`; `available: false` means the steps ran out their own wait. `looked.guest` adds `lines_written`, `since_mark` and `pattern`.

</details>

### Related tools

- [`perform`](#perform)
- [`send_keys`](input.md#send_keys)
- [`send_mouse`](input.md#send_mouse)
- [`log_wait`](machine.md#log_wait)
- [`log`](machine.md#log)
- [`capture_frame`](captures.md#capture_frame)

<details><summary>The contract your client receives</summary>

```text
A sequence that also waits for a line of the E9 log; with no line to wait for, `perform`
is the call. Marks the E9 log, runs `act` (steps in `perform`'s
vocabulary, a step `{"op": <tool>, ...arguments}`), then with `expect` waits up to
`seconds` (default 5, at most 600) for a new matching line. Needs a
`logfile`.

`pattern` and `limit` only filter the lines shown; `settle_seconds` is the call's, as in
`perform`. Refused: `seconds` without `expect`.

Reply: `act` (`ran`, `steps_completed`, `failed_at`), `verify` (`verdict` `TARGET` or
`TIMEOUT`, `seen`, `line`; `checked: false`), `looked.guest` (`lines`, `truncated`).
INVALID with the same fields on `step_failed`, `wait_stopped`, or the act's own refusal.
No screen: use `capture_frame`.

Reference: REFERENCE.md, Input and the screen.

summaries: True (of the call, never of a step) makes each step but the last a compact row; `ran` shows the first 24 (`truncated`), `ran_path` and `replies_path` hold all; `stops` counts the stops.
```

</details>
<!-- scry-reference:end drive -->
