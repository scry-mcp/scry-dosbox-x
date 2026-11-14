# The Input tools

Every input goes in inside the machine and nothing about the host is touched ([REFERENCE.md, Input and the screen](../../REFERENCE.md#input-and-the-screen)). A `send_mouse` `target` is a control of a [screen map](files.md#screen-maps).

## The route

The emulator's COM1 is a TCP client of a port the session listens on (`input_port`; transparent, so a byte 0xFF is data) and DOSBox-X's integration device is switched on, both as `-set` overrides the conf need not carry. A resident stub, `guest/SCRY.COM` (its header is the protocol), takes each command off the socket on the UART's own interrupt and carries it out in the guest. A game that takes the timer for itself (INT 08h with no chain to the BIOS, so INT 1Ch never runs again) still gets its input this way, unless it also masks IRQ 4 at the PIC. The host sends the commands a BIOS tick apart, so a game that reads its keys once a frame sees the make before the break. A running guest's tick is its own emulated time, asked of `RUNSTATE`, which falls behind the wall's when the emulator cannot keep real speed; a build with no `RUNSTATE` is spaced by the wall clock.

**The stub runs on the interrupted program's own stack.** Its entries (the serial interrupt, the timer tick) push a frame, the registers and the calls of `service`, and a program that keeps a small private stack has to leave room for them above its own handlers. `tests/guest/stack.asm` fills a private stack with a canary and idles; the host sends input and reads the stack back, and the lowest byte no longer the canary is the depth. It does not cover a real DOS driver's own use or a VBE BIOS call in a mode the emulator draws.

**A stub the debugger parked inside its own handler stays deaf.** Its busy latch is cleared by the handler's own exit, so a write of IP out of `service` (a `breakpoint_interrupt` on 33h hit by the stub's own INT 33h) leaves every later entry finding it busy. A latch a later entry could prove stale needs a clock, and under a program that owns the timer the BIOS tick does not move; `resume` from the stop instead.

**A stopped machine is run by retraces until the stub takes each command.** An input sent while the guest runs lands at whatever instant the wall clock delivers it, which no replay can find again. Sent to a parked machine, each command goes down the link and the machine runs one retrace at a time until the stub acknowledges it, the commands a BIOS tick of the guest's own clock apart, and it is left stopped at a retrace: the reply counts those retraces in `polls`, as `run_for` does, and carries the stop, its `frame` among it and its `e9` holding what the guest wrote on every retrace (the watches as the last one read them), so a session's export keeps the input as a step its replay holds to. A declared code breakpoint that stops one of those retraces ends the post there (`wait_stopped`, with the commands acknowledged before it in); a change-watch's or an interrupt breakpoint's stop cannot be told from a retrace, as with `run_for`, and counts as one. An `expect` is then waited for the same way, a retrace per look, and its `seconds` are the guest's own, so a replay that misses runs the same retraces the session did.

Each command is a numbered, checked frame, acknowledged on the same link before the next goes, so the guest sets the pace; a lost byte is sent again, a lost acknowledgement never runs a command twice. The pointer's report comes back on the serial link, never on the E9, where it could land inside a line the program was writing.

The conf owes the route one line: its autoexec runs the stub before the program. A session started with `program` needs none: `start` loads the stub itself, on the first drive from Y: down that `[autoexec]` does not mount (a conf mounting them all is refused). A conf that configures `serial1` itself loses it to the route.

The stub announces itself on the E9 (`STUB  . scry device=present proto=7 motion=1`), and the first input refuses (`no_channel`) when that line is missing or the protocol differs, because an older stub would read the frames as other commands. `motion` says whether the build's device takes relative motion (below). Without a `logfile` there is no line to read and input goes out on the conf's word.

## An input that went in is not one the program took

`expect` tells them apart: a modal popup can capture the cue key while the post succeeds. A miss is `TIMEOUT` beside the post, because a swallowed key and a key never sent are different facts; in a `perform` or a `drive` act it ends the list there.

- **The pattern is matched against what the program literally writes**, so read its log once first: a program logging `key down x mods=4` for alt+x and `key down SPACE` for space is telling you its case.
- **A machine that stopped during the wait** is refused `wait_stopped`. A command sent before the stop waits in the serial buffer and lands at the next resume; the ones after it are not sent, so a key whose make parked the machine (at an INT 9 breakpoint, say) stays down until a later post releases it. Whether it landed before the stop is the guest's log to say (a key can go in and its own reaction produce the stop), so `log` since the post is the judge. The pointer's read-back follows the button by a BIOS tick, and a program reacts within a frame, so a code breakpoint on what the click triggers fires before the read-back and the call ends `wait_stopped` from a parked machine and a running one alike (in a `perform`, that step is `step_failed`).
- **An emulator that died** is `verify.checked: false`, never "the program swallowed it"; a program that writes no instrumentation gives `expect` nothing to confirm against.
- **The mark cannot bracket the post itself** (the stub carries a frame the moment it is whole): a line the guest writes in that window is served with `seen_before_waiting: true` as the tell. The field is not called `already`, which would read as "it happened before the key was sent".

<!-- scry-reference:begin send_keys -->
## `send_keys`

*Send keystrokes*

```text
send_keys(keys, modifiers=null, expect="", seconds=null, action="press")
```

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

| argument | type | default |
|---|---|---|
| `keys` | array of string | required |
| `modifiers` | array of string (matching `^([sS][hH][iI][fF][tT]\|[cC][tT][rR][lL]\|[cC][oO][nN][tT][rR][oO][lL]\|[aA][lL][tT]\|[oO][pP][tT][iI][oO][nN])$`) or null | `null` |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |
| `action` | one of `"press"`, `"down"`, `"up"` | `"press"` |

| reply field | type |
|---|---|
| `cause` | string |
| `regpoint_hit` | object |
| `cpu_mode` | string or object |
| `e9` | object |
| `frame` | integer or object |
| `instruction` | DosboxInstruction |
| `pc` | string or object |
| `polls` | integer |
| `regs` | object |
| `stop_seq` | integer |
| `watches` | array |
| `bytes` | integer |
| `delivered` | boolean |
| `frames` | integer |
| `keys` | array |
| `modifiers` | array |
| `posted` | integer |
| `route` | string |
| `verify` | object |

Example, from a live run:

```json
{
  "keys": ["a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a", "a"]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified",
  "status": "ok",
  "keys": ["a", "a", "a", "a", "a", "a", "... 58 more"],
  "modifiers": [],
  "route": "guest",
  "posted": 64,
  "bytes": 128,
  "frames": 128,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  }
}
```
<!-- scry-reference:end send_keys -->

**A key sent while a dialog is closing can be swallowed.** To send it after the screen has settled: `stop` the machine, `run_for` a few frames, read `screen_signature`, and repeat until two reads in a row agree; then send the key, which a stopped machine takes retrace by retrace. A stopped machine's guest time only moves when `run_for` moves it, so the wait costs no guest seconds and a wrong key is never sent to a screen still changing.

`send_keys` composes scan code set 1 on the host; a DOS keyboard has no command key, and `cmd` is refused by name. The 64-key ceiling is because every scan byte is a frame, a BIOS tick after the last, under the session's lock. A key sent to a stopped machine runs it by retraces until the stub takes it (The route, above), rather than leaving the bytes to land at the next resume. A cancelled call releases any key it had pressed and not yet released (an extended key's break repeats its prefix), so none is left down repeating in the guest; a mouse button a cancelled call pressed is not released, since `action="down"` holds one on purpose.

