"""A raw address is stale by the build it was declared against, not by which session."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dosbox_x_server_support import _names, build_of, clean_session, install  # noqa: F401

from scry_dosbox_x import declarations as dec
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import server
from scry_dosbox_x import state as dstate


def test_a_declaration_carries_the_fingerprint_it_was_made_against() -> None:
    d = dec.Declaration("breakpoint", "address", "00A7:5C6F0", origin="s1", fingerprint="fp1")
    assert d.to_dict()["fingerprint"] == "fp1"
    assert dec.Declaration.from_dict(d.to_dict()) == d
    assert dec.Declaration.from_dict(d.to_dict()).fingerprint == "fp1"
    assert d.adopted_by("s2", "t2", "fp2").fingerprint == "fp2"
    assert "fingerprint" not in dec.Declaration("breakpoint", "address", "00A7:5C6F0").to_dict()


def test_the_fingerprint_is_the_conf(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[autoexec]\nGAME.EXE\n")
    one = dlaunch.fingerprint(conf)
    assert one == dlaunch.fingerprint(conf) and len(one) == 16
    conf.write_text("[autoexec]\nGAME.EXE /x\n")
    assert dlaunch.fingerprint(conf) != one


def test_symbols_load_re_arms_a_raw_address_over_the_same_map_and_leaves_it_over_another(
        tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    conf = fake.launch.conf
    dstate.STATE.conf_fingerprint = dlaunch.fingerprint(conf)

    def a_session(origin: str) -> dict[str, Any]:
        fake.rows.clear()
        dstate.STATE.forget_symbols()
        dstate.STATE.session_origin = origin
        got: dict[str, Any] = server.symbols_load(path=str(nm), base="0x400000")
        return got

    a_session("s1")
    server.breakpoint_at(ref="00A7:5C6F0")
    server.breakpoint_at(ref="_main")
    (raw,) = [d for d in dstate.STATE.store.declarations()   # type: ignore[union-attr]
              if d.by == "address"]
    assert raw.fingerprint == build_of(conf, nm.read_text(encoding="utf-8"))
    # same conf and map: everything re-arms, whoever declared it
    got = a_session("s2")
    assert got["declarations"]["stale"] == [], got["declarations"]
    assert {r["ref"] for r in got["declarations"]["rearmed"]} == {"_main", "00A7:5C6F0"}
    # relinked: the raw address is stale, the name re-resolves
    nm.write_text("00001000 T _start\n0016dd90 T _main\n", encoding="utf-8")
    got = a_session("s3")
    assert [r["ref"] for r in got["declarations"]["stale"]] == ["00A7:5C6F0"], \
        got["declarations"]
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"]
    listed = {b["ref"]: b for b in server.declaration_list("breakpoint")["breakpoints"]}
    assert listed["00A7:5C6F0"]["state"] == "stale"
    assert "no map held now vouches" in listed["00A7:5C6F0"]["why"]
