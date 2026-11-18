# The States tools

A saved state is the whole emulated machine as it stood at one instant, written to a file. `state_write` saves one under a name and loads it back, and `state_list` shows the ones in the session's state folder.

Loading a state replaces the machine, so it counts as a write. From then on the `session` block of every reply carries `altered`, which says this session has written to the machine.

<!-- scry-reference:begin state_list -->
## `state_list`

List the session's saved states, with what each file says of itself: program, machine, memory and time.

```text
state_list()
```

### Try it

On Bricks, the game this repository builds, after a state was saved as `third-brick`. The tour gives `start` a `state_dir` of its own.

Ask:

> Which saved states does this session have?

Call:

```text
state_list()
```

Reply, 3 of 5 fields:

```json
{
  "summary": "state_list: 1 state in ./tmp/demos/tour/files/states",
  "status": "ok",
  "state_dir": "./tmp/demos/tour/files/states"
}
```

The summary counts one state, and `state_dir` is the folder it is in: the `state_dir` given to `start`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "state_list: 1 state in ./tmp/demos/tour/files/states",
  "status": "ok",
  "state_dir": "./tmp/demos/tour/files/states",
  "states": [
    {
      "name": "third-brick",
      "path": "./tmp/demos/tour/files/states/third-brick.sav",
      "bytes": "<volatile>",
      "version": "<volatile>",
      "program": "BRICKS",
      "machine": "MCH_VGA",
      "memory_mb": 4096,
      "saved_at": "<volatile>"
    }
  ],
  "working_slot": {"available": false, "why": "the emulator's own numbered slot has not been written"}
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `state_dir`: The folder the states are in: the `state_dir` given to `start`, or one in the session's temporary folder, which `close` deletes.
- `states`: One row per named `.sav` file: `name`, `path`, `bytes`, `version`, `program`, `machine`, `memory_mb` and `saved_at`. A row that is no state carries a `note`.
- `working_slot`: The emulator's own numbered slot file, as a row of its own because it is not a named state. Unavailable when it has not been written.

<details><summary>All 3 reply fields</summary>

- `state_dir` (string)
- `states` (array)
- `working_slot` (object)

</details>

### Why it works this way

The list is read from the folder, not from the machine, so it answers while the program runs.

A file that is not a state keeps its row, with a `note` and its values unavailable. So does a `.sav` that is no regular file: a link to nothing, a directory, a FIFO. A `.sav` under a name no `load` reads, such as `Boss_1.sav` where a state is `boss-1`, carries a `note` saying to rename it.

### Related tools

