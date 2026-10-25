"""`memdump` past a segment's 64 KiB, and the debugger's own dump file around it.

Upstream reads byte `x` at `GetAddress(seg, off + x)`: the offset masked to sixteen bits on a
16-bit segment, no address past a protected-mode limit. `Debugger` is that rule over an image
holding the captured probe bytes (`fixtures/memdump/`).
"""
from __future__ import annotations

import random
import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import FakeSession, clean_session, install  # noqa: F401
from test_dosbox_x_machine import Bench

import dosbox_collect as dcollect
import dosbox_dump as dumping
import dosbox_find as finder
import dosbox_machine as machine
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

MEMDUMP = Path(__file__).parent / "fixtures" / "memdump"
PROBE_PSP_LINEAR = 0x8140                # 0814:0000
AFTER_PSP_LINEAR = 0x18130               # 1813:0000, the bytes that really follow 0814:FFFF
DUMP_COMMAND = re.compile(
    r"MEMDUMPBIN (?P<seg>[0-9A-F]{4}):(?P<off>[0-9A-F]+) (?P<len>[0-9A-F]+)(?: (?P<name>\S+))?$")
# Captured: `MEMDUMPBIN 0000:0000 20` wrote `00:0000 20`, the line from this offset on.
ARGS_TAIL_FROM = len("MEMDUMPBIN 00")
REAL_MEMORY = 0x110000                   # the megabyte and the HMA, A20 on as on the probe


def image() -> bytearray:
    """A memory image in which no 64 KiB window repeats another, with the captured bytes."""
    mem = bytearray((a * 7 + (a >> 8) * 13 + (a >> 16) * 101) & 0xFF for a in range(REAL_MEMORY))
    for at, name in ((PROBE_PSP_LINEAR, "probe-0814-0000.bin"),
                     (AFTER_PSP_LINEAR, "probe-1813-0000.bin")):
        data = (MEMDUMP / name).read_bytes()
        mem[at:at + len(data)] = data
    return mem


class Debugger(FakeSession):
    """A stopped real-mode machine whose `MEMDUMPBIN` is upstream's; `Session.memdump` runs
    for real against it.

    The default build writes `MEMDUMP.BIN` whatever follows the length. `takes_name` reads an
    optional name: given none, it names the file after the argument tail (`ARGS_TAIL_FROM`),
    which no candidate matches."""

    def __init__(self, cwd: Path, *, says: str = "DEBUG: Memory dump binary success.",
                 writes: bool = True, takes_name: bool = False) -> None:
        super().__init__()
        self.launch = SimpleNamespace(cwd=cwd, logfile=None, captures_dir=None, watched=False,
                                      input_port=None)
        self.mem = image()
        self.says = says
        self.writes = writes
        self.takes_name = takes_name
        self.typed: list[str] = []
        self.wrote: list[str] = []

    def command(self, text: str, **_: object) -> str:
        self.typed.append(text)
        line = text.upper()                 # `ParseCommand` upper-cases the line
        m = DUMP_COMMAND.match(line)
        assert m, text
        seg, off, n = (int(m[g], 16) for g in ("seg", "off", "len"))
        name = ((m["name"] or line[ARGS_TAIL_FROM:]) if self.takes_name
                else ds.MEMDUMP_NAME.upper())
        if self.writes:
            data = bytes(self.mem[seg * 16 + ((off + x) & 0xFFFF)] for x in range(n))
            (self.launch.cwd / name).write_bytes(data)
            self.wrote.append(name)
        return f"{self.says}\r\nI-> _"

    def _memdump_candidates(self) -> list[Path]:
        return ds.Session._memdump_candidates(cast(ds.Session, self))

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.memdump_calls.append((seg, off, length))
        return ds.Session.memdump(cast(ds.Session, self), seg, off, length, dest)


