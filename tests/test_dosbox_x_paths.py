"""Every path a caller gives this server, judged by one rule: absolute, `~` not expanded, the
shape before the session gate and the filesystem at the call (`dosbox_paths`)."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from test_dosbox_x_dump import debugger
from test_dosbox_x_server import clean_session, install  # noqa: F401

import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

#: Every (tool, argument) that carries a path. The registry test below holds the registered
#: tools' arguments NAMED as paths (`paths.PATH_PARAMETERS`) to it: a new one under one of those
#: names is added here and meets the rule, or fails; a path argument under another name is the
#: set's to add first.
INVENTORY = frozenset({
    ("start", "cwd"), ("start", "conf"), ("start", "logfile"), ("start", "captures_dir"),
    ("start", "state_dir"), ("memdump", "dest"), ("trace", "dest"), ("snapshot", "dest"),
    ("palette", "dest"), ("screen_view", "dest"), ("capture_frame", "dest"),
    ("capture_frame", "source"), ("symbols_load", "source"), ("symbols_load", "types"),
    ("comment_save", "dest"), ("comment_load", "source"), ("start", "binary"),
    ("build_check", "binary"), ("machine_map", "dest"),
})


def _refused(reply: Any, code: str, *words: str) -> None:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "INVALID" and r["code"] == code, r
    for w in words:
        assert w in r["message"], (w, r["message"])


# ------------------------------------------------------------------ the judge itself


@pytest.mark.parametrize(("value", "words"), [
    ("~/x.bin", "`~`"), ("~", "`~`"), ("~user/x", "`~`"),
    ("rel/x.bin", "relative"), ("x.bin", "relative"), ("./x", "relative"),
    ("", "empty"), ("/a\x00b", "NUL"), ("/a\udc80b", "surrogate"), (None, "not a path"),
])
def test_a_path_that_is_not_absolute_is_refused_naming_the_argument(
        value: object, words: str) -> None:
    with pytest.raises(ds.Invalid) as e:
        paths.absolute("dest", value)
    assert e.value.code == "bad_argument" and "dest" in str(e.value) and words in str(e.value)


def test_the_tilde_refusal_writes_the_home_directory_out() -> None:
    with pytest.raises(ds.Invalid, match=str(Path.home())):
        paths.absolute("cwd", "~/proj")


def test_the_tilde_refusal_stands_when_no_home_can_be_named(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")
    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    with pytest.raises(ds.Invalid, match="home directory, spelled in full"):
        paths.absolute("cwd", "~/proj")


def test_an_absolute_path_is_taken_as_written() -> None:
    assert paths.absolute("dest", "/tmp/x.bin") == Path("/tmp/x.bin")


def test_a_fresh_dest_has_its_directory_and_nothing_at_it(tmp_path: Path) -> None:
    assert paths.fresh_dest("dest", str(tmp_path / "new.bin")) == tmp_path / "new.bin"
    there = tmp_path / "there.bin"
    there.write_bytes(b"mine")
    dangling = tmp_path / "dangling.bin"
    dangling.symlink_to(tmp_path / "nowhere" / "x")
    afile = tmp_path / "afile"
    afile.write_bytes(b"")
    for dest, words in ((there, "already exists"), (dangling, "already exists"),
                        (tmp_path / "missing" / "x.bin", "is not a directory"),
                        (afile / "x.bin", "is not a directory")):
        with pytest.raises(ds.Invalid, match=words) as e:
            paths.fresh_dest("dest", str(dest))
        assert e.value.code == "bad_argument"
    assert there.read_bytes() == b"mine" and dangling.is_symlink()


def test_an_input_file_is_a_regular_file_there(tmp_path: Path) -> None:
    f = tmp_path / "x.sym"
    f.write_text("x")
    assert paths.input_file("source", str(f), "symbol file") == f
    for value in (str(tmp_path / "absent.sym"), str(tmp_path)):
        with pytest.raises(ds.Invalid, match="no symbol file at"):
            paths.input_file("source", value, "symbol file")


def test_a_path_the_host_will_not_look_at_or_read_is_refused_not_raised(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Before 3.14 a stat can raise rather than answer, a resolve can raise on a loop, and a
    read can be refused by the file's mode: each is a refusal naming the argument."""
    f = tmp_path / "t.types"
    f.write_text("pos: u32\n")
    f.chmod(0)
    try:
        with pytest.raises(ds.Invalid, match="types: .* cannot be read"):
            paths.read_text("types", str(f), "types file")
    finally:
        f.chmod(0o644)

    def raises(self: Path, *a: Any, **k: Any) -> Any:
        raise RuntimeError("Symlink loop")
    monkeypatch.setattr(Path, "resolve", raises)
    with pytest.raises(ds.Invalid, match="cwd: .* cannot be resolved"):
        paths.resolved("cwd", tmp_path)
    monkeypatch.undo()

    def denied(self: Path, *a: Any, **k: Any) -> bool:
        raise PermissionError(13, "Permission denied", str(self))
    monkeypatch.setattr(Path, "is_file", denied)
    with pytest.raises(ds.Invalid, match="source: .* cannot be looked at"):
        paths.input_file("source", str(f), "symbol file")