**A send while the emulator is inside a long host call** (a DOS file or device operation it waits on, such as the first long-name open in a folder of very many entries) meets a debugger channel that does not answer. A call that meets it before writing anything answers `host_failed` with `delivered: false`: nothing went into the guest, so sending it again puts it in once. `status` fails while the host call lasts and answers again at once when it ends, which is when to send.

A stop during the `expect` wait is INVALID (`wait_stopped`) with `last_stop`. `verify` also carries `line`, `note`, `waited_s`, `seen_before_waiting`, `lines_before`, `lines_total` and, on a `TIMEOUT`, `arrived_during`; `checked: false` when no `expect` was given. With no `logfile` there is no stub announce to read, so the keys go out unchecked.

<!-- scry-reference:begin send_mouse -->
## `send_mouse`

*Send mouse input*

```text
send_mouse(x=null, y=null, button="", action="", units="screen", expect="", seconds=null, target="", to_x=null, to_y=null)
```

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

| argument | type | default |
|---|---|---|
| `x` | integer (>= 0, <= 32767) or null | `null` |
| `y` | integer (>= 0, <= 32767) or null | `null` |
| `button` | one of `""`, `"left"`, `"right"`, `"middle"` | `""` |
| `action` | one of `""`, `"click"`, `"double"`, `"triple"`, `"down"`, `"up"`, `"drag"` | `""` |
| `units` | one of `"screen"`, `"mouse"` | `"screen"` |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |
| `target` | string | `""` |
| `to_x` | integer (>= 0, <= 32767) or null | `null` |
| `to_y` | integer (>= 0, <= 32767) or null | `null` |

