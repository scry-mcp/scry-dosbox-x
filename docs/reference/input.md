# The Input tools

Every input goes in inside the machine and nothing about the host is touched ([REFERENCE.md, Input and the screen](../../REFERENCE.md#input-and-the-screen)). A `send_mouse` `target` is a control of a [screen map](files.md#screen-maps).

### The route

The emulator's COM1 is a TCP client of a port the session listens on (`input_port`; transparent, so a byte 0xFF is data) and DOSBox-X's integration device is switched on, both as `-set` overrides the conf need not carry. A resident stub, `guest/SCRY.COM` (its header is the protocol), takes each command off the socket on the UART's own interrupt and carries it out in the guest. A game that takes the timer for itself (INT 08h with no chain to the BIOS, so INT 1Ch never runs again) still gets its input this way, unless it also masks IRQ 4 at the PIC. The host sends the commands a BIOS tick apart, so a game that reads its keys once a frame sees the make before the break.

**A stopped machine is run by retraces until the stub takes each command.** An input sent while the guest runs lands at whatever instant the wall clock delivers it, which no replay can find again. Sent to a parked machine, each command goes down the link and the machine runs one retrace at a time until the stub acknowledges it, the commands a BIOS tick of the guest's own clock apart, and it is left stopped at a retrace: the reply counts those retraces in `polls`, as `run_for` does, and carries the stop, its `frame` among it and its `e9` holding what the guest wrote on every retrace (the watches as the last one read them), so a session's export keeps the input as a step its replay holds to. A declared code breakpoint that stops one of those retraces ends the post there (`wait_stopped`, with the commands acknowledged before it in); a change-watch's or an interrupt breakpoint's stop cannot be told from a retrace, as with `run_for`, and counts as one. An `expect` is then waited for the same way, a retrace per look, and its `seconds` are the guest's own, so a replay that misses runs the same retraces the session did.

Each command is a numbered, checked frame, acknowledged on the same link before the next goes, so the guest sets the pace; a lost byte is sent again, a lost acknowledgement never runs a command twice. The pointer's report comes back on the serial link, never on the E9, where it could land inside a line the program was writing.

The conf owes the route one line: its autoexec runs the stub before the program. A session started with `program` needs none: `start` loads the stub itself, on the first drive from Y: down that `[autoexec]` does not mount (a conf mounting them all is refused). A conf that configures `serial1` itself loses it to the route.

The stub announces itself on the E9 (`STUB  . scry device=present proto=5 motion=1`), and the first input refuses (`no_channel`) when that line is missing or the protocol differs, because an older stub would read the frames as other commands. `motion` says whether the build's device takes relative motion (below). Without a `logfile` there is no line to read and input goes out on the conf's word.

### An input that went in is not one the program took

`expect` tells them apart: a modal popup can capture the cue key while the post succeeds. A miss is `TIMEOUT` beside the post, because a swallowed key and a key never sent are different facts; in a `perform` or a `drive` act it ends the list there.

- **The pattern is matched against what the program literally writes**, so read its log once first: a program logging `key down x mods=4` for alt+x and `key down SPACE` for space is telling you its case.
- **A machine that stopped during the wait** is refused `wait_stopped`. A command sent before the stop waits in the serial buffer and lands at the next resume; the ones after it are not sent, so a key whose make parked the machine (at an INT 9 breakpoint, say) stays down until a later post releases it. Whether it landed before the stop is the guest's log to say (a key can go in and its own reaction produce the stop), so `log` since the post is the judge.
- **An emulator that died** is `verify.checked: false`, never "the program swallowed it"; a program that writes no instrumentation gives `expect` nothing to confirm against.
- **The mark cannot bracket the post itself** (the stub carries a frame the moment it is whole): a line the guest writes in that window is served with `seen_before_waiting: true` as the tell. The field is not called `already`, which would read as "it happened before the key was sent".

<!-- scry-reference:begin send_keys -->
## `send_keys`

*Send keystrokes*

```text
send_keys(keys, modifiers=null, expect="", seconds=null)
```

Send keystrokes to the guest; with `expect`, prove the program took them.

`keys`: at most 64. `expect`: a regex over the E9 log the program's
reaction writes, waited up to `seconds` (default 10). A stopped machine is
run retrace by retrace until the stub takes each key, and left stopped at a retrace; its
`expect` waits `seconds` of the guest's own time.

Refused: an unknown key or modifier, `seconds` without `expect`, no stub, a stopped
machine on a build with no `RUNSTATE` (`no_channel`).

Reply: `route`, `posted`, `bytes`, `frames` (stub commands, a BIOS tick apart), `verify`
(`verdict` `TARGET` or `TIMEOUT`, `seen`); from a stopped machine `polls` and the stop
it was left at (the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, `watches`, `cause` and `e9`).

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `keys` | array of string | required |
| `modifiers` | array of string (matching `^([sS][hH][iI][fF][tT]\|[cC][tT][rR][lL]\|[cC][oO][nN][tT][rR][oO][lL]\|[aA][lL][tT]\|[oO][pP][tT][iI][oO][nN])$`) or null | `null` |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `frame` | integer or object |
| `instruction` | object |
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
  "keys": [
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "a"
  ]
}
```

```json
{
  "summary": "send_keys (guest): posted, unverified",
  "status": "ok",
  "keys": [
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "... 58 more"
  ],
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

`send_keys` composes scan code set 1 on the host; a DOS keyboard has no command key, and `cmd` is refused by name. The 64-key ceiling is because every scan byte is a frame, a BIOS tick after the last, under the session's lock. A key sent to a stopped machine runs it by retraces until the stub takes it (The route, above), rather than leaving the bytes to land, unannounced, at the next resume.

A stop during the `expect` wait is INVALID (`wait_stopped`) with `last_stop`. `verify` also carries `line`, `note`, `waited_s`, `seen_before_waiting`, `lines_before`, `lines_total` and, on a `TIMEOUT`, `arrived_during`; `checked: false` when no `expect` was given. With no `logfile` there is no stub announce to read, so the keys go out unchecked.

<!-- scry-reference:begin send_mouse -->
## `send_mouse`

*Send mouse input*

```text
send_mouse(x=null, y=null, button="", action="click", units="screen", expect="", seconds=null, target="")
```

Move the guest's mouse pointer, press buttons, and read the pointer back; `expect`
proves the program reacted, as in `send_keys`.

`x`, `y`: both or neither, in `units`. `target`: a control of the latest `map_find` screen,
instead of `x`, `y`. A drag is `down`, a move, `up`. A stopped machine is run as for
`send_keys`.

Refused: no move and no button, half a move, a place off the screen, no stub, a stopped
machine with no `RUNSTATE`; `target` beside `x`, `y` or `units="mouse"` (`bad_argument`);
no `map_find` match (`needs_call`); an unknown control (`unknown_ref`).

Reply: `route`, `pointer`, `arrived` (else `asked`), `motion` (a move reached the motion
counters too), `verify`; with `target`: `target`, `screen`, `identified_at_stop`; from a
stopped machine, `send_keys`' `polls` and stop.

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `x` | integer (>= 0, <= 32767) or null | `null` |
| `y` | integer (>= 0, <= 32767) or null | `null` |
| `button` | one of `""`, `"left"`, `"right"`, `"middle"` | `""` |
| `action` | one of `"click"`, `"double"`, `"down"`, `"up"` | `"click"` |
| `units` | one of `"screen"`, `"mouse"` | `"screen"` |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |
| `target` | string | `""` |

| reply field | type |
|---|---|
| `cause` | string |
| `cpu_mode` | string or object |
| `e9` | object |
| `frame` | integer or object |
| `instruction` | object |
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
  "summary": "send_mouse: pointer at 0,0; posted, unverified",
  "status": "ok",
  "x": 0,
  "y": 0,
  "units": "screen",
  "route": "guest",
  "pointer": {
    "screen": {
      "x": 0,
      "y": 0,
      "width": 80,
      "height": 25
    },
    "mouse": {
      "x": 0,
      "y": 0,
      "max_x": 639,
      "max_y": 199
    },
    "buttons": [],
    "bios_mode": "0x03"
  },
  "arrived": true,
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

`pointer` carries `screen` (`x`, `y`, `width`, `height`; unavailable in an unmapped mode), `mouse` (`x`, `y`, `max_x`, `max_y`), `buttons`, `bios_mode`. `arrived` is false when a text mode snaps to its cell or a program's own range clamps; `asked` then gives the driver coordinates. `screen` units are character cells in a text mode and pixels in a graphics one. `double` is two clicks a tick apart; a button with no `x`, `y` acts where the pointer is, and a move and a button in one call move first. A read-back that fails after the commands went in is INVALID with `delivered: true`, so nothing is sent twice. With no `logfile` the mouse goes in unchecked.

<!-- scry-reference:begin drive -->
## `drive`

*Drive an input and verify it*

```text
drive(act, expect="", seconds=null, pattern=".", limit=40, settle_seconds=30.0, summaries=false)
```

Look, act and verify in one call. Marks the E9 log, runs `act` (steps in `perform`'s
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
    {
      "op": "status"
    }
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
          "pid": 18391,
          "conf": "$TMPDIR/dosbox-x-live-job-vpw7rzm6/A/tests/guest/probe.conf",
          "conf_digest": "78bdc38f360b9b4a",
          "bound_s": 1200,
          "elapsed_s": 4.3,
          "captures": "off",
          "state_dir": "$TMPDIR/dosbox-x-live-matrix-82ee6fdd8370/jobs-scratch/A/n962-save",
          "last_stop": {
            "stop_seq": 11,
            "pc": "0814:00000130",
            "cause": "the retrace run_for ran to, at 0814:00000130",
            "since_s": 0.1,
            "wall_at": "2026-10-27T06:58:03+00:00"
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
            "watches": 0,
            "regpoints": 0
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
  },
  "verify": {
    "checked": false,
    "why": "no `expect` given; the act's own steps carried whatever verification they asked for"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": 99428,
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