def test_a_text_file_that_is_not_utf8_is_refused_where_it_broke(tmp_path: Path) -> None:
    f = tmp_path / "t.types"
    f.write_bytes(b"pos: u32\nname: char[8] \x82 cp437\n")
    with pytest.raises(ds.Invalid) as e:
        paths.read_text("types", str(f), "types file")
    assert e.value.code == "bad_argument" and str(f) in str(e.value) and "byte 23" in str(e.value)
    with pytest.raises(ds.Invalid) as e:
        placement.read_types(str(f))
    assert e.value.code == "bad_argument" and "UTF-8" in str(e.value)


# ------------------------------------------------- every path argument, with no session


def _start_stubbed(**kw: Any) -> dict[str, Any]:
    """`start` as far as it goes before a process: the emulator is never spawned."""
    def build(launch: ds.Launch) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    with mock.patch("dosbox_binary.shutil.which", lambda _n: "/somewhere/dosbox-x"), \
         mock.patch("dosbox_x_server.ds.Session", build):
        reply: Any = server.start(**kw)
    return cast(dict[str, Any], reply)


def _base(tool: str, tmp_path: Path) -> dict[str, Any]:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n")
    sym = tmp_path / "g.sym"
    sym.write_text("0000:0000 x\n")
    table: dict[str, dict[str, Any]] = {
        "start": {"conf": str(conf), "cwd": str(tmp_path), "seconds": 60},
        "memdump": {"ref": "0000:0000", "length": 16, "dest": str(tmp_path / "d.bin")},
        "trace": {"instructions": 16, "dest": str(tmp_path / "t.trace")},
        "snapshot": {"dest": str(tmp_path / "s.png")},
        "palette": {"dest": str(tmp_path / "p.png")},
        "screen_view": {"dest": str(tmp_path / "v.png")},
        "capture_frame": {"at": 0, "dest": str(tmp_path / "f.png"),
                          "source": str(tmp_path / "c.avi")},
        "symbols_load": {"source": str(sym), "types": str(sym)},
        "comment_save": {"dest": str(tmp_path / "c.tsv")},
        "comment_load": {"source": str(tmp_path / "c.tsv")},
        "build_check": {},
        "machine_map": {"dest": str(tmp_path / "m.json")},
    }
    return table[tool]


@pytest.mark.parametrize(("tool", "arg"), sorted(INVENTORY))
@pytest.mark.parametrize("spelled", ["~/x", "rel/x"])
def test_every_path_argument_refuses_tilde_and_relative_with_no_session(
        tool: str, arg: str, spelled: str, tmp_path: Path) -> None:
    kw = {**_base(tool, tmp_path), arg: spelled}
    reply = _start_stubbed(**kw) if tool == "start" else getattr(server, tool)(**kw)
    _refused(reply, "bad_argument", f"{arg}={spelled!r}")


def test_the_inventory_is_every_path_argument_the_server_registers() -> None:
    found = {(t.name, p) for t in server.mcp._tool_manager.list_tools()
             for p in t.parameters.get("properties", {}) if p in paths.PATH_PARAMETERS}
    assert found == INVENTORY


# ------------------------------------------------------------------ start's paths


def test_a_cwd_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    _refused(_start_stubbed(**{**kw, "cwd": str(tmp_path / "absent")}), "bad_argument", "cwd")
    _refused(_start_stubbed(**{**kw, "cwd": kw["conf"]}), "bad_argument", "cwd")


