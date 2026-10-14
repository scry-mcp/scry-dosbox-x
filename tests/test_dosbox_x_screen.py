"""The screen tools and the `vga` section, against what a real debugger wrote.

The listings, pages and video-memory windows are files under `fixtures/vga/`, captured from
live sessions (its PROVENANCE says where each one stopped), so the shapes the parsers accept are
the debugger's and the answers the decoders give are the guest's own arithmetic. Where a case
changes a capture (one word edited), it says so.
"""
from __future__ import annotations

import dataclasses
import gzip
import hashlib
import os
import struct
import time
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_dosbox_x_machine import Bench, Logfile, listing
from test_dosbox_x_run_for import Retraces
from test_dosbox_x_run_for import cap as cap_vrt
from test_dosbox_x_server import clean_session, install  # noqa: F401

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_machine as machine
import dosbox_paths as paths
import dosbox_png as png
import dosbox_retrace as retrace
import dosbox_screen as screen
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

VGA = Path(__file__).parent / "fixtures" / "vga"
BENCHES = ("probe-park", "probe-booted", "speedf", "rechip-startup", "rechip-ui", "screen-text",
           "screen-start80", "screen-dac01", "screen-13h", "screen-13h-start80", "screen-12h")


def vga(bench: str, command: str) -> str:
    return (VGA / f"{bench}-{command.replace(' ', '_')}.log.txt").read_bytes().decode("latin-1")


def parsed(bench: str, command: str) -> dict[str, Any]:
    return screen.parse_listing(vga(bench, command), screen.TITLES[command])


def window(name: str) -> bytes:
    return gzip.decompress((VGA / name).read_bytes())


# ------------------------------------------------------------------ the listings


@pytest.mark.parametrize("bench", BENCHES)
def test_every_vga_listing_parses_on_every_bench(bench: str) -> None:
    for _, command, title in screen.VGA_LISTINGS:
        got = screen.parse_listing(vga(bench, command), title)
        assert got, (bench, command)
        assert all(k == k.lower() and "-" not in k for k in got), got


def test_the_words_are_the_debuggers_and_the_values_the_text_it_printed() -> None:
    mode = parsed("probe-booted", "VGA MODE")
    assert mode["mode"] == "M_TEXT" and mode["vref"] == "70.087Hz"
    assert mode["disp_start"] == "0h" and mode["cursor_start"] == "140h"
    assert mode["complexity_flags"] == "0x4=oddeven|"
    crtc = parsed("probe-booted", "VGA CRTC")
    assert crtc["index"] == "0fh" and crtc["start_addr"] == "0000h" and crtc["maxscnl"] == "4fh"
    dac = parsed("probe-booted", "VGA DAC")
    assert dac["bits"] == "6" and dac["pel_mask"] == "ffh" and dac["pel_index"] == "00h"
    draw = parsed("speedf", "VGA DRAW")
    assert (draw["width"], draw["height"], draw["bpp"]) == ("640", "480", "15")
    assert parsed("screen-12h", "VGA MODE")["mode"] == "M_EGA"
    assert parsed("rechip-ui", "VGA MODE")["mode"] == "M_LIN8"


def test_the_attribute_controllers_palette_is_its_sixteen_registers() -> None:
    ac = parsed("probe-booted", "VGA AC")
    assert ac["palette"] == ["00", "01", "02", "03", "04", "05", "14", "07",
                             "38", "39", "3a", "3b", "3c", "3d", "3e", "3f"]
    assert ac["attrindexmode"] == "0" and ac["mode_control"] == "0ch"


@pytest.mark.parametrize(("command", "old", "new", "line"), [
    ("VGA MODE", "VGA mode info:", "VGA mode:", "VGA mode:"),
    ("VGA CRTC", "hdend=4fh", "hdend 4fh", "htotal=5fh hdend 4fh"),
    ("VGA CRTC", "strhb=50h", "hdend=50h", "htotal=5fh hdend=4fh hdend=50h"),
    ("VGA AC", "3a 3b-3c", "3a 3b 3c", "palette={ 00 01 02 03-04 05 14 07-38 39 3a 3b 3c"),
    ("VGA AC", "-3c 3d 3e 3f", "-3c 3d 3e", "palette={ 00 01 02 03-04 05 14 07-38 39 3a 3b-3c"),
    ("VGA AC", "38 39 3a 3b", "38 39 3A 3b", "palette={ 00 01 02 03-04 05 14 07-38 39 3A"),
    ("VGA DRAW", "blocks=80", "=80", "VGA draw info: resizing=0 width=720 height=400 =80"),
])
def test_a_listing_whose_shape_moved_is_unreadable_naming_the_line(
        command: str, old: str, new: str, line: str) -> None:
    """Each an edited capture of the booted probe: a lost title, a word with no `=`, a key
    printed twice, the AC's registers with a lost `-`, fifteen of them, or an upper-case digit,
    and a word with no key. The refusal names the line it stopped at."""
    text = vga("probe-booted", command)
    assert old in text
    with pytest.raises(machine.Unreadable) as got:
        screen.parse_listing(text.replace(old, new, 1), screen.TITLES[command])
    assert got.value.line.startswith(line), got.value.line


def test_a_listing_with_its_title_and_no_word_is_unreadable() -> None:
    with pytest.raises(machine.Unreadable):
        screen.parse_listing("VGA DAC info:\n", "VGA DAC info:")


# ------------------------------------------------------------------ the DAC


def test_dacpal_reads_all_256_entries_as_printed() -> None:
    booted = screen.parse_dacpal(vga("probe-booted", "VGA DACPAL"))
    assert len(booted) == 256 and booted[:4] == ["000000", "00002a", "002a00", "002a2a"]
    assert screen.parse_dacpal(vga("probe-park", "VGA DACPAL")) == ["000000"] * 256


def test_the_guests_ramp_is_the_dac_the_debugger_lists() -> None:
    """The screen guest writes entry i as (i & 3F, (i >> 1) & 3F, (i >> 2) & 3F) in 13h: the
    listing is that arithmetic, entry by entry."""
    want = [f"{i & 0x3F:02x}{(i >> 1) & 0x3F:02x}{(i >> 2) & 0x3F:02x}"
            for i in range(256)]
    assert screen.parse_dacpal(vga("screen-13h", "VGA DACPAL")) == want


def test_one_dac_write_moves_one_entry() -> None:
    before = screen.parse_dacpal(vga("screen-text", "VGA DACPAL"))
    after = screen.parse_dacpal(vga("screen-dac01", "VGA DACPAL"))
    assert (before[1], after[1]) == ("00002a", "3f0000")
    assert [i for i in range(256) if before[i] != after[i]] == [1]


@pytest.mark.parametrize(("old", "new"), [
    ("VGA DAC palette (RGB):", "VGA DAC palette:"),
    ("08: ", "09: "),
    ("\n10: ", "\n10:  "),
    ("002a2a-2a0000", "002a2a 2a0000"),
    ("00: 000000 00002a", "00: 000000 00402a"),
])
def test_a_dacpal_whose_shape_moved_is_unreadable(old: str, new: str) -> None:
    text = vga("probe-booted", "VGA DACPAL")
    assert old in text
    with pytest.raises(machine.Unreadable):
        screen.parse_dacpal(text.replace(old, new, 1))


def test_a_dacpal_missing_its_last_row_is_unreadable() -> None:
    text = vga("probe-booted", "VGA DACPAL")
    with pytest.raises(machine.Unreadable):
        screen.parse_dacpal(text[:text.rindex("f8: ")])


def test_the_dacpal_pager_is_answered_with_q_alone_and_read_whole(tmp_path: Path) -> None:
    """`VGA DACPAL` pages after row 90: the first page leaves the command on the input line and
    the marker under it; `Q` prints the rest, from row 98, and empties the line."""
    log = (VGA / "probe-booted-VGA_DACPAL.log.txt").read_bytes()
    cut = log.index(b"\n98: ") + 1
    ses = Logfile(tmp_path, [(VGA / "probe-booted-VGA_DACPAL.screen.txt").read_text(),
                             (VGA / "probe-booted-VGA_DACPAL.q.txt").read_text()],
                  [log[:cut], log[cut:]])
    assert ses.listing("VGA DACPAL") == log.decode("latin-1")
    assert ses.typed == [b"VGA DACPAL\r", b"Q"]


def test_vga_mode_does_not_page_and_is_read_with_one_command(tmp_path: Path) -> None:
    log = (VGA / "probe-booted-VGA_MODE.log.txt").read_bytes()
    ses = Logfile(tmp_path, [(VGA / "probe-booted-VGA_MODE.screen.txt").read_text()], [log])
    assert ses.listing("VGA MODE") == log.decode("latin-1")
    assert ses.typed == [b"VGA MODE\r"]


@pytest.mark.parametrize(("entry", "want"), [
    ("000000", "#000000"), ("00002a", "#0000aa"), ("3f0000", "#ff0000"), ("153f2a", "#55ffaa"),
    ("010203", "#04080c")])
def test_a_six_bit_entry_widens_as_the_emulator_renders_it(entry: str, want: str) -> None:
    """Each component's two top bits repeated below: the rule that reproduced every pixel of the
    emulator's own capture of the screen guest (63 is 255, 42 is 170, 1 is 4)."""
    assert screen.color(entry) == want


