"""The INPUT routes: a keystroke or a mouse event to the running guest, and the proof it landed.

Two routes carry keys: the serial socket to the resident stub (`guest/INJECT.COM`, scan
bytes one per timer tick, no window) and a host event to the emulator's window (brought
frontmost through Accessibility). The mouse has the window route only. Whichever route
posts, the proof is the same: a regex over the guest's E9 log that only the program's
reaction writes, waited for from a mark taken BEFORE the post (`_post_and_verify`).

`send_keys` and `send_mouse` have their bodies here; their contracts stay with the
registrations in `dosbox_x_server`.
"""

from __future__ import annotations

from typing import Any, cast

import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE


def _require_window(session: ds.Session, tool: str) -> None:
    """The driver's ACT half needs a WINDOW -- on the window route. A host key or mouse
    event reaches the guest only through the emulator's on-screen surface, so a headless
    (`videodriver=dummy`) session has nothing to receive it. Refused here, named, rather
    than posting into a void that reports success. Start the session `mode="shared"` to
    drive input into it, or with `input_port` for the serial route, which needs no window."""
    if session.launch.input_port is not None:
        return
    if not session.launch.watched:
        raise ds.Invalid("no_channel",
            f"{tool} needs a windowed session: a host input event reaches the guest through "
            f"the emulator's on-screen window, and a headless session has none. Start with "
            f"mode='shared' (and the placement flags), or with input_port= for the serial "
            f"route, to send input")


# SCAN CODE SET 1 MAKE CODES, by the mapper-style names `send_keys` takes (the same names the
# window route's helper knows, so a caller says the same thing on either route). An extended
# key carries the E0 prefix; the break code of a byte is the byte with bit 7 set, and the
# stub injects whatever it is handed, one byte per tick, so the sequence is composed HERE.
SCAN_SET1: dict[str, tuple[int, ...]] = {
    "escape": (0x01,), "esc": (0x01,),
    "1": (0x02,), "2": (0x03,), "3": (0x04,), "4": (0x05,), "5": (0x06,), "6": (0x07,),
    "7": (0x08,), "8": (0x09,), "9": (0x0A,), "0": (0x0B,),
    "minus": (0x0C,), "equals": (0x0D,), "backspace": (0x0E,), "tab": (0x0F,),
    "q": (0x10,), "w": (0x11,), "e": (0x12,), "r": (0x13,), "t": (0x14,), "y": (0x15,),
    "u": (0x16,), "i": (0x17,), "o": (0x18,), "p": (0x19,),
    "leftbracket": (0x1A,), "rightbracket": (0x1B,),
    "return": (0x1C,), "enter": (0x1C,),
    "a": (0x1E,), "s": (0x1F,), "d": (0x20,), "f": (0x21,), "g": (0x22,), "h": (0x23,),
    "j": (0x24,), "k": (0x25,), "l": (0x26,),
    "semicolon": (0x27,), "quote": (0x28,), "grave": (0x29,), "backslash": (0x2B,),
    "z": (0x2C,), "x": (0x2D,), "c": (0x2E,), "v": (0x2F,), "b": (0x30,), "n": (0x31,),
    "m": (0x32,), "comma": (0x33,), "period": (0x34,), "slash": (0x35,),
    "space": (0x39,), "capslock": (0x3A,),
    "f1": (0x3B,), "f2": (0x3C,), "f3": (0x3D,), "f4": (0x3E,), "f5": (0x3F,), "f6": (0x40,),
    "f7": (0x41,), "f8": (0x42,), "f9": (0x43,), "f10": (0x44,), "f11": (0x57,), "f12": (0x58,),
    "home": (0xE0, 0x47), "up": (0xE0, 0x48), "pageup": (0xE0, 0x49),
    "left": (0xE0, 0x4B), "right": (0xE0, 0x4D), "end": (0xE0, 0x4F),
    "down": (0xE0, 0x50), "pagedown": (0xE0, 0x51), "insert": (0xE0, 0x52),
    "delete": (0xE0, 0x53),
}
MAX_KEYS_PER_CALL = 64    # the same cap the window route's helper carries, for the same cost
SCAN_MODIFIERS: dict[str, tuple[int, ...]] = {
    "shift": (0x2A,), "ctrl": (0x1D,), "control": (0x1D,), "alt": (0x38,), "option": (0x38,),
}


