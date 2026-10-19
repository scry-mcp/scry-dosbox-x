"""How a session is launched: what it is launched with (`Launch`), judged before anything runs, the
command line built from it, the environment and the input listener it is given, and the files a
saved state carries beside it.

HEADLESS IS THE APPLICATION'S OWN SETTING, not an environment variable reached around
it with.  `videodriver` is a DOSBox-X `[sdl]` config property whose own description
reads "Forces a video driver (e.g. windib/windows, directx, x11, fbcon, dummy, etc)
for the SDL library to use", so `-set "sdl videodriver=dummy"` is the sanctioned
mechanism.  MEASURED: it alone yields `SDL: version 2.32.70, Video dummy, Audio
coreaudio` -- note it keeps REAL AUDIO, which `-silent` does not, and `-silent` also
exits after AUTOEXEC.BAT and so cannot host a session at all.

EVERY LAUNCH IS BOUNDED, and that is not belt-and-braces.  MEASURED: DOSBox-X does
NOT refuse an option it does not know -- `-loadstate 1` never returned at all.
So a session handed a bad flag does not fail, it hangs, and the bound is what stands
between that and an emulator running until the machine is rebooted.

THE COMMAND-LINE VOCABULARY IS FIXED; THE VALUES IN IT ARE THE CALLER'S.  Caller strings
land in argv: the flags, the program, the logfile, the captures and state directories.
`validate` checks the conf, the cwd, the logfile's directory, the flags and the bound; `start`
has judged every path absolute and created the two directories first; `program` is a DOS
command line and is not inspected.  No shell is involved (`Popen`
takes a list), so a caller string reaches the emulator as one argument and never as a
command; that is the whole of the guarantee, said here because this is the paragraph a
reviewer reads to decide exactly that question.
"""

from __future__ import annotations

import hashlib
import os
import re
import socket
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from scry_core import live_host
from scry_core import reply_contract as contract
from scry_core.reply_contract import Invalid

import dosbox_binary as binaries
import dosbox_control as control
import dosbox_paths as paths

# A bound so large it bounds nothing is the failure this exists to prevent, so there
# is a ceiling as well as a floor. Four hours is far past any interactive session and
# still finite.
MAX_SECONDS = 4 * 60 * 60


@dataclass
class Launch:
    """Everything a session needs to be reproducible, resolved by the CALLER.

    Nothing here defaults to a path inside anyone's home directory. The conf, the
    working directory and the window flags all come from outside, because this server
    is meant to be published and a default that only works on its author's machine is
    a private layout leaking into somebody else's install.
    """

    conf: Path
    cwd: Path
    seconds: int
    watched: bool = False
    window_flags: list[str] = field(default_factory=list)
    # THE CALLER'S EMULATOR FLAGS (a `-set` of a fixed clock, the quit warning back), in any
    # mode. Placement is `window_flags`; these are everything else, so a headless session
    # carries them too.
    flags: list[str] = field(default_factory=list)
    # `[dos] break on int3`: a guest's own `int 3` stops at the debugger.
    break_on_int3: bool = False
    program: str | None = None
    capture_video: bool = False
    captures_dir: Path | None = None
    logfile: Path | None = None
    # THE EMULATOR, the absolute path `start` resolved (`dosbox_binary`); the bare name is the
    # default a hand-built `Launch` runs, the PATH's.
    binary: str = binaries.EMULATOR_NAME
    # THE INPUT ROUTE: a TCP port the session listens on and the emulator's COM1 dials
    # (`serial1=nullmodem server:`), which the resident stub in `guest/INJECT.COM` reads its
    # commands from; 0 has the session's listener take a free one, which the session's
    # `launch` then carries. The conf's autoexec
    # runs the stub before its program, or `program` has it loaded first.
    input_port: int | None = None
    # WHETHER THE LAUNCH STAYS BEHIND the owner's front app (`judge_background`).
    background: bool = True
    # WHERE THE SAVE STATES LIVE: the slot directory the build's `-savedir` option names, and
    # the directory the state tools write `<name>.sav` into. None: `save/` under `cwd`, the
    # emulator's own default (measured), which the session names to the commands in full.
    state_dir: Path | None = None
    # THE DEBUGGER CHANNEL'S PORT (`dosbox_control`), the session's own listener's, set by the
    # session and never by a caller: it is how a running guest is broken in on.
    control_port: int | None = None