# ------------------------------------------------------------------ what the screen can be


def test_the_13h_window_is_the_guests_diagonal_ramp() -> None:
    """The screen guest fills A000 so the pixel at (x, y) is (x + y) & FF, 320 a row: the
    captured window is exactly that, and the one captured with the display start moved holds
    the same memory from its next row on."""
    want = bytes((x + y) & 0xFF for y in range(200) for x in range(320))
    assert window("screen-13h-a000.bin.gz") == want
    moved = window("screen-13h-start80-a000.bin.gz")
    assert moved[:64000 - 320] == want[320:] and set(moved[64000 - 320:]) == {0}


@pytest.mark.parametrize(("bench", "want"), [
    ("probe-booted", "text"), ("screen-text", "text"), ("rechip-startup", "text"),
    ("screen-13h", "indices"), ("screen-13h-start80", "indices")])
def test_text_and_the_chained_256_colour_mode_are_read(bench: str, want: str) -> None:
    assert screen.source_of(parsed(bench, "VGA MODE")) == want


@pytest.mark.parametrize(("bench", "old", "new", "word", "why"), [
    ("screen-12h", None, None, "M_EGA", "planar"),
    ("speedf", None, None, "M_LIN15", "linear-frame-buffer"),
    ("rechip-ui", None, None, "M_LIN8", "linear-frame-buffer"),
    ("probe-park", None, None, "M_ERROR", "no video mode is set"),
    ("screen-13h", "chained=1", "chained=0", "M_VGA", "unchained"),
    ("screen-12h", "mode=M_EGA", "mode=M_LIN4", "M_LIN4", "planar"),
    ("screen-12h", "mode=M_EGA", "mode=M_CGA4", "M_CGA4", "no decoder here"),
])
def test_every_other_mode_is_refused_naming_its_word_and_the_capture_route(
        bench: str, old: str | None, new: str | None, word: str, why: str) -> None:
    """The captured modes as they are, and three edited captures (the word named) for the
    families no bench draws."""
    text = vga(bench, "VGA MODE")
    if old is not None and new is not None:
        assert old in text
        text = text.replace(old, new, 1)
    with pytest.raises(ds.Invalid) as got:
        screen.source_of(screen.parse_listing(text, "VGA mode info:"))
    assert got.value.code == "no_channel"
    assert f"`{word}`" in str(got.value) and why in str(got.value)
    assert "capture_frame" in str(got.value) and "capture_video=True" in str(got.value)


# ------------------------------------------------------------------ the picture


PLTE_TRNS_IDAT = [b"PLTE", b"tRNS", b"IDAT"]


def decode_png(data: bytes) -> tuple[int, int, bytes, list[tuple[int, int, int]], bytes]:
    """An independent reader of the PNGs written here: the chunks walked and CRC-checked, the
    IDAT inflated and unfiltered (filter 0 only, which is all the writer emits)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks, kinds = 8, cast(dict[bytes, bytes], {}), cast(list[bytes], [])
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(kind + body), kind
        assert kind not in chunks or kind == b"IDAT", kind
        chunks[kind] = chunks.get(kind, b"") + body
        kinds.append(kind)
        pos += 12 + length
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and chunks[b"IEND"] == b""
    # The order a decoder may insist on: the palette, then its transparency, then the pixels.
    order = [k for k in kinds if k in PLTE_TRNS_IDAT]
    assert order == sorted(order, key=PLTE_TRNS_IDAT.index), order
    assert len(chunks[b"IHDR"]) == 13
    width, height, depth, ctype, method, filt, lace = struct.unpack(">IIBBBBB", chunks[b"IHDR"])
    assert (depth, ctype, method, filt, lace) == (8, 3, 0, 0, 0)
    raw = zlib.decompress(chunks[b"IDAT"])
    stride = width + 1
    assert all(raw[y * stride] == 0 for y in range(height))
    pixels = b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(height))
    plte = chunks[b"PLTE"]
    pal = [(plte[i], plte[i + 1], plte[i + 2]) for i in range(0, len(plte), 3)]
    return width, height, pixels, pal, chunks.get(b"tRNS", b"")


def test_the_png_holds_the_indices_and_the_palette_it_was_given() -> None:
    pixels = window("screen-13h-a000.bin.gz")
    pal = [screen.rgb8(e) for e in screen.parse_dacpal(vga("screen-13h", "VGA DACPAL"))]
    w, h, got, plte, trns = decode_png(png.indexed(320, 200, pixels, pal))
    assert (w, h, got, plte, trns) == (320, 200, pixels, pal, b"")


@pytest.mark.parametrize(("w", "h", "pixels", "entries", "clear"), [
    (4, 2, b"\x00" * 7, 1, None), (4, 2, b"\x00" * 9, 1, None), (1, 1, b"\x00", 0, None),
    (1, 1, b"\x00", 257, None), (1, 1, b"\x02", 2, None), (1, 1, b"\x00", 2, 2)])
def test_the_png_refuses_what_a_viewer_could_not_draw(
        w: int, h: int, pixels: bytes, entries: int, clear: int | None) -> None:
    """A raster short or long of its size, an empty or oversized palette, and an index (a pixel
    or the transparent one) past the palette's entries."""
    with pytest.raises(ValueError):
        png.indexed(w, h, pixels, [(0, 0, 0)] * entries, clear=clear)