def test_the_double_reads_one_command_across_offset_ffff_as_the_debugger_did(
        tmp_path: Path) -> None:
    """One command from 0814:FFF0 gives the bytes the debugger wrote live, wrap included."""
    s = Debugger(tmp_path)
    s.command("MEMDUMPBIN 0814:FFF0 20")
    written = (tmp_path / ds.MEMDUMP_NAME.upper()).read_bytes()
    assert written == (MEMDUMP / "probe-0814-FFF0-wrapped.bin").read_bytes()


def test_the_takes_name_double_writes_the_files_the_captured_build_wrote(
        tmp_path: Path) -> None:
    """A named dump lands under that name, an unnamed one under its argument tail."""
    s = Debugger(tmp_path, takes_name=True)
    s.command("MEMDUMPBIN 0000:0000 10 MCPDUMP.BIN")
    s.command("MEMDUMPBIN 0000:0000 20")
    assert {p.name: p.stat().st_size for p in tmp_path.iterdir()} == {
        "MCPDUMP.BIN": 0x10, "00:0000 20": 0x20}


def debugger(tmp_path: Path, **kw: Any) -> Debugger:
    cwd = tmp_path / "cwd"
    cwd.mkdir(exist_ok=True)
    s = Debugger(cwd, **kw)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


def dumped(ref: str, length: int, dest: Path) -> dict[str, Any]:
    return cast(dict[str, Any], server.memdump(ref=ref, length=length, dest=str(dest)))




@pytest.mark.parametrize(("seg", "off", "length", "windows"), [
    (0x0814, 0x0100, 0x10, [(0x0814, 0x0100, 0x10)]),
    (0x0000, 0x0000, 0x10000, [(0x0000, 0x0000, 0x10000)]),
    (0x0000, 0xFFFF, 2, [(0x0FFF, 0xF, 2)]),
    (0x0814, 0xFFF0, 0x20, [(0x1813, 0x0, 0x20)]),
    (0xF000, 0xFFF0, 0x20, [(0xFFFF, 0x0, 0x20)]),
    (0x0000, 0x0000, 0x100000, [(k * 0x1000, 0, 0x10000) for k in range(16)]),
    (0x0001, 0xFFF8, 0x20010, [(0x1000, 8, 0xFFF8), (0x2000, 0, 0x10000), (0x3000, 0, 0x18)]),
    (0xFFFF, 0x0000, 0x10000, [(0xFFFF, 0, 0x10000)]),
    (0xF000, 0x0000, 0x1FFF0, [(0xF000, 0, 0x10000), (0xFFFF, 0x10, 0xFFF0)]),
])
def test_a_range_is_read_in_windows_that_never_cross_a_segments_end(
        seg: int, off: int, length: int, windows: list[tuple[int, int, int]]) -> None:
    assert dumping.dump_windows(seg, off, length) == windows


@pytest.mark.parametrize(("seg", "off", "length"), [
    (0xFFFF, 0x0010, 0x10000), (0xF000, 0x0000, 0x20000), (0x0000, 0x0000, 0x10FFF1)])
def test_a_range_past_the_last_real_mode_byte_is_refused_naming_it(
        seg: int, off: int, length: int) -> None:
    with pytest.raises(ds.Invalid, match="FFFF:FFFF") as e:
        dumping.dump_windows(seg, off, length)
    assert e.value.code == "bad_argument"


def test_a_start_already_past_ffff_ffff_says_no_byte_is_reachable_from_there() -> None:
    with pytest.raises(ds.Invalid, match="starts past FFFF:FFFF") as e:
        dumping.dump_windows(0xFFFF, 0x20000, 1)
    assert "at most" not in str(e.value), "a length to ask for where none can be"


def test_the_last_byte_real_mode_reaches_is_dumped_and_one_past_it_is_not() -> None:
    assert dumping.REAL_REACH_LAST == 0xFFFF * machine.PARAGRAPH_BYTES + 0xFFFF
    assert dumping.dump_windows(0xFFFF, 0xFFFF, 1) == [(0xFFFF, 0xFFFF, 1)]
    assert dumping.dump_windows(0x0000, 0x0000, 0x10FFF0)[-1] == (0xFFFF, 0x10, 0xFFF0)
    with pytest.raises(ds.Invalid):
        dumping.dump_windows(0xFFFF, 0xFFFF, 2)