def digest(path: Path) -> str:
    """A short content digest, so a session can say the conf changed under it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


_digests: dict[Path, tuple[tuple[int, int, int], str]] = {}


def current_digest(path: Path) -> str:
    """`digest`, read again only when the file's size, mtime or inode moved: every reply
    carries whether the conf changed, and a hash per reply is a read of the whole file per
    call, twice per call a list steps through."""
    st = path.stat()
    key = (st.st_size, st.st_mtime_ns, st.st_ino)
    seen = _digests.get(path)
    if seen is None or seen[0] != key:
        seen = _digests[path] = (key, digest(path))
    return seen[1]


def fingerprint(conf: Path) -> str:
    """The stamp of the conf, the build before any map: a batch's stamp hashes it in
    (`dosbox_declarations.Build.stamp`)."""
    return hashlib.sha256(conf.read_bytes() if conf.exists()
                          else str(conf).encode()).hexdigest()[:16]


def build_argv(launch: Launch) -> list[str]:
    """The command line: our options with the caller's values, then the caller's own `flags`.

    `validate` judges the values first (`program`, a DOS command line, and the two directories
    `start` creates excepted), because
    an argv token DOSBox-X does not recognise does not fail, it hangs; and `flags` may name no
    option a named argument owns (`OWNED_OPTIONS`, `OWNED_SETS`), so a caller cannot undo one
    argument through another.
    """
    argv = [launch.binary, "-conf", str(launch.conf),
            "-time-limit", str(launch.seconds),
            "-break-start", "-fastlaunch",
            # NO QUIT-WARNING DIALOG: with a program loaded the emulator answers a TERM by
            # asking whether to quit anyway, and a session nobody is watching then sits
            # behind that question until the SIGKILL. The setting is `auto` by default and
            # a conf does not carry it, so it goes here, BEFORE the caller's flags: a later
            # `-set` wins, for the one caller who wants the dialog back.
            "-set", "dosbox quit warning=false"]
    # THE REMARK DIALOG IS OFF IN EVERY SESSION, for the same reason and in the same place:
    # measured, with `saveremark` at its default a `Save state` opens a dialog asking for
    # a remark, the dialog takes the SDL window with it (no window, no menu bar, the
    # process spinning) and nothing is written, stopped or running alike. Before the
    # caller's flags, so a later `-set` wins. The slot directory is the caller's when they
    # named one.
    argv += ["-set", "dosbox saveremark=false"]
    if launch.state_dir is not None:
        argv += ["-savedir", str(launch.state_dir)]
    if not launch.watched:
        # The application's own headless setting. See this module's docstring for why
        # it is this and not SDL_VIDEODRIVER, and not -silent.
        argv += ["-set", "sdl videodriver=dummy"]
    else:
        argv += launch.window_flags
    if launch.break_on_int3:
        argv += ["-set", "dos break on int3=true"]
    if launch.logfile is not None:
        argv += ["-set", f"log logfile={launch.logfile}"]
    if launch.input_port is not None:
        # THE INPUT ROUTE'S TWO SWITCHES, as `-set` overrides so the caller's conf need not
        # carry them: the integration device lives in the `[cpu]` section (upstream's own
        # Windows notes say so; under `[dosbox]` it is silently ignored -- measured), and
        # COM1 becomes a TCP client of the session's own listener. TRANSPARENT, because
        # otherwise the nullmodem reads a 0xFF from the socket as the escape of its own
        # line-status protocol, and a pointer coordinate holding that byte would arrive changed.
        # The stub is the conf's to run, or `program`'s.
        argv += ["-set", "cpu integration device=true",
                 "-set", f"serial serial1=nullmodem server:{INPUT_HOST} port:{launch.input_port} "
                         "transparent:1"]
    if launch.captures_dir is not None:
        argv += ["-set", f"dosbox captures={launch.captures_dir}"]
    if launch.control_port is not None:
        argv += ["-set", f"dosbox mcp_server={launch.control_port}"]
    # THE CALLER'S FLAGS COME AFTER EVERY `-set` OF OUR OWN, so one of the same key wins.
    argv += launch.flags
    if launch.program:
        # DX-CAPTURE runs the program WITH video capture and stops when it exits,
        # which is the only screen capture DOSBox-X offers with nobody at the
        # keyboard: the still screenshot is a mapper action and needs a keypress.
        #
        # A CONSTRAINT ON THE CONF, MEASURED rather than assumed: `-c` runs AFTER the
        # conf's `[autoexec]` section, so a conf whose autoexec ends in `exit` quits
        # the emulator before this command is ever reached. Verified both ways --
        # `-c "ECHO ran > C:\DASHC.TXT"` against such a conf leaves no file, and the
        # same command with `-noautoexec` leaves none either, because then C: is not
        # mounted. So `program` needs a conf that mounts what it needs and does NOT
        # run-and-exit; `captures()` says this when nothing appears, because the
        # symptom is an empty directory and the cause is three files away.
        cmd = f"DX-CAPTURE /V {launch.program}" if launch.capture_video else launch.program
        if launch.input_port is not None:
            # THE STUB GOES IN FIRST, by the same `-c` route: these run in order after the
            # conf's autoexec, so the program this launches finds it resident. A conf that runs
            # its own program from the autoexec never reaches here and carries the stub line.
            argv += ["-c", f'mount {STUB_DRIVE} "{GUEST_DIR}"', "-c", f"{STUB_DRIVE}:\\INJECT.COM"]
        argv += ["-c", cmd]
    return argv


# THE STUB'S HOME, shipped beside this module, and the drive a `program` session mounts it on:
# a letter late in the alphabet, so it does not take one a conf is likely to mount.
GUEST_DIR = Path(__file__).resolve().with_name("guest")


STUB_DRIVE = "Y"


INPUT_CONNECT_S = 8.0     # how long a session waits for the emulator's serial port to dial it


INPUT_HOST = control.LOCAL_HOST


# THE BACKGROUND LAUNCH (`live_host.BACKGROUND_VAR` says why). It reaches SDL3 through the
# sdl2-compat layer this build links: a shared window launched with it never comes to the front.
BACKGROUND_VAR = live_host.BACKGROUND_VAR


def judge_background(background: bool | None, watched: bool) -> bool:
    """Whether the emulator is launched behind: `background` when given, else behind for a
    session nobody watches and in front for a shared one."""
    return not watched if background is None else background


def launch_environment(background: bool) -> dict[str, str]:
    """The environment the emulator is spawned with: this server's, the terminal the debugger
    draws in, and the background hint set or REMOVED, never inherited, so a server started with
    the hint in its own environment cannot launch a `background=False` session behind."""
    spawned = dict(os.environ, TERM="xterm-256color", LINES="50", COLUMNS="132")
    if background:
        spawned[BACKGROUND_VAR] = "1"
    else:
        spawned.pop(BACKGROUND_VAR, None)
    return spawned


def listen_input(port: int) -> socket.socket:
    """The session's end of the serial input route, LISTENING before the emulator exists
    (`dosbox_control.listen_local`, which says why that way round): 0 takes the kernel's pick;
    a port already taken is refused before anything is spawned."""
    try:
        return control.listen_local(port)
    except OSError as e:
        if not port:
            raise Invalid("host_failed", f"the kernel would not hand out a free port for the "
                          f"input route ({e})") from None
        raise Invalid("host_failed", f"input_port {port} is already in use on this host ({e}): "
                      f"the session cannot listen there for the emulator. Pick another port, "
                      f"or omit it") from None


def accept_input(listener: socket.socket, seconds: float,
                  exited: Callable[[], int | None]) -> socket.socket:
    """The emulator's dial on the input route, accepted within the bound, then the listener
    closed. A refusal here is raised INTO `Session.__init__`'s `except BaseException`, which
    kills the child it has just spawned: a session on this route with no socket is one whose
    guest will block the moment its stub polls the port."""
    port = listener.getsockname()[1]
    try:
        got = control.await_dial(listener, seconds, exited)
    finally:
        listener.close()
    if isinstance(got, int):
        raise Invalid("session_broken",
            f"the emulator exited (code {got}) before it dialled the serial input port {port}")
    if got is None:
        raise Invalid("session_broken",
            f"the emulator never dialled the serial input port {port} within {seconds}s: the "
                      f"serial input route cannot be used, and a guest polling that port with no "
                      f"client would block the emulator")
    got.setblocking(True)
    return got


# WHAT A NAMED ARGUMENT OWNS, so `flags` cannot retune it: the options this server passes,
# and the `-set` keys it derives from an argument, each with the argument that sets it.
OWNED_OPTIONS = {"-conf": "conf", "-time-limit": "seconds", "-break-start": "start",
                 "-savedir": "state_dir", "-c": "program"}


OWNED_SETS = {"sdl videodriver": "mode", "dos break on int3": "break_on_int3",
              "log logfile": "logfile", "serial serial1": "input_port",
              "cpu integration device": "input_port", "dosbox captures": "captures_dir"}


# THE `-set` KEYS THE SESSION ITSELF OWNS, with no argument behind them: a caller's value would
# point the debugger channel somewhere the session is not listening.
SESSION_SETS = {"dosbox mcp_server"}


def _set_key(token: str) -> str:
    """The `section key` a `-set` token names, however the value is joined to it: DOSBox-X
    takes `section key=value` and also `section key value`, so the key is the longest owned
    one the words start with, else the words before an `=`."""
    words = token.split("=", 1)[0].lower().split()
    for n in range(len(words), 1, -1):
        key = " ".join(words[:n])
        if key in OWNED_SETS or key in SESSION_SETS:
            return key
    return " ".join(words)


def check_flags(name: str, flags: list[str]) -> None:
    """Argv tokens a caller hands in, each a separate non-empty string, never a glued option
    and value, and a `-set` never shredded. Both malformations fail SILENTLY in DOSBox-X."""
    for i, flag in enumerate(flags):
        if not isinstance(flag, str) or not flag:
            raise Invalid("bad_argument",
                f"{name} must be separate non-empty strings; got {flag!r}")
        # AND THE GLUED PAIR, WHICH THE CHECK ABOVE CANNOT SEE: `['-set "sdl display=1"']` is
        # a non-empty `str`. The rule is exact rather than a heuristic about quotes: an OPTION
        # is one word, a VALUE may hold spaces. `-set` and `sdl display=1` are two tokens and
        # both are fine; `-set sdl display=1` as one token is not an argument DOSBox-X
        # recognises, and it HANGS on those rather than refusing them, so the only
        # thing that would end that session is its own bound.
        if flag.startswith("-") and flag.split() != [flag]:
            raise Invalid("bad_argument",
                f"{flag!r} is an option and a value GLUED into one token. "
                          f"They are separate argv entries -- ['-set', 'sdl "
                          f"display=1'], not ['-set \"sdl display=1\"'] -- because "
                          f"DOSBox-X does not refuse an argument it cannot parse, it "
                          f"hangs on it")
        if flag == "-set" and (i + 1 >= len(flags) or " " not in str(flags[i + 1])):
            raise Invalid("bad_argument",
                f"{name}: the `-set` at {i} is not followed by one `section key=value` "
                f"token (a space inside it). A shredded `-set` is ignored by DOSBox-X at "
                f"rc 0, so the setting would silently not apply")
        if name == "flags":
            owner = OWNED_OPTIONS.get(flag)
            if flag == "-set":
                key = _set_key(str(flags[i + 1]))
                owner = OWNED_SETS.get(key)
                if key in SESSION_SETS:
                    raise Invalid("bad_argument",
                        f"flags: the `-set` at {i} sets `{key}`, which every session sets "
                        f"to its own debugger channel; it is not the caller's to change")
            if owner is not None:
                raise Invalid("bad_argument",
                    f"flags: {flag!r} at {i} sets what `{owner}` owns. Placed after this "
                    f"server's own options it would quietly undo that argument, so set it "
                    f"through `{owner}`")


def _judge_files(launch: Launch) -> None:
    """The launch's files on the filesystem: the conf there, the working directory there, the
    logfile's directory there and the logfile neither a directory, nor the conf, nor one of the
    directories `start` creates."""
    if not launch.conf.is_file():
        raise Invalid("bad_argument", f"conf: no conf at {launch.conf}: a session that cannot be "
                      f"reproduced is refused before it exists")
    if not launch.cwd.is_dir():
        # It is guarded HERE for the same reason the conf is. A missing cwd makes
        # `Popen` raise, and that raise lands after the pseudo-terminal has been
        # opened -- two leaked descriptors on an object nothing can reach to close.
        raise Invalid("bad_argument",
            f"cwd: no working directory at {launch.cwd}: a DOSBox-X conf mounts "
                      f"relative paths, so the directory is part of what makes the "
                      f"session reproducible")
    logfile = launch.logfile
    if logfile is not None:
        # A LINK IS JUDGED BY THE FILE IT NAMES, the one the emulator opens.
        log = paths.resolved("logfile", logfile)
        if not log.parent.is_dir() or log.is_dir():
            # The emulator opens its log afresh and says nothing when it cannot: a log under a
            # missing directory surfaced later as "no log", never as the path that was wrong.
            named = f" (a link to {log})" if logfile.is_symlink() else ""
            raise Invalid("bad_argument",
                f"logfile: {logfile}{named} " + ("is a directory" if log.is_dir() else
                                                 f"has no directory {log.parent}")
                + ": the emulator would write its log nowhere and say nothing")
        if log.exists() and log.samefile(launch.conf):
            raise Invalid("bad_argument",
                f"logfile: {logfile} is the conf {launch.conf}: the emulator opens its log "
                f"afresh, so it would write the log over the conf this session boots from")
    if launch.logfile is not None and launch.logfile in (launch.captures_dir, launch.state_dir):
        raise Invalid("bad_argument",
            f"logfile: {launch.logfile} is also the directory `start` creates for "
            f"{'captures_dir' if launch.logfile == launch.captures_dir else 'state_dir'}")


def validate(launch: Launch) -> None:
    """Everything that makes a session refusable, decided BEFORE any process exists.

    IT IS A FUNCTION OF ITS OWN AND NOT A FEW LINES INSIDE `Session.__init__`, and the
    reason is a leak this cost before it was moved. While these guards lived in the
    constructor, the only way to test them was to CONSTRUCT a session -- fine while
    they hold, and a disaster the moment one is removed: the break that deletes a
    guard makes the same test START a real emulator that nothing then closes.
    MEASURED, and found by hand before any gate noticed: six emulators left running
    on the machine, and the one from the missing-bound case carried `-time-limit 0`,
    which is not a short bound but NO bound at all.

    As a pure function it is testable without a process existing, so the break that
    removes a guard makes a test FAIL rather than spawn.
    """
    try:
        _judge_files(launch)
    except (OSError, ValueError) as e:     # a stat refused (before 3.14 it raises, not answers)
        raise Invalid("bad_argument",
                      f"a path of this launch cannot be looked at: {e}") from None
    if launch.watched and not launch.window_flags:
        raise Invalid("bad_argument",
            "a watched session needs its placement flags, and this server does "
            "not compute them: they come from the caller, which is what keeps "
            "one helper the single source of where a window goes. Inventing a "
            "geometry here is how windows end up off-screen or on the display "
            "nobody is looking at.")
    if not launch.watched and launch.window_flags:
        raise Invalid("bad_argument",
            "`window_flags` place a WINDOW and a headless session has none, so they would "
            "be dropped: an emulator flag (a `-set` of the clock, say) goes in `flags`, "
            "which reaches the command line in either mode")
    check_flags("window_flags", launch.window_flags)
    check_flags("flags", launch.flags)
    if launch.seconds <= 0:
        raise Invalid("bad_argument", "a session without a bound is refused: DOSBox-X does not "
                      "reject an option it does not know, it hangs, so the bound "
                      "is the only thing that ends an abandoned session. Note that "
                      "`-time-limit 0` is not a short bound, it is none at all")
    if launch.seconds > MAX_SECONDS:
        raise Invalid("bad_argument", f"{launch.seconds}s is not a bound, it is a formality: the "
                      f"ceiling is {MAX_SECONDS}s. A limit large enough to outlast "
                      f"the day protects nothing")
    if launch.capture_video and not launch.program:
        raise Invalid("bad_argument",
            "capture_video needs a program to capture: DX-CAPTURE wraps a "
                      "PROGRAM and stops when it exits, so without one the flag "
                      "would be accepted and quietly do nothing")
    if launch.input_port and not 1024 <= launch.input_port <= 65535:
        raise Invalid("bad_argument",
            f"input_port is the TCP port the emulator's COM1 dials, between "
                      f"1024 and 65535; got {launch.input_port}")


# A STATE'S NAME is a file name under the state directory, so it is held whole (`fullmatch`: a
# `$` would let a trailing newline through) and to a length a file system takes everywhere.
STATE_NAME_MAX = 64


STATE_NAME = re.compile(rf"[A-Za-z0-9][A-Za-z0-9_-]{{0,{STATE_NAME_MAX - 1}}}")


# The members of a state ZIP that identify it without loading it, measured off a real
# one: the emulator's version, the program, the machine, the memory size in megabytes (the
# conf's `memsize`), and the local time it was saved at, as the emulator stamps it.
STATE_META = {"version": "DOSBox-X_Version", "program": "Program_Name",
              "machine": "Machine_Type", "memory_mb": "Memory_Size",
              "saved_at": "Time_Stamp"}


#: A file in the state directory that is no state: said in its row, never refused.
NOT_A_STATE = "not a save state: the file is not a ZIP the emulator wrote"


def state_fields(meta: dict[str, object]) -> dict[str, object]:
    """`STATE_META`'s fields of a read state as a reply carries them: each the member's text,
    `memory_mb` a whole number, and a member the file lacks unavailable with its name."""
    out: dict[str, object] = {}
    for key, member in STATE_META.items():
        value = meta.get(key)
        if value is None:
            out[key] = contract.unavailable(f"the state carries no `{member}`")
        elif key == "memory_mb":
            out[key] = int(str(value)) if str(value).isdigit() else contract.unavailable(
                f"the state's `{member}` is {value!r}, not a count of megabytes")
        else:
            out[key] = value
    return out


def check_state_name(name: object) -> None:
    if not isinstance(name, str) or not STATE_NAME.fullmatch(name):
        raise Invalid("bad_argument",
            f"a state name is letters, digits, `_` and `-`, starting with a letter or a "
                      f"digit, at most {STATE_NAME_MAX} of them; got {name!r}. It becomes a "
                      f"file name under the state directory")
    if name.isdigit():
        # The emulator's own slot files are `<n>.sav` in the same directory, and a state
        # named `1` would be its working slot's file, written by the slot as well as by name.
        raise Invalid("bad_argument",
            f"a state name of digits only, {name!r}, is the emulator's own slot file name "
            f"(`{name}.sav`): add a letter")


def state_meta(path: Path) -> dict[str, object]:
    """What a state file says about itself, read off the ZIP without loading it. A file
    that is not a state ZIP gets a `note` rather than a refusal, because `state_list` is a
    reading of a directory and a stray file in it is information."""
    out: dict[str, object] = {"name": path.stem, "path": str(path),
                              "bytes": path.stat().st_size}
    read: dict[str, object] = {}
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            for key, member in STATE_META.items():
                if member in names:
                    read[key] = z.read(member).decode("utf-8", errors="replace").strip()
    except zipfile.BadZipFile:
        out["note"] = NOT_A_STATE
        return {**out, **{key: contract.unavailable(NOT_A_STATE) for key in STATE_META}}
    return {**out, **state_fields(read)}
