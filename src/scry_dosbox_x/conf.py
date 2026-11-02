"""What a launch reads out of the conf file it is given: the drives its `[autoexec]` mounts and
the cpu core it asks for, as the debugger will see them at boot."""

from __future__ import annotations

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
    """The `[dosbox] dpi aware` a run boots with: True, False, or None for auto."""
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
        named = [section_name, *key_name.split()]
        if (flag == "-set" and len(words) == len(named) + 1
                and [w.lower() for w in words[:-1]] == named):
            found = words[-1].lower()
    return found