| reply field | type |
|---|---|
| `cause` | string |
| `regpoint_hit` | object |
| `cpu_mode` | string or object |
| `e9` | object |
| `frame` | integer or object |
| `instruction` | DosboxInstruction |
| `pc` | string or object |
| `polls` | integer |
| `regs` | object |
| `stop_seq` | integer |
| `watches` | array |
| `action` | string |
| `arrived` | boolean |
| `asked` | object |
| `button` | string |
| `delivered` | boolean |
| `driver_arrived` | boolean |
| `identified_at_stop` | integer or object |
| `motion` | boolean or object |
| `pointer` | object |
| `route` | string |
| `screen` | string |
| `target` | string |
| `units` | string |
| `verify` | object |
| `x` | integer |
| `y` | integer |

Example, from a live run:

```json
{
  "x": 0,
  "y": 0
}
```

```json
{
  "summary": "send_mouse: pointer at 0,0, program's own pointer not read; no button pressed; posted, unverified",
  "status": "ok",
  "x": 0,
  "y": 0,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {"x": 0, "y": 0, "width": 80, "height": 25},
    "mouse": {"x": 0, "y": 0, "max_x": 639, "max_y": 199},
    "buttons": [],
    "bios_mode": "0x03"
  },
  "driver_arrived": true,
  "motion": true,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  }
}
```
<!-- scry-reference:end send_mouse -->

**The pointer is moved, then set.** Many games never ask where the pointer is: they read the driver's motion counters (INT 33h AX=0Bh), take its movement events (a handler installed with AX=0Ch), or drive a PS/2 mouse of their own through the BIOS. Setting the pointer (AX=04h) moves none of them, and DOSBox-X counts the host's motion only while the host mouse is captured, which no session does. So the stub first injects the move as relative motion through the integration device, in steps of a signed byte in the driver's units, which reaches a PS/2 mouse the program drives or, with none, the counters, the movement events and the position, whether or not anything is captured; AX=04h then lands the pointer exactly (a PS/2 mouse gets the motion as DOSBox-X scales it for its resolution, so a step of a few units can reach it as none), and the reply reports the guest's answer rather than rounding it away: a text mode snaps to its cell and a program's own range clamps. `motion` is `true` when the move went in as motion too; a build whose device takes none (the stub asks it once, at load) places the pointer only, and `motion` says why a program that reads motion saw nothing.

**Not reached:** a mouse driver loaded inside the guest, which reads its own hardware rather than DOSBox-X's driver.

`target` is explained in [Screen maps](files.md#screen-maps).

`pointer` carries `screen` (`x`, `y`, `width`, `height`; unavailable in an unmapped mode), `mouse` (`x`, `y`, `max_x`, `max_y`), `buttons`, `bios_mode`, under a VBE mode `vbe_mode`, and under a map that declares the program's pointer `program` (`x`, `y`, `corrections` before the press, and `reach` when it did not arrive after the sweep; unavailable, saying why, when it was not read). `screen` units are character cells in a text mode and pixels in a graphics one. Under a VBE mode the BIOS mode byte holds the emulated card's own number, which says nothing portable, so the stub asks VBE itself for the mode and its resolution (INT 10h 4F03h, 4F01h) and the units are that resolution, in pixels or, for a VBE text mode, in cells. Each unit is a span of the driver's coordinates: the move aims at the middle of the span, because the driver rounds to its own granularity and a program divides its range back out (Deluxe Paint sets eight coordinates a pixel and divides by eight), so the span's first coordinate can land in the unit before. `arrived` is judged in the units asked: any coordinate in the span is the unit, and it is false when the driver's rounding or a program's own range put the pointer in another one; `asked` then gives the driver coordinates sent. A move steered by the program's own pointer is judged by that pointer instead (Screen maps, *A program that keeps a pointer of its own*). It is only said when something judged the move: the program's own pointer (a map that declares it) or the driver's own coordinates (`units="mouse"`). A screen-unit move nothing judged answers `driver_arrived` instead, which is where the DRIVER is and no more. `double` and `triple` are two and three clicks a tick apart, close enough for a program that counts them; a button with no `x`, `y` acts where the pointer is, and a move and a button in one call move first. A read-back that fails after the commands went in is INVALID with `delivered: true`, so nothing is sent twice. With no `logfile` the mouse goes in unchecked.

**The driver's pointer is the one placed.** A program that keeps its own pointer from the motion counters alone moves with the motion but never reads the driver's position, so its pointer starts where it already was and stops at the edge of its own range: without a screen map that declares where the program keeps its own pointer (Screen maps, *A program that keeps a pointer of its own*) the reply can only say `driver_arrived`. With that map, when the aim is past what the driver's range lets the program's pointer reach, the range is widened once through the stub and `range_widened` says so in every reply's `session` block from then on. Allegro's default DOS mouse driver works that way; with `mouse = I33` in the program's `allegro.cfg` it reads the driver and sets the range to its screen, eight coordinates a pixel, and is pointed at by pixel like any other.
