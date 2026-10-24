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

Send KEYSTROKES into the RUNNING guest, inside the machine, and, with `expect`, PROVE
the program took them. The wait for the reaction reports its progress.

Arguments: `keys`, key names (`a`, `1`, `enter`, `esc`, `space`, `up`, `f1`..`f12`,
punctuation names), at most 64 per call; `modifiers` (`shift`, `ctrl`, `alt`), held
across them; `expect`, a regex over the guest's E9 log that only the program's REACTION
writes, waited for up to `seconds` (default 10).

Refused before anything is sent: an unknown key or modifier name; `seconds` without
`expect`; a machine stopped at the debugger (the keys would land at the next resume); a
guest whose log shows no stub announce, or an older stub (`no_channel`, naming the conf
line); with no `logfile` there is no announce to read and the keys go out.

Reply: `route: "guest"`, `posted`, `bytes`, `ticks`, and `verify`: `verdict` `TARGET`
with `seen`, `line`, `waited_s`, `seen_before_waiting`, `lines_before`, `lines_total`, or
`TIMEOUT` (a miss, the program did not react) with `arrived_during` and a `note`; or
`checked: false` with no `expect`. A stop that lands DURING the wait is INVALID
(`wait_stopped`) with `last_stop`. Timing is "now", on a running guest.

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
    "a",
    "a",
    "a",
    "a",
    "a",
    "a",
    "... 58 more"
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
  "ticks": 128,
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  }
}
```
<!-- scry-reference:end send_keys -->

`send_keys` composes scan code set 1 on the host; a DOS keyboard has no command key, and `cmd` is refused by name. The 64-key ceiling is because every scan byte waits a timer tick under the session's lock. A key sent to a stopped machine is refused because the bytes would land, unannounced, at the next resume.

<!-- scry-reference:begin send_mouse -->
## `send_mouse`

*Send mouse input*

```text
send_mouse(x=null, y=null, button="", action="click", units="screen", expect="", seconds=null, target="")
```

Move the guest's MOUSE POINTER and press its buttons, inside the machine, and read the
pointer back. With `expect`, PROVE the program reacted, as `send_keys` does.

`x`, `y`: where the pointer goes, both or neither, in `units`: `screen` (default), the
screen's own units as `screen_view` counts them (character cells in a text mode, pixels in
a graphics one; the standard BIOS modes), or `mouse`, the DOS driver's own coordinates (for
a VESA or custom mode). `target`: instead of `x`, `y`, a control of the screen the latest
`map_find` matched, its centre in `screen` units. `button` and `action` (`double`: two
clicks a tick apart; a drag is `down`, a move, `up`). A button with no `x`, `y` acts where the
pointer is, so `down` alone holds it for the calls that follow. A move and a button in one
call: the move goes first.

Refused before anything is sent: no move and no button, half a move, a place off the
screen or outside the driver's range, `screen` units in a mode this server does not map, a
stopped machine, no stub (with no `logfile` there is no announce to read and the mouse goes in).
A `target` beside `x`, `y` or `units="mouse"` (`bad_argument`); no `map_find` match since
the start, or a guest no longer showing that screen's kind and size (`needs_call`); a
control that screen lacks (`unknown_ref`).

Reply: `route` (`guest`), `pointer` read back (`screen` with `x`, `y`,
`width`, `height`, or unavailable in an unmapped mode; `mouse` with the driver's `x`, `y`,
`max_x`, `max_y`; `buttons` held; `bios_mode`), `arrived` (the read-back is where it was
asked; when it is not, `asked` says where in the driver's coordinates: a text mode snaps to
its cell, a program's own range clamps), the arguments, `verify` as `send_keys`'; with a
`target`, `target`, `screen` and `identified_at_stop` (`map_find`'s stop). A
read-back that fails after the commands went in is INVALID with `delivered: true`, so
nothing is sent twice.

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
  "verify": {
    "checked": false,
    "why": "no `expect` was given, so the reply says what went into the guest and NOT that the program took it; pass expect=<E9 pattern> to confirm its reaction"
  }
}
```
<!-- scry-reference:end send_mouse -->

**The pointer is set and read back, not moved.** The device's motion registers feed DOSBox-X's relative motion, which the driver scales by its mickey ratio and sensitivity, so one delta lands at a different distance per mode and axis. INT 33h AX=04h places the pointer where asked, and the reply reports the guest's answer rather than rounding it away: a text mode snaps to its cell and a program's own range clamps.