def test_a_picture_is_never_written_over_and_a_failed_write_leaves_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    there = tmp_path / "there.png"
    there.write_bytes(b"mine")
    with pytest.raises(ds.Invalid) as got:
        png.write(there, 1, 1, b"new")
    assert got.value.code == "bad_argument" and there.read_bytes() == b"mine"
    real_open = Path.open

    class Full:
        def __init__(self, f: Any) -> None:
            self.f = f

        def __enter__(self) -> Full:
            return self

        def __exit__(self, *exc: object) -> None:
            self.f.close()

        def write(self, data: bytes) -> int:
            raise OSError(28, "No space left on device")

    def full_open(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        return Full(real_open(self, mode, *a, **k))

    monkeypatch.setattr(Path, "open", full_open)
    dest = tmp_path / "half.png"
    with pytest.raises(ds.Invalid) as got:
        png.write(dest, 1, 1, b"data")
    assert got.value.code == "bad_argument" and "No space left" in str(got.value)
    assert not dest.exists()


# ------------------------------------------------------------------ the palette tool


def bench(name: str, tmp_path: Path) -> Bench:
    """A stopped machine answering the `VGA` listings captured at `name` (`fixtures/vga/`)."""
    s = Bench(name, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


def test_palette_answers_the_whole_dac_off_two_listings(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "ok", r
    assert (r["entries"], r["first"], r["count"]) == (256, 0, 256)
    assert r["rgb"][:2] == ["000000", "00002a"] and r["colors"][:2] == ["#000000", "#0000aa"]
    assert r["bits"] == 6 and r["pel_mask"] == "ffh" and "image" not in r
    assert s.asked == ["VGA DAC", "VGA DACPAL"]
    assert r["session"]["altered"] is False
    assert r["summary"] == "palette: entries 0 to 255 of 256"


def test_palette_returns_the_entries_asked_for(tmp_path: Path) -> None:
    bench("screen-dac01", tmp_path)
    one = cast(dict[str, Any], server.palette(first=1, count=1))
    assert one["count"] == 1 and one["rgb"] == ["3f0000"] and one["colors"] == ["#ff0000"]
    assert one["summary"] == "palette: entry 1 #ff0000 of 256"
    ramp = screen.parse_dacpal(vga("screen-13h", "VGA DACPAL"))
    bench("screen-13h", tmp_path)
    tail = cast(dict[str, Any], server.palette(first=250))
    assert tail["count"] == 6 and tail["first"] == 250 and tail["rgb"] == ramp[250:]
    last = cast(dict[str, Any], server.palette(first=255, count=1))
    assert last["rgb"] == [ramp[255]] and last["colors"] == [screen.color(ramp[255])]
    whole = cast(dict[str, Any], server.palette(first=0, count=256))
    assert whole["count"] == 256 and whole["rgb"] == ramp


@pytest.mark.parametrize(("first", "count"), [
    (0, 16), (3, 5), (1, 40), (16, 32), (200, 56), (0, 256), (255, 1), (0, 1), (0, 17), (1, 255)])
def test_the_palette_picture_is_one_square_per_entry_indexed_by_the_entry(
        tmp_path: Path, first: int, count: int) -> None:
    bench("screen-13h", tmp_path)
    dest = tmp_path / "pal.png"
    r = cast(dict[str, Any], server.palette(first=first, count=count, dest=str(dest)))
    assert r["status"] == "ok", r
    image = r["image"]
    data = dest.read_bytes()
    assert image["sha256"] == hashlib.sha256(data).hexdigest() and image["indexed"] is True
    assert image["path"] == str(dest) and r["summary"].endswith(f", picture to {dest}")
    w, h, pixels, plte, trns = decode_png(data)
    assert (w, h) == (image["width"], image["height"])
    assert w == min(count, 16) * 16 and h == -(-count // 16) * 16
    dac = screen.parse_dacpal(vga("screen-13h", "VGA DACPAL"))
    assert plte == [screen.rgb8(e) for e in dac]
    squares = [pixels[y * w + x] for y in range(h) for x in range(w)]
    returned = [first + (y // 16) * 16 + x // 16 for y in range(h) for x in range(w)]
    short = [i for i, k in enumerate(returned) if k >= first + count]
    assert all(squares[i] == returned[i] for i in range(len(squares)) if i not in set(short))
    if short:
        filler = {squares[i] for i in short}
        assert len(filler) == 1 and not first <= min(filler) < first + count
        assert trns == b"\xff" * min(filler) + b"\x00"
    else:
        assert trns == b""


@pytest.mark.parametrize("kw", [
    {"first": 256}, {"first": -1}, {"count": 257}, {"count": -1}, {"first": 200, "count": 57},
    {"first": True}, {"first": "1"}, {"count": 1.5}, {"dest": "pal.png"}, {"dest": "./pal.png"},
    {"dest": "/tmp/a\x00b.png"}, {"dest": "~nosuchuser-d2/p.png"}, {"dest": 7}])
def test_palette_refuses_an_argument_before_anything_is_typed(
        tmp_path: Path, kw: dict[str, Any]) -> None:
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.palette(**kw))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert s.asked == []


def test_perform_refuses_a_home_that_does_not_resolve_before_any_step_runs(
        tmp_path: Path) -> None:
    """`~somebody` naming no account cannot become a path: judged with the whole list, so the
    step before it never runs."""
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "palette"}, {"op": "palette", "dest": "~nosuchuser-d2/p.png"}]))
    assert r["status"] == "INVALID" and [e["step"] for e in r["errors"]] == [1], r
    assert s.asked == []


def test_a_dest_from_home_is_refused_because_nothing_expands_it() -> None:
    with pytest.raises(ds.Invalid, match="`~`"):
        checks.check("palette", dest="~/pal.png")


def test_a_dest_under_a_directory_nobody_may_search_is_refused_not_raised(
        tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    shut = tmp_path / "shut"
    shut.mkdir()
    os.chmod(shut, 0)
    try:
        r = cast(dict[str, Any], server.palette(dest=str(shut / "pal.png")))
    finally:
        os.chmod(shut, 0o700)
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert not (shut / "pal.png").exists() and s.asked in ([], ["VGA DAC", "VGA DACPAL"])


def test_a_dest_the_filesystem_will_not_look_at_is_refused_not_raised(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Before Python 3.14 `Path.exists` raises on EACCES rather than answering False: the
    refusal is the same whichever interpreter runs it."""
    def denied(self: Path, *a: Any, **k: Any) -> bool:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "exists", denied)
    with pytest.raises(ds.Invalid) as got:
        paths.fresh_dest("dest", tmp_path / "pal.png")
    assert got.value.code == "bad_argument" and "Permission denied" in str(got.value)


def test_palette_reaches_the_last_entry_exactly(tmp_path: Path) -> None:
    bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.palette(first=200, count=56))
    assert r["status"] == "ok" and r["count"] == 56


def test_palette_refuses_a_dest_already_there_or_with_no_directory(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    there = tmp_path / "there.png"
    there.write_bytes(b"mine")
    for dest in (there, tmp_path / "no" / "dir.png"):
        r = cast(dict[str, Any], server.palette(dest=str(dest)))
        assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert there.read_bytes() == b"mine" and s.asked == []


def test_palette_without_a_logfile_is_refused_naming_it(tmp_path: Path) -> None:
    s = Bench("probe-booted", None)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "no_channel" and "logfile" in r["message"]


def test_palette_on_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    s.at_debugger = lambda: False  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "not_stopped" and s.asked == []


def test_a_dac_not_in_its_six_bit_mode_is_not_expanded(tmp_path: Path) -> None:
    """The booted probe's `VGA DAC` with `bits=8` (an edited capture): the widening was measured
    on the six-bit DAC only."""
    s = bench("probe-booted", tmp_path)
    plain = s.listing
    s.listing = lambda command: plain(command).replace("bits=6", "bits=8")  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer"
    assert "bits=8" in r["message"] and s.asked == ["VGA DAC"]


def test_a_dac_listing_in_another_shape_is_refused_before_the_entries_are_read(
        tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    plain = s.listing
    s.listing = lambda command: plain(command).replace("pel_mask=ffh", "pel_mask ffh")  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer"
    assert "pel_mask ffh" in r["message"] and s.asked == ["VGA DAC"]


def test_a_dacpal_in_another_shape_is_refused_quoting_its_line(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    plain = s.listing
    s.listing = lambda command: plain(command).replace("08: ", "09: ")  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer" and "09: " in r["message"]


def test_perform_runs_palette_and_checks_its_arguments_first(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[{"op": "palette", "count": 2}]))
    assert r["status"] == "ok" and r["completed"] == 1, r
    s.asked.clear()
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "palette"},
                                                     {"op": "palette", "first": 300}]))
    assert bad["status"] == "INVALID" and [e["step"] for e in bad["errors"]] == [1], bad
    assert s.asked == []


# ------------------------------------------------------------------ the vga section


def mapped(name: str, tmp_path: Path) -> dict[str, Any]:
    s = Bench(name, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    reply = cast(dict[str, Any], server.machine_map())
    reply["_asked"] = s.asked
    return reply


def test_machine_map_carries_the_vga_section_read_last(tmp_path: Path) -> None:
    r = mapped("probe-booted", tmp_path)
    assert r["status"] == "ok", r
    assert r["vga"]["mode"]["mode"] == "M_TEXT" and r["vga"]["draw"]["blocks"] == "80"
    assert r["vga"]["ac"]["palette"][6] == "14"
    assert set(r["vga"]) == {"mode", "crtc", "seq", "gc", "ac", "dac", "draw"}
    commands = ["VGA MODE", "VGA CRTC", "VGA SEQ", "VGA GC", "VGA AC", "VGA DAC", "VGA DRAW"]
    assert r["sources"]["vga"] == commands and r["_asked"][-7:] == commands
    assert "VGA DACPAL" not in r["_asked"]


def test_machine_map_in_protected_mode_reads_the_vga_after_the_page_runs(tmp_path: Path) -> None:
    r = mapped("rechip", tmp_path)
    assert r["_asked"][-8] == "PAGING" and r["vga"]["mode"]["mode"] == "M_TEXT"


def test_a_vga_listing_in_another_shape_makes_the_section_absent_quoting_it(
        tmp_path: Path) -> None:
    """The booted probe's `VGA GC` with a word that is no `key=value` (an edited capture): the
    section is absent, the rest of the map stands, and the listings after it are not typed."""
    s = Bench("probe-booted", tmp_path / "x.log")
    plain = s.listing
    s.listing = lambda command: (plain(command).replace("misc=0eh", "misc 0eh")  # type: ignore[method-assign]
                                 if command == "VGA GC" else plain(command))
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.machine_map())
    assert r["status"] == "ok" and "vga" not in r and "vga" not in r["sources"]
    assert r["coverage_note"].startswith("read from the debugger's own listings")
    assert ". `vga` is absent: `VGA GC` printed a line no known shape matches" \
        in r["coverage_note"]
    assert "misc 0eh" in r["coverage_note"] and r["mcbs"]
    assert "VGA AC" not in s.asked


def test_a_vga_listing_that_printed_nothing_makes_the_section_absent(tmp_path: Path) -> None:
    s = Bench("probe-booted", tmp_path / "x.log")
    plain = s.listing
    s.listing = lambda command: "" if command == "VGA MODE" else plain(command)  # type: ignore[method-assign]
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.machine_map())
    assert "vga" not in r and "`vga` is absent: `VGA MODE` printed nothing" in r["coverage_note"]
    assert "VGA CRTC" not in s.asked


def test_the_listing_reader_fixture_names_every_vga_capture() -> None:
    """The machine tests' bench reader serves the `VGA` listings from this directory, under the
    stop each machine bench was captured at."""
    assert listing("probe-booted", "VGA MODE") == vga("probe-booted", "VGA MODE")
    assert listing("rechip", "VGA MODE") == vga("rechip-startup", "VGA MODE")
    assert listing("probe-reset", "VGA DAC") == vga("probe-park", "VGA DAC")



# ------------------------------------------------------------------ where the screen is


def words_of(bench_name: str, **edits: tuple[str, str]) -> dict[str, dict[str, Any]]:
    """The four listings that place the screen at a capture, keyed as `geometry` takes them,
    with an edit per key where a case names one."""
    out = {}
    for key in screen.SHAPE_KEYS:
        command = screen.COMMAND_OF[key]
        text = vga(bench_name, command)
        if key in edits:
            old, new = edits[key]
            assert old in text, (key, old)
            text = text.replace(old, new, 1)
        out[key] = screen.parse_listing(text, screen.TITLES[command])
    return out


def shape_of(bench_name: str, **edits: tuple[str, str]) -> screen.Geometry:
    return screen.geometry(words_of(bench_name, **edits))


@pytest.mark.parametrize(("bench_name", "linear", "cursor"), [
    ("probe-booted", 0xB8000, [0, 4]), ("screen-text", 0xB8000, [0, 2]),
    ("screen-start80", 0xB80A0, [0, 1]), ("rechip-startup", 0xB8000, [0, 14])])
def test_a_text_screen_is_80_by_25_where_the_start_address_puts_it(
        bench_name: str, linear: int, cursor: list[int]) -> None:
    """Columns are the draw state's blocks; rows its 400 scan lines over its `addrline-total`;
    the start moves the page by `addr-shift` (two bytes a cell); the cursor counts from the
    start."""
    got = shape_of(bench_name)
    assert (got.source, got.width, got.height, got.length) == ("text", 80, 25, 4000)
    assert got.linear == linear and got.cursor == cursor


@pytest.mark.parametrize(("bench_name", "linear"), [
    ("screen-13h", 0xA0000), ("screen-13h-start80", 0xA0140)])
def test_the_256_colour_screen_is_320_by_200_and_its_start_moves_it_four_bytes_a_unit(
        bench_name: str, linear: int) -> None:
    got = shape_of(bench_name)
    assert (got.source, got.width, got.height, got.length) == ("indices", 320, 200, 64000)
    assert got.linear == linear and got.cursor is None


@pytest.mark.parametrize(("bench_name", "key", "old", "new", "why"), [
    ("screen-13h", "mode", "disp-start=0h", "disp-start=181h", "past the window"),
    ("screen-text", "mode", "disp-start=0h", "disp-start=3831h", "past the window"),
    ("screen-13h", "gc", "misc=05h", "misc=0dh", "memory map select 11"),
    ("screen-text", "gc", "misc=0eh", "misc=06h", "memory map select 01"),
    ("screen-13h", "draw", "height=400", "height=0", "320 x 0"),
    ("screen-13h", "draw", "addrline-total=2", "addrline-total=0", "320 x 0"),
    ("screen-13h", "draw", "width=320", "width=0", "0 x 200"),
    ("screen-13h", "mode", "scanlen=40", "scanlen=80", "rows of 640 bytes"),
    ("screen-text", "mode", "scanlen=40", "scanlen=41", "rows of 164 bytes"),
    ("screen-13h", "draw", "has-split=0", "has-split=1", "a split screen"),
    ("screen-13h", "mode", "pel-pan=0", "pel-pan=2", "panning"),
    ("screen-text", "mode", "byte-skip=0", "byte-skip=1", "panning"),
])
def test_a_screen_this_cannot_place_is_refused_rather_than_misread(
        bench_name: str, key: str, old: str, new: str, why: str) -> None:
    """A capture with one word edited: a start one unit past the last that fits the window, a
    memory map select the family does not use, no width or no scan line, a logical row wider
    than the screen, a split screen, pixel or byte panning."""
    with pytest.raises(ds.Invalid) as got:
        shape_of(bench_name, **{key: (old, new)})
    assert got.value.code == "no_channel" and why in str(got.value), str(got.value)


@pytest.mark.parametrize(("bench_name", "start", "base", "window"), [
    ("screen-13h", "180h", 0xA0000, 0x10000), ("screen-text", "3830h", 0xB8000, 0x8000)])
def test_a_screen_ending_exactly_at_its_windows_end_is_read(
        bench_name: str, start: str, base: int, window: int) -> None:
    """The start one unit before the refused one: the screen's last byte is the window's."""
    got = shape_of(bench_name, mode=("disp-start=0h", f"disp-start={start}"))
    assert got.linear - base + got.length == window


def test_the_monochrome_window_is_b0000() -> None:
    assert shape_of("screen-text", gc=("misc=0eh", "misc=0ah")).linear == 0xB0000
    assert shape_of("probe-mono").linear == 0xB0000


def test_the_256_colour_window_is_a0000_under_select_00_too() -> None:
    """13h's own select (01, 64 KiB at A0000) and 00 (128 KiB from A0000), an edited capture."""
    assert shape_of("screen-13h", gc=("misc=05h", "misc=01h")).linear == 0xA0000


def test_a_double_scanned_cell_counts_its_scan_lines_twice() -> None:
    """INT 10h's 200-line text mode (`probe-200line`): CRTC `maxscnl=c7h` is an eight-line cell
    drawn twice, so the 400 rendered lines are 25 rows, as DRAW's `addrline-total` says, not
    the 50 the cell height alone gives."""
    got = shape_of("probe-200line")
    assert (got.source, got.width, got.height, got.length) == ("text", 80, 25, 4000)


def test_a_listing_missing_a_word_is_an_unexpected_answer() -> None:
    with pytest.raises(ds.Invalid) as got:
        shape_of("probe-booted", draw=("blocks=80", "columns=80"))
    assert got.value.code == "unexpected_answer" and "blocks" in str(got.value)


def test_fifty_rows_of_forty_columns() -> None:
    """The booted probe drawing eight-line rows of forty blocks (edited captures: DRAW's
    `blocks` and `addrline-total`, MODE's `scanlen`): rows and columns follow the words, no
    80 x 25 assumed."""
    draw = vga("probe-booted", "VGA DRAW").replace("blocks=80", "blocks=40", 1).replace(
        "addrline-total=16", "addrline-total=8", 1)
    got = screen.geometry({**words_of("probe-booted", mode=("scanlen=40", "scanlen=20")),
                           "draw": screen.parse_listing(draw, screen.TITLES["VGA DRAW"])})
    assert (got.width, got.height, got.length) == (40, 50, 4000)


@pytest.mark.parametrize(("loc", "cursor"), [
    ("0145h", [5, 4]), ("0000h", [0, 0]), ("07cfh", [79, 24]), ("07d0h", None)])
def test_the_cursor_is_column_and_row_and_null_off_the_screen(
        loc: str, cursor: list[int] | None) -> None:
    """The booted probe's CRTC with its cursor location edited: a column inside a row, the
    first cell, the last, and one past the screen."""
    assert shape_of("probe-booted", crtc=("curs-loc=0140h", f"curs-loc={loc}")).cursor == cursor


def test_a_cursor_before_the_display_start_is_null() -> None:
    """The start-address capture (start 50h) with the cursor edited to cell 4Fh, above it."""
    got = shape_of("screen-start80", crtc=("curs-loc=00a0h", "curs-loc=004fh"))
    assert got.cursor is None


def test_a_hidden_cursor_is_null() -> None:
    """The booted probe's draw state with `curs-en=0` (an edited capture)."""
    assert shape_of("probe-booted", draw=("curs-en=1", "curs-en=0")).cursor is None


def machine_tables(cpu_mode: str = "paged", v86: bool = False,
                   **edits: tuple[str, str]) -> screen.Tables:
    found: dict[str, Any] = {}
    for name, parse in (("gdt", lambda t: machine.parse_descriptors(t, "GDT")),
                        ("ldt", lambda t: machine.parse_descriptors(t, "LDT")),
                        ("paging", machine.parse_paging)):
        text = listing("rechip", name.upper())
        if name in edits:
            old, new = edits[name]
            assert old in text
            text = text.replace(old, new, 1)
        found[name] = parse(text)
    return screen.Tables(cpu_mode, v86, found)


def test_real_mode_reads_the_page_through_its_paragraph() -> None:
    assert screen.selector_for(0xB80A0, 4000, screen.Tables("real", False, {})) == (0xB80A, 0)


def test_a_virtual_8086_task_reads_through_the_paragraph_where_the_pages_allow() -> None:
    """A V86 task's segments are paragraphs whatever cr0 says; the page check still applies."""
    assert screen.selector_for(0xB8000, 4000, machine_tables(v86=True)) == (0xB800, 0)
    moved = machine_tables(v86=True, paging=("page 000B8xxx -> 00B8xxx",
                                             "page 000B8xxx -> 01B8xxx"))
    with pytest.raises(ds.Invalid):
        screen.selector_for(0xB8000, 4000, moved)


def test_paged_protected_mode_reads_through_the_lowest_gdt_segment_covering_the_page() -> None:
    """ReChip at its DPMI client's first stop: GDT 0038 is base 0 and covers the whole space, and
    the page tables map B8000 to itself."""
    assert screen.selector_for(0xB8000, 4000, machine_tables()) == (0x38, 0xB8000)


def test_the_lowest_covering_selector_is_chosen() -> None:
    """GDT 0030 edited to a flat data segment too: both cover, the lower wins."""
    found = machine_tables(gdt=("0030: b:000D12E0 type: 12 parbg\n      l:0000FFFF",
                                "0030: b:00000000 type: 12 parbg\n      l:FFFFFFFF"))
    assert screen.selector_for(0xB8000, 4000, found) == (0x30, 0xB8000)


def test_the_offset_is_counted_from_the_chosen_segments_base() -> None:
    """GDT 0030 edited to a data segment based at B0000, and then at B8000 itself: lower than
    0038, it is chosen, and the page lies 8000h into it, then at its first byte."""
    for base, off in (("000B0000", 0x8000), ("000B8000", 0)):
        found = machine_tables(gdt=("0030: b:000D12E0 type: 12 parbg",
                                    f"0030: b:{base} type: 12 parbg"))
        assert screen.selector_for(0xB8000, 4000, found) == (0x30, off)


@pytest.mark.parametrize(("old", "new", "gdt_kept"), [
    ("0038: b:00000000 type: 12", "0038: b:00000000 type: 1A", False),
    ("0038: b:00000000 type: 12", "0038: b:00000000 type: 10", True),
    ("0038: b:00000000 type: 12", "0038: b:00000000 type: 13", True),
    ("0038: b:00000000 type: 12", "0038: b:00000000 type: 14", False),
    ("0038: b:00000000 type: 12", "0038: b:00000000 type: 16", False),
    ("l:FFFFFFFF dpl : 3  10011", "l:FFFFFFFF dpl : 3  00011", False),
    ("l:FFFFFFFF dpl : 3  10011", "l:000B8F9F dpl : 3  10011", True),
    ("l:FFFFFFFF dpl : 3  10011", "l:000B8F9E dpl : 3  10011", False),
    ("l:FFFFFFFF dpl : 3  10011", "l:0000FFFF dpl : 3  10011", False),
])
def test_only_a_present_data_segment_whose_limit_reaches_the_last_byte_is_taken(
        old: str, new: str, gdt_kept: bool) -> None:
    """GDT 0038 edited: a code segment, the first and the last expand-up data types (10h, 13h:
    taken), the first expand-down one and one past it (14h, 16h, whose limit is where they stop
    being valid), not present, a limit
    ending exactly on the page's last byte, one byte short, and 64 KiB. Where 0038 no longer
    qualifies the LDT's flat segment answers."""
    sel, off = screen.selector_for(0xB8000, 4000, machine_tables(gdt=(old, new)))
    assert (sel == 0x38) is gdt_kept and off == 0xB8000
    if not gdt_kept:
        assert sel & 0x4


def test_a_page_mapped_elsewhere_is_not_read_as_the_screen() -> None:
    """The PAGING capture with B8000's page sent to another physical page (an edited capture)."""
    found = machine_tables(paging=("page 000B8xxx -> 00B8xxx", "page 000B8xxx -> 01B8xxx"))
    with pytest.raises(ds.Invalid) as got:
        screen.selector_for(0xB8000, 4000, found)
    assert got.value.code == "no_channel" and "000B8000" in str(got.value)


def test_every_page_the_screen_spans_is_checked_from_a_start_inside_one() -> None:
    """A screen starting at B80A0 runs into page B9000; that page sent elsewhere (an edited
    capture) is refused, though the first page maps to itself."""
    found = machine_tables(paging=("page 000B9xxx -> 00B9xxx", "page 000B9xxx -> 01B9xxx"))
    assert screen.selector_for(0xB8000, 4000, found) == (0x38, 0xB8000)
    with pytest.raises(ds.Invalid) as got:
        screen.selector_for(0xB80A0, 4000, found)
    assert "000B9000" in str(got.value)


def test_paging_on_with_no_page_runs_read_is_refused() -> None:
    tables = machine_tables()
    del tables.found["paging"]
    with pytest.raises(ds.Invalid) as got:
        screen.selector_for(0xB8000, 4000, tables)
    assert got.value.code == "no_channel" and "`PAGING`" in str(got.value)


def test_no_covering_segment_at_all_is_refused() -> None:
    with pytest.raises(ds.Invalid) as got:
        screen.selector_for(0xB8000, 4000, screen.Tables("protected", False,
                                                         {"gdt": [], "ldt": []}))
    assert got.value.code == "no_channel" and "000B8000" in str(got.value)
    assert "could not be read" not in str(got.value)
    with pytest.raises(ds.Invalid) as got:
        screen.selector_for(0xB8000, 4000, screen.Tables("protected", False, {}))
    assert "`GDT` could not be read" in str(got.value)


# ------------------------------------------------------------------ what the screen shows


PAGES = {"probe-booted": "probe-booted-page.bin", "probe-mono": "probe-mono-page.bin",
         "screen-text": "screen-text-page.bin",
         "screen-start80": "screen-start80-page.bin",
         "rechip-startup": "rechip-startup-page.bin", "screen-13h": "screen-13h-a000.bin.gz",
         "screen-13h-start80": "screen-13h-start80-a000.bin.gz"}


def page(bench_name: str) -> bytes:
    data = (VGA / PAGES[bench_name]).read_bytes()
    return gzip.decompress(data) if PAGES[bench_name].endswith(".gz") else data


def test_the_text_is_what_the_screen_shows() -> None:
    rows = screen.text_rows(page("probe-booted"), 80, 25)
    assert rows[:5] == ['Z:\\>mount c "."', "Drive C is mounted as local directory ./",
                        "Z:\\>c:", "C:\\>PROBE.COM", ""]
    assert screen.text_rows(page("screen-start80"), 80, 25)[0] == "SECOND ROW"
    rechip = screen.text_rows(page("rechip-startup"), 80, 25)
    assert rechip[13] == "C:\\>RECHIPD.EXE D:\\MIDI\\MONKEY.MID -a"


def test_control_bytes_are_the_glyphs_the_pc_draws_for_them() -> None:
    """The booted probe's page with its first cells edited to 00, 01, 1F, 7F and B0."""
    cells = bytearray(page("probe-booted"))
    for i, b in enumerate((0x00, 0x01, 0x1F, 0x7F, 0xB0)):
        cells[i * 2] = b
    assert screen.text_rows(bytes(cells), 80, 25)[0].startswith(" ☺▼⌂░")
    # The IBM PC's glyphs for 01-1F and 7F, as Unicode code points, one by one.
    assert [ord(screen.CP437[b]) for b in (*range(0x01, 0x20), 0x7F)] == [
        0x263A, 0x263B, 0x2665, 0x2666, 0x2663, 0x2660, 0x2022, 0x25D8, 0x25CB, 0x25D9, 0x2642,
        0x2640, 0x266A, 0x266B, 0x263C, 0x25BA, 0x25C4, 0x2195, 0x203C, 0x00B6, 0x00A7, 0x25AC,
        0x21A8, 0x2191, 0x2193, 0x2192, 0x2190, 0x221F, 0x2194, 0x25B2, 0x25BC, 0x2302]
    # 00 and FF draw as the blank 20 does, and every other byte as a glyph of its own.
    assert len(screen.CP437) == 256 and len(set(screen.CP437)) == 254
    assert screen.CP437[0x00] == screen.CP437[0x20] == screen.CP437[0xFF] == " "
    assert screen.text_rows(bytes([0xFF, 7]) * 2000, 80, 25)[0] == ""


class ScreenBench(Bench):
    """A stopped machine answering what was captured at one stop: the `VGA` listings and the
    video memory there (`fixtures/vga/`), and the cpu's own listings of the machine bench that
    stopped there (`fixtures/machine/`), the screen guest sharing the booted probe's machine."""

    MACHINE = {"rechip-startup": "rechip", "speedf": "speedf"}

    def __init__(self, name: str, logfile: Path | None) -> None:
        super().__init__(name, logfile)
        self.dumps: list[tuple[int, int, int]] = []

    def listing(self, command: str) -> str:
        if self.launch.logfile is None or command.startswith("VGA "):
            return super().listing(command)
        self.asked.append(command)
        return listing(self.MACHINE.get(self.bench, "probe-booted"), command)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.dumps.append((seg, off, length))
        data = page(self.bench)
        assert len(data) == length, (len(data), length)
        dest.write_bytes(data)
        return dest


def screen_bench(name: str, tmp_path: Path) -> ScreenBench:
    s = ScreenBench(name, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


def test_screen_view_reads_a_text_screen_in_real_mode(tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["status"] == "ok", r
    assert (r["mode"], r["source"], r["width"], r["height"]) == ("M_TEXT", "text", 80, 25)
    assert r["text"][3] == "C:\\>PROBE.COM" and r["cursor"] == [0, 4]
    assert r["display_start"] == "0h" and "image" not in r
    assert s.asked == ["VGA MODE", "VGA CRTC", "VGA GC", "VGA DRAW", "CPU"]
    assert s.dumps == [(0xB800, 0, 4000)] and r["session"]["altered"] is False
    assert r["summary"] == "screen_view M_TEXT: 80 x 25 text, cursor at 0,4"


def test_screen_view_reads_the_page_from_where_the_display_starts(tmp_path: Path) -> None:
    s = screen_bench("screen-start80", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["text"][0] == "SECOND ROW" and r["display_start"] == "50h" and r["cursor"] == [0, 1]
    assert s.dumps == [(0xB80A, 0, 4000)]


def test_screen_view_reads_a_paged_guests_text_through_its_gdt(tmp_path: Path) -> None:
    s = screen_bench("rechip-startup", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["status"] == "ok", r
    assert r["text"][13] == "C:\\>RECHIPD.EXE D:\\MIDI\\MONKEY.MID -a" and r["cursor"] == [0, 14]
    assert s.asked[-4:] == ["CPU", "GDT", "LDT", "PAGING"]
    assert s.dumps == [(0x38, 0xB8000, 4000)]


@pytest.mark.parametrize(("bench_name", "dump", "moved"), [
    ("screen-13h", (0xA000, 0, 64000), 0), ("screen-13h-start80", (0xA014, 0, 64000), 320)])
def test_screen_view_writes_the_256_colour_screen_as_its_indices(
        tmp_path: Path, bench_name: str, dump: tuple[int, int, int], moved: int) -> None:
    """The picture's pixel (x, y) is the guest's (x + y) & FF, from the row the display starts
    at; the PLTE is the DAC the guest set, widened."""
    s = screen_bench(bench_name, tmp_path)
    dest = tmp_path / "screen.png"
    r = cast(dict[str, Any], server.screen_view(dest=str(dest)))
    assert r["status"] == "ok", r
    assert (r["source"], r["width"], r["height"]) == ("indices", 320, 200)
    w, h, pixels, plte, trns = decode_png(dest.read_bytes())
    ramp = bytes((x + y) & 0xFF for y in range(200) for x in range(320)) + bytes(320)
    assert (w, h, trns) == (320, 200, b"") and pixels == ramp[moved:moved + 64000]
    assert plte == [screen.rgb8(e) for e in screen.parse_dacpal(vga(bench_name, "VGA DACPAL"))]
    assert r["image"]["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert s.dumps == [dump] and s.asked[-2:] == ["VGA DAC", "VGA DACPAL"]
    assert r["summary"] == f"screen_view M_VGA: 320 x 200 pixels to {dest}"


@pytest.mark.parametrize(("bench_name", "word"), [
    ("screen-12h", "M_EGA"), ("speedf", "M_LIN15"), ("rechip-ui", "M_LIN8"),
    ("probe-park", "M_ERROR")])
def test_screen_view_and_signature_refuse_a_mode_they_do_not_read_after_one_listing(
        tmp_path: Path, bench_name: str, word: str) -> None:
    s = screen_bench(bench_name, tmp_path)
    for r in (server.screen_view(), server.screen_signature()):
        assert r["status"] == "INVALID" and r["code"] == "no_channel", r
        assert f"`{word}`" in r["message"] and "capture_frame" in r["message"]
    assert s.asked == ["VGA MODE", "VGA MODE"] and s.dumps == []


def test_screen_view_refuses_a_dest_in_text_and_none_in_256_colours(tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.screen_view(dest=str(tmp_path / "t.png")))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and "text mode" in r["message"]
    assert s.asked == ["VGA MODE"] and s.dumps == []
    s = screen_bench("screen-13h", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and "`dest`" in r["message"]
    there = tmp_path / "there.png"
    there.write_bytes(b"mine")
    r = cast(dict[str, Any], server.screen_view(dest=str(there)))
    assert r["code"] == "bad_argument" and there.read_bytes() == b"mine" and s.dumps == []
    assert s.asked == ["VGA MODE", "VGA MODE"]


@pytest.mark.parametrize("dest", ["screen.png", "/tmp/a\x00b.png", 3])
def test_screen_view_refuses_a_dest_before_anything_is_typed(tmp_path: Path, dest: Any) -> None:
    s = screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.screen_view(dest=dest))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and s.asked == []


def test_the_screen_tools_without_a_logfile_or_on_a_running_guest(tmp_path: Path) -> None:
    s = ScreenBench("probe-booted", None)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    for r in (server.screen_view(), server.screen_signature()):
        assert r["status"] == "INVALID" and r["code"] == "no_channel" and "logfile" in r["message"]
    s = screen_bench("probe-booted", tmp_path)
    s.at_debugger = lambda: False  # type: ignore[method-assign]
    for r in (server.screen_view(), server.screen_signature()):
        assert r["status"] == "INVALID" and r["code"] == "not_stopped"
    assert s.asked == []


class Edited(ScreenBench):
    """The screen bench with one byte of its page, or one word of a listing, changed."""

    def __init__(self, name: str, logfile: Path, byte: int | None = None,
                 listing_edit: tuple[str, str, str] | None = None) -> None:
        super().__init__(name, logfile)
        self.byte, self.listing_edit = byte, listing_edit

    def listing(self, command: str) -> str:
        text = super().listing(command)
        if self.listing_edit and command == self.listing_edit[0]:
            assert self.listing_edit[1] in text
            text = text.replace(self.listing_edit[1], self.listing_edit[2], 1)
        return text

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        path = super().memdump(seg, off, length, dest)
        if self.byte is not None:
            data = bytearray(path.read_bytes())
            data[self.byte] ^= 0x01
            path.write_bytes(bytes(data))
        return path


def signature_of(s: ScreenBench) -> dict[str, Any]:
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return cast(dict[str, Any], server.screen_signature())


def test_the_signature_is_the_same_number_for_the_same_screen(tmp_path: Path) -> None:
    first = ScreenBench("probe-booted", tmp_path / "x.log")
    one = signature_of(first)
    assert first.asked == ["VGA MODE", "VGA CRTC", "VGA GC", "VGA DRAW", "CPU", "VGA DAC",
                           "VGA DACPAL"]
    two = signature_of(ScreenBench("probe-booted", tmp_path / "x.log"))
    assert one["status"] == "ok" and isinstance(one["signature"], int), one
    assert one["signature"] == two["signature"]
    assert (one["source"], one["mode"], one["width"], one["height"]) == ("text", "M_TEXT", 80, 25)
    assert one["summary"] == f"screen_signature M_TEXT 80 x 25: {one['signature']:#010x}"


@pytest.mark.parametrize(("byte", "edit"), [
    (0, None), (1, None), (None, ("VGA DACPAL", "00002a", "00002b")),
    (None, ("VGA DACPAL", "f8: 000000 000000 000000 000000-000000 000000 000000 000000",
            "f8: 000000 000000 000000 000000-000000 000000 000000 000001"))])
def test_a_changed_character_attribute_or_dac_entry_is_a_changed_number(
        tmp_path: Path, byte: int | None, edit: tuple[str, str, str] | None) -> None:
    """The first cell's character (byte 0) and attribute (byte 1), and DAC entry 1 (edits of the
    captures), each move the number."""
    plain = signature_of(ScreenBench("probe-booted", tmp_path / "x.log"))["signature"]
    moved = signature_of(Edited("probe-booted", tmp_path / "x.log", byte, edit))["signature"]
    assert moved != plain


def test_the_signature_folds_the_mode_and_the_size_as_well_as_the_bytes() -> None:
    shape = shape_of("probe-booted")
    data, dac = page("probe-booted"), ["000000"] * 256
    plain = screen.signature(shape, data, dac)
    for other in (dataclasses.replace(shape, word="M_TEXT2"),
                  dataclasses.replace(shape, width=40, height=50)):
        assert screen.signature(other, data, dac) != plain


def test_the_screen_tools_refuse_a_dac_not_in_its_six_bit_mode(tmp_path: Path) -> None:
    """The 13h capture's `VGA DAC` with `bits=8` (an edited capture): the PLTE and the fold are
    widened from six bits, so neither is written."""
    for tool in ("view", "signature"):
        s = Edited("screen-13h", tmp_path / "x.log",
                   listing_edit=("VGA DAC", "bits=6", "bits=8"))
        install()
        dstate.STATE.session = cast(ds.Session, s)
        r = (server.screen_view(dest=str(tmp_path / f"{tool}.png")) if tool == "view"
             else server.screen_signature())
        assert r["status"] == "INVALID" and r["code"] == "unexpected_answer", r
        assert "bits=8" in r["message"] and not (tmp_path / f"{tool}.png").exists()


def test_an_unreadable_cpu_listing_is_an_unexpected_answer(tmp_path: Path) -> None:
    s = Edited("probe-booted", tmp_path / "x.log", listing_edit=("CPU", "cpl=0", "cpl=?"))
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.screen_view())
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer" and "`CPU`" in r["message"]
    assert s.dumps == []


def test_a_listing_that_printed_nothing_is_said_so(tmp_path: Path) -> None:
    s = ScreenBench("probe-booted", tmp_path / "x.log")
    s.listing = lambda command: "" if command == "VGA GC" else ScreenBench.listing(s, command)  # type: ignore[method-assign]
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.screen_view())
    assert r["code"] == "unexpected_answer" and "`VGA GC` printed nothing" in r["message"]


def test_the_256_colour_signature_folds_the_pixels(tmp_path: Path) -> None:
    plain = signature_of(ScreenBench("screen-13h", tmp_path / "x.log"))
    assert plain["status"] == "ok" and plain["source"] == "indices"
    moved = signature_of(Edited("screen-13h", tmp_path / "x.log", 64000 - 1))
    assert moved["signature"] != plain["signature"]


def test_perform_runs_the_screen_tools(tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[{"op": "screen_view"},
                                                   {"op": "screen_signature"}]))
    assert r["status"] == "ok" and r["completed"] == 2, r
    s = screen_bench("probe-booted", tmp_path)
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "screen_signature"},
                                                     {"op": "screen_view", "dest": "x.png"}]))
    assert bad["status"] == "INVALID" and [e["step"] for e in bad["errors"]] == [1], bad
    assert s.asked == [] and s.dumps == []


# ------------------------------------------------------------------ screen_wait


class Frames(Retraces):
    """A machine stepped retrace by retrace through captured stops: `VRT` and its survey come off
    `fixtures/vrt/` as `run_for`'s double has them, and after `k` retraces every listing and the
    screen's bytes are those captured at `stops[k]` (the last one held), the `CPU` listing that
    stop's machine bench's."""

    MACHINE = {"probe-park": "probe-reset", "rechip-startup": "rechip"}

    def __init__(self, stops: list[str], vrts: int, logfile: Path) -> None:
        super().__init__([cap_vrt("probe-survey-0")] * (vrts + 2),
                         [cap_vrt(f"probe-vrt-{1 + i % 3}") for i in range(vrts)])
        self.stops = stops
        self.launch = SimpleNamespace(cwd=Path("/"), logfile=logfile, watched=False,
                                      input_port=None)
        self.asked: list[str] = []
        self.dumps: list[tuple[int, int, int]] = []

    @property
    def stop(self) -> str:
        done = self.keys.count(ds.RETRACE_COMMAND)
        return self.stops[min(done, len(self.stops) - 1)]

    def listing(self, command: str) -> str:
        self.asked.append(command)
        if command.startswith("VGA "):
            return vga(self.stop, command)
        return listing(self.MACHINE.get(self.stop, "probe-booted"), command)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.dumps.append((seg, off, length))
        dest.write_bytes(page(self.stop))
        return dest


def waiting(stops: list[str], vrts: int, tmp_path: Path,
            kind: type[Frames] = Frames) -> Frames:
    dbg = kind(stops, vrts, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, dbg)
    dstate.STATE.remember_stop(cast(ds.Session, dbg),
                               {"cs": "F000", "eip": "0000FFF0", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return dbg


def test_a_string_that_appears_after_a_retrace_is_found_with_the_stop_reply(
        tmp_path: Path) -> None:
    """From the probe's park (no mode set: examined as no match) one retrace lands in the
    booted probe, whose screen holds the launch line."""
    dbg = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok", r
    assert r["already"] is False and r["polls"] == 1 and r["point"] == [4, 3], r
    assert r["line"] == "C:\\>PROBE.COM" and isinstance(r["waited_s"], float)
    assert r["registers"] and "attribution" in r and "stop_seq" in r
    assert dbg.keys == [ds.RETRACE_COMMAND] and dbg.dumps == [(0xB800, 0, 4000)]
    assert dbg.asked.count("VGA MODE") == 2 and dbg.asked.count("VGA CRTC") == 1
    assert r["summary"] == "screen_wait 'PROBE.COM': found at 4,3 after 1 retrace(s)"


def test_a_string_already_on_screen_is_answered_without_moving_the_machine(
        tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 0, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="mounted as local", seconds=10))
    assert r["status"] == "ok" and r["already"] is True and r["polls"] == 0, r
    assert r["waited_s"] == 0.0 and r["point"] == [11, 1] and dbg.keys == []
    assert r["line"] == "Drive C is mounted as local directory ./"


def test_each_frame_reads_where_the_page_lies_and_the_cursor_listing_once(
        tmp_path: Path) -> None:
    """Three retraces on the booted probe's still page, the fourth `VRT` never answered: each
    frame costs `VGA MODE`, `VGA DRAW`, `VGA GC`, `CPU` and a dump; `VGA CRTC` comes once."""
    dbg = waiting(["probe-booted"], 3, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["status"] == "INVALID" and r["code"] == "wait_expired", r
    assert r["polls"] == 3 and r["running"] is True and len(dbg.dumps) == 4
    assert dbg.asked.count("VGA CRTC") == 1
    for each in ("VGA MODE", "VGA DRAW", "VGA GC", "CPU"):
        assert dbg.asked.count(each) == len(dbg.dumps), each


class ByAddress(Frames):
    """`Frames` whose video memory answers by the address dumped rather than by the stop: B8000
    holds the booted probe's colour page throughout, B0000 the monochrome page `probe-mono`
    captured."""

    AT = {0xB8000: "probe-booted", 0xB0000: "probe-mono"}

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.dumps.append((seg, off, length))
        dest.write_bytes(page(self.AT[(seg << 4) + off]))
        return dest


def test_a_switch_to_the_monochrome_page_under_the_same_draw_state_is_followed(
        tmp_path: Path) -> None:
    """One retrace from the booted probe lands in mode 7 (`probe-mono`): the mode word and the
    draw state are the colour mode's, and GC `misc` alone moves the page to B0000, where `QZQ`
    is."""
    dbg = waiting(["probe-booted", "probe-mono"], 1, tmp_path, ByAddress)
    r = cast(dict[str, Any], server.screen_wait(text="QZQ", seconds=2))
    assert r["status"] == "ok" and r["point"] == [0, 0] and r["line"] == "QZQ", r
    assert dbg.dumps == [(0xB800, 0, 4000), (0xB000, 0, 4000)]


class EditedAfterRetrace(Frames):
    """`Frames` whose listings, once a retrace has run, carry the edits `EDITS` names: per
    command, a word and what replaces it, each asserted present so an edit cannot miss."""

    EDITS: dict[str, tuple[str, str]] = {}

    def listing(self, command: str) -> str:
        text = super().listing(command)
        if command in self.EDITS and self.keys.count(ds.RETRACE_COMMAND):
            old, new = self.EDITS[command]
            assert old in text, (command, old)
            text = text.replace(old, new, 1)
        return text


class Resized(EditedAfterRetrace):
    """The booted probe whose second stop renders 80 x 50 in the same `M_TEXT` (DRAW edited to
    an eight-line row), its page the captured one with a second, blank half."""

    EDITS = {"VGA DRAW": ("addrline-total=16", "addrline-total=8")}

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        path = super().memdump(seg, off, length, dest)
        path.write_bytes(path.read_bytes().ljust(length, b"\x00"))
        return path


def test_a_screen_resized_under_the_same_mode_word_is_placed_again(tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 1, tmp_path, Resized)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == "wait_expired", r
    assert dbg.asked.count("VGA CRTC") == 1 and [d[2] for d in dbg.dumps][:2] == [4000, 8000]
    assert len(r["text"]) == 50


def test_protected_mode_frames_read_the_tables_once(tmp_path: Path) -> None:
    dbg = waiting(["rechip-startup"], 2, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == "wait_expired", r
    assert dbg.asked.count("GDT") == 1 and len(dbg.dumps) >= 2
    assert set(dbg.dumps) == {(0x38, 0xB8000, 4000)}


class Costly(Frames):
    """`Frames` whose every listing costs `cost` seconds of the clock a case runs ahead."""

    cost = 0.0
    ahead: list[float]

    def listing(self, command: str) -> str:
        self.ahead[0] += self.cost
        return super().listing(command)


@pytest.fixture
def ahead(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """`dosbox_retrace`'s clock run ahead of the real one by what a case adds: the bound is read
    off it, while the session's own wait for a stop keeps the real clock, so a `VRT` the double
    answers is heard."""
    by = [0.0]
    real = time.monotonic
    monkeypatch.setattr(retrace, "time", SimpleNamespace(monotonic=lambda: real() + by[0]))
    return by


def costly(stops: list[str], vrts: int, tmp_path: Path, ahead: list[float],
           cost: float) -> Costly:
    dbg = cast(Costly, waiting(stops, vrts, tmp_path, Costly))
    dbg.ahead, dbg.cost = ahead, cost
    return dbg


def test_an_expiry_before_any_retrace_types_nothing_and_leaves_the_stop(tmp_path: Path) -> None:
    """A bound spent before the first `VRT` goes out: nothing moved, so the stop is not recorded
    again, and a retrace an earlier cut run left armed is still armed, and said so."""
    dbg = waiting(["probe-booted"], 3, tmp_path)
    dstate.STATE.retrace_pending = True
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1e-9))
    assert r["code"] == "wait_expired" and r["polls"] == 0 and dbg.keys == [], r
    assert r["running"] is False and r["retrace_pending"] is True and "stop_seq" not in r
    assert dstate.STATE.retrace_pending is True and dstate.STATE.last_stop["seq"] == before
    assert r["text"][3] == "C:\\>PROBE.COM"


def test_a_short_bound_still_reaches_the_first_frame_and_records_the_stop_it_expires_at(
        tmp_path: Path, ahead: list[float]) -> None:
    """Each listing costs a second against a half-second bound. The bound starts after the
    first read, as `run_for`'s after its first survey, so one `VRT` goes out; the read of its
    frame is finished past the bound, and the wait expires stopped at that retrace, which is
    recorded. The description says when the bound starts."""
    dbg = costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == "wait_expired" and r["polls"] == 1 and r["running"] is False, r
    assert r["retrace_pending"] is False and dbg.keys == [ds.RETRACE_COMMAND]
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"] == before + 1
    doc = " ".join((server.screen_wait.__doc__ or "").split())
    assert "counted from after the first read of the screen, so a short one still reaches the " \
        "first frame" in doc


def test_screen_wait_on_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 1, tmp_path)
    dbg.running = True
    r = cast(dict[str, Any], server.screen_wait(text="PROBE", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "not_stopped", r
    assert dbg.asked == [] and dbg.keys == []


def test_an_expired_wait_says_what_it_examined(tmp_path: Path) -> None:
    dbg = waiting(["probe-park", "probe-park", "probe-booted"], 3, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1.0))
    assert r["status"] == "INVALID" and r["code"] == "wait_expired", r
    # A `VRT` still out at the bound is typed and unanswered: `running`, and one key past polls.
    assert len(dbg.keys) == r["polls"] + int(r["running"]) and r["polls"] >= 2
    assert r["retrace_pending"] is r["running"]
    assert "were not in a text mode" in r["message"]
    assert r["text"][3] == "C:\\>PROBE.COM"


def cut_by_breakpoint(tmp_path: Path) -> Frames:
    """The booted probe whose first `VRT` is cut by a declared breakpoint at 0814:0108."""
    dbg = waiting(["probe-booted"], 2, tmp_path)
    dbg.panes = [cap_vrt("probe-survey-cut-by-bp-0108")] * 3
    dbg.vrts = [cap_vrt("probe-vrt-cut-by-bp-0108")]
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", "0814:0108"))
    return dbg


def test_a_breakpoint_that_cuts_a_frame_ends_the_wait_naming_it(tmp_path: Path) -> None:
    cut_by_breakpoint(tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "wait_stopped", r
    assert r["attribution"]["ref"] == "0814:0108" and r["retrace_pending"] is True
    assert r["polls"] == 1 and dstate.STATE.retrace_pending is True
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"]


@pytest.mark.parametrize("kw", [
    {"text": ""}, {"text": "x" * 133}, {"text": "a\nb"}, {"text": 3}, {"text": "Name: "},
    {"text": "   "}, {"text": "€uro"},
    {"text": "C:", "seconds": 0}, {"text": "C:", "seconds": 601}])
def test_screen_wait_refuses_an_argument_before_anything_is_typed(
        tmp_path: Path, kw: dict[str, Any]) -> None:
    dbg = waiting(["probe-booted"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(**kw))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert dbg.asked == [] and dbg.keys == []


def test_a_cpu_mode_change_under_the_same_text_screen_reads_the_tables_again(
        tmp_path: Path) -> None:
    """From the booted probe (real mode) one retrace lands at ReChip's DPMI client (paged, the
    shell's text page unchanged in mode): the page is then read through GDT 0038, not through
    the paragraph the real-mode frame used."""
    dbg = waiting(["probe-booted", "rechip-startup"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="RECHIPD.EXE", seconds=10))
    assert r["status"] == "ok" and r["point"] == [4, 13], r
    assert dbg.dumps == [(0xB800, 0, 4000), (0x38, 0xB8000, 4000)]
    assert dbg.asked.count("VGA CRTC") == 1 and "GDT" in dbg.asked


def test_perform_runs_screen_wait_and_checks_it_first(tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 0, tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "screen_wait", "text": "PROBE.COM", "seconds": 5}, {"op": "screen_signature"}]))
    assert r["status"] == "ok" and r["completed"] == 2, r
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "screen_signature"},
                                                     {"op": "screen_wait", "text": ""}]))
    assert bad["status"] == "INVALID" and [e["step"] for e in bad["errors"]] == [1], bad
    assert dbg.keys == []