def scan_sequence(keys: list[str], mods: str) -> bytes:
    """The scan bytes a press of `keys` with `mods` held produces: every modifier's make,
    then each key's make and break, then the modifiers' breaks in reverse. An extended key's
    break repeats the E0 prefix. Unknown names are refused with nothing composed; `cmd` has
    no DOS keyboard to land on and is refused by name."""
    held: list[tuple[int, ...]] = []
    if mods != "-":
        for m in mods.split("+"):
            if m.lower() not in SCAN_MODIFIERS:
                raise ds.Invalid("bad_argument", f"the serial route knows the modifiers "
                                 f"{sorted(SCAN_MODIFIERS)}; got {m!r} (a DOS keyboard has "
                                 f"no command key)")
            held.append(SCAN_MODIFIERS[m.lower()])
    out = bytearray()
    for code in held:
        out.extend(code)
    for name in keys:
        key_code = SCAN_SET1.get(name.lower())
        if key_code is None:
            raise ds.Invalid("bad_argument",
                f"unknown key name {name!r} for the serial route; the names "
                             f"are {sorted(SCAN_SET1)}")
        out.extend(key_code)
        out.extend(key_code[:-1] + (key_code[-1] | 0x80,))
    for code in reversed(held):
        out.extend(code[:-1] + (code[-1] | 0x80,))
    return bytes(out)


def effect_seen(expect: str, reaction: dict[str, object]) -> dict[str, Any]:
    """The verified-and-seen block a post or an act hands back, ONE shape for `send_keys`,
    `send_mouse` and `drive`. `seen_before_waiting` is what `e9_wait`'s `already` means from
    a mark: the reaction was in the log when the wait first looked -- which, with the mark
    taken BEFORE the post, includes a reaction the guest wrote WHILE the key was going in.
    It is not named `already`: that reads as "it had happened before the post", and a run
    whose every reaction is stamped after its post would carry it on each.
    `lines_before` is how many lines the guest wrote between the mark and the reaction."""
    return {"checked": True, "seen": True, "expected": expect, "line": reaction["line"],
            "seen_before_waiting": reaction["already"],
            "lines_before": reaction["lines_before"],
            "waited_s": reaction["waited_s"], "lines_total": reaction["lines_total"]}


EFFECT_WAIT_DEFAULT_S = 10.0    # how long a verified post waits for the guest's reaction