- [`state_write`](#state_write)
- [`start`](session.md#start)

<details><summary>The contract your client receives</summary>

```text
List the session's saved states, read off each file without loading it.

Reply: `state_dir`, `states` (`name`, `path`, `version`, `program`, `machine`, `memory_mb`,
`saved_at`, `bytes`, `note`), `working_slot`.

Reference: REFERENCE.md, Saved states.
```

</details>
<!-- scry-reference:end state_list -->

<!-- scry-reference:begin state_write -->
## `state_write`

Save the emulated machine to a file under a name, or load a saved one back.

```text
state_write(method, name, seconds=30.0)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, while the game runs. The demo saves, presses the left arrow, and loads the state back.

Ask:

> Save the machine as it is now under the name bricks, without stopping my game.

Call:

```text
state_write(method="save", name="bricks")
```

Reply, 6 of 11 fields:

```json
{
  "status": "ok",
  "name": "bricks",
  "path": "./tmp/demos/bricks/bricks-states/bricks.sav",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "paused": true
}
```

Then, after the paddle has moved, the load:

Call:

```text
state_write(method="load", name="bricks")
```

Reply, 4 of 11 fields:

```json
{
  "status": "ok",
  "name": "bricks",
  "program": "BRICKS",
  "paused": true
}
```

The game was running, so `paused` is true both times: it was stopped for the command and resumed. `program` and `machine` are read off the state's file.

<details><summary>The two replies, whole</summary>

The first call's:

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "bricks",
  "path": "./tmp/demos/bricks/bricks-states/bricks.sav",
  "bytes": "<volatile>",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": true
}
```

The second call's:

```json
{
  "summary": "<volatile>",
  "status": "ok",
  "name": "bricks",
  "path": "./tmp/demos/bricks/bricks-states/bricks.sav",
  "version": "<volatile>",
  "program": "BRICKS",
  "machine": "MCH_VGA",
  "memory_mb": 4096,
  "saved_at": "<volatile>",
  "paused": true,
  "mark": "<volatile>"
}
```

</details>

### The two methods

| method | what it does |
|---|---|
| `save` | Writes the machine to a new file. It never overwrites one. |
| `load` | Replaces the machine with a saved one. Every later reply then carries `altered`: this session has written to the machine. |

### Arguments

- `method` (one of `"save"`, `"load"`, required): `save` or `load`, as above.
- `name` (string, required): The state's name, spelled as a file name is: `Boss_1` becomes `boss-1`. At most 64 characters, with at least one letter or digit, and not digits only.
- `seconds` (number (> 0, <= 600.0), default `30.0`): How long to wait for the debugger's answer to the command, in seconds. Left out, 30.

### What comes back

- `path`: The state's file: `<name>.sav` in the state folder.
- `paused`: `true` when the program was running: it was stopped for the command and resumed afterwards.
- `program`: The program the state was saved from, read off the file with `version`, `machine`, `memory_mb` and `saved_at`.
- `bytes`: On `save`: the size of the file.
- `mark`: On `load`: where the log ended as the load was sent. `log` and `log_wait` take it as `since_mark`.
- `taps`: On `load`, when a count or capture watch had to be set again: `rearmed` lists each `ref`, `unarmed` the ones that could not be, each with `why`.

<details><summary>All 11 reply fields</summary>

- `bytes` (integer)
- `machine` (string)
- `mark` (object)
- `memory_mb` (integer)
- `name` (string)
- `path` (string)
- `paused` (boolean)
- `program` (string)
- `saved_at` (string)
- `taps` (object)
- `version` (string)

</details>

### What it refuses

- A name with no letter or digit, of digits only, or longer than 64 characters (`bad_argument`).
- A `save` under a name that already has a file (`bad_argument`).
- A `load` of a name with no state, or whose `.sav` is no regular file (`unknown_ref`).
- A `load` of a state saved from another program than the one running; the message names it (`needs_call`).
- A state of another DOSBox-X version, memory size or machine type, or any other refusal the emulator prints (`unexpected_answer`).
- A DOSBox-X whose debugger has no `SAVESTATE` and `LOADSTATE` commands (`no_channel`).

### Why it works this way

Both methods are the debugger's own commands, `SAVESTATE` and `LOADSTATE`, sent over the debugger connection: no window, no menu, no dialog, and no focus taken from your screen.

They need the debugger stopped: a load while the program runs would replace the timer handlers the emulator is in the middle of calling. So a running program is stopped for the command and resumed afterwards, and `paused` says so.

A load replaces the whole machine, so a state of another version, memory size or machine type is refused. A state of another program is the one a call can mend: the emulator loads a state only while the program it was saved from runs. Run until that program runs, then load.

<details><summary>More on why</summary>

A state of another program is refused with the machine left as it was. That is the case at the stop before DOS boots, where no program runs yet.

`save` alters nothing. A `load` marks the session `altered` even when the emulator refuses it part of the way through, since part of the machine may have been replaced.

A name is never digits only, because the emulator's own slot files are `<n>.sav` in the same folder. The command's own answer is the confirmation: a refusal the emulator prints comes back quoted.

A load can move the program's load address. Each breakpoint saved by symbol name is then cleared at its old address and set again, because the debugger's own rows outlive a load.

`mark` is where each log ended as the load was sent, the same position for `guest`, `emulator` and `all`. `log` and `log_wait` take it as `since_mark` to read what came after. It is a position in the file, not a moment, so a line written before the load and not yet flushed lands after it.

</details>

### Related tools

- [`state_list`](#state_list)
- [`build_check`](session.md#build_check)
- [`log`](machine.md#log)
- [`log_wait`](machine.md#log_wait)
- [`resume`](run.md#resume)
- [`stop`](run.md#stop)

<details><summary>The contract your client receives</summary>

```text
Save or load the machine as `<state_dir>/<name>.sav` through the debugger's `SAVESTATE` and
`LOADSTATE`; no window or focus needed. `method`: `save` or `load`. A running guest is
stopped for it and released again. `name`: kept as a file name is (`Boss_1` is `boss-1`),
at most 64 characters, with a letter or digit, not digits only. `seconds`
bounds the command's reply.

`save`: never overwrites. Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`,
`memory_mb`, `saved_at`, `paused`.

`load`: replaces the machine, altering the session, and taps the declared count and capture
watches again (the load resets the page handlers). Reply: `name`, `path`, the state's own
members, `paused`, `mark`, `taps` (`rearmed` refs and `unarmed` rows with `why`) when
a declared tap was tapped again or could not be (a guest released running again waits for
a stop).

Refused: a DOSBox-X without the commands (`no_channel`); a state of another version,
program, memory size or machine type; a `.sav` that is no regular file (`unknown_ref`).

Reference: REFERENCE.md, Saved states.
```

</details>
<!-- scry-reference:end state_write -->