def test_a_found_wait_says_a_watch_or_interrupt_stop_could_pass_for_a_retrace(
        tmp_path: Path) -> None:
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("interrupt", "address", "BPINT 21 AH=4C"))
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["note"] == retrace.UNTOLD_NOTE, r


def test_a_cut_repaint_after_a_retrace_is_not_taken_for_a_breakpoint(tmp_path: Path) -> None:
    """With a code breakpoint declared every frame is surveyed; a survey that comes back with no
    pane (an empty repaint) cannot place the stop, so the wait reads the screen and goes on."""
    dbg = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    dbg.panes = ["", *[cap_vrt("probe-survey-0")] * 3]
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", "0814:0108"))
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["polls"] == 1 and r["point"] == [4, 3], r


def test_a_find_whose_stop_survey_comes_back_cut_keeps_the_find(tmp_path: Path) -> None:
    """The text is found at the first retrace, and the stop reply's survey repaints nothing: the
    find stands with its enrichment marked unavailable, as `run_for` keeps its account."""
    dbg = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    dbg.panes = ["", *[cap_vrt("probe-survey-0")] * 3]
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["point"] == [4, 3] and r["line"] == "C:\\>PROBE.COM", r
    assert r["enrichment"]["available"] is False and "registers" not in r


class PannedAfterRetrace(EditedAfterRetrace):
    """The booted probe whose screen pans by a pixel after the first retrace (`pel-pan=1`, an
    edited capture): a layout the reader refuses."""

    EDITS = {"VGA MODE": ("pel-pan=0", "pel-pan=1")}


