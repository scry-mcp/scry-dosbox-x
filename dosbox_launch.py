"""How a session is launched: `Launch`, its command line and environment, the input listener,
and the files a saved state carries.

Headless is `-set "sdl videodriver=dummy"`: unlike `-silent` it keeps real audio, and
`-silent` exits after AUTOEXEC.BAT.

Every launch is bounded: DOSBox-X does not refuse an option it does not know (`-loadstate 1`
never returns), so a bad flag hangs, and the bound is all that ends it.

Caller strings land in argv. `validate` checks the conf, cwd, logfile directory, flags and
bound; `start` has made the two directories absolute and created them; `program` is a DOS
command line and is not inspected. No shell is involved, so a caller string is one argument.
"""

from __future__ import annotations

import hashlib
import lzma
import os
import socket
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scry_core import live_host, state_files
from scry_core import reply_contract as contract
from scry_core.reply_contract import Invalid

import dosbox_binary as binaries
import dosbox_control as control
import dosbox_paths as paths

# A ceiling as well as a floor: a bound so large it bounds nothing is no bound.
MAX_SECONDS = 4 * 60 * 60
INPUT_PORT_MIN, INPUT_PORT_MAX = 1024, 65535


@dataclass
class Launch:
    """Everything a session needs to be reproducible, resolved by the caller."""

    conf: Path
    cwd: Path
    seconds: int
    watched: bool = False
    window_flags: list[str] = field(default_factory=list)
    # Every flag but placement, so a headless session carries them too.
    flags: list[str] = field(default_factory=list)
    # `[dos] break on int3`: a guest's own `int 3` stops at the debugger.
    break_on_int3: bool = False
    program: str | None = None
    capture_video: bool = False
    captures_dir: Path | None = None
    logfile: Path | None = None
    # The absolute path `start` resolved; the bare name is the PATH's.
    binary: str = binaries.EXECUTABLE_NAME
    # TCP port the emulator's COM1 dials, read by `guest/INJECT.COM`; 0 takes a free one.
    input_port: int | None = None
    # Chosen once at `start`, so later replies name the drive used.
    stub_drive: str = ""
    background: bool = True
    # The `-savedir` slot directory, where state tools write; None: `save/` under `cwd`.
    state_dir: Path | None = None
    # The session's own debugger listener, never a caller's.
    control_port: int | None = None
    # Whether the build's debugger runs with no screen (`binaries.debugger_headless`), and which
    # optional debugger commands it has (`binaries.debugger_commands`), read once at `start`.
    debugger_headless: bool = False
    debugger_commands: frozenset[str] = frozenset()


def digest(path: Path) -> str:
    """A short content digest of the conf."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


_digests: dict[Path, tuple[tuple[int, int, int], str]] = {}


def current_digest(path: Path) -> str:
    """`digest`, re-read only when the file's size, mtime or inode moved: every reply carries it."""
    st = path.stat()
    key = (st.st_size, st.st_mtime_ns, st.st_ino)
    seen = _digests.get(path)
    if seen is None or seen[0] != key:
        seen = _digests[path] = (key, digest(path))
    return seen[1]


def fingerprint(conf: Path) -> str:
    """The stamp of the conf."""
    return hashlib.sha256(conf.read_bytes() if conf.exists()
                          else str(conf).encode()).hexdigest()[:16]


def build_argv(launch: Launch) -> list[str]:
    """The command line: our options with the caller's values, then the caller's `flags`."""
    argv = [launch.binary, "-conf", str(launch.conf),
            "-time-limit", str(launch.seconds),
            "-break-start", "-fastlaunch", binaries.NO_FOLDER_PROMPT,
            # With a program loaded a TERM raises a quit dialog nobody answers.
            "-set", "dosbox quit warning=false"]
    # A debugger with no screen needs no terminal or console to stop at `-break-start`; a build
    # without the option is given one (`dosbox_process`).
    if launch.debugger_headless:
        argv += ["-set", "dosbox debugger headless=true"]
    # With `saveremark` on, `Save state` opens a dialog that hangs the window.
    argv += ["-set", "dosbox saveremark=false"]
    if launch.state_dir is not None:
        argv += ["-savedir", str(launch.state_dir)]
    if not launch.watched:
        argv += ["-set", "sdl videodriver=dummy"]
    else:
        argv += launch.window_flags
    if launch.break_on_int3:
        argv += ["-set", "dos break on int3=true"]
    if launch.logfile is not None:
        argv += ["-set", f"log logfile={launch.logfile}"]
    if launch.input_port is not None:
        # The integration device is read from `[cpu]`; under `[dosbox]` it is ignored.
        # `transparent`: else the nullmodem takes a 0xFF as its own escape.
        argv += ["-set", "cpu integration device=true",
                 "-set", f"serial serial1=nullmodem server:{INPUT_HOST} port:{launch.input_port} "
                         "transparent:1"]
    if launch.captures_dir is not None:
        argv += ["-set", f"dosbox captures={launch.captures_dir}"]
    if launch.control_port is not None:
        argv += ["-set", f"dosbox mcp_server={launch.control_port}"]
    # After every `-set` of ours, so the caller's of the same key wins.
    argv += launch.flags
    if launch.program:
        # DX-CAPTURE is the only capture with nobody at the keyboard. `-c` runs after the
        # conf's `[autoexec]`, so a conf ending in `exit` never reaches `program`.
        cmd = f"DX-CAPTURE /V {launch.program}" if launch.capture_video else launch.program
        if launch.input_port is not None:
            # The stub goes in first so the program finds it resident.
            drive = launch.stub_drive or stub_drive(launch.conf)
            argv += ["-c", f'mount {drive} "{GUEST_DIR}"', "-c", f"{drive}:\\INJECT.COM"]
        argv += ["-c", cmd]
    return argv