def test_every_window_sits_in_one_segment_and_together_they_are_the_range() -> None:
    rng = random.Random(0x10000)
    for _ in range(2000):
        seg, off = rng.randrange(0x10000), rng.randrange(0x10000)
        start = seg * 16 + off
        length = rng.randrange(1, min(0x30000, dumping.REAL_REACH_LAST - start + 1) + 1)
        at = start
        for s, o, n in dumping.dump_windows(seg, off, length):
            assert 0 <= s <= 0xFFFF and o + n <= 0x10000 and n > 0
            assert s * 16 + o == at
            at += n
        assert at == start + length


# -------------------------------------------------------- real mode, through the tool


def test_a_megabyte_from_0000_is_the_memory_there_and_not_window_0_sixteen_times(
        tmp_path: Path) -> None:
    """Bytes 0x10000-0x100FF equal what `1000:0000` holds, not bytes 0-0xFF, and the reply
    carries `ref`, `path` and `bytes`."""
    s = debugger(tmp_path)
    whole = dumped("0000:0000", 0x100000, tmp_path / "1m.bin")
    one = dumped("1000:0000", 256, tmp_path / "1000.bin")
    assert whole["status"] == "ok" and set(whole) >= {"ref", "path", "bytes"}, whole
    assert one["status"] == "ok", one
    assert whole["bytes"] == 0x100000
    data = (tmp_path / "1m.bin").read_bytes()
    assert data == bytes(s.mem[:0x100000])
    assert data[0x10000:0x10100] == (tmp_path / "1000.bin").read_bytes() != data[:0x100]
    assert [c[2] for c in s.memdump_calls[:16]] == [0x10000] * 16


def test_a_dump_across_offset_ffff_holds_the_next_segments_bytes(tmp_path: Path) -> None:
    """One command from 0814:FFF0 wraps to 0814:0000; the window from 1813:0000 holds the rest."""
    debugger(tmp_path)
    got = dumped("0814:FFF0", 0x20, tmp_path / "x.bin")
    assert got["status"] == "ok", got
    data = (tmp_path / "x.bin").read_bytes()
    assert data == (MEMDUMP / "probe-1813-0000.bin").read_bytes()
    assert data != (MEMDUMP / "probe-0814-FFF0-wrapped.bin").read_bytes()