def test_a_frame_refused_after_a_retrace_records_the_stop_the_wait_ends_at(
        tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 2, tmp_path, PannedAfterRetrace)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "no_channel" and "panning" in r["message"]
    assert r["polls"] == 1 and dbg.keys == [ds.RETRACE_COMMAND], r
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"] == before + 1


ON_ITS_OWN: dict[str, Any] = {"stop_seq": 1, "at": "F000:FFF0", "attribution": {}}
APPLIED: dict[str, Any] = {"armed": ["0814:0108"]}
ACCOUNTS = {"stopped_on_its_own": ON_ITS_OWN, "applied_on_stop": APPLIED}


@pytest.mark.parametrize("end", ["wait_expired", "wait_stopped", "no_channel"])
def test_a_wait_refused_at_a_stop_carries_what_that_stops_reply_delivered(
        tmp_path: Path, ahead: list[float], end: str) -> None:
    """The stop reply that records where a refused wait stopped is also the first reply built
    since the contact that found a stop the guest reached on its own, or applied declarations
    on one: the refusal carries those accounts, rather than spending them on a reply nobody
    sees. Ended by the bound, by a breakpoint, and by a frame the reader refuses."""
    if end == "wait_expired":
        costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    elif end == "wait_stopped":
        cut_by_breakpoint(tmp_path)
    else:
        waiting(["probe-booted"], 2, tmp_path, PannedAfterRetrace)
    dstate.STATE.found_stop_last = dict(ON_ITS_OWN)
    dstate.STATE.applied_last.update(APPLIED)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == end and r["polls"] == 1 and "stop_seq" in r, r
    assert {k: r.get(k) for k in ACCOUNTS} == ACCOUNTS