def _post_and_verify(session: ds.Session, mode: str, args: list[str],
                     expect: str | None, seconds: float | None, focus: str, *,
                     progress: ds.Progress = ds.no_progress, **fields: Any) -> dict[str, Any]:
    """Post one input event and say whether the GUEST REACTED -- the two-channel half of
    the driver's ACT, shared by `send_keys` and `send_mouse`.

    A HOST EVENT THAT WAS POSTED IS NOT A KEY THAT WAS DELIVERED. Measured on a real
    session: a modal popup captured the cue key after a song load while this tool reported
    the post as a success -- a false green of exactly the shape this package is written
    against. So with `expect` (a regex over the guest's E9 log) the sequence is: MARK the
    log, post, then wait for a NEW line matching it. A line already on disk before the mark
    is history and is never served as the reaction. A miss is INVALID, saying the guest did
    not react, and it still carries `posted`/`activated`, because a swallowed key is a
    different fact from a key that was never sent.

    WHAT THE MARK CANNOT BRACKET, said rather than implied. The helper borrows the focus
    for a moment between the mark and the post, and the emulator flushes the log in its
    own time (measured on one boot: the file grows in line- or burst-sized steps, never a
    page at once, so a line the guest wrote before the mark is on disk at the mark to within
    the emulator's own flush). A line the guest writes INSIDE that window -- a key it was
    still digesting from an earlier post, a timer it logs on -- is after the mark and is
    served. `seen_before_waiting` and `waited_s` ride in `effect` so a caller can see a
    reaction that was there the instant the post returned, which is the shape of that case.

    ONLY THE EXPIRED BOUND IS THE PROGRAM'S MISS. The wait refuses for four things after
    it starts looking: `E9Expired` is the observation that nothing matched; `E9Stopped` is
    the machine at the debugger, reached while the wait looked (a breakpoint armed before
    the post fired after it; a machine already stopped is refused before the post, on both
    routes) -- reported as a miss that names the stop and where the key went, with
    `effect.stopped_during_wait` and `last_stop`, never as "the program swallowed it";
    a GONE emulator or a SHRUNK log is the instrument breaking, and comes back
    `effect.checked: False` with the wait's own words leading the reason.

    WITHOUT `expect` NOTHING IS VERIFIED, and the reply says so in `effect` rather than
    letting `posted` read as delivered. A guest that writes no instrumentation has no channel
    this can confirm through; that limit is stated, not papered over with a frame diff this
    server cannot take on a running guest (the emulator's screenshot is a mapper action).

    EVERYTHING THAT WOULD MAKE THE VERIFICATION IMPOSSIBLE IS REFUSED BEFORE THE POST -- no
    logfile, a pattern that is empty or not a regex, a wait that is not a bound, `seconds`
    with nothing to bound -- because a post cannot be taken back, and a key sent and then
    declared unverifiable is the failure with the post already spent. What this cannot
    exclude is the helper itself failing mid-post; that comes back as the helper's own
    refusal, `posted` unknown.
    """
    # WHICH ROUTE: keys take the serial route whenever the session has one; the mouse
    # takes the window route whenever the session has a window, because the serial route
    # carries keys only today. A headless session with a port and a mouse request has no
    # route at all, and the refusal names the remedy that fits THAT session.
    has_port = session.launch.input_port is not None
    serial = has_port and (mode == "keys" or not session.launch.watched)

    def post_serial() -> dict[str, Any]:
        # THE SERIAL ROUTE: the scan sequence goes down the socket and the guest's resident
        # stub injects one byte per timer tick. No window, no focus, no Accessibility: the
        # host facts of the window route do not exist here, and `route` says which route
        # answered so a caller never reads their absence as a refusal.
        if mode != "keys":
            raise ds.Invalid("no_channel",
                "the serial input route carries KEYS only today, and this "
                             "session has no window for a click or a pointer motion: start "
                             "it in mode='shared' (with the placement flags) as well")
        seq = scan_sequence(args[1:], args[0])
        sent = session.send_scancodes(seq)
        return dict(fields, route="serial", posted=len(args) - 1, bytes=sent, ticks=len(seq))

    def refused_before_posting(exc: ds.Invalid) -> dict[str, Any]:
        # THE HELPER REFUSED BEFORE ANY EVENT WENT OUT (the pointer outside the window,
        # say): a different fact from a posted event the guest ignored, and the reply
        # says so with the same fields a miss carries, `posted` at zero.
        return st.reply(**exc.reply(
            route="window", posted=0, activated=False, attempts=0,
            effect={"checked": False, "seen": False,
                    "why": "nothing was posted, so there is no reaction to wait for"},
            **fields))

    def post_host_event() -> dict[str, Any]:
        if serial:
            return post_serial()
        # `activated` is READ BACK by the helper (AX frontmost, and the window server's own
        # topmost window), not the activation request's result; `attempts` says how many
        # rounds the window server took. A helper that never got the window in front refuses
        # (exit 6) and posts nothing, which arrives here as the helper's own Invalid.
        # `restore` keeps the helper's answers apart: `done`/`failed` are AX's read-back of
        # the hand-back; `kept`/`lost` the read-back of a call asked to keep the focus;
        # `skipped` means there was nothing to hand it back to; a fact that never arrived is
        # `unknown`, never a verdict. `restored` is the plain bool: was the previous app put
        # back by THIS call (so False on a deliberate keep). `window` is the emulator's front
        # window per the window server, which a caller placing the pointer wants.
        facts = session.send_input(mode, args, keep_focus=(focus == "keep"))
        restored = facts.get("restored", "unknown")
        window = facts.get("window", "none")
        return dict(fields, route="window", posted=int(facts.get("posted", 0)),
                    activated=facts.get("activated") == "true",
                    attempts=int(facts.get("attempts", 0)),
                    restored=restored == "true",
                    restore={"true": "done", "false": "failed", "kept": "kept", "lost": "lost",
                             "skipped": "skipped"}.get(restored, "unknown"),
                    window=None if window == "none" else [int(v) for v in window.split(",")])

    check_focus(focus)
    # A STOPPED MACHINE CANNOT TAKE INPUT, on either route: on the serial route the bytes
    # would sit in the emulator's buffer and land, unannounced, at the next resume; on
    # the window route the event went to the window while the debugger held the machine
    # and whether the emulator kept it was not something this server could see, so the
    # post was reported and the reply read `ok` with no `expect`. Refused before posting,
    # naming the stop. PASSIVE, and not `where()`: on a running guest the nudge is
    # swallowed and its collect stays open for its whole timeout, and that window is
    # exactly where a stop's prompt was consumed unrecorded.
    if session.at_debugger():
        running.observe_stop(session)
        stop, where = STATE.stop_named(session)
        # A PLAIN `Invalid`, not `NotStopped`: that class names a machine that is NOT
        # stopped, and the tool layer answers it with the running-guest envelope, whose
        # `answers_while_running` would tell the caller which tools answer while the
        # guest runs, about a guest that is stopped.
        raise ds.Invalid("not_running",
            f"the machine is STOPPED at the debugger{where}, so a {mode} "
                            f"event sent now could not be taken by the guest: on the serial "
                            f"route it would sit in the buffer and land at the next resume, "
                            f"on the window route it would go to a window whose machine the "
                            f"debugger holds. `resume` first, then send")
    if expect is None:
        try:
            host = post_host_event()
        except ds.Invalid as exc:
            return refused_before_posting(exc)
        return st.reply(**host, effect={
            "checked": False,
            "why": "no `expect` was given, so `posted` says the host event went out and "
                   "NOT that the guest received it; pass expect=<E9 pattern> to confirm the "
                   "program's own reaction"})
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    try:
        mark = session.e9_mark()          # refuses a session with no logfile: no channel
    except ds.Invalid as e:
        raise ds.Invalid("bad_argument", f"`expect` cannot be checked: {e}. Refused before posting "
                         f"anything, because a post cannot be taken back") from None
    try:
        host = post_host_event()
    except ds.Invalid as exc:
        return refused_before_posting(exc)
    try:
        reaction = session.e9_wait(expect, wait_s, mark=mark, progress=progress)
    except ds.E9Stopped as e:
        # THE MACHINE IS AT THE DEBUGGER, so no reaction could arrive and the program is not
        # to blame: it STOPPED while the wait looked (a breakpoint armed before the post
        # fired after it; a machine already stopped was refused before the post). The stop
        # is surveyed once here and named when its position could be read.
        running.observe_stop(session)
        stop, where = STATE.stop_named(session)
        effect = {"checked": True, "seen": False, "expected": expect,
                  "stopped_during_wait": True, "waited_s": e.waited_s,
                  "lines_on_disk": e.arrived, "why": str(e)}
        # WHETHER THE KEY LANDED BEFORE THE STOP IS THE GUEST'S LOG'S TO SAY, not this
        # reply's: a key can go in, its own reaction produce the wrap that fires the
        # stopper, and the log carry the lines, while a reply claiming the key is still in
        # the buffer would be wrong. What is known is where an undelivered key waits.
        landing = ("whether the stub delivered the key before the stop is the guest's log's "
                   "to say (`e9` since the post); a key not delivered waits in the serial "
                   "buffer and lands at the next resume"
                   if host.get("route") == "serial" else
                   "the event went to the window while the debugger holds the machine; "
                   "whether the guest took it before the stop is its log's to say (`e9` "
                   "since the post)")
        return st.reply(status="INVALID", code="wait_stopped", **host, last_stop=stop,
                      effect=effect,
                      message=f"the {mode} event was posted ({host['posted']}) and the machine "
                             f"STOPPED at the debugger during the wait{where}, so no line "
                             f"matching {expect!r} could arrive: a stopped guest writes "
                             f"nothing. This MISS is the stop's, not the program's; {landing}")
    except ds.E9Expired as e:
        cause = ("The program may have swallowed it (a modal, a loading state)"
                 if host.get("route") == "serial" else
                 "The program may have swallowed it (a modal, a loading state) or the "
                 "window may not have had the focus at the post")
        return st.reply(status="INVALID", code="wait_expired", **host,
                      effect={"checked": True, "seen": False, "expected": expect,
                              "why": str(e)},
                      message=f"the {mode} event was posted ({host['posted']}) but the guest "
                             f"did not react: no new line matching {expect!r} within "
                             f"{wait_s}s of the post returning. {cause}; either way this "
                             f"is a MISS, not a delivery. {e}")
    except ds.Invalid as e:
        return st.reply(status="INVALID", code=e.code, **host,
                      effect={"checked": False, "expected": expect, "why": str(e)},
                      message=f"the {mode} event was posted ({host['posted']}) and its effect "
                             f"could NOT be verified: {e}")
    return st.reply(**host, effect=effect_seen(expect, reaction))