def test_a_dump_inside_one_segment_is_one_command_and_reads_no_mode(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    s.where = None  # type: ignore[method-assign,assignment]   # asking it would raise
    got = dumped("0814:0000", 0x20, tmp_path / "x.bin")
    assert got["status"] == "ok" and s.typed == [
        f"MEMDUMPBIN 0814:0000 20 {ds.MEMDUMP_FILE}"], (got, s.typed)


def test_a_window_that_fails_leaves_nothing_at_dest_and_no_piece_behind(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    real = s.command
    calls = iter(range(100))

    def second_fails(text: str, **kw: object) -> str:
        out = real(text, **kw)
        return "DEBUG: Memory binary dump failed.\r\nI-> _" if next(calls) == 1 else out
    s.command = second_fails  # type: ignore[method-assign]
    dest = tmp_path / "x.bin"
    got = dumped("0000:0000", 0x30000, dest)
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert not dest.exists() and list(s.launch.cwd.iterdir()) == []
    assert len(s.typed) == 2, "a window after the failed one was asked"


def test_a_dest_that_appears_while_the_windows_are_read_is_refused_and_kept(
        tmp_path: Path) -> None:
    s = debugger(tmp_path)
    dest = tmp_path / "x.bin"
    real = s.command

    def plants(text: str, **kw: object) -> str:
        if len(s.typed) == 1:
            dest.write_bytes(b"theirs")
        return real(text, **kw)
    s.command = plants  # type: ignore[method-assign]
    got = dumped("0000:0000", 0x20000, dest)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert dest.read_bytes() == b"theirs" and list(s.launch.cwd.iterdir()) == []


def test_a_dest_under_a_file_is_refused_before_anything_is_typed(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    (tmp_path / "afile").write_bytes(b"")
    got = dumped("0000:0000", 0x20000, tmp_path / "afile" / "x.bin")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "is not a directory" in got["message"] and s.typed == []


def test_a_dest_that_cannot_be_created_is_the_callers_and_leaves_no_piece(
        tmp_path: Path) -> None:
    """The caller named the path, so a directory that will not take it is `bad_argument`."""
    s = debugger(tmp_path)
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0o555)
    try:
        got = dumped("0000:0000", 0x20000, shut / "x.bin")
    finally:
        shut.chmod(0o755)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert not (shut / "x.bin").exists() and list(s.launch.cwd.iterdir()) == []


def test_a_join_that_cannot_be_written_whole_takes_its_file_away(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    debugger(tmp_path)
    dest = tmp_path / "x.bin"
    real_open = Path.open

    def short_write(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        f = real_open(self, mode, *a, **k)
        if self == dest:
            f.write = lambda _data: (_ for _ in ()).throw(  # type: ignore[method-assign]
                OSError(28, "No space left"))
        return f
    monkeypatch.setattr(Path, "open", short_write)
    got = dumped("0000:0000", 0x20000, dest)
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert not dest.exists()


def test_find_over_several_windows_finds_a_hit_in_the_third_and_names_its_paragraph(
        tmp_path: Path) -> None:
    s = debugger(tmp_path)
    at = 0x24567
    needle = bytes(s.mem[at:at + 8])
    got = cast(dict[str, Any], server.find(data_hex=needle.hex(), ref="0000:0000",
                                           length=0x30000))
    assert got["status"] == "ok" and "2456:00000007" in got["hits"], got


def test_a_windowed_dump_judges_dest_before_anything_is_typed(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    there = tmp_path / "there.bin"
    there.write_bytes(b"mine")
    for dest, words in ((there, "already exists"),
                        (s.launch.cwd / "x.bin", "working directory")):
        got = dumped("0000:0000", 0x20000, dest)
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert words in got["message"] and s.typed == []
    assert there.read_bytes() == b"mine"


def test_a_range_past_ffff_ffff_is_refused_before_anything_is_typed(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    got = dumped("FFFF:0010", 0x10000, tmp_path / "x.bin")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "FFFF:FFFF" in got["message"] and s.typed == []
    assert not (tmp_path / "x.bin").exists()


def test_find_across_offset_ffff_spells_a_hit_past_it_by_its_own_paragraph(
        tmp_path: Path) -> None:
    """A real-mode offset cannot pass 0xFFFF, so a hit in the second window is named from its
    own paragraph."""
    s = debugger(tmp_path)
    needle = bytes(s.mem[AFTER_PSP_LINEAR + 0x14:AFTER_PSP_LINEAR + 0x1C])
    got = cast(dict[str, Any], server.find(data_hex=needle.hex(), ref="0814:FFF0", length=0x20))
    assert got["status"] == "ok", got
    assert "1814:00000004" in got["hits"], got["hits"]      # 0814:10004, linear 18144
    assert all(int(h.split(":")[1], 16) <= 0xFFFF for h in got["hits"])


def test_find_inside_one_segment_keeps_the_callers_segment(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    needle = bytes(s.mem[PROBE_PSP_LINEAR + 2:PROBE_PSP_LINEAR + 6])
    got = finder.find(cast(ds.Session, s), 0x0814, 0, 0x20, needle)
    assert "0814:00000002" in got["hits"], got


# ----------------------------------------------------------------- protected mode


def protected(tmp_path: Path, logfile: bool = True) -> Bench:
    s = Bench("dos-djgpp32", tmp_path / "x.log" if logfile else None)
    s.mode = "Pr32"
    s.launch.cwd = tmp_path / "cwd"          # a dest beside it is outside it, as a caller's is
    s.launch.cwd.mkdir(exist_ok=True)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


@pytest.mark.parametrize(("ref", "length", "words"), [
    ("0040:0000FFF0", 0x20, "16-bit"),                 # GDT 0040: D/B clear
    ("0084:00000000", 0x10001, "16-bit"),              # LDT 0084, through its table bit
    ("0020:0000FFF0", 0x20, "limit 0000FFFF"),         # GDT 0020: 32-bit, 64 KiB limit
    ("00AF:002BFFF0", 0x11, "limit 002BFFFF"),         # LDT 00AC at RPL 3: one byte past it
    ("0048:00000000", 0x20000, "names no descriptor"),  # no such row
    ("0003:00000000", 0x20000, "names no descriptor"),  # the null selector
])
def test_a_protected_range_past_ffff_that_would_wrap_or_read_zeros_is_refused(
        tmp_path: Path, ref: str, length: int, words: str) -> None:
    s = protected(tmp_path)
    got = dumped(ref, length, tmp_path / "x.bin")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert words in got["message"] and s.memdump_calls == [], got
    assert s.asked[-2:] == ["GDT", "LDT"]


@pytest.mark.parametrize(("ref", "length"), [
    ("0038:00000000", 0x20000), ("00AF:002BFFF0", 0x10), ("00BF:00010000", 0x100)])
def test_a_protected_range_inside_a_32_bit_limit_is_one_command(
        tmp_path: Path, ref: str, length: int) -> None:
    s = protected(tmp_path)
    got = dumped(ref, length, tmp_path / "x.bin")
    seg, off = (int(p, 16) for p in ref.split(":"))
    assert got["status"] == "ok" and s.memdump_calls == [(seg, off, length)], got


def test_a_protected_range_inside_offset_ffff_reads_no_table(tmp_path: Path) -> None:
    """Inside 0 to 0xFFFF a 16-bit and a 32-bit segment address alike: no listing is paid."""
    s = protected(tmp_path)
    got = dumped("0040:00000000", 0x10000, tmp_path / "x.bin")
    assert got["status"] == "ok" and s.asked == [] and s.memdump_calls == [(0x40, 0, 0x10000)]


def test_find_through_a_32_bit_selector_keeps_its_offsets_past_ffff(tmp_path: Path) -> None:
    s = protected(tmp_path)
    got = finder.find(cast(ds.Session, s), 0x38, 0, 0x20000, b"\x00\x00")
    assert got["hits_total"] == 0x20000 - 1, got     # the FakeSession dump is all zeros
    assert "0038:0001FFFE" in got["hits"]


def test_a_protected_range_past_ffff_without_a_logfile_names_start_logfile(
        tmp_path: Path) -> None:
    s = protected(tmp_path, logfile=False)
    got = dumped("0038:00000000", 0x20000, tmp_path / "x.bin")
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert "`start` with `logfile`" in got["message"] and s.memdump_calls == []


def test_an_expand_down_segment_is_judged_above_its_limit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """No bench has one, so the row is hand-written (type 16h): offsets lie above the limit."""
    found = {"gdt": [{"selector": "0050", "base": "00000000", "limit": "0000FFFF",
                      "type": "16", "b": 1}]}
    reading = SimpleNamespace(found=found, notes=["read"])
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: reading)
    s = cast(ds.Session, SimpleNamespace(launch=SimpleNamespace(logfile=Path("/x.log"))))
    dumping.judge_protected(s, 0x50, 0x10000, 0x100)
    for off in (0xFFF0, 0xFFFF):              # below the limit, and the limit itself
        with pytest.raises(ds.Invalid, match="expand-down"):
            dumping.judge_protected(s, 0x50, off, 0x20)


@pytest.mark.parametrize(("rows", "words"), [
    ([{"selector": "0050", "base": "00000000", "limit": "FFFFFFFF", "type": "00", "b": 1}],
     "names no descriptor"),
    ([{"selector": "0050", "base": "00000000", "limit": "FFFFFFFF", "type": "12", "b": 1}],
     None),
])
def test_a_row_of_type_0_is_no_descriptor(monkeypatch: pytest.MonkeyPatch,
                                          rows: list[dict[str, Any]], words: str | None) -> None:
    reading = SimpleNamespace(found={"gdt": rows}, notes=["read"])
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: reading)
    s = cast(ds.Session, SimpleNamespace(launch=SimpleNamespace(logfile=Path("/x.log"))))
    if words is None:
        dumping.judge_protected(s, 0x50, 0, 0x20000)
        return
    with pytest.raises(ds.Invalid, match=words):
        dumping.judge_protected(s, 0x50, 0, 0x20000)


def test_a_table_that_could_not_be_read_says_so_and_why(
        monkeypatch: pytest.MonkeyPatch) -> None:
    why = "`gdt` and `ldt` are absent: `GDT` answered \"nope\""
    reading = SimpleNamespace(found={}, notes=["read from the listings", why])
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: reading)
    s = cast(ds.Session, SimpleNamespace(launch=SimpleNamespace(logfile=Path("/x.log"))))
    with pytest.raises(ds.Invalid, match="could not be read") as e:
        dumping.judge_protected(s, 0x38, 0, 0x20000)
    assert e.value.code == "unexpected_answer" and why in str(e.value)


# ------------------------------------------------------- the debugger's own file


def test_a_dump_of_the_wrong_size_leaves_no_file_and_the_next_dump_is_not_refused(
        tmp_path: Path) -> None:
    """A failure after `MEMDUMPBIN` removes the debugger's file, or the next call refuses it."""
    s = debugger(tmp_path)
    real = s.command

    def short(text: str, **kw: object) -> str:
        out = real(text, **kw)
        (s.launch.cwd / ds.MEMDUMP_NAME.upper()).write_bytes(b"\0" * 3)
        return out
    s.command = short  # type: ignore[method-assign]
    first = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert first["status"] == "INVALID" and first["code"] == "readback_refused", first
    assert list(s.launch.cwd.iterdir()) == []
    s.command = real  # type: ignore[method-assign]
    second = dumped("0814:0000", 0x20, tmp_path / "b.bin")
    assert second["status"] == "ok", second


def test_a_failed_dump_is_read_off_the_last_dump_line_and_its_file_removed(
        tmp_path: Path) -> None:
    """The screen holds an earlier success line; this command's own line is the failure."""
    s = debugger(tmp_path, says="DEBUG: Memory dump binary success.\r\n"
                                "DEBUG: Memory binary dump failed.")
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert "did not report a successful dump" in got["message"], got
    assert list(s.launch.cwd.iterdir()) == [] and not (tmp_path / "a.bin").exists()
    s.says = "DEBUG: Memory dump binary success."
    assert dumped("0814:0000", 0x20, tmp_path / "b.bin")["status"] == "ok"


def test_a_scrollback_with_a_failure_above_this_success_is_a_success(tmp_path: Path) -> None:
    debugger(tmp_path, says="DEBUG: Memory binary dump failed.\r\n"
                            "DEBUG: Memory dump binary success.")
    assert dumped("0814:0000", 0x20, tmp_path / "a.bin")["status"] == "ok"


def test_a_dump_longer_than_asked_is_refused_too(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    real = s.command

    def long(text: str, **kw: object) -> str:
        out = real(text, **kw)
        (s.launch.cwd / ds.MEMDUMP_NAME.upper()).write_bytes(b"\0" * 0x21)
        return out
    s.command = long  # type: ignore[method-assign]
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["code"] == "readback_refused" and list(s.launch.cwd.iterdir()) == [], got


def test_a_command_that_breaks_after_the_debugger_wrote_leaves_no_file(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    real = s.command

    def breaks(text: str, **kw: object) -> str:
        real(text, **kw)
        raise ds.Invalid("unexpected_answer", "the console stopped answering")
    s.command = breaks  # type: ignore[method-assign]
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["code"] == "unexpected_answer" and list(s.launch.cwd.iterdir()) == [], got


def test_a_dump_that_cannot_be_moved_is_removed_and_the_reply_says_so(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0o555)
    try:
        got = dumped("0814:0000", 0x20, shut / "a.bin")
    finally:
        shut.chmod(0o755)
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "removed" in got["message"] and list(s.launch.cwd.iterdir()) == []
    assert not (shut / "a.bin").exists()


def test_a_copy_cut_short_on_another_volume_leaves_no_partial_dest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`collect` copies when a rename cannot cross volumes; a copy dying part-way leaves no
    half file at `dest`."""
    s = debugger(tmp_path)

    def no_rename(self: Path, target: Any) -> Path:
        raise OSError(18, "Cross-device link")

    def half_copy(src: Any, dst: Any) -> Any:
        Path(dst).write_bytes(b"\0" * 5)
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(Path, "replace", no_rename)
    monkeypatch.setattr(shutil, "copyfile", half_copy)
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["code"] == "host_failed" and not (tmp_path / "a.bin").exists(), got
    assert list(s.launch.cwd.iterdir()) == []


@pytest.mark.parametrize("takes_name", [False, True])
def test_a_dump_on_either_build_is_the_memory_asked_for_and_leaves_no_file(
        tmp_path: Path, takes_name: bool) -> None:
    """Both builds: the memory asked for, and no file left behind."""
    s = debugger(tmp_path, takes_name=takes_name)
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["status"] == "ok", got
    want = (MEMDUMP / "probe-0814-0000.bin").read_bytes()[:0x20]
    assert (tmp_path / "a.bin").read_bytes() == want
    assert list(s.launch.cwd.iterdir()) == []
    # By the string and not by the filesystem, which folds case here: a candidate in another
    # case than the line the debugger upper-cased is never found on a case-sensitive one.
    assert s.wrote[-1] in {c.name for c in s._memdump_candidates()}, s.wrote


def test_a_file_there_before_the_command_is_never_removed(tmp_path: Path) -> None:
    s = debugger(tmp_path)
    theirs = s.launch.cwd / ds.MEMDUMP_NAME
    theirs.write_bytes(b"somebody's")
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["code"] == "bad_argument" and theirs.read_bytes() == b"somebody's"
    assert s.typed == []


@pytest.mark.parametrize("name", [ds.MEMDUMP_FILE, ds.MEMDUMP_NAME, ds.MEMDUMP_NAME.upper()])
@pytest.mark.parametrize("shape", ["missing_directory", "free_name"])
def test_a_dangling_link_where_the_debugger_writes_is_refused_and_nothing_written_through(
        tmp_path: Path, name: str, shape: str) -> None:
    """A link where the debugger writes is somebody's file: refused before the command is typed."""
    s = debugger(tmp_path)
    target = (tmp_path / "nowhere" / "x" if shape == "missing_directory"
              else tmp_path / "elsewhere.bin")
    link = s.launch.cwd / name
    link.symlink_to(target)
    got = dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert s.typed == [] and link.is_symlink() and not target.exists()
    assert not (tmp_path / "a.bin").exists() and not (tmp_path / "a.bin").is_symlink()


def test_the_leftover_guard_sees_a_dangling_link(tmp_path: Path) -> None:
    link = tmp_path / "memdump.bin"
    link.symlink_to(tmp_path / "nowhere")
    with pytest.raises(ds.Invalid, match="already sitting at") as e:
        dcollect.refuse_leftover([link], "dump")
    assert e.value.code == "bad_argument"
    dcollect.refuse_leftover([tmp_path / "absent.bin"], "dump")   # the control: nothing there


def test_a_leftover_refuses_a_windowed_dump_before_anything_is_typed_or_surveyed(
        tmp_path: Path) -> None:
    """The mode survey is a console command, so the leftover is judged before it."""
    s = debugger(tmp_path)
    surveyed: list[str] = []

    def where() -> dict[str, str]:
        surveyed.append("where")
        return {"cs": "0814", "eip": "0000", "mode": "Real"}
    s.where = where  # type: ignore[method-assign]
    theirs = s.launch.cwd / ds.MEMDUMP_NAME
    theirs.write_bytes(b"somebody's")
    got = dumped("0000:0000", 0x20000, tmp_path / "a.bin")
    assert got["code"] == "bad_argument" and "already sitting" in got["message"], got
    assert s.typed == [] and surveyed == [] and theirs.read_bytes() == b"somebody's"


def test_a_protected_range_past_ffff_judges_the_leftover_before_any_listing(
        tmp_path: Path) -> None:
    s = protected(tmp_path)
    (s.launch.cwd / ds.MEMDUMP_NAME).write_bytes(b"somebody's")
    got = dumped("0038:00000000", 0x20000, tmp_path / "x.bin")
    assert got["code"] == "bad_argument" and "already sitting" in got["message"], got
    assert s.asked == [] and s.memdump_calls == []


def test_a_host_error_after_the_debugger_wrote_leaves_no_file_to_refuse_the_next_dump(
        tmp_path: Path) -> None:
    s = debugger(tmp_path)
    real = s.command

    def breaks(text: str, **kw: object) -> str:
        real(text, **kw)
        raise OSError(5, "Input/output error")
    s.command = breaks  # type: ignore[method-assign]
    with pytest.raises(OSError):
        dumped("0814:0000", 0x20, tmp_path / "a.bin")
    assert list(s.launch.cwd.iterdir()) == []
    s.command = real  # type: ignore[method-assign]
    got = dumped("0814:0000", 0x20, tmp_path / "b.bin")
    assert got["status"] == "ok", got


def test_a_dump_file_that_could_not_be_removed_is_never_said_removed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = debugger(tmp_path)
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0o555)
    unlink = Path.unlink

    def refused_in_cwd(self: Path, missing_ok: bool = False) -> None:
        if self.parent == s.launch.cwd:
            raise PermissionError(1, "Operation not permitted", str(self))
        unlink(self, missing_ok=missing_ok)
    monkeypatch.setattr(Path, "unlink", refused_in_cwd)
    try:
        got = dumped("0814:0000", 0x20, shut / "a.bin")
    finally:
        shut.chmod(0o755)
    assert got["code"] == "host_failed", got
    assert "was removed" not in got["message"] and "could not be removed" in got["message"], got
    assert any(s.launch.cwd.iterdir())       # the file is there, as the reply says


def test_a_dump_file_that_could_not_be_removed_is_named_once_under_two_spellings(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Where the filesystem folds case the two spellings are one file, named once on failure."""
    s = debugger(tmp_path)
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0o555)
    typed = s.command

    def then_read_only(text: str, **kw: object) -> str:
        out = typed(text, **kw)
        s.launch.cwd.chmod(0o555)
        return out
    monkeypatch.setattr(s, "command", then_read_only)
    try:
        got = dumped("0814:0000", 0x20, shut / "a.bin")
    finally:
        shut.chmod(0o755)
        s.launch.cwd.chmod(0o755)
    assert got["code"] == "host_failed", got
    kept = got["message"].split("could not be removed: ", 1)[1]
    assert kept.count(str(s.launch.cwd)) == 1, got["message"]
    assert any(s.launch.cwd.iterdir())       # the file is there, as the reply says


def test_a_windowed_dump_leaves_no_scratch_directory_behind(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    debugger(tmp_path)
    got = dumped("0000:0000", 0x20000, tmp_path / "a.bin")
    assert got["status"] == "ok" and list(scratch.iterdir()) == [], (got, list(scratch.iterdir()))


@pytest.mark.parametrize("kind", ["1E", "06"])
def test_bit_2_outside_a_data_segment_is_not_expand_down(
        monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """Bit 2 means expand-down only on a data segment (1Eh conforming code, 06h system)."""
    found = {"gdt": [{"selector": "0050", "base": "00000000", "limit": "0001FFFF",
                      "type": kind, "b": 1}]}
    reading = SimpleNamespace(found=found, notes=["read"])
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: reading)
    s = cast(ds.Session, SimpleNamespace(launch=SimpleNamespace(logfile=Path("/x.log"))))
    dumping.judge_protected(s, 0x50, 0xFFF0, 0x20)
    with pytest.raises(ds.Invalid, match="up to its limit"):
        dumping.judge_protected(s, 0x50, 0x1FFF0, 0x20)