def test_an_expired_wait_counts_the_frames_that_were_not_text(tmp_path: Path) -> None:
    """The park, the park again after one retrace, the booted text page after the second, and a
    third `VRT` never answered: two of the three frames examined were not text."""
    waiting(["probe-park", "probe-park", "probe-booted"], 2, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1.0))
    assert r["code"] == "wait_expired" and r["polls"] == 2 and r["running"] is True, r
    assert "; 2 of 3 frames examined were not in a text mode" in r["message"]


class V86AfterRetrace(EditedAfterRetrace):
    """ReChip's DPMI client's stop, whose `CPU` says after the first retrace that the cpu runs a
    virtual-8086 task (`vm=1`, an edited capture): still paged, so the cpu mode is unchanged."""

    EDITS = {"CPU": ("[vm=0 ", "[vm=1 ")}


def test_a_virtual_8086_task_entered_under_the_same_cpu_mode_reads_through_the_paragraph(
        tmp_path: Path) -> None:
    dbg = waiting(["rechip-startup"], 1, tmp_path, V86AfterRetrace)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == "wait_expired", r
    assert dbg.dumps == [(0x38, 0xB8000, 4000), (0xB800, 0, 4000)]


#: What a reply can carry whatever the tool, described once for all rather than in each tool.
ENVELOPE = {"summary", "status", "code", "message", "session", "stopped_on_its_own",
            "applied_on_stop"}