# Drives for the stub: late first, where a conf rarely mounts, never one its `[autoexec]` mounted.
GUEST_DIR = Path(__file__).resolve().with_name("guest")
STUB_DRIVES = "YXWVUTSRQPONMLKJIHGFED"
MOUNTING = frozenset({"mount", "imgmount", "subst"})


def conf_mounts(conf: Path) -> list[str]:
    """The drive letters the conf's `[autoexec]` mounts, in order."""
    found: list[str] = []
    section = ""
    try:
        text = conf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return found                    # gone since `start`: `conf_changed_on_disk` says so
    for line in text.splitlines():
        words = line.split()
        if line.strip().startswith("["):
            section = line.strip().lower()
        elif section == "[autoexec]" and words and words[0].lstrip("@").lower() in MOUNTING:
            letters = [w.rstrip(":").upper() for w in words[1:]
                       if len(w.rstrip(":")) == 1 and w[0].isalpha()]
            if letters and letters[0] not in found:
                found.append(letters[0])
    return found


def stub_drive(conf: Path) -> str:
    """The first of `STUB_DRIVES` the conf leaves free, else a refusal."""
    mounted = conf_mounts(conf)
    free = [d for d in STUB_DRIVES if d not in mounted]
    if not free:
        raise Invalid("bad_argument",
            f"no drive from {STUB_DRIVES[0]}: to {STUB_DRIVES[-1]}: is free for the input stub: "
            f"the conf's [autoexec] mounts {', '.join(f'{d}:' for d in mounted)}. Leave one "
            f"unmounted, or load the stub from the conf (`G:\\INJECT.COM` after mounting this "
            f"package's guest directory) and run the program from there")
    return free[0]


INPUT_CONNECT_S = 8.0     # seconds to wait for the emulator's serial port to dial


INPUT_HOST = control.LOCAL_HOST


# A shared window launched with it never comes to the front (`live_host.BACKGROUND_VAR`).
BACKGROUND_VAR = live_host.BACKGROUND_VAR


def judge_background(background: bool | None, watched: bool) -> bool:
    """`background` when given, else behind unless the session is watched."""
    return not watched if background is None else background


def launch_environment(background: bool, terminal: bool = False) -> dict[str, str]:
    """The spawn environment; the background hint is set or removed, never inherited.

    The terminal and its size go only to a debugger that draws on the terminal nobody reads:
    Windows' release build, handed `LINES` and `COLUMNS`, resizes its console and dies."""
    spawned = {k: v for k, v in os.environ.items() if k not in ("LINES", "COLUMNS")}
    if terminal:
        spawned.update(TERM="xterm-256color", LINES="50", COLUMNS="132")
    if background:
        spawned[BACKGROUND_VAR] = "1"
    else:
        spawned.pop(BACKGROUND_VAR, None)
    return spawned


def binary_facts(resolved: binaries.Resolved, seconds: float) -> dict[str, Any]:
    """The build's facts, its `-version` probe spawned behind and bounded."""
    return binaries.facts(resolved, env=launch_environment(True), seconds=seconds)


def listen_input(port: int) -> socket.socket:
    """The input route's listener, up before the emulator exists; 0 takes any free port."""
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
    """The emulator's dial, accepted within the bound, then the listener closed."""
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


# What a named argument owns, so `flags` cannot retune it, each with the argument that sets it.
OWNED_OPTIONS = {"-conf": "conf", "-time-limit": "session_seconds", "-break-start": "start",
                 "-savedir": "state_dir", "-c": "program"}


OWNED_SETS = {"sdl videodriver": "shared", "dos break on int3": "break_on_int3",
              "log logfile": "logfile", "serial serial1": "input_port",
              "cpu integration device": "input_port", "dosbox captures": "captures_dir"}


# Keys the session owns with no argument behind them: a caller's value would point the debugger
# channel where the session is not listening, or give a debugger that has no terminal a screen.
SESSION_SETS = {"dosbox mcp_server", "dosbox debugger headless"}


