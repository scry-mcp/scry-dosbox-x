"""What a launch reads out of the conf file it is given: the drives its `[autoexec]` mounts, the
cpu core, the `sdl output`, a stated `windowresolution` and `dpi aware`, as boot will see them."""

from __future__ import annotations

import re
from pathlib import Path

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
            section = line.partition("#")[0].strip().lower()
        elif section == "[autoexec]" and words and words[0].lstrip("@").lower() in MOUNTING:
            letters = [w.rstrip(":").upper() for w in words[1:]
                       if len(w.rstrip(":")) == 1 and w[0].isalpha()]
            if letters and letters[0] not in found:
                found.append(letters[0])
    return found


_STUB_RUN = re.compile(r"^@?([A-Za-z]):[\\/](?:.*[\\/])?scry(?:\.com)?$", re.IGNORECASE)
_STUB_SIGNATURE = re.compile(rb"SCRY-INJECT-(\d+)")


def stub_protocols(conf: Path, cwd: Path) -> list[tuple[str, str]]:
    """Each stub the conf's `[autoexec]` runs off a drive it mounted, with the protocol that file
    carries: a conf can mount a copy older than the server."""
    try:
        text = conf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    mounts: dict[str, Path] = {}
    found: list[tuple[str, str]] = []
    section = ""
    for line in text.splitlines():
        words = line.split()
        if line.strip().startswith("["):
            section = line.partition("#")[0].strip().lower()
        if section != "[autoexec]" or not words:
            continue
        if words[0].lstrip("@").lower() == "mount":
            args = [w.strip('"') for w in words[1:] if not w.startswith("-")]
            if len(args) >= 2 and len(args[0].rstrip(":")) == 1:
                mounts[args[0].rstrip(":").upper()] = cwd / args[1]
        elif (run := _STUB_RUN.match(words[0])) is not None and run[1].upper() in mounts:
            try:
                carried = _STUB_SIGNATURE.search((mounts[run[1].upper()] / "SCRY.COM").read_bytes())
            except OSError:
                continue
            if carried is not None:
                found.append((words[0], carried[1].decode()))
    return found


def cpu_core(conf: Path, flags: list[str]) -> str:
    """The core a session boots with: the conf's `[cpu] core=`, then the last `-set` of `flags`."""
    return setting(conf, flags, "cpu", "core", "auto")


def sdl_output(conf: Path, flags: list[str]) -> str:
    """The `[sdl] output` a session boots with, `default` when nothing says."""
    return setting(conf, flags, "sdl", "output", "default")


SIZED_OUTPUTS = ("opengl", "openglnb", "openglhq", "openglpp", "direct3d")


def honours_window_size(output: str, platform: str) -> bool:
    """Whether `output` reads `windowresolution`; `surface` and the text outputs do not."""
    return output in SIZED_OUTPUTS or (output == "default" and platform in ("darwin", "win32"))


def dpi_awareness(conf: Path, flags: list[str]) -> bool | None:
    """The `[dosbox] dpi aware` a run boots with: True, False, or None for auto; `-nodpiaware`
    wins over the setting."""
    if "-nodpiaware" in flags:
        return False
    return {"true": True, "1": True, "false": False, "0": False}.get(
        setting(conf, flags, "dosbox", "dpi aware", "auto"))


def states_window_size(conf: Path, flags: list[str]) -> bool:
    """Whether the conf or a `-set` gives `windowresolution` a size."""
    return "x" in setting(conf, flags, "sdl", "windowresolution", "")


def setting(conf: Path, flags: list[str], section_name: str, key_name: str, default: str) -> str:
    """`[section] key` as the conf sets it, then the last `-set` of `flags`, lowercased."""
    found = default
    try:
        text = conf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        text = ""                       # gone since `start`: `conf_changed_on_disk` says so
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.partition("#")[0].strip().lower()
        elif section == f"[{section_name}]":
            key, _, value = line.partition("=")
            if key.strip().lower() == key_name and (cut := value.partition("#")[0].strip()):
                found = cut.lower()
    for flag, asked in zip(flags, flags[1:], strict=False):
        words = asked.replace("=", " ").split()
        wanted = key_name.split()
        named = [w.lower() for w in words[:-1]]
        if flag == "-set" and named in ([section_name, *wanted], wanted):
            found = words[-1].lower()
    return found
