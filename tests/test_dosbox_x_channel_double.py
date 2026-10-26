"""The channel double answers as the debugger did: every captured exchange of a command it
models, replayed in order on a machine set to the capture's own stop, comes back line for line."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import cast

import pytest
from channel_double import FIXTURES, PROTECTED_STOP, REAL_STOP, Machine, protected

#: The commands whose replies depend only on what the double models; a listing of the guest's
#: memory, a release or a scan is the emulator's alone.
MODELLED = ("BPLIST", "BP", "BPINT", "BPM", "BPPM", "BPDEL", "SR", "SM", "NOSUCHCOMMAND")


def _replayed(name: str) -> list[tuple[str, tuple[bool, list[str]], tuple[bool, list[str]]]]:
    doc = json.loads((FIXTURES / name).read_text())
    official = name.startswith("official")
    machine = Machine(commands=() if official else ("RUNSTATE", "STEPIN", "SAVESTATE",
                                                   "LOADSTATE", "PRESENCE"))
    if "dpmi" in name:
        protected(machine)
    else:
        machine.regs = dict(REAL_STOP)
    out = []
    for e in doc["exchanges"]:
        request, said = e["request"], (e["ok"], e["lines"])
        word = request.removeprefix("EXEC ").split()[0].upper()
        if word == "EV" and request.startswith("EXEC EV EAX EBX"):
            values = said[1][-1].split()
            names = request.split()[2:]
            machine.regs.update({n: int(v, 16) for n, v in zip(names, values, strict=True)})
        if word in MODELLED:
            out.append((request, machine.request(request), said))
    return out


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_each_modelled_reply_is_the_one_the_debugger_gave(name: str) -> None:
    replayed = _replayed(name)
    assert replayed, f"{name} has no exchange the double models: the control replays nothing"
    wrong = [(req, got, said) for req, got, said in replayed if got != said]
    assert not wrong, wrong[:3]


def test_the_run_state_line_is_the_one_runstate_printed() -> None:
    doc = json.loads((FIXTURES / "scry-real.json").read_text())
    said = next(e["lines"] for e in doc["exchanges"] if e["request"] == "EXEC RUNSTATE")
    got = Machine(clock_ms=0.7).request("EXEC RUNSTATE")[1]
    assert got == said, (got, said)


def test_a_build_without_the_command_answers_as_the_official_build_did() -> None:
    doc = json.loads((FIXTURES / "official-step.json").read_text())
    said = {e["request"]: (e["ok"], e["lines"]) for e in doc["exchanges"]}
    machine = Machine(commands=())
    for request in ("EXEC RUNSTATE", "EXEC STEPIN"):
        assert machine.request(request) == said[request]


def test_the_selector_lines_are_the_captured_ones_in_both_modes() -> None:
    for name, machine in (("scry-real.json", Machine()),
                          ("scry-dpmi.json", protected(Machine()))):
        doc = json.loads((FIXTURES / name).read_text())
        for e in doc["exchanges"]:
            if e["request"] in ("EXEC SELINFO CS", "EXEC SELINFO DS"):
                assert machine.request(e["request"]) == (e["ok"], e["lines"]), (name, e)


def test_the_protected_stop_is_the_captured_one() -> None:
    doc = json.loads((FIXTURES / "scry-dpmi.json").read_text())
    ev = next(e for e in doc["exchanges"] if e["request"].startswith("EXEC EV EAX EBX"))
    names = ev["request"].split()[2:]
    assert {n: int(v, 16) for n, v in zip(names, ev["lines"][-1].split(), strict=True)} \
        == PROTECTED_STOP


def test_the_stepped_landing_is_the_line_stepin_printed(tmp_path: Path) -> None:
    doc = json.loads((FIXTURES / "scry-step.json").read_text())
    said = next(e["lines"] for e in doc["exchanges"] if e["request"] == "EXEC STEPIN")
    machine = Machine(steps=[{"EIP": 0x105, "EAX": 0x1234, "ECX": 0xFF, "EBX": 0}])
    assert machine.request("EXEC STEPIN")[1] == said


def _capture_exchanges() -> list[tuple[str, list[str]]]:
    """`tests/fixtures/captures/capture-lines.txt`: each request (`## ...`) and what it printed."""
    out: list[tuple[str, list[str]]] = []
    for line in (FIXTURES.parent / "captures" / "capture-lines.txt").read_text().splitlines():
        if line.startswith("## "):
            out.append((line[3:], []))
        elif out and not line.startswith("#"):
            out[-1][1].append(line)
    return out


def test_capture_answers_as_the_debugger_did() -> None:
    said = dict(_capture_exchanges())
    machine = Machine(cwd=Path("/"))
    assert machine.request("EXEC CAPTURE")[1] == said["CAPTURE"]
    assert machine.request("EXEC CAPTURE OPL ON")[1] == said["CAPTURE OPL ON"]
    assert machine.request("EXEC CAPTURE WAV ON")[1] == said["CAPTURE WAV ON"]
    # The capture was made on a POSIX host, whose separators any host's double must print.
    machine.capturing.update(WAV=cast(Path, PurePosixPath("/captures/sound_000.wav")),
                             VIDEO=cast(Path, PurePosixPath("/captures/sound_000.avi")))
    del machine.capturing["OPL"]
    assert machine.request("EXEC CAPTURE")[1] == said["CAPTURE (while recording)"]
    assert machine.request("EXEC CAPTURE WAV OFF")[1] == said["CAPTURE WAV OFF"]
    machine.request("EXEC CAPTURE MIDI ON")
    assert machine.request("EXEC CAPTURE MIDI OFF")[1] == said[
        "CAPTURE MIDI OFF (no data arrived)"]
