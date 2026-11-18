# The Input tools

These tools deliver keys, mouse buttons and pointer moves to the program running inside DOS. Everything goes in inside the emulated machine: no window comes to the front and your own pointer never moves ([Input and the screen](../../REFERENCE.md#input-and-the-screen)).

## How input gets into the program

A small helper, `SCRY.COM`, stays resident inside DOS and carries out each key or mouse command the server sends it over the emulated COM1 port. `start` with `program` loads the helper by itself; a conf that starts the program from its own `[autoexec]` has to run the helper first.

Sent to a machine stopped at the debugger, an input runs it one frame at a time until the helper has taken every command, then leaves it stopped again. A frame here ends at the vertical retrace.

## An input that was sent is not one the program took

Without `expect` a reply says what was sent, not that the program reacted: a dialog can swallow a key that went in correctly. Give `expect`, a pattern for the line the program writes to its own log (port 0xE9) when it reacts, and the reply says whether that line came.

The `summary` of every input says which case it is: "sent, reaction not checked", "reaction seen", "no reaction seen (TIMEOUT)" or "reaction could not be checked".

<!-- scry-reference:begin send_keys -->
## `send_keys`

Send keystrokes to the DOS program, and check in its log that it reacted to them.

```text
send_keys(keys, modifiers=null, expect="", seconds=null, action="press")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, running, with the ball waiting on the paddle. The tour sends this key as one step of a `perform`.

Ask:

> Press the space bar to serve the ball, and tell me whether the game logged the serve.

Call:

```text
send_keys(keys=["space"], expect="SERVE$", seconds=10)
```

Reply, 7 of 9 fields:

```json
{
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["space"],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2
}
```

"reaction seen" means the game wrote a line matching `SERVE$` to its log after the key. One key (`posted`) went in as two scan-code bytes, each a command (`frames`) to the helper inside DOS, the `guest` route.

<details><summary>The whole reply</summary>

```json
{
  "summary": "send_keys (guest): reaction seen",
  "status": "ok",
  "keys": ["space"],
  "modifiers": [],
  "route": "guest",
  "posted": 1,
  "bytes": 2,
  "frames": 2,
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
  }
}
```

</details>

### Arguments

- `keys` (array of string, required): The names of the keys to send, in order: at most 64, such as `enter`, `a`, `f1` or `left`.
- `modifiers` (array of string (matching `^([sS][hH][iI][fF][tT]|[cC][tT][rR][lL]|[cC][oO][nN][tT][rR][oO][lL]|[aA][lL][tT]|[oO][pP][tT][iI][oO][nN])$`), optional): Keys held around the others: `shift`, `ctrl` (or `control`) and `alt` (or `option`), in any case. Left out, none.
- `expect` (string, default `""`): A regular expression for the line the program writes to its log when it reacts. Left out, nothing is checked.
- `seconds` (number (> 0, <= 600.0), optional): How long to wait for the `expect` line, up to 600. Left out, 10; refused without `expect`.
- `action` (one of `"press"`, `"down"`, `"up"`, default `"press"`): `press` taps each key; `down` presses and holds, `up` lets go, so a key can stay held across calls. Left out, `press`.

### What comes back

- `verify`: Whether the program reacted. `checked` is `false` with no `expect`; else `verdict` is `TARGET` (the line came, in `line`) or `TIMEOUT` (it did not).
- `posted`: How many keys were sent into the program. `bytes` is how many scan-code bytes they made, and `frames` how many commands the helper took.
- `route`: Which way the input went in: always `guest` here, through the helper inside DOS.
- `polls`: From a stopped machine, how many frames it ran while the keys went in. The reply then also carries the stop it was left at.
- `delivered`: Only on a send that failed: `false` when nothing went in and the call can be sent again, `true` when part of it did.

<details><summary>All 19 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `e9` (object)
- `frame` (integer or object)
- `instruction` (DosboxInstruction)
- `pc` (string or object)
- `polls` (integer)
- `regs` (object)
- `stop_seq` (integer)
- `watches` (array)
- `bytes` (integer)
- `delivered` (boolean)
- `frames` (integer)
- `keys` (array)
- `modifiers` (array)
- `posted` (integer)
- `route` (string)
- `verify` (object)

</details>

### What it refuses

- A key or a modifier it has no name for; a DOS keyboard has no command key (`bad_argument`).
- No key at all, or more than 64 (`bad_argument`).
- `seconds` without `expect`, an `expect` that is no valid pattern, or an `expect` with no log to read (`bad_argument`).
- No helper answering inside DOS, or a helper of another protocol version (`no_channel`).
- A stopped machine on a build whose debugger has no `RUNSTATE` command (`no_channel`).
- A breakpoint that stops the machine while the keys go in, or during the `expect` wait (`wait_stopped`).
- An emulator busy inside a long host call, which answers nothing: no key was sent (`host_failed`).

### Why it works this way

An input sent to a running program lands whenever it arrives, an instant no replay can find again. Sent to a machine stopped at the debugger, it goes in as the machine runs frame by frame. The reply counts those frames in `polls` and carries the stop, so an exported session can replay the input.

The commands go in a BIOS timer tick apart, so a game that reads its keyboard once a frame sees a key go down before it comes up. That is also why a call takes at most 64 keys: every scan-code byte is one command, and the session answers nothing else until the last one is in.

`expect` is matched against what the program literally writes, so read its log once first: a program that logs `key down x mods=4` for alt+x is telling you its pattern. A miss is `TIMEOUT` beside what was sent, because a swallowed key and a key never sent are different facts.

<details><summary>More on why</summary>

**The helper**

The server takes the emulated COM1 for the helper and switches on DOSBox-X's integration device itself: your conf needs neither, and one that sets `serial1` loses it. `start` loads the helper on the first drive letter from Y: down that the conf's `[autoexec]` does not mount; a conf that mounts them all is refused.

The helper announces itself in the program's log. The first input is refused `no_channel` when that line is missing or names another protocol version; with no `logfile` there is no line to read, and input goes out unchecked.

- It works from the serial port's interrupt, so a game that takes over the timer still gets its input. One that also masks IRQ 4 does not.
- It runs on the stack of the program it interrupts, so a small private stack has to leave room for it.
- Each command is acknowledged before the next goes: a lost byte is sent again, and no command runs twice.
- The tick between commands is the program's own emulated time, which a slow host stretches; without the `RUNSTATE` debugger command it is real time.

If a breakpoint stops the machine inside the helper, `resume` from that stop: moving the instruction pointer out leaves the helper ignoring every later input. A `breakpoint_interrupt` on INT 33h can stop there, since the helper calls INT 33h itself.

**A stopped machine**

A code breakpoint that stops one of the frames ends the send there (`wait_stopped`), with the commands already taken in. A stop from a change watch or an interrupt breakpoint looks like the end of a frame and counts as one, as in `run_for`.

`expect` is then waited for one frame per look, and its `seconds` are the program's own time, so a replay that misses runs the same frames. In the stop the reply carries, `e9` is what the program logged during every frame run, and `watches` are as the last frame read them.

**No reaction seen**

A machine that stops during the `expect` wait is refused `wait_stopped`, with `last_stop`. A command sent before the stop lands at the next `resume`, and later ones are not sent. So a key whose press stopped the machine stays down until a later send lets it go.

- Whether an input went in before such a stop is for the program's log to say: read `log` since the send.
- An emulator that died is `verify.checked: false`, never a swallowed key.
- A program that writes nothing to its log gives `expect` nothing to match.
- `seen_before_waiting: true`: the line came while the keys were still going in. It is still this input's reaction.
- In a `perform` or a `drive`, a `TIMEOUT` ends the list there.
- A new session's first key can be swallowed while DOS settles: send it once more before looking for a dialog.

`verify` in full: `checked`, `expected` (the pattern), `seen`, `verdict`, `waited_s`; when seen, `line`, `seen_before_waiting`, `lines_before` and `lines_total`; on a `TIMEOUT`, `note`, `arrived_during` and `lines_examined`. `arrived_during` counts the lines the program wrote during the wait: zero means it wrote nothing at all. `why` says why nothing was checked, and a stop during the wait adds `stopped_during_wait` and `lines_on_disk`.

**Keys**

A key sent while a dialog is closing can be swallowed. To send it once the screen has settled: `stop`, `run_for` a few frames, read `screen_signature`, and repeat until two reads agree; then send the key. A stopped machine's time moves only when `run_for` moves it, so the wait costs the program no time.

- The keys go in as set 1 scan codes, composed by the server.
- A cancelled call lets go of every key it had pressed, so none stays down repeating in the program.

**A send the emulator could not take**

While the emulator is inside a long host call, such as the first long-name open in a folder of very many files, its debugger does not answer. A send that meets this before writing anything is refused `host_failed` with `delivered: false`. Nothing went in: send it again once `status` answers.

A send cut part-way answers `delivered: true` with how many commands went in and how many did not: send only what was not written. A key it pressed and could not let go stays down until the session's next input, which lets it go first and says so in `note`.

Keys a call holds on purpose (`action="down"`) are not let go this way, and loading a saved state forgets any key still owed.

</details>

### Related tools

- [`send_mouse`](#send_mouse)
- [`drive`](sequences.md#drive)
- [`screen_wait`](run.md#screen_wait)
- [`log`](machine.md#log)
- [`screen_signature`](screen.md#screen_signature)
- [`perform`](sequences.md#perform)

<details><summary>The contract your client receives</summary>

```text
Send keystrokes to the guest; with `expect`, prove the program took them.

`keys`: at most 64. `action`: `press` taps them; `down` holds the modifiers and
presses the keys, `up` releases them, so a held key spans the calls between; a held key
makes no repeats of its own, each repeat is a further `down`. `expect`: a regex over the
E9 log the program's reaction writes, waited up to `seconds` (default 10).
A stopped machine is
run retrace by retrace until the stub takes each key, and left stopped at a retrace; its
`expect` waits `seconds` of the guest's own time.

Refused: an unknown key or modifier, `seconds` without `expect`, no stub, a stopped
machine on a build with no `RUNSTATE` (`no_channel`).

Reply: `route`, `posted`, `bytes`, `frames` (stub commands, a BIOS tick apart), `verify`
(`verdict` `TARGET` or `TIMEOUT`, `seen`); from a stopped machine `polls` and the stop
it was left at (the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause`, `regpoint_hit` (a registerpoint stopped it) and `e9`).

Reference: REFERENCE.md, Input and the screen.
```

</details>
<!-- scry-reference:end send_keys -->

<!-- scry-reference:begin send_mouse -->
## `send_mouse`

Move the DOS program's mouse pointer, press its buttons or drag, and read back where the pointer ended.

```text
send_mouse(x=null, y=null, button="", action="", units="screen", expect="", seconds=null, target="",
    to_x=null, to_y=null)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, running with the mouse in control of the paddle, after `screen_map_find` recognised the play screen. `court` is an area of the demo's screen map.

Ask:

> Put the mouse pointer on the middle of the court and show me where it ended.

Call:

```text
send_mouse(target="court", expect="MOUSE$", seconds=10)
```

Reply, 5 of 13 fields:

```json
{
  "status": "ok",
  "pointer": {
    "screen": {"x": 240, "y": 100, "width": 320, "height": 200},
    "mouse": {"x": 480, "y": 100, "max_x": 639, "max_y": 199},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "motion": true,
  "target": "court"
}
```

The pointer went to the centre of `court`: pixel 240,100 of a 320x200 screen, 480,100 in the mouse driver's own coordinates. `driver_arrived` speaks for the driver's pointer only; `motion` says the move also went in as mouse motion.

<details><summary>The whole reply</summary>

```json
{
  "summary": "send_mouse: pointer at 240,100, program's own pointer not read; no button pressed; reaction seen",
  "status": "ok",
  "x": 240,
  "y": 100,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {"x": 240, "y": 100, "width": 320, "height": 200},
    "mouse": {"x": 480, "y": 100, "max_x": 639, "max_y": 199},
    "buttons": [],
    "bios_mode": "0x13"
  },
  "driver_arrived": true,
  "motion": true,
  "verify": {
    "checked": true,
    "seen": true,
    "expected": "MOUSE$",
    "verdict": "TARGET",
    "line": "Bochs port E9h: MOUSE",
    "seen_before_waiting": "<volatile>",
    "lines_before": "<volatile>",
    "waited_s": "<volatile>",
    "lines_total": "<volatile>"
  },
  "target": "court",
  "screen": "play",
  "identified_at_stop": 2
}
```

</details>

### Arguments

- `x` (integer (>= 0, <= 32767), optional): Where the pointer goes, across, in `units`. Give it with `y`; left out, the pointer stays where it is.
- `y` (integer (>= 0, <= 32767), optional): Where the pointer goes, down, in `units`. Give it with `x`.
- `button` (one of `""`, `"left"`, `"right"`, `"middle"`, default `""`): The button that acts: `left`, `right` or `middle`. Left out, the left one when an `action` is named, else none.
- `action` (one of `""`, `"click"`, `"double"`, `"triple"`, `"down"`, `"up"`, `"drag"`, default `""`): What the button does: `click`, `double`, `triple`, `down`, `up` or `drag`. Left out, a click when a `button` is named, else no button.
- `units` (one of `"screen"`, `"mouse"`, default `"screen"`): `screen`, the default, counts character cells in a text mode and pixels in a graphics one, as `screen_view` does. `mouse` is the mouse driver's own coordinates.
- `expect` (string, default `""`): A regular expression for the line the program logs when it reacts, as in [`send_keys`](#send_keys). Left out, nothing is checked.
- `seconds` (number (> 0, <= 600.0), optional): How long to wait for the `expect` line, up to 600. Left out, 10; refused without `expect`.
- `target` (string, default `""`): A control, a named area of the screen the latest `screen_map_find` recognised, in place of `x` and `y`. The pointer goes to its centre.
- `to_x` (integer (>= 0, <= 32767), optional): Where a drag ends, across, in `units`. Only with `action="drag"`, and with `to_y`.
- `to_y` (integer (>= 0, <= 32767), optional): Where a drag ends, down, in `units`. Only with `action="drag"`, and with `to_x`.

### What comes back

- `pointer`: Where the pointer ended: `screen` in screen units, `mouse` in the driver's coordinates with its range, the `buttons` held and the `bios_mode`.
- `arrived`: Whether the pointer is on the point asked for. It comes only when something could check that: the program's own pointer, or `units="mouse"`.
- `driver_arrived`: In place of `arrived` for a plain screen move: whether the mouse driver's pointer got there. A program with a pointer of its own may not have followed.
- `asked`: When the pointer did not get there, the driver coordinates that were sent.
- `motion`: `true` when the move also went in as mouse motion, which a program that reads motion needs. Otherwise it says why not.
- `verify`: Whether the program reacted, as in [`send_keys`](#send_keys).

<details><summary>All 27 reply fields</summary>

- `cause` (string)
- `regpoint_hit` (object)
- `cpu_mode` (string or object)
- `e9` (object)
- `frame` (integer or object)
- `instruction` (DosboxInstruction)
- `pc` (string or object)
- `polls` (integer)
- `regs` (object)
- `stop_seq` (integer)
- `watches` (array)
- `action` (string)
- `arrived` (boolean)
- `asked` (object)
- `button` (string)
- `delivered` (boolean)
- `driver_arrived` (boolean)
- `identified_at_stop` (integer or object)
- `motion` (boolean or object)
- `pointer` (object)
- `route` (string)
- `screen` (string)
- `target` (string)
- `units` (string)
- `verify` (object)
- `x` (integer)
- `y` (integer)

</details>

### What it refuses

- No move and no button, or `x` without `y` (`bad_argument`).
- A point off the screen, or a screen mode of unknown size, where `units="mouse"` still works (`bad_argument`).
- `target` together with `x`, `y` or `units="mouse"` (`bad_argument`).
- A drag without both ends, or `to_x` and `to_y` without a drag (`bad_argument`).
- A `target` with no screen recognised by `screen_map_find`, or after the screen mode changed (`needs_call`).
- A `target` the recognised screen does not have (`unknown_ref`).
- No helper inside DOS, or a stopped machine on a build without the `RUNSTATE` debugger command (`no_channel`).
- A breakpoint that stops the machine during the send or the `expect` wait (`wait_stopped`).
- An emulator busy inside a long host call: nothing was sent (`host_failed`).

### Why it works this way

DOS programs read the mouse in different ways: some ask the driver where the pointer is, many read how far it moved, and some drive a PS/2 mouse themselves. So a move goes in twice: first as motion, which reaches all of them, then as an exact position. `motion` says whether the first half went in.

The pointer that moves is the mouse driver's, the one DOSBox-X provides: a mouse driver loaded inside DOS reads its own hardware and is not reached. A program that keeps a pointer of its own, adding up motion, can end somewhere else, so a plain screen move answers only `driver_arrived`.

A [screen map](files.md#screen-maps) is a file that names a program's screens and the areas of each. When it also says where the program keeps its pointer, the server reads that pointer and corrects the move, and `arrived` then speaks for it.

<details><summary>More on why</summary>

**How programs read the mouse**

DOSBox-X passes on your own mouse's motion only while its window has captured the mouse, which no session does. So the helper sends the motion itself, through DOSBox-X's integration device, then sets the position.

- Motion counters (INT 33h AX=0Bh) and movement events (a handler set with AX=0Ch): reached by the motion.
- A PS/2 mouse the program drives through the BIOS: reached too, as DOSBox-X scales the motion, so a move of a few units can reach it as none.
- The driver's position: set exactly (AX=04h) after the motion.
- A build whose integration device takes no motion only sets the position, and `motion` says why.

**`pointer` in full**

- `screen`: `x`, `y`, `width`, `height` in screen units; unavailable in a mode of unknown size.
- `mouse`: `x`, `y` in the driver's coordinates, with its range `max_x`, `max_y`.
- `buttons` held, `bios_mode`, and `vbe_mode` under a VBE mode.
- `program`: the program's own pointer when a screen map gives it: `x`, `y`, and `corrections`, how many times the move was corrected.
- `program.reach`: when it did not get there, the span (`x`, `y`, low and high) it covered between the driver's two corners.
- `program.range_widened`: the driver range (`x`, `y`) the server set, in the reply that widened it.

Under a VBE mode the BIOS mode byte is the emulated card's own number, so the helper asks VBE for the mode and its resolution (INT 10h 4F03h and 4F01h). The units are then that resolution: pixels, or character cells for a VBE text mode.

Each screen unit covers several driver coordinates, and the move aims at the middle of them. The driver rounds to its own steps and a program divides its range back, as Deluxe Paint does with eight coordinates a pixel. Aimed at a unit's first coordinate, the pointer could land in the unit before.

`arrived` is checked in the units asked: any driver coordinate inside the unit counts. It is `false` when the driver's rounding or the program's own range left the pointer in another unit, and `asked` then gives the driver coordinates sent. A text mode snaps the pointer to its character cell, and the reply reports where it ended.

**A program with a pointer of its own**

Its pointer is read only on a stopped machine, in `units="screen"`, in a mode of known size; otherwise `pointer.program` says why it was not read. A drag's end is not corrected. When the target is past what the driver's range lets that pointer reach, the server widens the range once; `range_widened` then shows in every reply's `session`.

Allegro's default DOS mouse driver keeps its own pointer this way. With `mouse = I33` under `[mouse]` in the program's `allegro.cfg` it reads the driver instead, sets the range to its screen, and is pointed at by pixel like any other program.

**Buttons**

- `double` and `triple` are two and three clicks a timer tick apart, close enough for a program that counts them.
- A button with no `x`, `y` acts where the pointer is. A move and a button in one call move first.
- A cancelled call does not let go of a button it pressed, since `action="down"` holds one on purpose.
- A call with a button and no move answers `arrived: true`.

A click that fires a code breakpoint ends the call `wait_stopped`, stopped machine or running: the program reacts within a frame, before the pointer is read back. In a `perform` that step is `step_failed`. A read-back that fails after the commands went in is refused with `delivered: true`, so nothing is sent twice.

**The rest of the reply**

With `target`, the reply adds `target`, `screen` (the screen recognised) and `identified_at_stop`, the number of the stop at which `screen_map_find` recognised it.

In a [`perform`](sequences.md#perform) run with `summaries`, each frame a send ran on a stopped machine is a numbered stop, and only the last one is in a reply. `stops.unaccounted` counts the stops numbered during the list that no step's reply shows, so a few sends make it large.

The helper, a stopped machine, `expect` and a failed send work as under [`send_keys`](#send_keys). With no `logfile` the mouse goes in unchecked too.

</details>

### Related tools

- [`send_keys`](#send_keys)
- [`screen_map_find`](read.md#screen_map_find)
- [`screen_map_write`](read.md#screen_map_write)
- [`screen_view`](screen.md#screen_view)
- [`drive`](sequences.md#drive)
- [`perform`](sequences.md#perform)

<details><summary>The contract your client receives</summary>

```text
Move the guest's mouse pointer, press buttons, and read the pointer back; `expect`
proves the program reacted, as in `send_keys`, and is waited up to `seconds`.

`x`, `y`: both or neither, in `units`. `action` names what the button does; with an `action`
and no `button` the left one is used, and with neither only the pointer moves. `target`: a
control of the latest `screen_map_find`
screen, instead of `x`, `y`. `action="drag"` presses at that place and releases at `to_x`,
`to_y`, with the move between. A stopped machine is run as for `send_keys`; under a map that
declares the program's own pointer, a move there nudges the driver until that pointer is on
the place and `arrived` judges it (`pointer.program`, unavailable with its reason on a running
guest, `units="mouse"` or a mode of unknown size). A drag's end is not steered.

Refused: no move and no button, half a move, a place off the screen, no stub, a stopped
machine with no `RUNSTATE`; `target` beside `x`, `y` or `units="mouse"`, a drag without
both ends, `to_x` and `to_y` without a drag (`bad_argument`);
no `screen_map_find` match (`needs_call`); an unknown control (`unknown_ref`).

Reply: `route`, `pointer`, `arrived` (the program's pointer read, or `units="mouse"`; else
`driver_arrived` and `asked`: only the driver is known), `motion` (a move reached the motion
counters too), `verify`; with `target`: `target`, `screen`, `identified_at_stop`; from a
stopped machine, `send_keys`' `polls` and stop.

Reference: REFERENCE.md, Input and the screen.
```

</details>
<!-- scry-reference:end send_mouse -->
