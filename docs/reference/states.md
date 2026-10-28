# The States tools

`state_write(method="save")` and `state_write(method="load")` are the debugger's own commands, `SAVESTATE <file>` and `LOADSTATE <file>`, sent down the debugger channel `stop` uses: no window, no menu, no dialog and no focus taken. The build that carries them is named in [REFERENCE.md, Saved states](../../REFERENCE.md#saved-states).

**They need the debugger stopped.** While the guest runs, the channel is served from a timer tick handler, and loading a state there would replace the tick handlers the timer is walking. So a running guest is stopped for the command (`stop`'s `BREAK`) and released again, and `paused` says it happened.

**The command is the confirmation**: a refusal of its own is `unexpected_answer` quoting it. A name is never digits only: the emulator's own slot files are `<n>.sav` in the same directory.

When the base moved, the breakpoints declared by name are cleared at their old places (the debugger's rows outlive a load) and armed anew.

<!-- scry-reference:begin state_list -->
## `state_list`

*List the saved states*

```text
state_list()
```

List the session's saved states, read off each file without loading it.

Reply: `state_dir`, `states` (`version`, `program`, `machine`, `memory_mb`, `saved_at`,
`bytes`, `note`), `working_slot`.

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
  "summary": "state_list: 1 state in $TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n986-save",
  "status": "ok",
  "state_dir": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n986-save",
  "states": [
    {
      "name": "matrix_a_stopped",
      "path": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n986-save/matrix_a_stopped.sav",
      "bytes": 81713,
      "version": "DOSBox-X 2026.10.01 (SDL2)",
      "program": "PROBE",
      "machine": "MCH_VGA",
      "memory_mb": 4096,
      "saved_at": "2026-10-27 12:18"
    }
  ],
  "working_slot": {
    "available": false,
    "why": "the emulator's own numbered slot has not been written"
  }
}
```
<!-- scry-reference:end state_list -->

A file in the folder that is not a state carries a `note`, and so does a `.sav` that is no regular file (a link to nothing, a directory, a FIFO), each reading unavailable. The emulator's own numbered slot file is not a named state, hence reported apart as `working_slot`. It works on a running guest and needs no window.

<!-- scry-reference:begin state_write -->
## `state_write`

*Save or load a machine state*

```text
state_write(method, name, seconds=30.0)
```

Save or load the machine as `<state_dir>/<name>.sav` through the debugger's `SAVESTATE` and
`LOADSTATE`; no window or focus needed. A running guest is stopped for it and released
again. `name`: letters, digits, `_`, `-`, never `-` first, at most 64,
not digits only. `seconds` bounds the command's reply.

`save`: never overwrites. Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`,
`memory_mb`, `saved_at`, `paused`.

`load`: replaces the machine, altering the session. Reply: `name`, `path`, the state's own
members, `paused`, `mark`.

Refused: a DOSBox-X without the commands (`no_channel`); a state of another version,
program, memory size or machine type; a `.sav` that is no regular file (`unknown_ref`).

Reference: REFERENCE.md, Saved states.

| argument | type | default |
|---|---|---|
| `method` | one of `"save"`, `"load"` | required |
| `name` | string | required |
| `seconds` | number (> 0, <= 600.0) | `30.0` |

| reply field | type |
|---|---|
| `bytes` | integer |
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
  "method": "save",
  "name": "matrix_a_stopped",
  "seconds": 10
}
```

```json
{
  "summary": "state_write save: matrix_a_stopped, 81713 bytes, PROBE 2026-10-27 12:18",
  "status": "ok",
  "name": "matrix_a_stopped",
  "path": "$TMPDIR/dosbox-x-live-matrix-0fa8c3f37660/jobs-scratch/A/n986-save/matrix_a_stopped.sav",
  "bytes": 81713,
  "version": "DOSBox-X 2026.10.01 (SDL2)",
  "program": "PROBE",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "2026-10-27 12:18",
  "paused": false
}
```
<!-- scry-reference:end state_write -->

`load` refuses a state of another version, program, memory size or machine type because it replaces the whole machine. `save` alters nothing. A DOSBox-X build without the `SAVESTATE`/`LOADSTATE` commands answers `no_channel`.

`mark` is where each log channel ended as the load was sent: `log`/`log_wait`'s `since_mark` for that channel reads what came after it. It is a position in the file, not a moment, so a line written before the load and not yet flushed lands after it.