def _set_key(token: str) -> str:
    """The `section key` a `-set` token names; DOSBox-X also takes `section key value`."""
    words = token.split("=", 1)[0].lower().split()
    for n in range(len(words), 1, -1):
        key = " ".join(words[:n])
        if key in OWNED_SETS or key in SESSION_SETS:
            return key
    return " ".join(words)


def check_flags(name: str, flags: list[str]) -> None:
    """Argv tokens are separate non-empty strings, never a glued option and value; DOSBox-X
    hangs or ignores both."""
    for i, flag in enumerate(flags):
        if not isinstance(flag, str) or not flag:
            raise Invalid("bad_argument",
                f"{name} must be separate non-empty strings; got {flag!r}")
        # An option is one word, a value may hold spaces.
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
                        f"for its own debugger channel; it is not the caller's to change")
            if owner is not None:
                raise Invalid("bad_argument",
                    f"flags: {flag!r} at {i} sets what `{owner}` owns. Placed after this "
                    f"server's own options it would quietly undo that argument, so set it "
                    f"through `{owner}`")


def _judge_files(launch: Launch) -> None:
    """The conf, cwd and logfile directory exist; the logfile collides with none of them."""
    if not launch.conf.is_file():
        raise Invalid("bad_argument", f"conf: no conf at {launch.conf}: a session that cannot be "
                      f"reproduced is refused before it exists")
    if not launch.cwd.is_dir():
        # A missing cwd makes `Popen` raise after the pty is opened.
        raise Invalid("bad_argument",
            f"cwd: no working directory at {launch.cwd}: a DOSBox-X conf mounts "
                      f"relative paths, so the directory is part of what makes the "
                      f"session reproducible")
    logfile = launch.logfile
    if logfile is not None:
        # A link is judged by the file it names, the one the emulator opens.
        log = paths.resolved("logfile", logfile)
        if not log.parent.is_dir() or log.is_dir():
            # The emulator says nothing when it cannot open its log.
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
    """Everything that makes a session refusable, decided before any process exists, so a
    removed guard fails a test instead of starting a real emulator."""
    try:
        _judge_files(launch)
    except (OSError, ValueError) as e:     # a stat refused (before 3.14 it raises, not answers)
        raise Invalid("bad_argument",
                      f"a path of this launch cannot be looked at: {e}") from None
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
    if launch.program and launch.input_port is not None:
        stub_drive(launch.conf)
    if launch.input_port and not INPUT_PORT_MIN <= launch.input_port <= INPUT_PORT_MAX:
        raise Invalid("bad_argument",
            f"input_port is the TCP port the emulator's COM1 dials, between "
                      f"{INPUT_PORT_MIN} and {INPUT_PORT_MAX}; got {launch.input_port}")


# Members of a state ZIP that identify it without loading it; memory is in megabytes.
STATE_META = {"version": "DOSBox-X_Version", "program": "Program_Name",
              "machine": "Machine_Type", "memory_mb": "Memory_Size",
              "saved_at": "Time_Stamp"}


#: Where the states go when `start` is given no `state_dir`: this directory under `cwd`.
DEFAULT_STATE_SUBDIR = "save"


def state_dir_of(launch: Launch) -> Path:
    """Where this session's states are written and listed."""
    return launch.state_dir if launch.state_dir is not None else launch.cwd / DEFAULT_STATE_SUBDIR

#: A file in the state directory that is no state: said in its row, never refused.
NOT_A_STATE = "not a save state: the file is not a ZIP the emulator wrote"


def state_fields(meta: dict[str, object]) -> dict[str, object]:
    """`STATE_META`'s fields as a reply carries them."""
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
    name = state_files.check_state_name(name, "a file name under the state directory")
    if name.isdigit():          # `1` is the emulator's own slot file
        raise Invalid("bad_argument",
            f"a state name of digits only, {name!r}, is the emulator's own slot file name "
            f"(`{name}.sav`): add a letter")


def state_meta(path: Path) -> dict[str, object]:
    """What a state file says about itself, read off the ZIP. Anything that is no state ZIP
    gets a `note`, not a refusal."""
    if (why := state_files.not_a_state(path)) is not None:
        gone = contract.unavailable(why)
        return {"name": path.stem, "path": str(path), "bytes": gone, "note": why,
                **{key: gone for key in STATE_META}}
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
    except FileNotFoundError:
        raise      # gone since it was listed: the caller leaves it out
    # A member's decompressor raises its own: zlib's, LZMA's, and EOFError for a stream cut short.
    except (OSError, zlib.error, lzma.LZMAError, EOFError, NotImplementedError,
            RuntimeError) as e:
        why = f"the file could not be read: {e}"
        return {**out, "note": why, **{key: contract.unavailable(why) for key in STATE_META}}
    return {**out, **state_fields(read)}