def test_the_screen_wait_description_names_every_key_its_replies_carry(
        tmp_path: Path, ahead: list[float]) -> None:
    """Found with its stop reply, found with that reply's survey cut, stopped by a breakpoint,
    and expired at a retrace of its own: each key beside the envelope's is named in the
    description, in backticks."""
    replies: list[dict[str, Any]] = []
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    replies.append(cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10)))
    dbg = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    dbg.panes = ["", *[cap_vrt("probe-survey-0")] * 3]
    replies.append(cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10)))
    cut_by_breakpoint(tmp_path)
    replies.append(cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5)))
    costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    replies.append(cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5)))
    assert [r.get("code", r["status"]) for r in replies] == ["ok", "ok", "wait_stopped",
                                                               "wait_expired"], replies
    doc = server.screen_wait.__doc__ or ""
    unnamed = sorted({k for r in replies for k in r} - ENVELOPE
                     - {k for r in replies for k in r if f"`{k}`" in doc})
    assert not unnamed, unnamed


class ConsoleFailsAfterRetrace(Frames):
    """The booted probe whose console, after the first retrace, answers `VGA DRAW` with nothing
    the reader can take: a refusal about the console, not about the screen."""

    def listing(self, command: str) -> str:
        if command == "VGA DRAW" and self.keys.count(ds.RETRACE_COMMAND):
            self.asked.append(command)
            raise ds.Invalid("unexpected_answer", "`VGA DRAW` printed nothing")
        return super().listing(command)


def test_a_refusal_about_the_console_mid_wait_is_passed_on_and_nothing_more_is_typed(
        tmp_path: Path) -> None:
    dbg = waiting(["probe-booted"], 2, tmp_path, ConsoleFailsAfterRetrace)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["code"] == "unexpected_answer" and "stop_seq" not in r and "polls" not in r, r
    assert dstate.STATE.last_stop["seq"] == before and dbg.asked[-1] == "VGA DRAW"


def test_a_refused_wait_whose_stop_survey_comes_back_cut_says_so_and_records_nothing(
        tmp_path: Path, ahead: list[float]) -> None:
    """Expired at a retrace of its own, the stop reply's survey repainting nothing: no stop is
    recorded, so no `stop_seq`; `enrichment` says why."""
    dbg = costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    dbg.panes = ["", *[cap_vrt("probe-survey-0")] * 3]
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["code"] == "wait_expired" and r["polls"] == 1 and "stop_seq" not in r, r
    assert r["enrichment"]["available"] is False and dstate.STATE.last_stop["seq"] == before
