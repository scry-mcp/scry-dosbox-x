# The States tools

`state_save` and `state_load` are the debugger's own commands, `SAVESTATE <file>` and `LOADSTATE <file>`, sent down the debugger channel `stop` uses: no window, no menu, no dialog and no focus taken. The build that carries them is named in [REFERENCE.md, Saved states](../../REFERENCE.md#saved-states).

**They need the debugger stopped.** While the guest runs, the channel is served from a timer tick handler, and loading a state there would replace the tick handlers the timer is walking. So a running guest is stopped for the command (`stop`'s `BREAK`) and released again, and `paused` says it happened.

**The command is the confirmation**: a refusal of its own is `unexpected_answer` quoting it. A name is never digits only: the emulator's own slot files are `<n>.sav` in the same directory.

<!-- scry-reference:begin state_save -->
## `state_save`

*Save the machine state*

```text
state_save(name, seconds=30.0)
```

Save the machine under `name` as `<state_dir>/<name>.sav`, by the debugger's own
`SAVESTATE` sent down the debugger channel: no window, no menu, no focus taken, headless
or windowed. Needs a DOSBox-X that carries the command; any other build is refused
`no_channel`, naming the command it lacks. The command needs the debugger stopped, so
a RUNNING guest is stopped for it and released again (`paused: true`); a parked one stays
parked. The file is read back for what it says about itself. Never overwrites. Saving
alters nothing. `seconds` bounds the command's reply. `name`: letters, digits, `_`, `-`, a
letter or digit first, at most 64, not digits only (the emulator's slot files).

Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`, `memory_mb`, `saved_at`
(the state's own members, the local time it was saved), `paused`; `session.running` says
whether the guest runs after the call.

Reference: REFERENCE.md, Saved states.

| argument | type | default |
|---|---|---|
| `name` | string | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `bytes` | integer |
| `machine` | string |
| `memory_mb` | integer |
| `name` | string |
| `path` | string |
| `paused` | boolean |
| `program` | string |
| `saved_at` | string |
| `version` | string |

Example, from a live run:

```json
{
  "name": "matrix_a_stopped",
  "seconds": 10
}
```

```json
{
  "summary": "state_save matrix_a_stopped: 81267 bytes, PROBE 2026-10-24 18:10",
  "status": "ok",
  "name": "matrix_a_stopped",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save/matrix_a_stopped.sav",
  "bytes": 81267,
  "version": "DOSBox-X 2026.10.01 (SDL2)",
  "program": "PROBE",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "2026-10-24 18:10",
  "paused": false
}
```
<!-- scry-reference:end state_save -->

<!-- scry-reference:begin state_load -->
## `state_load`

*Load a machine state*

```text
state_load(name, seconds=30.0)
```

Load the state `name` from `<state_dir>/<name>.sav`, by the debugger's own `LOADSTATE`
sent down the debugger channel, as `state_save` saves (same build, no window). A RUNNING
guest is stopped for it and released again (`paused: true`), now running the loaded
machine; a parked one stays parked, at the loaded machine's position. A state of another
DOSBox-X version, program, memory size or machine type is refused, never asked about. It
REPLACES the machine, so the session is altered from here on; the symbol table is kept,
and a base measured off a register is measured again at the first stop in the program's
code (`applied_on_stop.base_remeasured` when it moved; `status`'s `pending` until then).

Reply: `name`, `path`, the state's own members, `paused`, `mark` (where each log channel ended as the load was sent: `log`/`log_wait`'s `since_mark` for that channel reads what came after it; a position in the file, not a moment, so a line written before the load and not yet flushed lands after); `session.running`
says whether the guest runs after the call. A `.sav` that is no regular file is `unknown_ref`,
never opened.

Reference: REFERENCE.md, Saved states.

| argument | type | default |
|---|---|---|
| `name` | string | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `machine` | string |
| `mark` | object |
| `memory_mb` | integer |
| `name` | string |
| `path` | string |
| `paused` | boolean |
| `program` | string |
| `saved_at` | string |
| `version` | string |

Example, from a live run:

```json
{
  "name": "matrix_a_stopped",
  "seconds": 10
}
```

```json
{
  "summary": "state_load matrix_a_stopped: loaded",
  "status": "ok",
  "name": "matrix_a_stopped",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save/matrix_a_stopped.sav",
  "version": "DOSBox-X 2026.10.01 (SDL2)",
  "program": "PROBE",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "2026-10-24 18:10",
  "paused": false,
  "mark": {
    "guest": 33647,
    "emulator": 33647,
    "all": 33647
  }
}
```
<!-- scry-reference:end state_load -->

When the base moved, the breakpoints declared by name are cleared at their old places (the debugger's rows outlive a load) and armed anew.

<!-- scry-reference:begin state_list -->
## `state_list`

*List the saved states*

```text
state_list()
```

Every state under the session's state directory, each with what it says about
itself (`version`, `program`, `machine`, `memory_mb`, `saved_at`, `bytes`), read
off the file without loading it. A file there that is not a state carries a `note`, and so
does a `.sav` that is no regular file (a link to nothing, a directory, a FIFO), each reading
unavailable.
The emulator's own numbered slot file is NOT a named state and is reported apart, as
`working_slot`. Works on a running guest and needs no window.

Reply: `state_dir`, `states`, `working_slot`.

Reference: REFERENCE.md, Saved states.

Takes no argument.

| reply field | type |
|---|---|
| `state_dir` | string |
| `states` | array |
| `working_slot` | object |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "state_list: 1 state in $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save",
  "status": "ok",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save",
  "states": [
    {
      "name": "matrix_a_stopped",
      "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save/matrix_a_stopped.sav",
      "bytes": 81267,
      "version": "DOSBox-X 2026.10.01 (SDL2)",
      "program": "PROBE",
      "machine": "MCH_VGA",
      "memory_mb": 4096,
      "saved_at": "2026-10-24 18:10"
    }
  ],
  "working_slot": {
    "available": false,
    "why": "the emulator's own numbered slot has not been written"
  }
}
```
<!-- scry-reference:end state_list -->
