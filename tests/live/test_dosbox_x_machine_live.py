"""The DOS guest run through the server: its DOS calls traced with their results, its ports and
interrupt controller, its counter frozen, and the file it leaves (`tests/guest/dosio.asm`)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from live_private import guest_dir

from scry_dosbox_x import server

pytestmark = pytest.mark.live

GUEST = guest_dir()


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def test_the_dos_guest_through_the_machine_tools_and_its_channels(tmp_path: Path) -> None:
    for name in ("dosio.com", "dosio.conf", "in.txt"):
        shutil.copy2(GUEST / name, tmp_path / name)
    out = tmp_path / "OUT.TXT"
    _ok(server.start(conf=str(tmp_path / "dosio.conf"), cwd=str(tmp_path), session_seconds=120,
                     program="DOSIO.COM W", dos_calls=True, guest_files=[str(out)],
                     logfile=str(tmp_path / "s.log"), presence=False))
    assert _ok(server.run_for(milliseconds=3000))["verdict"] == "ELAPSED"
    missing = _ok(server.log(pattern="MISSING", channel="dos"))["calls"]
    assert missing[0]["error"] == {"code": 2, "name": "file not found"}, missing
    psp = missing[0]["psp"][2:]
    assert _ok(server.log_wait(pattern=r"open IN\.TXT", channel="dos", seconds=5))["already"]
    assert _ok(server.port(method="read", port=0x21))["value"].startswith("0x")
    assert _ok(server.pic(method="read"))["irqs"][2]["cascade"] is True
    assert isinstance(_ok(server.a20(method="read"))["enabled"], bool)
    frozen = _ok(server.watch_add(ref=f"{psp}:018F", mode="freeze", length=1))
    stop = _ok(server.run_for(milliseconds=500))
    assert stop["verdict"] == "ELAPSED", stop
    held = next(w for w in stop["watches"] if w["ref"] == f"{psp}:018F")
    assert held["state"] == "holding" and held["bytes"] == frozen["frozen_hex"], held
    assert _ok(server.guest_file(path=str(out)))["state"] == "written"
    closed = _ok(server.close())
    assert closed["guest_files"][0]["state"] == "written" and out.read_bytes() == b"SCRY"
