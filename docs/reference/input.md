# The Input tools

Every input goes in inside the machine and nothing about the host is touched ([REFERENCE.md, Input and the screen](../../REFERENCE.md#input-and-the-screen)). A `send_mouse` `target` is a control of a [screen map](files.md#screen-maps).

### The route

The emulator's COM1 is a TCP client of a port the session listens on (`input_port`; transparent, so a byte 0xFF is data) and DOSBox-X's integration device is switched on, both as `-set` overrides the conf need not carry. A resident stub, `guest/INJECT.COM` (its header is the protocol), takes one command off the socket per timer tick, the 8042's own pace, and carries it out in the guest.

Each command is a numbered, checked frame, acknowledged on the same link before the next goes, so the guest sets the pace; a lost byte is sent again, a lost acknowledgement never runs a command twice. The pointer's report comes back on the serial link, never on the E9, where it could land inside a line the program was writing.

The conf owes the route one line: its autoexec runs the stub before the program. A session started with `program` needs none: `start` loads the stub itself, on the first drive from Y: down that `[autoexec]` does not mount (a conf mounting them all is refused). A conf that configures `serial1` itself loses it to the route.

The stub announces itself on the E9 (`STUB  . inject device=present proto=3`), and the first input refuses (`no_channel`) when that line is missing or the protocol differs, because an older stub would read the frames as other commands. Without a `logfile` there is no line to read and input goes out on the conf's word.

### An input that went in is not one the program took

`expect` tells them apart: a modal popup can capture the cue key while the post succeeds. A miss is `TIMEOUT` beside the post, because a swallowed key and a key never sent are different facts; in a `perform` or a `drive` act it ends the list there.

- **The pattern is matched against what the program literally writes**, so read its log once first: a program logging `key down x mods=4` for alt+x and `key down SPACE` for space is telling you its case.
- **A machine that stopped during the wait** is refused `wait_stopped`. An undelivered key waits in the serial buffer and lands at the next resume. Whether it landed before the stop is the guest's log to say (a key can go in and its own reaction produce the stop), so `log` since the post is the judge.
- **An emulator that died** is `verify.checked: false`, never "the program swallowed it"; a program that writes no instrumentation gives `expect` nothing to confirm against.
- **The mark cannot bracket the post itself** (one command per tick): a line the guest writes in that window is served with `seen_before_waiting: true` as the tell. The field is not called `already`, which would read as "it happened before the key was sent".

<!-- scry-reference:begin send_keys -->
## `send_keys`

*Send keystrokes*

```text
send_keys(keys, modifiers=null, expect="", seconds=null)
```

Send keystrokes to the running guest; with `expect`, prove the program took them.

`keys`: at most 64. `expect`: a regex over the E9 log the program's
reaction writes, waited up to `seconds` (default 10).

Refused: an unknown key or modifier, `seconds` without `expect`, a stopped machine, no
stub (`no_channel`).

Reply: `route`, `posted`, `bytes`, `ticks`, `verify` (`verdict` `TARGET` or `TIMEOUT`,
`seen`).

Reference: REFERENCE.md, Input and the screen.

| argument | type | default |
|---|---|---|
| `keys` | array of string | required |
| `modifiers` | array of string (matching `^([sS][hH][iI][fF][tT]\|[cC][tT][rR][lL]\|[cC][oO][nN][tT][rR][oO][lL]\|[aA][lL][tT]\|[oO][pP][tT][iI][oO][nN])$`) or null | `null` |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |

| reply field | type |
|---|---|
| `bytes` | integer |
| `delivered` | boolean |
| `keys` | array |
| `modifiers` | array |
| `posted` | integer |
| `route` | string |
| `ticks` | integer |
| `verify` | object |

Example, from a live run:

```json
{
  "keys": [
    "a"
  ]
}
```

```json
{
  "summary": "send_keys: INVALID (no_session), there is no live session. `start` one first; a reply from a dead session would be a reading of nothing.",
  "status": "INVALID",
  "code": "no_session",
  "message": "there is no live session. `start` one first; a reply from a dead session would be a reading of nothing."
}
```
<!-- scry-reference:end send_keys -->

`send_keys` composes scan code set 1 on the host; a DOS keyboard has no command key, and `cmd` is refused by name. The 64-key ceiling is because every scan byte waits a timer tick under the session's lock. A key sent to a stopped machine is refused because the bytes would land, unannounced, at the next resume.

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
instead of `x`, `y`. A drag is `down`, a move, `up`.

Refused: no move and no button, half a move, a place off the screen, a stopped machine, no
stub; `target` beside `x`, `y` or `units="mouse"` (`bad_argument`); no `map_find` match
(`needs_call`); an unknown control (`unknown_ref`).

Reply: `route`, `pointer`, `arrived` (else `asked`), `verify`; with `target`: `target`,
`screen`, `identified_at_stop`.

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
| `action` | string |
| `arrived` | boolean |
| `asked` | object |
| `button` | string |
| `delivered` | boolean |
| `identified_at_stop` | integer or object |
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
  "button": "left"
}
```

```json
{
  "summary": "send_mouse: INVALID (no_session), there is no live session. `start` one first; a reply from a dead session would be a reading of nothing.",
  "status": "INVALID",
  "code": "no_session",
  "message": "there is no live session. `start` one first; a reply from a dead session would be a reading of nothing."
}
```
<!-- scry-reference:end send_mouse -->

**The pointer is set and read back, not moved.** The device's motion registers feed DOSBox-X's relative motion, which the driver scales by its mickey ratio and sensitivity, so one delta lands at a different distance per mode and axis. INT 33h AX=04h places the pointer where asked, and the reply reports the guest's answer rather than rounding it away: a text mode snaps to its cell and a program's own range clamps.

**Not reached:** a mouse driver loaded inside the guest, a program reading the PS/2 port directly, and one reading the driver's motion counters (INT 33h AX=0Bh): setting the pointer produces no motion, and DOSBox-X counts motion only while the host mouse is captured.

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
  },
  "verify": {
    "checked": false,
    "why": "no `expect` given; the act's own steps carried whatever verification they asked for"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": 37703,
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