# THE MODIFIERS THE WINDOW ROUTE'S HELPER KNOWS BEYOND THE DOS KEYBOARD'S: a host key event
# can carry the command key; a scan sequence down the serial line cannot.
WINDOW_ONLY_MODIFIERS = ("cmd", "command")


def check_focus(focus: str) -> None:
    if focus not in ("return", "keep"):
        raise ds.Invalid("bad_argument",
            f"focus is 'return' (hand the focus back afterwards) or 'keep' "
                         f"(leave the emulator in front, which a captured mouse needs); "
                         f"got {focus!r}")


def check_expectation(expect: str | None, seconds: float | None) -> None:
    """The reaction half's arguments: a non-empty pattern that compiles, and a bound only
    beside it. TYPES ARE CHECKED because a `perform` step hands its arguments over untyped
    (JSON, no signature check on values), and a TypeError out of `re.compile` or `0 < "3"`
    is a traceback the tool wrapper deliberately does not translate."""
    if expect is None:
        if seconds is not None:
            raise ds.Invalid("bad_argument",
                "`seconds` bounds the wait for the guest's reaction, and without "
                             "`expect` there is no reaction to wait for: it would be "
                             "silently ignored. Give an `expect` pattern, or drop `seconds`")
        return
    if not isinstance(cast(object, expect), str) or not expect:
        raise ds.Invalid("bad_argument",
            f"`expect` is a non-empty regular expression over the E9 log; got "
                         f"{expect!r}. An empty pattern matches every line, so it would "
                         f"take the first unrelated trace as the reaction")
    ds.compiled(expect)
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    if isinstance(cast(object, wait_s), bool) or not isinstance(cast(object, wait_s),
                                                                  int | float):
        raise ds.Invalid("bad_argument", f"`seconds` is a number; got {seconds!r}")
    if not 0 < wait_s <= ds.RUN_TO_MAX:
        raise ds.Invalid("bad_argument",
            f"a wait of {wait_s}s for the effect is not a bound: it is more "
                         f"than zero and at most {ds.RUN_TO_MAX}s. Refused before posting")


