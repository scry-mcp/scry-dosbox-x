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
    core = "auto"
    try:
        text = conf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        text = ""                       # gone since `start`: `conf_changed_on_disk` says so
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.partition("#")[0].strip().lower()
        elif section == "[cpu]":
            key, _, value = line.partition("=")
            if key.strip().lower() == "core" and (cut := value.partition("#")[0].strip()):
                core = cut.lower()
    for flag, setting in zip(flags, flags[1:], strict=False):
        words = setting.replace("=", " ").split()
        if flag == "-set" and len(words) == 3 and [w.lower() for w in words[:2]] == ["cpu", "core"]:
            core = words[2].lower()
    return core