**Not reached:** a mouse driver loaded inside the guest, a program reading the PS/2 port directly, and one reading the driver's motion counters (INT 33h AX=0Bh): setting the pointer produces no motion, and DOSBox-X counts motion only while the host mouse is captured.

`target` is explained in [Screen maps](files.md#screen-maps).

<!-- scry-reference:begin drive -->
## `drive`

*Drive an input and verify it*

```text
drive(act, expect="", seconds=null, pattern=".", limit=40, settle_seconds=30.0, summaries=false)
```

LOOK, ACT, VERIFY in one call: the way a browser is driven, for a DOS program. The
waits inside (for a stop between steps, for `expect`) report their progress.

The E9 log is MARKED first; `act` (a list of steps in `perform`'s vocabulary, typically
`send_keys`/`send_mouse` each with its own `expect`) runs with `perform`'s rules; with
`expect` (a regex; empty for none) the call then waits up to `seconds` (default
5, at most 600) for a NEW matching line from that mark, the act's
overall effect; and `looked.guest` is what the guest wrote since the mark, filtered by
`pattern` (a regex) and cut to the LAST `limit`: `pattern`
only filters what is SHOWN and proves nothing, so it is never the `expect`. An act that
ended stopped at the debugger has the log read once, not waited on: a stopped guest cannot
write. `settle_seconds` and `summaries` are `perform`'s. `seconds` with no `expect` is
refused. Needs a session with `logfile`.

Reply: `act` (`ran`, `steps_completed`, `failed_at`, `failed` when a step did, `perform`'s
tail), `verify` (`checked`; `verdict` `TARGET` with `seen`, `line`, `seen_before_waiting`,
`lines_before`, `waited_s`, `lines_total`, or `TIMEOUT`, the expectation not met, with
`arrived_during` and a `note`; `checked: false` with `why` when no `expect` was given;
`available: false` when `act.verdict` is `TIMEOUT`), and `looked.guest` (`lines_written`,
`lines_total`, `truncated`, `lines`, `since_mark`, `pattern`). INVALID with the same `act`,
`verify` and `looked` when a step failed (`step_failed`), when the act itself was refused or
its emulator went (its own code: `not_stopped`, `session_broken`, `diverged`...), when a
stopped machine lacks the line (`wait_stopped`), or when the verify itself refused (its
`code`). No screen in the look: a still is `capture_frame`.

`checked` is whether a check ran at all, `seen` whether the line arrived; neither is
`verified`, which everywhere else means a readback equal to what was sent.

| argument | type | default |
|---|---|---|
| `act` | array of object | required |
| `expect` | string | `""` |
| `seconds` | number (> 0, <= 600.0) or null | `null` |
| `pattern` | string | `"."` |
| `limit` | integer (>= 1, <= 400) | `40` |
| `settle_seconds` | number (>= 0, <= 600.0) | `30.0` |
| `summaries` | boolean | `false` |

- `summaries`: True keeps a long list readable (an argument of the call, never of a step): each step but the one the list ended on becomes a compact row (a failed one stays whole under `failed`); `ran` shows the first 24 (`truncated`, of `steps_total`), `ran_path` and `replies_path` hold all, and `stops` counts the stops.

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
          "pid": 42881,
          "conf": "$TMPDIR/dosbox-x-live-job-tcl53hm5/A/tests/guest/probe.conf",
          "conf_digest": "78bdc38f360b9b4a",
          "conf_changed_on_disk": false,
          "watched": false,
          "bound_s": 1200,
          "elapsed_s": 54.8,
          "terminal_bytes_dropped": 0,
          "drain_alive": true,
          "captures": "off",
          "state_dir": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n632-save",
          "last_stop": {
            "stop_seq": 9,
            "pc": "0814:00000130",
            "cause": "no declared code breakpoint at 0814:00000130: the debugger keeps no hit flag and a memory watch stops at the instruction that wrote, so which declaration fired cannot be told",
            "since_s": 8.8,
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
  },
  "verify": {
    "checked": false,
    "why": "no `expect` given; the act's own steps carried whatever verification they asked for"
  },
  "looked": {
    "guest": {
      "available": true,
      "since_mark": 36825,
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