def check_keys(keys: list[str], modifiers: list[str] | None, expect: str | None = None,
               seconds: float | None = None, focus: str = "return", *,
               serial: bool = False) -> None:
    """Everything `send_keys` refuses before touching a route, with the names judged against
    the ONE vocabulary both routes share (the window helper's table is held equal to the
    serial table by a test), so an unknown name costs no focus switch and reads the same
    whichever route would have answered."""
    # A STRING IS NOT A LIST OF NAMES. Over the transport `keys` arrives as raw JSON, so
    # `"keys": "enter"` reaches here as a str; `*keys` would then splat it into e,n,t,e,r --
    # five wrong keys. Refused rather than mis-sent (the failure this route most easily hides).
    # `cast(object, ...)`: the annotation is list[str], but the transport hands `keys` over as
    # raw JSON, so a caller's `"keys": "enter"` really does arrive as a str at runtime -- the
    # cast is what lets the honest runtime guard past the type checker.
    if isinstance(cast(object, keys), str):
        raise ds.Invalid("bad_argument",
            "keys is a LIST of names (['enter']), not a string ('enter'): a "
                         "bare string would be sent as its individual characters")
    if not keys:
        raise ds.Invalid("bad_argument", "send_keys needs at least one key name")
    if len(keys) > MAX_KEYS_PER_CALL:
        # THE COST IS WALL TIME UNDER THE SERVER'S LOCK: on the window route the helper
        # posts each key with its own pauses, on the serial route every scan byte waits a
        # timer tick, so a long text is many seconds during which `status` and `e9` cannot
        # be asked. The helper caps at the same number; a longer text goes in several calls.
        raise ds.Invalid("bad_argument",
            f"at most {MAX_KEYS_PER_CALL} key names per call (got {len(keys)}): "
                         f"each key costs wall time under the session's lock; send a longer "
                         f"text in several calls")
    for name in keys:
        if not isinstance(cast(object, name), str) or name.lower() not in SCAN_SET1:
            raise ds.Invalid("bad_argument",
                f"unknown key name {name!r}; the names are {sorted(SCAN_SET1)}")
    for m in modifiers or []:
        known = m.lower() in SCAN_MODIFIERS or (
            not serial and m.lower() in WINDOW_ONLY_MODIFIERS)
        if not known:
            allowed = sorted(SCAN_MODIFIERS) + ([] if serial else list(WINDOW_ONLY_MODIFIERS))
            why = " (a DOS keyboard has no command key)" if serial else ""
            raise ds.Invalid("bad_argument",
                f"unknown modifier {m!r}; the modifiers are {allowed}{why}")
    check_focus(focus)
    check_expectation(expect, seconds)


