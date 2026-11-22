"""What a reply names with `names` on and off, and what the base answers for an unserved key."""
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
#: `int 21h`, which DOS reads as the function in AH.
INT_21 = "CD21"
EXIT = 0x4C00


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def _named_at_exit(tmp_path: Path, names: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """`breakpoint_interrupt`'s reply for DOS's exit and the `disassemble` of an `int 21h` at
    AH=4Ch, in a session started with `names`."""
    where = tmp_path / f"names-{names}"
    where.mkdir()
    for name in ("dosio.com", "dosio.conf", "in.txt"):
        shutil.copy2(GUEST / name, where / name)
    _ok(server.start(conf=str(where / "dosio.conf"), cwd=str(where), session_seconds=60,
                     program="DOSIO.COM W", names=names, presence=False,
                     logfile=str(where / "s.log")))
    armed = _ok(server.breakpoint_interrupt(number=0x21, ah=0x4C))
    here = _ok(server.run_for(milliseconds=3000))["pc"]
    _ok(server.write(ref=here, data_hex=INT_21))
    _ok(server.set_register(name="eax", value=EXIT))
    listing = _ok(server.disassemble(ref=here, length=2))
    _ok(server.close())
    return armed, listing


def test_names_off_leaves_a_reply_bare_and_a_disassembled_line_with_no_note(
        tmp_path: Path) -> None:
    armed, listing = _named_at_exit(tmp_path, names=True)
    assert [n["name"] for n in armed["names"]] == ["exit"], armed
    assert listing["line_notes"] == [{"line": 0, "note": "exit (0x4C)", "live": True}], listing
    bare, plain = _named_at_exit(tmp_path, names=False)
    assert "names" not in bare, bare
    assert "line_notes" not in plain, plain
    # Addresses differ between launches; the decoding must not.
    assert [ln.split(None, 1)[1] for ln in plain["lines"]] == [
        ln.split(None, 1)[1] for ln in listing["lines"]], "the names changed the decoding"


def test_a_key_the_base_does_not_serve_answers_none_and_says_it_stays_a_number() -> None:
    reply = _ok(server.knowledge_find(kind="call", key="0x21/0x3D"))
    assert reply["entries"] == [] and reply["entries_total"] == 0, reply
    assert reply["unconfirmed"] == ["ibm-pc:call:0x21/0x3D"], reply
    assert "not confirmed, so it is not served" in reply["note"], reply
    assert reply["session"]["alive"] is False, reply