def test_a_conf_that_is_not_there_is_refused_naming_it(tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    _refused(_start_stubbed(**{**kw, "conf": str(tmp_path / "absent.conf")}), "bad_argument",
             "conf")


def test_a_logfile_whose_directory_is_missing_or_that_is_a_directory_is_refused(
        tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    _refused(_start_stubbed(**{**kw, "logfile": str(tmp_path / "nowhere" / "e9.log")}),
             "bad_argument", "logfile", str(tmp_path / "nowhere"))
    _refused(_start_stubbed(**{**kw, "logfile": str(tmp_path)}), "bad_argument", "logfile")


def test_a_logfile_that_is_the_conf_is_refused_and_the_conf_kept(tmp_path: Path) -> None:
    """The emulator opens its log afresh, so a logfile naming the conf (by its own path, a link
    or a second name of the same file) would write the log over the conf the session boots."""
    kw = _base("start", tmp_path)
    conf = Path(kw["conf"])
    before = conf.read_bytes()
    link = tmp_path / "e9-link.log"
    link.symlink_to(conf)
    hard = tmp_path / "e9-hard.log"
    os.link(conf, hard)
    for log in (conf, link, hard):
        _refused(_start_stubbed(**{**kw, "logfile": str(log)}), "bad_argument", "logfile",
                 "conf")
    assert conf.read_bytes() == before
    # the control: a logfile beside the conf reaches the boot
    _refused(_start_stubbed(**{**kw, "logfile": str(tmp_path / "e9.log")}), "session_broken")


def test_a_logfile_that_is_a_link_is_judged_by_the_file_it_names(tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    dangling = tmp_path / "e9.log"
    dangling.symlink_to(tmp_path / "missing" / "x.log")
    _refused(_start_stubbed(**{**kw, "logfile": str(dangling)}), "bad_argument", "logfile",
             str(tmp_path / "missing"))
    # the control: a link to a free name in a directory that is there reaches the boot
    free = tmp_path / "e9-free.log"
    free.symlink_to(tmp_path / "free.log")
    _refused(_start_stubbed(**{**kw, "logfile": str(free)}), "session_broken")


def test_a_logfile_that_is_a_link_loop_is_refused_naming_it(tmp_path: Path) -> None:
    """A link that comes back to itself, at once or round a second link, names no file: the
    emulator would write its log nowhere and say nothing, as under a missing directory."""
    kw = _base("start", tmp_path)
    own = tmp_path / "own.log"
    own.symlink_to(own)
    there, back = tmp_path / "there.log", tmp_path / "back.log"
    there.symlink_to(back)
    back.symlink_to(there)
    for log in (own, there):
        _refused(_start_stubbed(**{**kw, "logfile": str(log)}), "bad_argument", "logfile",
                 str(log), "loop")


def test_a_byte_order_mark_an_editor_wrote_is_not_part_of_the_first_name(
        tmp_path: Path) -> None:
    f = tmp_path / "t.types"
    f.write_bytes(b"\xef\xbb\xbfPOS: u32\nB: u8\n")
    got = placement.read_types(str(f))
    assert "POS" in got and not any(k.startswith("﻿") for k in got), got


@pytest.mark.parametrize("arg", ["captures_dir", "state_dir"])
def test_a_directory_start_cannot_create_is_host_failed(tmp_path: Path, arg: str) -> None:
    kw = _base("start", tmp_path)
    afile = tmp_path / "afile"
    afile.write_bytes(b"")
    _refused(_start_stubbed(**{**kw, arg: str(afile / "sub")}), "host_failed", str(afile))


@pytest.mark.parametrize("arg", ["captures_dir", "state_dir"])
def test_a_directory_start_names_is_created_with_its_parents(tmp_path: Path, arg: str) -> None:
    kw = _base("start", tmp_path)
    where = tmp_path / "a" / "b"
    _refused(_start_stubbed(**{**kw, arg: str(where)}), "session_broken")
    assert where.is_dir()


def test_start_takes_no_savedir_argument() -> None:
    res = asyncio.run(server.mcp.call_tool("start", {"conf": "/x.conf", "cwd": "/", "seconds": 60,
                                                    "savedir": "/tmp/states"}))
    reply = json.loads("".join(c.text for c in res.content if getattr(c, "text", None)))
    _refused(reply, "bad_argument", "savedir")


def test_the_state_directory_is_state_dir_in_status_and_state_list(tmp_path: Path) -> None:
    launch = ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60,
                       state_dir=tmp_path / "states")
    bare = ds.Session.__new__(ds.Session)
    bare.launch = launch
    assert ds.Session.state_list(bare)["state_dir"] == str(tmp_path / "states")
    assert "savedir" not in ds.Session.state_list(bare)


# ------------------------------------------------------------------ the dests at the call


@pytest.mark.parametrize("tool", ["memdump", "palette", "trace"])
def test_a_dangling_link_dest_is_refused_and_nothing_written_through(
        tool: str, tmp_path: Path) -> None:
    """Judged right before the write, by the one judge: `memdump` through the real
    `Session.memdump` over a debugger double, the others before anything is typed."""
    if tool == "memdump":
        debugger(tmp_path)
    else:
        install()
    link = tmp_path / "link.out"
    target = tmp_path / "elsewhere" / "x"
    link.symlink_to(target)
    kw = {**_base(tool, tmp_path), "dest": str(link)}
    _refused(getattr(server, tool)(**kw), "bad_argument", "already exists")
    assert link.is_symlink() and not target.exists()


# ------------------------------------------------------- start's order and its empties


def test_start_judges_a_path_before_a_live_session_or_the_binary(tmp_path: Path) -> None:
    """A path as wrong with a session live as with none, and with no emulator installed: the
    path is the refusal, and nothing of the live session is touched."""
    live = install()
    got = cast(dict[str, Any], server.start(conf="/x.conf", cwd="~/x", seconds=60))
    _refused(got, "bad_argument", "cwd='~/x'")
    assert cast(object, dstate.STATE.session) is live
    dstate.STATE.session = None
    with mock.patch("dosbox_binary.shutil.which", lambda _n: None):
        got = cast(dict[str, Any], server.start(conf="rel.conf", cwd="/", seconds=60))
    _refused(got, "bad_argument", "conf='rel.conf'")


def test_start_judges_the_binary_s_shape_before_a_live_or_expired_session(
        tmp_path: Path) -> None:
    """`binary` is a path like the others: a relative one is the refusal whatever the session
    is, and an expired session is neither closed nor its symbols forgotten for it."""
    live = install()
    got = cast(dict[str, Any], server.start(conf="/x.conf", cwd="/", seconds=60,
                                            binary="rel/dosbox-x"))
    _refused(got, "bad_argument", "binary='rel/dosbox-x'")
    assert cast(object, dstate.STATE.session) is live
    expired = install(alive=False)
    closed: list[bool] = []
    expired.close = lambda **_k: closed.append(True)   # type: ignore[method-assign]
    got = cast(dict[str, Any], server.start(conf="/x.conf", cwd="/", seconds=60,
                                            binary="~/dosbox-x"))
    _refused(got, "bad_argument", "binary='~/dosbox-x'")
    assert closed == [] and cast(object, dstate.STATE.session) is expired


def test_a_start_refused_for_another_reason_creates_no_directory(tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    made = tmp_path / "caps"
    _refused(_start_stubbed(**{**kw, "seconds": 0, "captures_dir": str(made)}), "bad_argument")
    _refused(_start_stubbed(**{**kw, "logfile": str(made), "captures_dir": str(made)}),
             "bad_argument", "logfile", "captures_dir")
    _refused(_start_stubbed(**{**kw, "logfile": str(made), "state_dir": str(made)}),
             "bad_argument", "logfile", "state_dir")
    assert not made.exists() and not (tmp_path / "save").exists()


def test_a_directory_already_there_is_taken_and_the_default_state_dir_is_made(
        tmp_path: Path) -> None:
    kw = _base("start", tmp_path)
    there = tmp_path / "states"
    there.mkdir()
    _refused(_start_stubbed(**{**kw, "state_dir": str(there)}), "session_broken")
    _refused(_start_stubbed(**kw), "session_broken")
    assert there.is_dir() and (tmp_path / "save").is_dir()


@pytest.mark.parametrize("arg", ["logfile", "captures_dir", "state_dir"])
def test_an_empty_optional_path_of_start_is_refused_not_taken_for_none(
        tmp_path: Path, arg: str) -> None:
    """An argument whose absence is its default (none) is refused when given empty; a `dest`
    whose default is the empty string takes it as none (the next case)."""
    _refused(_start_stubbed(**{**_base("start", tmp_path), arg: ""}), "bad_argument",
             f"{arg} is empty")


def test_an_empty_dest_means_none_where_that_is_its_default() -> None:
    for tool in ("palette", "screen_view", "snapshot", "trace"):
        kw: dict[str, Any] = {"instructions": 16} if tool == "trace" else {}
        got = cast(dict[str, Any], getattr(server, tool)(dest="", **kw))
        assert got["code"] == "no_session", (tool, got)


# ------------------------------------------------------------------ the readers


def test_a_map_with_a_code_page_byte_loads_and_one_the_host_will_not_read_is_refused(
        tmp_path: Path) -> None:
    from test_dosbox_x_server import _names
    nm = tmp_path / "cp437.nm"
    nm.write_bytes(b"0016dd80 T _main\n0016dd90 T _caf\x82\n")
    _names(tmp_path)
    got = cast(dict[str, Any], server.symbols_load(source=str(nm), base="400000"))
    assert got["status"] == "ok" and got["kept"] >= 1, got
    nm.chmod(0)
    try:
        got = cast(dict[str, Any], server.symbols_load(source=str(nm), base="400000"))
    finally:
        nm.chmod(0o644)
    _refused(got, "bad_argument", "cannot read")


def test_a_capture_source_that_is_not_there_is_refused_naming_it(tmp_path: Path) -> None:
    install()
    got = server.capture_frame(at=1, dest=str(tmp_path / "f.png"),
                               source=str(tmp_path / "absent.avi"))
    _refused(got, "bad_argument", "no capture at", str(tmp_path / "absent.avi"))