# THE NUDGE'S CEILING, and it is `keypost.swift`'s `MAX_NUDGE_PX`. It is stated on BOTH
# sides on purpose: the helper enforces it because it emits one delta event per point and a
# runaway call would run for ever, and this side enforces it so the refusal arrives as
# `bad_argument` BEFORE the window is touched, the layer `send_keys` already validates an
# unknown key name in. Two tools of one server refusing in different layers, one with the native
# helper's exit code, is an unevenness the caller feels. `tests/test_dosbox_x_nudge_
# bound.py` holds the two equal, and holds the COMPARISON equal too: the same number with an
# off-by-one in either guard would pass an equality check and still disagree.
MAX_NUDGE_PX = 2000


def check_mouse(button: str | None, x: int | None, y: int | None, dx: int | None,
                dy: int | None, place: str | None, expect: str | None = None,
                seconds: float | None = None, focus: str = "keep") -> None:
    """Everything `send_mouse` refuses before touching the window: ONE event shape, whole
    numbers (a `perform` step hands values over untyped, and the helper refuses a float or
    a bool only after the focus has been taken), the button and place vocabularies."""
    shapes = [button is not None, place is not None, x is not None or y is not None,
              dx is not None or dy is not None]
    if sum(shapes) != 1:
        raise ds.Invalid("bad_argument",
            "name ONE event: a `button` to click, `place='center'`, `x` and `y` "
                         "to place the host pointer, or `dx` and `dy` to move the guest's "
                         "pointer")
    for name, value in (("x", x), ("y", y), ("dx", dx), ("dy", dy)):
        if value is not None and (isinstance(cast(object, value), bool)
                                  or not isinstance(cast(object, value), int)):
            raise ds.Invalid("bad_argument",
                f"`{name}` is a whole number of screen points; got {value!r}")
    if button is not None and button not in ("left", "right"):
        raise ds.Invalid("bad_argument", f"a mouse button is 'left' or 'right'; got {button!r}")
    if place is not None and place != "center":
        raise ds.Invalid("bad_argument",
            f"`place` is 'center' (the emulator window's middle); got "
                         f"{place!r}")
    if (x is not None or y is not None) and (x is None or y is None):
        raise ds.Invalid("bad_argument", "placing the pointer needs BOTH `x` and `y`")
    if (dx is not None or dy is not None) and (dx is None or dy is None):
        raise ds.Invalid("bad_argument",
            "relative motion needs BOTH `dx` and `dy` (0 is fine for either)")
    for name, value in (("dx", dx), ("dy", dy)):
        if value is not None and abs(value) > MAX_NUDGE_PX:
            raise ds.Invalid("bad_argument",
                f"`{name}`={value} is past the {MAX_NUDGE_PX} px a single nudge carries: the "
                "motion goes out as one delta event per point, so the run is bounded. Split "
                "it across calls. Nothing was posted and the window was not touched")
    check_focus(focus)
    check_expectation(expect, seconds)


def send_keys(session: ds.Session, keys: list[str], modifiers: list[str] | None,
              expect: str | None, seconds: float | None, focus: str,
              progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The body of the `send_keys` tool."""
    _require_window(session, "send_keys")
    check_keys(keys, modifiers, expect, seconds, focus,
               serial=session.launch.input_port is not None)
    mods = "+".join(modifiers) if modifiers else "-"
    if session.launch.input_port is not None:
        note = "the keys went down the serial socket to the guest's resident stub; no window"
    else:
        note = "the emulator window was brought to the front to receive the keys" + (
            " and stays there (focus='keep')" if focus == "keep" else
            " and focus was handed back; over a stream that switch is visible")
    return _post_and_verify(session, "keys", [mods, *keys], expect, seconds, focus,
                            progress=progress, keys=keys, modifiers=modifiers or [], note=note)


def send_mouse(session: ds.Session, button: str | None, x: int | None, y: int | None,
               dx: int | None, dy: int | None, place: str | None, expect: str | None,
               seconds: float | None, focus: str,
               progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The body of the `send_mouse` tool."""
    _require_window(session, "send_mouse")
    check_mouse(button, x, y, dx, dy, place, expect, seconds, focus)
    if button is not None:
        return _post_and_verify(session, "click", [button], expect, seconds, focus,
                                progress=progress, button=button)
    if place is not None:
        return _post_and_verify(session, "move", ["center"], expect, seconds, focus,
                                progress=progress, place=place)
    if x is not None or y is not None:
        return _post_and_verify(
            session, "move", [str(x), str(y)], expect, seconds, focus, progress=progress,
            x=x, y=y,
            caveat="this placed the HOST pointer; the guest's pointer moves only through "
                   "`dx`/`dy` while the emulator has captured the mouse")
    return _post_and_verify(session, "nudge", [str(dx), str(dy)], expect, seconds, focus,
                            progress=progress, dx=dx, dy=dy)
