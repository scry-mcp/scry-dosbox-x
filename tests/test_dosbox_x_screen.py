"""The screen tools and the `vga` section, against what a real debugger wrote.

The listings, pages and video-memory windows are files under `fixtures/vga/`, captured from
live sessions (its provenance says where each one stopped), so the shapes the parsers accept are
the debugger's and the answers the decoders give are the guest's own arithmetic. Where a case
changes a capture (one word edited), it says so.
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import importlib.util
import os
import re
import struct
import time
import zlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from channel_double import REAL_STOP, Machine, Stop, session_over
from dosbox_x_server_support import NO_SUCH_HOME, clean_session, documented, install  # noqa: F401
from scry_core import png, screen_map
from scry_core.host_program import MODE_BITS
from test_dosbox_x_machine import Bench, listing
from test_dosbox_x_run_for import FRAME_MS

from scry_dosbox_x import arming, checks, docs, grammar, machine, paths, retrace, screen, server
from scry_dosbox_x import dac as vgadac
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import vga as dvga

VGA = Path(__file__).parent / "fixtures" / "vga"
BENCHES = ("probe-park", "probe-booted", "dos-real16", "dos-djgpp32-startup", "dos-djgpp32-ui",
           "screen-text", "screen-start80", "screen-dac01", "screen-13h", "screen-13h-start80",
           "screen-12h")
#: The planes guest's stops, and the mode word each is in.
PLANES = {"planes-12h": "M_EGA", "planes-modex": "M_VGA", "planes-lin8": "M_LIN8",
          "planes-lin15": "M_LIN15", "planes-lin16": "M_LIN16", "planes-lin32": "M_LIN32"}

#: Every section a map can read, for the cases that judge the whole map.
EVERY = list(machine.SECTION_NAMES)


def vga(bench: str, command: str) -> str:
    name = f"{bench}-{command.lower().replace(' ', '-')}-log.txt"
    return (VGA / name).read_bytes().decode("latin-1")


def parsed(bench: str, command: str) -> dict[str, Any]:
    return dvga.parse_listing(vga(bench, command), dvga.TITLES[command])


def window(name: str) -> bytes:
    return gzip.decompress((VGA / name).read_bytes())


# ------------------------------------------------------------------ the listings


def _real_bp(ref: str) -> None:
    """A raw breakpoint declared at the real-mode stop the probe guest sits at."""
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", ref, cpu=grammar.REAL_MODE))


@pytest.mark.parametrize("bench", BENCHES)
def test_every_vga_listing_parses_on_every_bench(bench: str) -> None:
    for _, command, title in dvga.VGA_LISTINGS:
        got = dvga.parse_listing(vga(bench, command), title)
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
    draw = parsed("dos-real16", "VGA DRAW")
    assert (draw["width"], draw["height"], draw["bpp"]) == ("640", "480", "15")
    assert parsed("screen-12h", "VGA MODE")["mode"] == "M_EGA"
    assert parsed("dos-djgpp32-ui", "VGA MODE")["mode"] == "M_LIN8"


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
        dvga.parse_listing(text.replace(old, new, 1), dvga.TITLES[command])
    assert got.value.line.startswith(line), got.value.line


def test_a_listing_with_its_title_and_no_word_is_unreadable() -> None:
    with pytest.raises(machine.Unreadable):
        dvga.parse_listing("VGA DAC info:\n", "VGA DAC info:")


# ------------------------------------------------------------------ the DAC


def test_dacpal_reads_all_256_entries_as_printed() -> None:
    booted = vgadac.parse_dacpal(vga("probe-booted", "VGA DACPAL"))
    assert len(booted) == 256 and booted[:4] == ["000000", "00002a", "002a00", "002a2a"]
    assert vgadac.parse_dacpal(vga("probe-park", "VGA DACPAL")) == ["000000"] * 256


def test_the_guests_ramp_is_the_dac_the_debugger_lists() -> None:
    """The screen guest writes entry i as (i & 3F, (i >> 1) & 3F, (i >> 2) & 3F) in 13h: the
    listing is that arithmetic, entry by entry."""
    want = [f"{i & 0x3F:02x}{(i >> 1) & 0x3F:02x}{(i >> 2) & 0x3F:02x}"
            for i in range(256)]
    assert vgadac.parse_dacpal(vga("screen-13h", "VGA DACPAL")) == want


def test_one_dac_write_moves_one_entry() -> None:
    before = vgadac.parse_dacpal(vga("screen-text", "VGA DACPAL"))
    after = vgadac.parse_dacpal(vga("screen-dac01", "VGA DACPAL"))
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
        vgadac.parse_dacpal(text.replace(old, new, 1))


def test_a_dacpal_missing_its_last_row_is_unreadable() -> None:
    text = vga("probe-booted", "VGA DACPAL")
    with pytest.raises(machine.Unreadable):
        vgadac.parse_dacpal(text[:text.rindex("f8: ")])


def test_a_listing_that_pages_on_the_screen_comes_back_whole_from_one_command(
        tmp_path: Path) -> None:
    """`VGA DACPAL` pages after row 90 on the debugger's screen; over the channel the command
    prints every row at once, so it is read with one request and nothing typed after it."""
    machine = waiting(["probe-booted"], 0, tmp_path)
    s = cast(ds.Session, dstate.STATE.session)
    assert s.listing("VGA DACPAL") == vga("probe-booted", "VGA DACPAL")
    assert machine.sent == ["EXEC VGA DACPAL"]


@pytest.mark.parametrize(("entry", "want"), [
    ("000000", "#000000"), ("00002a", "#0000aa"), ("3f0000", "#ff0000"), ("153f2a", "#55ffaa"),
    ("010203", "#04080c")])
def test_a_six_bit_entry_widens_as_the_emulator_renders_it(entry: str, want: str) -> None:
    """Each component's two top bits repeated below: the rule that reproduced every pixel of the
    emulator's own capture of the screen guest (63 is 255, 42 is 170, 1 is 4)."""
    assert vgadac.color(entry) == want


# ------------------------------------------------------------------ what the screen can be


def test_the_13h_window_is_the_guests_diagonal_ramp() -> None:
    """The screen guest fills A000 so the pixel at (x, y) is (x + y) & FF, 320 a row: the
    captured window is exactly that, and the one captured with the display start moved holds
    the same memory from its next row on."""
    want = bytes((x + y) & 0xFF for y in range(200) for x in range(320))
    assert window("screen-13h-a000-bin.gz") == want
    moved = window("screen-13h-start80-a000-bin.gz")
    assert moved[:64000 - 320] == want[320:] and set(moved[64000 - 320:]) == {0}


@pytest.mark.parametrize(("bench", "want"), [
    ("probe-booted", "text"), ("screen-text", "text"), ("dos-djgpp32-startup", "text"),
    ("screen-13h", "indices"), ("screen-13h-start80", "indices"),
    ("screen-12h", "planar"), ("planes-12h", "planar"), ("planes-modex", "unchained"),
    ("dos-real16", "linear"), ("dos-djgpp32-ui", "linear"), ("planes-lin8", "linear"),
    ("planes-lin15", "linear"), ("planes-lin16", "linear"), ("planes-lin32", "linear")])
def test_every_mode_with_a_decoder_names_where_it_is_read(bench: str, want: str) -> None:
    assert dvga.source_of(parsed(bench, "VGA MODE")) == want


@pytest.mark.parametrize(("bench", "old", "new", "word", "why"), [
    ("probe-park", None, None, "M_ERROR", "no video mode is set"),
    ("dos-real16", "mode=M_LIN15", "mode=M_LIN24", "M_LIN24", "no decoder here"),
    ("screen-12h", "mode=M_EGA", "mode=M_CGA4", "M_CGA4", "no decoder here"),
])
def test_every_other_mode_is_refused_naming_its_word_and_the_capture_route(
        bench: str, old: str | None, new: str | None, word: str, why: str) -> None:
    """The captured mode as it is, and two edited captures (the word named) for the families no
    bench draws."""
    text = vga(bench, "VGA MODE")
    if old is not None and new is not None:
        assert old in text
        text = text.replace(old, new, 1)
    with pytest.raises(ds.Invalid) as got:
        dvga.source_of(dvga.parse_listing(text, "VGA mode info:"))
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
    """scry-core's codec, read back by this file's own reader: the indices the guest wrote and
    the DAC as the PLTE."""
    pixels = window("screen-13h-a000-bin.gz")
    pal = [vgadac.rgb8(e) for e in vgadac.parse_dacpal(vga("screen-13h", "VGA DACPAL"))]
    w, h, got, plte, trns = decode_png(png.encode(png.Raster(320, 200, pixels, tuple(pal))))
    assert (w, h, got, plte, trns) == (320, 200, pixels, pal, b"")


@pytest.mark.parametrize(("w", "h", "pixels", "entries", "clear"), [
    (4, 2, b"\x00" * 7, 1, None), (4, 2, b"\x00" * 9, 1, None), (1, 1, b"\x00", 0, None),
    (1, 1, b"\x00", 257, None), (1, 1, b"\x02", 2, None), (1, 1, b"\x00", 2, 2)])
def test_the_png_refuses_what_a_viewer_could_not_draw(
        w: int, h: int, pixels: bytes, entries: int, clear: int | None) -> None:
    """A raster short or long of its size, an empty or oversized palette, and an index (a pixel
    or the transparent one) past the palette's entries."""
    with pytest.raises(ValueError):
        png.encode(png.Raster(w, h, pixels, ((0, 0, 0),) * entries), clear)


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
    assert r["bits"] == 6 and r["pel_mask"] == "ffh"
    assert s.asked == ["VGA DAC", "VGA DACPAL"]
    assert r["session"]["altered"] is False
    # THE SWATCH IS ALWAYS DRAWN, into the session's scratch when no `dest` is named, and
    # attached: 256 squares of 16 px enlarged x4 is 1024 a side, inside the inline ceiling.
    image = r["image"]
    assert Path(image["path"]).parent.parent == dstate.STATE.session_dir
    assert (image["width"], image["height"], image["scale"], image["inline"]) == (
        1024, 1024, 4, True)
    assert r["summary"] == "palette: entries 0 to 255 of 256; 1024x1024 PNG x4, inline"


def test_palette_returns_the_entries_asked_for(tmp_path: Path) -> None:
    bench("screen-dac01", tmp_path)
    one = cast(dict[str, Any], server.palette(first=1, count=1))
    assert one["count"] == 1 and one["rgb"] == ["3f0000"] and one["colors"] == ["#ff0000"]
    assert one["summary"].startswith("palette: entry 1 #ff0000 of 256; ")
    ramp = vgadac.parse_dacpal(vga("screen-13h", "VGA DACPAL"))
    bench("screen-13h", tmp_path)
    tail = cast(dict[str, Any], server.palette(first=250))
    assert tail["count"] == 6 and tail["first"] == 250 and tail["rgb"] == ramp[250:]
    last = cast(dict[str, Any], server.palette(first=255, count=1))
    assert last["rgb"] == [ramp[255]] and last["colors"] == [vgadac.color(ramp[255])]
    whole = cast(dict[str, Any], server.palette(first=0, count=256))
    assert whole["count"] == 256 and whole["rgb"] == ramp


@pytest.mark.parametrize(("first", "count"), [
    (0, 16), (3, 5), (1, 40), (16, 32), (200, 56), (0, 256), (255, 1), (0, 1), (0, 17), (1, 255)])
def test_the_palette_picture_is_one_square_per_entry_indexed_by_the_entry(
        tmp_path: Path, first: int, count: int) -> None:
    bench("screen-13h", tmp_path)
    dest = tmp_path / "pal.png"
    r = cast(dict[str, Any], server.palette(first=first, count=count, scale=1, dest=str(dest)))
    assert r["status"] == "ok", r
    image = r["image"]
    data = dest.read_bytes()
    assert image["sha256"] == hashlib.sha256(data).hexdigest() and image["indexed"] is True
    assert image["path"] == str(dest) and image["scale"] == 1
    w, h, pixels, plte, trns = decode_png(data)
    assert (w, h) == (image["width"], image["height"])
    assert w == min(count, 16) * 16 and h == -(-count // 16) * 16
    dac = vgadac.parse_dacpal(vga("screen-13h", "VGA DACPAL"))
    assert plte == [vgadac.rgb8(e) for e in dac]
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


@NO_SUCH_HOME
def test_perform_refuses_a_home_that_does_not_resolve_before_any_step_runs(
        tmp_path: Path) -> None:
    """`~somebody` naming no account cannot become a path: judged with the whole list, so the
    step before it never runs."""
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "palette"}, {"op": "palette", "dest": "~nosuchuser-d2/p.png"}]))
    assert r["status"] == "INVALID" and [e["step"] for e in r["errors"]] == [1], r
    assert s.asked == []


def test_perform_refuses_an_attach_that_is_no_yes_or_no_before_any_step_runs(
        tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "palette"}, {"op": "screen_view", "attach": "no"}]))
    assert r["status"] == "INVALID" and [e["step"] for e in r["errors"]] == [1], r
    assert "attach is true or false" in str(r["errors"]) and s.asked == []


def test_a_dest_from_home_passes_the_gate_expanded(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    checks.check("palette", dest="~/pal.png")
    with pytest.raises(ds.Invalid, match="must be an absolute path or start with `~`"):
        checks.check("palette", dest="pal.png")


@MODE_BITS
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


def test_palette_without_a_logfile_reads_its_listings_all_the_same(tmp_path: Path) -> None:
    s = Bench("probe-booted", None)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "ok" and r["entries"] == 256 and "VGA DACPAL" in s.asked, r


def test_palette_on_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    s = bench("probe-booted", tmp_path)
    s.at_debugger = lambda: False  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.palette())
    assert r["status"] == "INVALID" and r["code"] == "not_stopped" and s.asked == []


def test_a_dac_not_in_its_six_bit_mode_is_not_expanded(tmp_path: Path) -> None:
    """The booted probe's `VGA DAC` with `bits=8` (an edited capture): the widening applies
    to the six-bit DAC only."""
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
    assert r["status"] == "ok" and r["steps_completed"] == 1, r
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
    reply = cast(dict[str, Any], server.machine_map(sections=EVERY))
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
    r = mapped("dos-djgpp32", tmp_path)
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
    r = cast(dict[str, Any], server.machine_map(sections=EVERY))
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
    r = cast(dict[str, Any], server.machine_map(sections=EVERY))
    assert "vga" not in r and "`vga` is absent: `VGA MODE` printed nothing" in r["coverage_note"]
    assert "VGA CRTC" not in s.asked


def test_the_listing_reader_fixture_names_every_vga_capture() -> None:
    """The machine tests' bench reader serves the `VGA` listings from this directory, under the
    stop each machine bench was captured at."""
    assert listing("probe-booted", "VGA MODE") == vga("probe-booted", "VGA MODE")
    assert listing("dos-djgpp32", "VGA MODE") == vga("dos-djgpp32-startup", "VGA MODE")
    assert listing("probe-reset", "VGA DAC") == vga("probe-park", "VGA DAC")



# ------------------------------------------------------------------ where the screen is


def words_of(bench_name: str, **edits: tuple[str, str]) -> dict[str, dict[str, Any]]:
    """The four listings that place the screen at a capture, keyed as `geometry` takes them,
    with an edit per key where a case names one."""
    out = {}
    for key in dvga.SHAPE_KEYS:
        command = dvga.COMMAND_OF[key]
        text = vga(bench_name, command)
        if key in edits:
            old, new = edits[key]
            assert old in text, (key, old)
            text = text.replace(old, new, 1)
        out[key] = dvga.parse_listing(text, dvga.TITLES[command])
    return out


def shape_of(bench_name: str, **edits: tuple[str, str]) -> dvga.Geometry:
    return dvga.geometry(words_of(bench_name, **edits))


@pytest.mark.parametrize(("bench_name", "linear", "cursor"), [
    ("probe-booted", 0xB8000, [0, 4]), ("screen-text", 0xB8000, [0, 2]),
    ("screen-start80", 0xB80A0, [0, 1]), ("dos-djgpp32-startup", 0xB8000, [0, 14])])
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
    ("screen-13h", "mode", "real-start=0h", "real-start=181h", "past the window"),
    ("screen-text", "mode", "real-start=0h", "real-start=3831h", "past the window"),
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
    got = shape_of(bench_name, mode=("real-start=0h", f"real-start={start}"))
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
    got = dvga.geometry({**words_of("probe-booted", mode=("scanlen=40", "scanlen=20")),
                           "draw": dvga.parse_listing(draw, dvga.TITLES["VGA DRAW"])})
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
                   **edits: tuple[str, str]) -> dvga.Tables:
    found: dict[str, Any] = {}
    for name, parse in (("gdt", lambda t: machine.parse_descriptors(t, "GDT")),
                        ("ldt", lambda t: machine.parse_descriptors(t, "LDT")),
                        ("paging", machine.parse_paging)):
        text = listing("dos-djgpp32", name.upper())
        if name in edits:
            old, new = edits[name]
            assert old in text
            text = text.replace(old, new, 1)
        found[name] = parse(text)
    return dvga.Tables(cpu_mode, v86, found)


def test_real_mode_reads_the_page_through_its_paragraph() -> None:
    assert dvga.selector_for(0xB80A0, 4000, dvga.Tables("real", False, {})) == (0xB80A, 0)


def test_a_virtual_8086_task_reads_through_the_paragraph_where_the_pages_allow() -> None:
    """A V86 task's segments are paragraphs whatever cr0 says; the page check still applies."""
    assert dvga.selector_for(0xB8000, 4000, machine_tables(v86=True)) == (0xB800, 0)
    moved = machine_tables(v86=True, paging=("page 000B8xxx -> 00B8xxx",
                                             "page 000B8xxx -> 01B8xxx"))
    with pytest.raises(ds.Invalid):
        dvga.selector_for(0xB8000, 4000, moved)


def test_paged_protected_mode_reads_through_the_lowest_gdt_segment_covering_the_page() -> None:
    """dos-djgpp32 at its DPMI client's first stop: GDT 0038 is base 0 and covers the whole
    space, and the page tables map B8000 to itself."""
    assert dvga.selector_for(0xB8000, 4000, machine_tables()) == (0x38, 0xB8000)


def test_the_lowest_covering_selector_is_chosen() -> None:
    """GDT 0030 edited to a flat data segment too: both cover, the lower wins."""
    found = machine_tables(gdt=("0030: b:000D12E0 type: 12 parbg\n      l:0000FFFF",
                                "0030: b:00000000 type: 12 parbg\n      l:FFFFFFFF"))
    assert dvga.selector_for(0xB8000, 4000, found) == (0x30, 0xB8000)


def test_the_offset_is_counted_from_the_chosen_segments_base() -> None:
    """GDT 0030 edited to a data segment based at B0000, and then at B8000 itself: lower than
    0038, it is chosen, and the page lies 8000h into it, then at its first byte."""
    for base, off in (("000B0000", 0x8000), ("000B8000", 0)):
        found = machine_tables(gdt=("0030: b:000D12E0 type: 12 parbg",
                                    f"0030: b:{base} type: 12 parbg"))
        assert dvga.selector_for(0xB8000, 4000, found) == (0x30, off)


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
    sel, off = dvga.selector_for(0xB8000, 4000, machine_tables(gdt=(old, new)))
    assert (sel == 0x38) is gdt_kept and off == 0xB8000
    if not gdt_kept:
        assert sel & 0x4


def test_a_page_mapped_elsewhere_is_not_read_as_the_screen() -> None:
    """The PAGING capture with B8000's page sent to another physical page (an edited capture)."""
    found = machine_tables(paging=("page 000B8xxx -> 00B8xxx", "page 000B8xxx -> 01B8xxx"))
    with pytest.raises(ds.Invalid) as got:
        dvga.selector_for(0xB8000, 4000, found)
    assert got.value.code == "no_channel" and "000B8000" in str(got.value)


def test_every_page_the_screen_spans_is_checked_from_a_start_inside_one() -> None:
    """A screen starting at B80A0 runs into page B9000; that page sent elsewhere (an edited
    capture) is refused, though the first page maps to itself."""
    found = machine_tables(paging=("page 000B9xxx -> 00B9xxx", "page 000B9xxx -> 01B9xxx"))
    assert dvga.selector_for(0xB8000, 4000, found) == (0x38, 0xB8000)
    with pytest.raises(ds.Invalid) as got:
        dvga.selector_for(0xB80A0, 4000, found)
    assert "000B9000" in str(got.value)


def test_paging_on_with_no_page_runs_read_is_refused() -> None:
    tables = machine_tables()
    del tables.found["paging"]
    with pytest.raises(ds.Invalid) as got:
        dvga.selector_for(0xB8000, 4000, tables)
    assert got.value.code == "no_channel" and "`PAGING`" in str(got.value)


def test_no_covering_segment_at_all_is_refused() -> None:
    with pytest.raises(ds.Invalid) as got:
        dvga.selector_for(0xB8000, 4000, dvga.Tables("protected", False,
                                                         {"gdt": [], "ldt": []}))
    assert got.value.code == "no_channel" and "000B8000" in str(got.value)
    assert "could not be read" not in str(got.value)
    with pytest.raises(ds.Invalid) as got:
        dvga.selector_for(0xB8000, 4000, dvga.Tables("protected", False, {}))
    assert "`GDT` could not be read" in str(got.value)


# ------------------------------------------------------------------ what the screen shows


PAGES = {"probe-booted": "probe-booted-page.bin", "probe-mono": "probe-mono-page.bin",
         "screen-text": "screen-text-page.bin",
         "screen-start80": "screen-start80-page.bin",
         "dos-djgpp32-startup": "dos-djgpp32-startup-page.bin",
         "screen-13h": "screen-13h-a000-bin.gz",
         "screen-13h-start80": "screen-13h-start80-a000-bin.gz"}


def page(bench_name: str) -> bytes:
    data = (VGA / PAGES[bench_name]).read_bytes()
    return gzip.decompress(data) if PAGES[bench_name].endswith(".gz") else data


def test_the_text_is_what_the_screen_shows() -> None:
    rows = screen.text_rows(page("probe-booted"), 80, 25)
    assert rows[:5] == ['Z:\\>mount c "."', "Drive C is mounted as local directory ./",
                        "Z:\\>c:", "C:\\>PROBE.COM", ""]
    assert screen.text_rows(page("screen-start80"), 80, 25)[0] == "SECOND ROW"
    dos_djgpp32 = screen.text_rows(page("dos-djgpp32-startup"), 80, 25)
    assert dos_djgpp32[13] == "C:\\>DJGPP32.EXE D:\\MIDI\\TUNE00.MID -a"


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

    MACHINE = {"dos-djgpp32-startup": "dos-djgpp32", "dos-real16": "dos-real16"}

    def __init__(self, name: str, logfile: Path | None) -> None:
        super().__init__(name, logfile)
        self.dumps: list[tuple[int, int, int]] = []
        self.vga_dumps: list[tuple[int, int]] = []

    def listing(self, command: str) -> str:
        if self.launch.logfile is None or command.startswith("VGA "):
            return super().listing(command)
        self.asked.append(command)
        return listing(self.MACHINE.get(self.bench, "probe-booted"), command)

    def vgamemdump(self, offset: int, length: int, dest: Path) -> Path:
        self.vga_dumps.append((offset, length))
        data = window(f"{self.bench}-vgamem-bin.gz")[offset:offset + length]
        assert len(data) == length, (len(data), length)
        dest.write_bytes(data)
        return dest

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
    assert (r["vga_mode"], r["kind"], r["width"], r["height"]) == ("M_TEXT", "text", 80, 25)
    assert r["text"][3] == "C:\\>PROBE.COM" and r["cursor"] == [0, 4]
    assert r["display_start"] == "0h" and "image" not in r
    assert s.asked == ["VGA MODE", "VGA CRTC", "VGA GC", "VGA DRAW", "CPU"]
    assert s.dumps == [(0xB800, 0, 4000)] and r["session"]["altered"] is False
    assert r["crop"] == [0, 0, 80, 25]
    assert r["summary"] == "screen_view M_TEXT: 80x25 at [0, 0] text, cursor at 0,4"


def test_a_text_crop_is_in_characters_and_the_cursor_is_counted_from_it(
        tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.screen_view(crop=[0, 3, 4, 2]))
    assert r["text"] == ["C:\\>", ""] and r["cursor"] == [0, 1] and r["crop"] == [0, 3, 4, 2]
    screen_bench("probe-booted", tmp_path)
    outside = cast(dict[str, Any], server.screen_view(crop=[10, 0, 4, 2]))
    assert outside["cursor"]["available"] is False
    screen_bench("probe-booted", tmp_path)
    off = cast(dict[str, Any], server.screen_view(crop=[78, 0, 4, 1]))
    assert off["code"] == "bad_argument" and "characters" in off["message"]


def test_screen_view_reads_the_page_from_where_the_display_starts(tmp_path: Path) -> None:
    s = screen_bench("screen-start80", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["text"][0] == "SECOND ROW" and r["display_start"] == "50h" and r["cursor"] == [0, 1]
    assert s.dumps == [(0xB80A, 0, 4000)]


def test_screen_view_reads_a_paged_guests_text_through_its_gdt(tmp_path: Path) -> None:
    s = screen_bench("dos-djgpp32-startup", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert r["status"] == "ok", r
    assert r["text"][13] == "C:\\>DJGPP32.EXE D:\\MIDI\\TUNE00.MID -a" and r["cursor"] == [0, 14]
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
    r = cast(dict[str, Any], server.screen_view(scale=1, dest=str(dest)))
    assert r["status"] == "ok", r
    assert (r["kind"], r["width"], r["height"]) == ("pixel", 320, 200)
    w, h, pixels, plte, trns = decode_png(dest.read_bytes())
    ramp = bytes((x + y) & 0xFF for y in range(200) for x in range(320)) + bytes(320)
    assert (w, h, trns) == (320, 200, b"") and pixels == ramp[moved:moved + 64000]
    assert plte == [vgadac.rgb8(e) for e in vgadac.parse_dacpal(vga(bench_name, "VGA DACPAL"))]
    assert r["image"]["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert s.dumps == [dump] and s.asked[-2:] == ["VGA DAC", "VGA DACPAL"]
    assert r["image"]["inline"] is True and r["image"]["scale"] == 1
    assert r["summary"] == ("screen_view M_VGA: 320x200 at [0, 0] pixels; 320x200 PNG x1, "
                            "inline")


def test_a_snapshot_at_a_stop_writes_the_graphics_screen_from_video_memory(
        tmp_path: Path) -> None:
    """The same picture `screen_view` writes at scale 1, with the route that made it."""
    s = screen_bench("screen-13h", tmp_path)
    s.launch.captures_dir = tmp_path / "caps"
    kept = tmp_path / "kept.png"
    r = cast(dict[str, Any], server.snapshot(dest=str(kept)))
    assert r["status"] == "ok" and r["route"] == "video_memory" and r["path"] == str(kept), r
    assert r["bytes"] == kept.stat().st_size
    assert r["sha256"] == hashlib.sha256(kept.read_bytes()).hexdigest()
    w, h, pixels, _, _ = decode_png(kept.read_bytes())
    assert (w, h) == (320, 200) and pixels[:4] == bytes(range(4))
    assert r["session"]["altered"] is False and s.dumps == [(0xA000, 0, 64000)]
    again = cast(dict[str, Any], server.snapshot())
    assert Path(again["path"]) == tmp_path / "caps" / "snapshot-1.png", again
    assert again["sha256"] == r["sha256"]


@pytest.mark.parametrize("tool", ["screen_view", "snapshot"])
def test_a_dest_is_written_under_the_name_the_caller_gave(tmp_path: Path, tool: str) -> None:
    """`dest` is honoured as the caller wrote it: `a_b.png` stays `a_b.png` (the card's case),
    and nothing of the name is rewritten; the reply's `path` is the name asked for."""
    screen_bench("screen-13h", tmp_path)
    out = tmp_path / "out"
    out.mkdir()

    def write(name: str) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(server, tool)(dest=str(out / name)))
    r = write("a_b.png")
    assert r["status"] == "ok", r
    assert (r["path"] if tool == "snapshot" else r["image"]["path"]) == str(out / "a_b.png")
    kept = write("Shot_1.PNG")
    assert kept["status"] == "ok", kept
    assert (kept["path"] if tool == "snapshot" else kept["image"]["path"]) == str(
        out / "Shot_1.PNG")
    bare = write("shot")
    assert bare["status"] == "ok", bare
    assert (bare["path"] if tool == "snapshot" else bare["image"]["path"]) == str(out / "shot")
    again = write("a_b.png")
    assert again["code"] == "bad_argument" and "already exists" in again["message"], again
    assert sorted(p.name for p in out.iterdir()) == ["Shot_1.PNG", "a_b.png", "shot"]


def test_palette_writes_its_dest_under_the_name_the_caller_gave(tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    r = cast(dict[str, Any], server.palette(dest=str(out / "Shot_1.PNG")))
    assert r["status"] == "ok", r
    assert r["image"]["path"] == str(out / "Shot_1.PNG")
    assert [p.name for p in out.iterdir()] == ["Shot_1.PNG"]


def test_a_snapshot_at_a_stop_in_a_text_mode_is_refused_naming_screen_view(
        tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    s.launch.captures_dir = tmp_path / "caps"
    r = cast(dict[str, Any], server.snapshot())
    assert r["status"] == "INVALID" and r["code"] == "no_channel", r
    assert "`screen_view`" in r["message"] and "text mode" in r["message"], r
    assert s.dumps == [] and not (tmp_path / "caps").exists()


def test_the_256_colour_screen_is_attached_enlarged_and_a_crop_is_the_zoom(
        tmp_path: Path) -> None:
    """With no `dest` the picture goes to the session's scratch; the default scale is the
    largest that fits the inline ceiling (320x200 at x4 is 1280x800), and a crop is enlarged
    as far as it fits."""
    screen_bench("screen-13h", tmp_path)
    whole = cast(dict[str, Any], server.screen_view())
    image = whole["image"]
    assert (image["width"], image["height"], image["scale"], image["inline"]) == (
        1280, 800, 4, True)
    assert Path(image["path"]).parent.parent == dstate.STATE.session_dir
    screen_bench("screen-13h", tmp_path)
    part = cast(dict[str, Any], server.screen_view(crop=[8, 8, 16, 8]))
    w, h, pixels, _, _ = decode_png(Path(part["image"]["path"]).read_bytes())
    k = part["image"]["scale"]
    assert (w, h, k) == (16 * 8, 8 * 8, 8), "a small crop enlarged all the way"
    assert pixels[0] == (8 + 8) & 0xFF and pixels[k] == (9 + 8) & 0xFF


def _ramp_pen(x: int, y: int) -> int:
    return (x + y) & 0xFF


def test_a_screen_read_names_its_view_and_the_pens_the_palette_holds(tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    r = cast(dict[str, Any], server.screen_view())
    assert (r["mode"], r["screen_indexed"], r["entries"]) == ("render", True, 256), r
    screen_bench("probe-booted", tmp_path)
    assert cast(dict[str, Any], server.screen_view())["mode"] == "render"


def test_isolate_marks_the_pens_asked_for_and_says_how_many_pixels_and_where(
        tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    dest = tmp_path / "iso.png"
    crop = [10, 20, 100, 50]
    r = cast(dict[str, Any], server.screen_view(mode="isolate", pens=[40, 41], crop=crop, scale=1,
                                                dest=str(dest)))
    assert r["status"] == "ok" and r["mode"] == "isolate" and r["crop"] == crop, r
    hits = [(x, y) for y in range(20, 70) for x in range(10, 110) if _ramp_pen(x, y) in (40, 41)]
    assert r["pixels"] == len(hits) and r["pens"] == [40, 41], r
    assert r["bbox"] == [min(x for x, _ in hits), min(y for _, y in hits),
                         max(x for x, _ in hits), max(y for _, y in hits)], r
    w, h, pixels, plte, _ = decode_png(dest.read_bytes())
    assert (w, h) == (100, 50) and plte[40] == plte[41] == (255, 0, 255), (w, h)
    grey = plte[42]
    assert grey != (255, 0, 255) and grey[0] == grey[1] == grey[2], "the rest is grey"
    assert pixels[0] == _ramp_pen(10, 20) and r["image"]["path"] == str(dest)
    none = cast(dict[str, Any], server.screen_view(mode="isolate", pens=[5], crop=[0, 0, 2, 1]))
    assert none["pixels"] == 0 and none["bbox"]["available"] is False, none


def test_histogram_counts_the_pens_used_and_names_the_unused_runs(tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    r = cast(dict[str, Any], server.screen_view(mode="histogram", crop=[0, 0, 16, 1]))
    assert r["status"] == "ok" and r["mode"] == "histogram" and "image" not in r, r
    assert r["histogram"] == [[p, 1] for p in range(16)] and r["pens_used"] == 16, r
    assert r["unused"] == ["0x10-0xff"] and r["entries"] == 256, r


def test_pixel_names_the_pen_under_a_point_and_its_colour(tmp_path: Path) -> None:
    s = screen_bench("screen-13h", tmp_path)
    dest = tmp_path / "px.png"
    r = cast(dict[str, Any], server.screen_view(mode="pixel", point=[10, 3], scale=1,
                                                dest=str(dest)))
    assert r["status"] == "ok" and r["mode"] == "pixel" and r["pen"] == 13, r
    palette = vgadac.parse_dacpal(vga("screen-13h", "VGA DACPAL"))
    assert r["color"] == "#{:02x}{:02x}{:02x}".format(*vgadac.rgb8(palette[13])), r
    assert (r["x"], r["y"]) == (10, 3) and r["crop"] == [0, 0, 48, 48], r
    assert r["point_in_crop"] == [10, 3] and "set_by" not in r, r
    assert r["image"]["path"] == str(dest) and r["session"]["altered"] is False
    assert s.dumps == [(0xA000, 0, 64000)]
    edge = cast(dict[str, Any], server.screen_view(mode="pixel", point=[319, 199]))
    assert edge["crop"] == [272, 152, 48, 48] and edge["point_in_crop"] == [47, 47], edge
    off = cast(dict[str, Any], server.screen_view(mode="pixel", point=[320, 0]))
    assert off["code"] == "bad_argument" and "320x200" in off["message"], off


@pytest.mark.parametrize("mode", ["isolate", "histogram", "pixel"])
def test_a_view_by_pens_is_refused_by_name_in_text_and_in_direct_colour(
        tmp_path: Path, mode: str) -> None:
    more: dict[str, Any] = {"isolate": {"pens": [1]}, "pixel": {"point": [0, 0]}}.get(mode, {})
    for bench_name, word in (("probe-booted", "M_TEXT"), ("planes-lin15", "M_LIN15")):
        screen_bench(bench_name, tmp_path)
        r = cast(dict[str, Any], server.screen_view(mode=mode, **more))
        assert r["status"] == "INVALID" and r["code"] == "no_channel", r
        assert word in r["message"] and "render" in r["message"], r["message"]


@pytest.mark.parametrize(("call", "said"), [
    ({"mode": "bogus"}, "mode"),
    ({"mode": "isolate"}, "pens"),
    ({"mode": "isolate", "pens": []}, "pens"),
    ({"mode": "isolate", "pens": [256]}, "pens"),
    ({"mode": "isolate", "pens": [1] * 65}, "pens"),
    ({"mode": "render", "pens": [1]}, "pens"),
    ({"mode": "pixel"}, "point"),
    ({"mode": "render", "point": [0, 0]}, "point"),
    ({"mode": "pixel", "point": [0]}, "point"),
    ({"mode": "pixel", "point": [0, 0], "crop": [0, 0, 4, 4]}, "crop"),
    ({"mode": "histogram", "dest": "~/never.png"}, "histogram"),
    ({"mode": "histogram", "scale": 2}, "histogram"),
    ({"mode": "histogram", "attach": False}, "histogram"),
])
def test_the_arguments_of_a_view_are_judged_before_the_machine_is_asked(
        tmp_path: Path, call: dict[str, Any], said: str) -> None:
    s = screen_bench("screen-13h", tmp_path)
    r = cast(dict[str, Any], server.screen_view(**call))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert said in r["message"], r["message"]
    assert s.asked == [] and s.dumps == []


def test_the_256_colour_screen_asked_not_to_attach_is_written_and_says_why(
        tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    r = cast(dict[str, Any], server.screen_view(attach=False))
    assert r["status"] == "ok", r
    image = r["image"]
    assert image["inline"] is False and image["not_inlined"] == "attach=false"
    assert Path(image["path"]).is_file() and r["summary"].endswith("not inlined")


def test_an_attach_that_is_no_yes_or_no_is_refused_before_anything_is_typed(
        tmp_path: Path) -> None:
    s = screen_bench("screen-13h", tmp_path)
    with pytest.raises(ds.Invalid, match="attach is true or false"):
        screen.screen_view(cast(Any, dstate.STATE.session), None, 0, None, tmp_path,
                           cast(Any, "no"))
    assert s.asked == [] and s.dumps == []


def test_screen_view_and_signature_refuse_a_mode_they_do_not_read_after_one_listing(
        tmp_path: Path) -> None:
    s = screen_bench("probe-park", tmp_path)
    for r in (server.screen_view(), server.screen_signature()):
        assert r["status"] == "INVALID" and r["code"] == "no_channel", r
        assert "`M_ERROR`" in r["message"] and "capture_frame" in r["message"]
    assert s.asked == ["VGA MODE", "VGA MODE"] and s.dumps == []


@pytest.mark.parametrize(("bench_name", "word"), [
    ("screen-12h", "M_EGA"), ("dos-real16", "M_LIN15"), ("dos-djgpp32-ui", "M_LIN8")])
def test_a_mode_read_from_video_memory_is_refused_by_a_build_without_vgamemdump(
        tmp_path: Path, bench_name: str, word: str) -> None:
    s = screen_bench(bench_name, tmp_path)
    s.commands = frozenset(s.commands - {dvga.VGAMEMDUMP})
    for r in (server.screen_view(), server.screen_signature()):
        assert r["status"] == "INVALID" and r["code"] == "no_channel", r
        assert f"`{word}`" in r["message"] and "`VGAMEMDUMP`" in r["message"]
        assert "`start`'s reply" in r["message"] and "build_check" not in r["message"]
        assert "capture_frame" in r["message"]
    assert s.dumps == [] and s.vga_dumps == []


def _planes_known() -> Callable[[str, int, int], int | tuple[int, int, int]]:
    """The live tier's copy of the planes guest's arithmetic, loaded by its path."""
    spec = importlib.util.spec_from_file_location(
        "planes_known", Path(__file__).resolve().parent / "live" / "planes_known.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[str, int, int], int | tuple[int, int, int]], module.known)


_KNOWN = _planes_known()


def _known(bench: str, x: int, y: int) -> int | tuple[int, int, int]:
    return _KNOWN(PLANES[bench], x, y)


@pytest.mark.parametrize(("bench_name", "key", "old", "new", "why"), [
    ("planes-modex", "mode", "hline-skip=0", "hline-skip=3", "panning"),
    ("planes-12h", "mode", "pel-pan=0", "pel-pan=1", "panning"),
    ("planes-12h", "draw", "has-split=0", "has-split=1", "a split screen"),
    ("planes-12h", "mode", "scanlen=40", "scanlen=39", "rows of 78"),
    ("planes-12h", "mode", "real-start=0h", "real-start=6a01h", "wraps"),
    ("planes-modex", "mode", "real-start=0h", "real-start=f00dh", "wraps"),
    ("planes-lin32", "mode", "real-start=0h", "real-start=35001h", "wraps"),
    ("planes-12h", "mode", "mode=M_EGA", "mode=M_CGA4", "`M_CGA4`"),
])
def test_a_screen_in_video_memory_this_cannot_place_is_refused_rather_than_misread(
        bench_name: str, key: str, old: str, new: str, why: str) -> None:
    """A capture with one word edited: vertical panning, pixel panning, a split screen, a row
    narrower than the screen, a frame running past the end where the CRTC wraps (one plane
    address, or one byte, past the last that fits), a planar mode no capture measured."""
    with pytest.raises(ds.Invalid) as got:
        shape_of(bench_name, **{key: (old, new)})
    assert got.value.code == "no_channel" and why in str(got.value), str(got.value)


def test_vbe_102h_is_read_as_a_planar_mode() -> None:
    """The planes guest's seventh stop: 800 x 600 in four planes, laid out as 12h's are (the live
    cell of section W compares its pixels with the guest's arithmetic)."""
    assert shape_of("planes-12h", mode=("mode=M_EGA", "mode=M_LIN4")).source == dvga.PLANAR


@pytest.mark.parametrize(("bench_name", "start", "end"), [
    ("planes-12h", "6a00h", 0x10000 * 4), ("planes-lin32", "35000h", 0x200000)])
def test_a_frame_ending_exactly_where_the_crtc_wraps_is_read(
        bench_name: str, start: str, end: int) -> None:
    """The start one unit before the refused one: 12h's 480 rows of 80 plane addresses end at
    the 64 K `pln-mask` spans, the 32-bit frame at the 2 MB of `lin-mask`."""
    got = shape_of(bench_name, mode=("real-start=0h", f"real-start={start}"))
    assert got.linear + got.length == end, got


def test_the_frame_starts_where_the_crtc_latched_it_and_steps_by_the_logical_row() -> None:
    """`real-start` is what the frame is drawn from (`disp-start` waits for the next retrace),
    and a logical row wider than the screen is stepped over whole."""
    got = shape_of("planes-12h", mode=("real-start=0h", "real-start=10h"))
    assert got.linear == 0x10 * 4, got
    got = shape_of("planes-12h", mode=("scanlen=40", "scanlen=50"))
    assert (got.stride, got.length) == (100 * 4, 100 * 4 * 479 + 80 * 4), got


def test_a_mode_listing_with_no_chain_word_is_refused_not_read_as_unchained() -> None:
    with pytest.raises(ds.Invalid) as got:
        shape_of("screen-13h", mode=("chained=1", "nochain=1"))
    assert got.value.code == "unexpected_answer", str(got.value)


def test_a_16_colour_pixel_goes_through_the_colour_plane_enable_first() -> None:
    """The emulator indexes the palette register with the pixel AND `color_plane_enable`."""
    ac = parsed("planes-12h", "VGA AC")
    whole = screen.ac_indices(ac)
    two = screen.ac_indices({**ac, "color_plane_en": "03h"})
    assert [two[n] for n in range(16)] == [whole[n & 3] for n in range(16)], two


def test_an_indexed_picture_takes_its_colours_through_the_pel_mask(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The DAC is looked up at the index AND `pel_mask`: the pixels stay the guest's bytes and
    the PLTE carries the colour each one shows."""
    s = screen_bench("planes-lin8", tmp_path)
    shape = dvga.geometry(dvga.read_listings(cast(ds.Session, s)))
    whole = screen.pixels(cast(ds.Session, s), shape, dvga.read_screen(cast(ds.Session, s), shape))
    info, dac = vgadac.read_dac(cast(ds.Session, s))
    monkeypatch.setattr(vgadac, "read_dac", lambda _s: ({**info, "pel_mask": "0fh"}, dac))
    masked = screen.pixels(cast(ds.Session, s), shape,
                           dvga.read_screen(cast(ds.Session, s), shape))
    assert masked.pixels == whole.pixels and masked.palette is not None
    assert whole.palette is not None
    assert [masked.palette[i] for i in range(256)] == [whole.palette[i & 0x0F] for i in range(256)]


@pytest.mark.parametrize("bench", PLANES)
def test_each_mode_read_from_video_memory_is_the_guests_own_arithmetic(
        tmp_path: Path, bench: str) -> None:
    s = screen_bench(bench, tmp_path)
    shape = dvga.geometry(dvga.read_listings(cast(ds.Session, s)))
    assert (shape.word, shape.width, shape.height) == (
        PLANES[bench], 320 if bench == "planes-modex" else 640,
        200 if bench == "planes-modex" else 480)
    pic = screen.pixels(cast(ds.Session, s), shape, dvga.read_screen(cast(ds.Session, s), shape))
    assert s.vga_dumps == [(shape.linear, shape.length)]
    resolved = screen.ac_indices(parsed(bench, "VGA AC"))
    for y in range(0, shape.height, 17):
        for x in range(0, shape.width, 13):
            want = _known(bench, x, y)
            if pic.palette is None:
                at = (y * shape.width + x) * 3
                assert tuple(pic.pixels[at:at + 3]) == want, (x, y)
            else:
                assert isinstance(want, int)
                got = pic.pixels[y * shape.width + x]
                assert got == (resolved[want] if bench == "planes-12h" else want), (x, y)


@pytest.mark.parametrize("bench", PLANES)
def test_screen_view_and_signature_answer_in_every_mode_read_from_video_memory(
        tmp_path: Path, bench: str) -> None:
    screen_bench(bench, tmp_path)
    view = cast(dict[str, Any], server.screen_view(dest=str(tmp_path / "s.png")))
    assert view["status"] == "ok" and view["vga_mode"] == PLANES[bench], view
    sig = cast(dict[str, Any], server.screen_signature())
    assert sig["status"] == "ok" and sig["kind"] == "pixel" and len(sig["signature"]) == 16


def test_screen_view_refuses_a_dest_or_a_scale_in_text_and_a_dest_already_there(
        tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    for kw in ({"dest": str(tmp_path / "t.png")}, {"scale": 2}, {"attach": False}):
        r = cast(dict[str, Any], server.screen_view(**kw))
        assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
        assert "text mode" in r["message"] and f"`{next(iter(kw))}`" in r["message"]
    assert s.asked == ["VGA MODE"] * 3 and s.dumps == []
    s = screen_bench("screen-13h", tmp_path)
    there = tmp_path / "there.png"
    there.write_bytes(b"mine")
    r = cast(dict[str, Any], server.screen_view(dest=str(there)))
    assert r["code"] == "bad_argument" and there.read_bytes() == b"mine" and s.dumps == []
    assert s.asked == ["VGA MODE"]


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
        assert r["status"] == "ok" and r["kind"] == "text", r
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


def test_the_signature_is_the_same_string_for_the_same_screen(tmp_path: Path) -> None:
    first = ScreenBench("probe-booted", tmp_path / "x.log")
    one = signature_of(first)
    assert first.asked == ["VGA MODE", "VGA CRTC", "VGA GC", "VGA DRAW", "CPU", "VGA DAC",
                           "VGA DACPAL", "VGA AC"]
    two = signature_of(ScreenBench("probe-booted", tmp_path / "x.log"))
    assert one["status"] == "ok" and re.fullmatch(r"[0-9a-f]{16}", one["signature"]), one
    assert one["signature"] == two["signature"]
    assert (one["vga_mode"], one["width"], one["height"], one["kind"],
            one["crop"]) == ("M_TEXT", 80, 25, "text", [0, 0, 80, 25])
    assert one["summary"] == f"screen_signature M_TEXT 80x25 at [0, 0]: {one['signature']}"


def test_a_text_cell_is_its_byte_and_the_colours_its_attribute_resolves_to() -> None:
    """Counted by hand on the booted screen: cell 0 is `Z` (0x5a) in attribute 07, whose
    foreground is the Attribute Controller's register 7 (07), DAC entry 7, `2a2a2a`, widened to
    170; its background register 0, entry 0, black."""
    ac = dvga.parse_listing(vga("probe-booted", "VGA AC"), dvga.TITLES["VGA AC"])
    dac = vgadac.parse_dacpal(vga("probe-booted", "VGA DACPAL"))
    cells = screen.text_cells(page("probe-booted"), ac, dac)
    assert cells[:7] == bytes([0x5A, 170, 170, 170, 0, 0, 0])
    assert len(cells) == 80 * 25 * 7


def test_the_attribute_controller_decides_the_colour_of_a_cell() -> None:
    """A synthetic Attribute Controller: register 1 holds 0x3e; with `mode_control` bit 7 the
    low four bits (0x0e) take `color-select`'s bits 0-1 (01) above them, 0x1e; `color-select`'s
    bits 2-3 (10) put 0x80 on top, 0x9e. With blink (bit 3) the background's fourth bit blinks."""
    dac = [f"{i % 64:02x}0000" for i in range(256)]
    regs = ["00", "3e"] + ["00"] * 14
    plain = {"palette": regs, "mode_control": "00h", "color_select": "00h",
             "color_plane_en": "0fh"}
    assert screen.text_cells(bytes([0x41, 0x01]), plain, dac)[1:4] == bytes(
        vgadac.rgb8(dac[0x3E]))
    selected = {"palette": regs, "mode_control": "80h", "color_select": "09h",
                "color_plane_en": "0fh"}
    assert screen.text_cells(bytes([0x41, 0x01]), selected, dac)[1:4] == bytes(
        vgadac.rgb8(dac[0x9E]))
    blink = {"palette": regs, "mode_control": "08h", "color_select": "00h",
             "color_plane_en": "0fh"}
    assert screen.text_cells(bytes([0x41, 0x90]), blink, dac)[4:7] == bytes(
        vgadac.rgb8(dac[0x3E])), "background 9 blinks: register 1 shows"
    assert screen.text_cells(bytes([0x41, 0x90]), plain, dac)[4:7] == bytes(
        vgadac.rgb8(dac[0x00])), "background 9 without blink: register 9 (00)"


@pytest.mark.parametrize(("byte", "edit"), [
    (0, None), (1, None), (None, ("VGA DACPAL", "2a2a00 2a2a2a", "2a2a00 2a2a2b"))])
def test_a_changed_character_attribute_or_shown_colour_is_a_changed_string(
        tmp_path: Path, byte: int | None, edit: tuple[str, str, str] | None) -> None:
    """The first cell's character (byte 0) and attribute (byte 1), and DAC entry 7, the colour
    every cell of the booted screen is drawn in, each move the signature."""
    plain = signature_of(ScreenBench("probe-booted", tmp_path / "x.log"))["signature"]
    moved = signature_of(Edited("probe-booted", tmp_path / "x.log", byte, edit))["signature"]
    assert moved != plain


def test_a_dac_entry_no_cell_shows_leaves_the_string_as_it_is(tmp_path: Path) -> None:
    """Two screens that look the same have one signature: entry 1 is drawn by no cell of the
    booted screen (every cell is attribute 07)."""
    plain = signature_of(ScreenBench("probe-booted", tmp_path / "x.log"))["signature"]
    edit = ("VGA DACPAL", "000000 00002a", "000000 00002b")
    assert signature_of(Edited("probe-booted", tmp_path / "x.log", None, edit))[
        "signature"] == plain


def test_a_cropped_signature_is_the_crops_and_one_off_the_screen_is_refused(
        tmp_path: Path) -> None:
    install()
    dstate.STATE.session = cast(ds.Session, ScreenBench("probe-booted", tmp_path / "x.log"))
    whole = server.screen_signature()
    part = server.screen_signature(crop=[0, 0, 10, 1])
    assert part["crop"] == [0, 0, 10, 1] and part["signature"] != whole["signature"]
    off = server.screen_signature(crop=[75, 0, 6, 1])
    assert off["code"] == "bad_argument" and "leaves the screen (characters)" in off["message"]


def test_a_cropped_text_signature_is_its_definition_counted_by_hand(tmp_path: Path) -> None:
    """`scry-sig/1` over the crop's own size and its cells row by row, seven bytes a cell
    (the byte, then the foreground and background RGB), built here from the definition: a crop
    of two rows off the corner, so an x/y or a width/height swap hashes other cells."""
    install()
    dstate.STATE.session = cast(ds.Session, ScreenBench("probe-booted", tmp_path / "x.log"))
    ac = dvga.parse_listing(vga("probe-booted", "VGA AC"), dvga.TITLES["VGA AC"])
    dac = vgadac.parse_dacpal(vga("probe-booted", "VGA DACPAL"))
    cells = screen.text_cells(page("probe-booted"), ac, dac)
    x, y, w, h = 2, 1, 3, 2
    rows = b"".join(cells[7 * (80 * r + x):7 * (80 * r + x + w)] for r in range(y, y + h))
    want = hashlib.blake2b(b"scry-sig/1|text|3x2|" + rows, digest_size=8).hexdigest()
    assert server.screen_signature(crop=[x, y, w, h])["signature"] == want


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
    assert plain["status"] == "ok" and plain["kind"] == "pixel"
    moved = signature_of(Edited("screen-13h", tmp_path / "x.log", 64000 - 1))
    assert moved["signature"] != plain["signature"]


def test_perform_runs_the_screen_tools(tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[{"op": "screen_view"},
                                                   {"op": "screen_signature"}]))
    assert r["status"] == "ok" and r["steps_completed"] == 2, r
    s = screen_bench("probe-booted", tmp_path)
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "screen_signature"},
                                                     {"op": "screen_view", "dest": "x.png"}]))
    assert bad["status"] == "INVALID" and [e["step"] for e in bad["errors"]] == [1], bad
    assert s.asked == [] and s.dumps == []


# ------------------------------------------------------------------ screen_wait


VIDEO_START, VIDEO_END = 0xA0000, 0xC0000


class Frames(Machine):
    """A machine stepped retrace by retrace through captured stops: after `k` `VRT`s every
    listing and the screen's bytes are those captured at `stops[k]` (the last one held), the
    `CPU` listing that stop's machine bench's. `vrts` retraces come back; the next never does."""

    MACHINE = {"probe-park": "probe-reset", "dos-djgpp32-startup": "dos-djgpp32"}

    def __init__(self, stops: list[str], vrts: int) -> None:
        super().__init__(regs=dict(REAL_STOP), releases=[Stop(ms=FRAME_MS)] * vrts)
        self.stops = stops
        self.asked: list[str] = []
        self.dumps: list[tuple[int, int, int]] = []

    @property
    def stop(self) -> str:
        return self.stops[min(len(vrts(self)), len(self.stops) - 1)]

    def text(self, command: str) -> str:
        if command.startswith("VGA "):
            return vga(self.stop, command)
        return listing(self.MACHINE.get(self.stop, "probe-booted"), command)

    def _listed(self, word: str, args: list[str]) -> tuple[bool, list[str]]:
        command = " ".join([word, *args])
        self.asked.append(command)
        return True, self.text(command).split("\n")

    def _do_vga(self, args: list[str]) -> tuple[bool, list[str]]:
        return self._listed("VGA", args)

    def _do_cpu(self, args: list[str]) -> tuple[bool, list[str]]:
        return self._listed("CPU", args)

    def _do_gdt(self, args: list[str]) -> tuple[bool, list[str]]:
        return self._listed("GDT", args)

    def _do_ldt(self, args: list[str]) -> tuple[bool, list[str]]:
        return self._listed("LDT", args)

    def _do_paging(self, args: list[str]) -> tuple[bool, list[str]]:
        return self._listed("PAGING", args)

    def page_at(self, seg: int, off: int, length: int) -> bytes:
        return page(self.stop)

    def _do_memdumpbin(self, args: list[str]) -> tuple[bool, list[str]]:
        """Video memory from the stop's captured page, counted in `dumps`; any other dump (the
        stop reply's instruction bytes) zeros."""
        seg, off = (int(x, 16) for x in args[0].split(":"))
        length = int(args[1], 16)
        video = VIDEO_START <= (off if self.regs["CR0"] & 1 else (seg << 4) + off) < VIDEO_END
        if video:
            self.dumps.append((seg, off, length))
        assert self.cwd is not None
        (self.cwd / args[2]).write_bytes(self.page_at(seg, off, length) if video
                                         else bytes(length))
        return True, ["DEBUG: Memory dump binary success."]


def waiting(stops: list[str], vrts: int, tmp_path: Path,
            kind: type[Frames] = Frames) -> Frames:
    machine = kind(stops, vrts)
    install()
    cwd = tmp_path / "cwd"
    cwd.mkdir(exist_ok=True)
    s = session_over(machine, cwd, logfile=tmp_path / "x.log")
    dstate.STATE.session = s
    dstate.STATE.remember_stop(s, {"cs": "F000", "eip": "0000FFF0", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return machine


def vrts(machine: Machine) -> list[str]:
    return [c for c in machine.sent if c == f"EXEC {ds.RETRACE_COMMAND}"]


def cut_surveys(machine: Machine, cut: int = 1) -> None:
    """The first `cut` surveys answer an `EV` with no values: a stop that cannot be placed."""
    left = [cut]

    def ev(command: str) -> tuple[bool, list[str]] | None:
        if left[0] <= 0:
            return None
        left[0] -= 1
        return True, [f"EV of '{command.removeprefix('EV ')}' is:", ""]
    machine.hooks["EV"] = ev


def test_a_string_that_appears_after_a_retrace_is_found_with_the_stop_reply(
        tmp_path: Path) -> None:
    """From the probe's park (no mode set: examined as no match) one retrace lands in the
    booted probe, whose screen holds the launch line."""
    machine = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok", r
    assert r["already"] is False and r["polls"] == 1 and r["point"] == [4, 3], r
    assert r["line"] == "C:\\>PROBE.COM" and isinstance(r["waited_s"], float)
    assert r["regs"] and "cause" in r and "stop_seq" in r
    assert len(vrts(machine)) == 1 and machine.dumps == [(0xB800, 0, 4000)]
    assert machine.asked.count("VGA MODE") == 2 and machine.asked.count("VGA CRTC") == 1
    assert r["summary"] == "screen_wait 'PROBE.COM': found at 4,3 after 1 retrace"


def test_a_string_already_on_screen_is_answered_without_moving_the_machine(
        tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 0, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="mounted as local", seconds=10))
    assert r["status"] == "ok" and r["already"] is True and r["polls"] == 0, r
    assert r["waited_s"] == 0.0 and r["point"] == [11, 1] and vrts(machine) == []
    assert r["line"] == "Drive C is mounted as local directory ./"


def test_each_frame_reads_where_the_page_lies_and_the_cursor_listing_once(
        tmp_path: Path) -> None:
    """Three retraces on the booted probe's still page, the fourth `VRT` never answered and so
    interrupted at the bound: each frame costs `VGA MODE`, `VGA DRAW`, `VGA GC`, `CPU` and a
    dump; `VGA CRTC` comes once."""
    machine = waiting(["probe-booted"], 3, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["status"] == "ok" and r["verdict"] == "TIMEOUT", r
    assert r["polls"] == 3 and "BREAK" in machine.sent and len(machine.dumps) == 4, r
    assert machine.asked.count("VGA CRTC") == 1
    for each in ("VGA MODE", "VGA DRAW", "VGA GC", "CPU"):
        assert machine.asked.count(each) == len(machine.dumps), each


class ByAddress(Frames):
    """`Frames` whose video memory answers by the address dumped rather than by the stop: B8000
    holds the booted probe's colour page throughout, B0000 the monochrome page `probe-mono`
    captured."""

    AT = {0xB8000: "probe-booted", 0xB0000: "probe-mono"}

    def page_at(self, seg: int, off: int, length: int) -> bytes:
        return page(self.AT[(seg << 4) + off])


def test_a_switch_to_the_monochrome_page_under_the_same_draw_state_is_followed(
        tmp_path: Path) -> None:
    """One retrace from the booted probe lands in mode 7 (`probe-mono`): the mode word and the
    draw state are the colour mode's, and GC `misc` alone moves the page to B0000, where `QZQ`
    is."""
    machine = waiting(["probe-booted", "probe-mono"], 1, tmp_path, ByAddress)
    r = cast(dict[str, Any], server.screen_wait(text="QZQ", seconds=2))
    assert r["status"] == "ok" and r["point"] == [0, 0] and r["line"] == "QZQ", r
    assert machine.dumps == [(0xB800, 0, 4000), (0xB000, 0, 4000)]


class EditedAfterRetrace(Frames):
    """`Frames` whose listings, once a retrace has run, carry the edits `EDITS` names: per
    command, a word and what replaces it, each asserted present so an edit cannot miss."""

    EDITS: dict[str, tuple[str, str]] = {}

    def text(self, command: str) -> str:
        text = super().text(command)
        if command in self.EDITS and vrts(self):
            old, new = self.EDITS[command]
            assert old in text, (command, old)
            text = text.replace(old, new, 1)
        return text


class Resized(EditedAfterRetrace):
    """The booted probe whose second stop renders 80 x 50 in the same `M_TEXT` (DRAW edited to
    an eight-line row), its page the captured one with a second, blank half."""

    EDITS = {"VGA DRAW": ("addrline-total=16", "addrline-total=8")}

    def page_at(self, seg: int, off: int, length: int) -> bytes:
        return super().page_at(seg, off, length).ljust(length, b"\x00")


def test_a_screen_resized_under_the_same_mode_word_is_placed_again(tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 1, tmp_path, Resized)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["verdict"] == "TIMEOUT", r
    assert machine.asked.count("VGA CRTC") == 1
    assert [d[2] for d in machine.dumps][:2] == [4000, 8000]
    assert len(r["text"]) == 50


def test_protected_mode_frames_read_the_tables_once(tmp_path: Path) -> None:
    machine = waiting(["dos-djgpp32-startup"], 2, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["verdict"] == "TIMEOUT", r
    assert machine.asked.count("GDT") == 1 and len(machine.dumps) >= 2
    assert set(machine.dumps) == {(0x38, 0xB8000, 4000)}


class Costly(Frames):
    """`Frames` whose every listing costs `cost` seconds of the clock a case runs ahead."""

    cost = 0.0
    ahead: list[float]

    def text(self, command: str) -> str:
        self.ahead[0] += self.cost
        return super().text(command)


@pytest.fixture
def ahead(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """`retrace`'s clock run ahead of the real one by what a case adds: the bound is read
    off it, while the session's own wait for a stop keeps the real clock, so a `VRT` the double
    answers is heard."""
    by = [0.0]
    real = time.monotonic
    monkeypatch.setattr(retrace, "time", SimpleNamespace(monotonic=lambda: real() + by[0]))
    return by


def costly(stops: list[str], vrts: int, tmp_path: Path, ahead: list[float],
           cost: float) -> Costly:
    machine = cast(Costly, waiting(stops, vrts, tmp_path, Costly))
    machine.ahead, machine.cost = ahead, cost
    return machine


def test_an_expiry_before_any_retrace_sends_nothing_and_leaves_the_stop(tmp_path: Path) -> None:
    """A bound spent before the first `VRT` goes out: nothing moved, so the stop is not recorded
    again, and a retrace an earlier cut run left armed is still armed, and said so."""
    machine = waiting(["probe-booted"], 3, tmp_path)
    dstate.STATE.retrace_pending = True
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1e-9))
    assert r["verdict"] == "TIMEOUT" and r["polls"] == 0 and vrts(machine) == [], r
    assert "BREAK" not in machine.sent and r["retrace_pending"] is True and "stop_seq" not in r
    assert dstate.STATE.retrace_pending is True and dstate.STATE.last_stop["seq"] == before
    assert r["text"][3] == "C:\\>PROBE.COM"


def test_a_short_bound_still_reaches_the_first_frame_and_records_the_stop_it_expires_at(
        tmp_path: Path, ahead: list[float]) -> None:
    """Each listing costs a second against a half-second bound. The bound starts after the
    first read, as `run_for`'s after its first survey, so one `VRT` goes out; the read of its
    frame is finished past the bound, and the wait expires stopped at that retrace, which is
    recorded. The description says when the bound starts."""
    machine = costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["verdict"] == "TIMEOUT" and r["polls"] == 1 and "BREAK" not in machine.sent, r
    assert r["retrace_pending"] is False and len(vrts(machine)) == 1
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"] == before + 1
    assert "counted from after the first read so that a short one still reaches the first " \
        "frame" in documented("screen_wait")


def test_screen_wait_on_a_build_without_runstate_is_refused_naming_itself_before_a_read(
        tmp_path: Path) -> None:
    machine = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    machine.commands = ()
    cast(ds.Session, dstate.STATE.session).commands = frozenset()
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "no_channel", r
    assert "screen_wait" in r["message"] and "RUNSTATE" in r["message"], r["message"]
    assert machine.asked == [] and vrts(machine) == []


def test_screen_wait_on_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 1, tmp_path)
    machine.stopped = False
    cast(ds.Session, dstate.STATE.session).forget_stop()
    r = cast(dict[str, Any], server.screen_wait(text="PROBE", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "not_stopped", r
    assert machine.asked == [] and vrts(machine) == []


def test_an_expired_wait_says_what_it_examined(tmp_path: Path) -> None:
    machine = waiting(["probe-park", "probe-park", "probe-booted"], 3, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1.0))
    assert r["status"] == "ok" and r["verdict"] == "TIMEOUT", r
    # THE SAME FIELDS AS A FOUND WAIT, which is what the page promises: the predicate was not
    # the one in front when the wait began, so nothing was answered before a frame ran.
    assert r["already"] is False, r
    # A `VRT` still out at the bound is sent and unanswered: interrupted, one past polls.
    out = "BREAK" in machine.sent
    assert len(vrts(machine)) == r["polls"] + int(out) and r["polls"] >= 2
    assert r["retrace_pending"] is out
    assert "were not in a text mode" in r["note"]
    assert r["text"][3] == "C:\\>PROBE.COM"


def cut_by_breakpoint(tmp_path: Path) -> Frames:
    """The booted probe whose first `VRT` is cut by a declared breakpoint at 0814:0108."""
    machine = waiting(["probe-booted"], 2, tmp_path)
    machine.releases = [Stop({"EIP": 0x108}, ms=3.0), Stop(ms=FRAME_MS)]
    _real_bp("0814:0108")
    machine.breakpoints.insert(0, "BP 0814:0108")
    return machine


def test_a_breakpoint_that_cuts_a_frame_ends_the_wait_naming_it(tmp_path: Path) -> None:
    cut_by_breakpoint(tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "wait_stopped", r
    assert "breakpoint 0814:0108 " in r["cause"] and r["retrace_pending"] is True
    assert r["polls"] == 1 and dstate.STATE.retrace_pending is True
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"]


def at_breakpoint(tmp_path: Path, stops: list[str], releases: list[Stop | None],
                  refs: tuple[str, ...] = ("0814:0108",)) -> Frames:
    """`stops` per `VRT` sent, `releases` in order; each of `refs` a declared breakpoint."""
    machine = waiting(stops, len(releases), tmp_path)
    machine.releases = releases
    for ref in refs:
        _real_bp(ref)
        machine.breakpoints.insert(0, f"BP {ref}")
    return machine


BP_STOP = {"EIP": 0x108}
#: The double keeps the registers a stop set, so a retrace stop names its own place.
FRAME_STOP = {"EIP": 0x10C}


def test_a_wait_on_a_breakpoint_judges_the_retrace_after_its_firing(tmp_path: Path) -> None:
    machine = at_breakpoint(tmp_path, ["probe-park", "probe-park", "probe-booted"],
                            [Stop(BP_STOP, ms=3.0), Stop(FRAME_STOP, ms=FRAME_MS)])
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_breakpoint="0814:0108",
                                                seconds=5))
    assert r["status"] == "ok" and r["verdict"] == "TARGET", r
    assert r["waited_on"] == {"kind": "breakpoint", "ref": "0814:0108"}
    assert r["firings"] == 1 and r["frames_examined"] == 1 and r["fired_line"]["available"] is False
    assert "polls" not in r and "sampled_every" not in r and r["already"] is False
    assert len(vrts(machine)) == 2 and r["stop_seq"] == dstate.STATE.last_stop["seq"]
    assert r["summary"] == ("screen_wait 'PROBE.COM': found at 4,3 after 1 firing of "
                            "breakpoint '0814:0108'")


def test_a_retrace_before_any_firing_is_not_judged_even_with_the_screen_there(
        tmp_path: Path) -> None:
    machine = at_breakpoint(tmp_path, ["probe-booted"] * 4,
                            [Stop(FRAME_STOP, ms=FRAME_MS), Stop(BP_STOP, ms=3.0),
                             Stop(FRAME_STOP, ms=FRAME_MS)])
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_breakpoint="0814:0108",
                                                seconds=5))
    assert r["status"] == "ok" and r["firings"] == 1 and r["frames_examined"] == 1, r
    assert len(vrts(machine)) == 3


def test_a_firing_whose_condition_fails_arms_no_judgement(tmp_path: Path) -> None:
    at_breakpoint(tmp_path, ["probe-booted"] * 5,
                  [Stop(BP_STOP, ms=3.0), Stop(FRAME_STOP, ms=FRAME_MS)] * 2)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_breakpoint="0814:0108",
                                                condition="AX==FFFF", seconds=0.5))
    assert r["status"] == "ok" and r["verdict"] == "TIMEOUT", r
    assert r["firings"] == 2 and r["frames_examined"] == 0
    assert r["waited_on"]["condition"] == "AX==FFFF"
    assert "met the condition, so no screen was judged" in r["note"], r["note"]


def test_a_breakpoint_that_never_fires_is_refused_not_a_timeout(tmp_path: Path) -> None:
    at_breakpoint(tmp_path, ["probe-booted"] * 3, [Stop(FRAME_STOP, ms=FRAME_MS)] * 2)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_breakpoint="0814:0108",
                                                seconds=0.5))
    assert r["status"] == "INVALID" and r["code"] == "never_fired", r
    assert r["firings"] == 0 and "0814:0108" in r["message"]


def test_another_declared_breakpoint_ends_the_wait_naming_it(tmp_path: Path) -> None:
    at_breakpoint(tmp_path, ["probe-booted"] * 2, [Stop(BP_STOP, ms=3.0)],
                  refs=("0814:0108", "0814:0200"))
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_breakpoint="0814:0200",
                                                seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "wait_stopped", r
    assert "0814:0108" in r["cause"] and r["firings"] == 0
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"]


def test_a_declared_breakpoint_ends_a_wait_on_a_watch_and_is_not_taken_for_a_retrace(
        tmp_path: Path) -> None:
    machine = at_breakpoint(tmp_path, ["probe-booted"] * 2, [Stop(BP_STOP, ms=3.0)])
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("watch", "address", "0040:006C", cpu=grammar.REAL_MODE,
                                          watch_mode="change", width=1, fmt="u8"))
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", on_watch="0040:006C",
                                                seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "wait_stopped", r
    assert "0814:0108" in r["cause"] and len(vrts(machine)) == 1


@pytest.mark.parametrize(("kw", "code"), [
    ({"text": "C:", "on_breakpoint": "0814:0999"}, "unknown_ref"),
    ({"text": "C:", "on_watch": "0814:0108"}, "unknown_ref"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "every": 7}, "bad_argument"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "on_watch": "x"}, "bad_argument"),
    ({"text": "C:", "condition": "AX==1"}, "bad_argument"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "condition": "AX=1"}, "bad_argument"),
    ({"text": "C:", "changed": True}, "bad_argument"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "condition": "FLAGS==2"}, "bad_argument"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "condition": "D0==1"}, "bad_argument"),
    ({"text": "C:", "on_breakpoint": "0814:0108", "condition": "AL==100"}, "bad_argument"),
])
def test_a_wait_at_a_stop_refuses_what_cannot_be_waited_on_before_a_retrace(
        tmp_path: Path, kw: dict[str, Any], code: str) -> None:
    machine = at_breakpoint(tmp_path, ["probe-booted"], [Stop(ms=FRAME_MS)])
    r = cast(dict[str, Any], server.screen_wait(seconds=5, **kw))
    assert r["status"] == "INVALID" and r["code"] == code, r
    assert vrts(machine) == []


@pytest.mark.parametrize("kw", [
    {"text": ""}, {"text": "x" * 133}, {"text": "a\nb"}, {"text": 3}, {"text": "Name: "},
    {"text": "   "}, {"text": "€uro"},
    {"text": "C:", "seconds": 0}, {"text": "C:", "seconds": 601}])
def test_screen_wait_refuses_an_argument_before_anything_is_sent(
        tmp_path: Path, kw: dict[str, Any]) -> None:
    machine = waiting(["probe-booted"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(**kw))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert machine.asked == [] and vrts(machine) == []


def test_a_cpu_mode_change_under_the_same_text_screen_reads_the_tables_again(
        tmp_path: Path) -> None:
    """From the booted probe (real mode) one retrace lands at dos-djgpp32's DPMI client (paged, the
    shell's text page unchanged in mode): the page is then read through GDT 0038, not through
    the paragraph the real-mode frame used."""
    machine = waiting(["probe-booted", "dos-djgpp32-startup"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="DJGPP32.EXE", seconds=10))
    assert r["status"] == "ok" and r["point"] == [4, 13], r
    assert machine.dumps == [(0xB800, 0, 4000), (0x38, 0xB8000, 4000)]
    assert machine.asked.count("VGA CRTC") == 1 and "GDT" in machine.asked


def test_perform_runs_screen_wait_and_checks_it_first(tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 0, tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "screen_wait", "text": "PROBE.COM", "seconds": 5}, {"op": "screen_signature"}]))
    assert r["status"] == "ok" and r["steps_completed"] == 2, r
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "screen_signature"},
                                                     {"op": "screen_wait", "text": ""}]))
    assert bad["status"] == "INVALID" and [e["step"] for e in bad["errors"]] == [1], bad
    assert vrts(machine) == []


def test_a_found_wait_says_a_watch_or_interrupt_stop_could_pass_for_a_retrace(
        tmp_path: Path) -> None:
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("interrupt", "address", "BPINT 21 AH=4C"))
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["note"] == retrace.UNTOLD_NOTE, r


def test_a_survey_that_cannot_place_a_retrace_stop_is_not_taken_for_a_breakpoint(
        tmp_path: Path) -> None:
    """With a code breakpoint declared every frame is surveyed; a survey that cannot place the
    stop is no cut, so the wait reads the screen and goes on."""
    machine = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    cut_surveys(machine)
    _real_bp("0814:0108")
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["polls"] == 1 and r["point"] == [4, 3], r


def test_a_find_whose_stop_survey_fails_keeps_the_find(tmp_path: Path) -> None:
    """The text is found at the first retrace, and the stop reply's survey cannot place the
    stop: the find stands with its enrichment marked unavailable, as `run_for` keeps its
    account."""
    machine = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    cut_surveys(machine)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and r["point"] == [4, 3] and r["line"] == "C:\\>PROBE.COM", r
    assert r["enrichment"]["available"] is False and "regs" not in r


class PannedAfterRetrace(EditedAfterRetrace):
    """The booted probe whose screen pans by a pixel after the first retrace (`pel-pan=1`, an
    edited capture): a layout the reader refuses."""

    EDITS = {"VGA MODE": ("pel-pan=0", "pel-pan=1")}


def test_a_frame_refused_after_a_retrace_records_the_stop_the_wait_ends_at(
        tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 2, tmp_path, PannedAfterRetrace)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["status"] == "INVALID" and r["code"] == "no_channel" and "panning" in r["message"]
    assert r["polls"] == 1 and len(vrts(machine)) == 1, r
    assert r["stop_seq"] == dstate.STATE.last_stop["seq"] == before + 1


ON_ITS_OWN: dict[str, Any] = {"stop_seq": 1, "at": "F000:FFF0", "attribution": {}}
APPLIED: dict[str, Any] = {"armed": ["0814:0108"]}
ACCOUNTS = {"stopped_on_its_own": ON_ITS_OWN, "applied_on_stop": APPLIED}


@pytest.mark.parametrize("end", ["TIMEOUT", "wait_stopped", "no_channel"])
def test_a_wait_ended_at_a_stop_carries_what_that_stops_reply_delivered(
        tmp_path: Path, ahead: list[float], end: str) -> None:
    """The stop reply that records where a wait ended is also the first reply built since the
    contact that found a stop the guest reached on its own, or applied declarations on one:
    the reply carries those accounts, rather than spending them on a reply nobody sees. Ended
    by the bound, by a breakpoint, and by a frame the reader refuses."""
    if end == "TIMEOUT":
        costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    elif end == "wait_stopped":
        cut_by_breakpoint(tmp_path)
    else:
        waiting(["probe-booted"], 2, tmp_path, PannedAfterRetrace)
    dstate.STATE.found_stop_last = dict(ON_ITS_OWN)
    dstate.STATE.applied_last.update(APPLIED)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r.get("code", r.get("verdict")) == end and r["polls"] == 1 and "stop_seq" in r, r
    assert {k: r.get(k) for k in ACCOUNTS} == ACCOUNTS


def test_an_expired_wait_counts_the_frames_that_were_not_text(tmp_path: Path) -> None:
    """The park, the park again after one retrace, the booted text page after the second, and a
    third `VRT` never answered, interrupted: two of the three frames examined were not text."""
    machine = waiting(["probe-park", "probe-park", "probe-booted"], 2, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=1.0))
    assert r["verdict"] == "TIMEOUT" and r["polls"] == 2 and "BREAK" in machine.sent, r
    assert "; 2 of 3 frames examined were not in a text mode" in r["note"]


class V86AfterRetrace(EditedAfterRetrace):
    """dos-djgpp32's DPMI client's stop, whose `CPU` says after the first retrace that the cpu
    runs a virtual-8086 task (`vm=1`, an edited capture): still paged, so the cpu mode is
    unchanged."""

    EDITS = {"CPU": ("[vm=0 ", "[vm=1 ")}


def test_a_virtual_8086_task_entered_under_the_same_cpu_mode_reads_through_the_paragraph(
        tmp_path: Path) -> None:
    machine = waiting(["dos-djgpp32-startup"], 1, tmp_path, V86AfterRetrace)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["verdict"] == "TIMEOUT", r
    assert machine.dumps == [(0x38, 0xB8000, 4000), (0xB800, 0, 4000)]


#: What a reply can carry whatever the tool, described once for all rather than in each tool.
ENVELOPE = {"summary", "status", "code", "message", "session", "stopped_on_its_own",
            "applied_on_stop"}


def test_the_screen_wait_description_names_every_key_its_replies_carry(
        tmp_path: Path, ahead: list[float]) -> None:
    """Found with its stop reply, found with that reply's survey failing, stopped by a
    breakpoint, and expired at a retrace of its own: each key beside the envelope's is named in
    the description or on its family page, in backticks."""
    replies: list[dict[str, Any]] = []
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    replies.append(cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10)))
    cut_surveys(waiting(["probe-park", "probe-booted"], 1, tmp_path))
    replies.append(cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10)))
    cut_by_breakpoint(tmp_path)
    replies.append(cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5)))
    costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    replies.append(cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5)))
    assert [r.get("code", r.get("verdict")) for r in replies] == [
        "TARGET", "TARGET", "wait_stopped", "TIMEOUT"], replies
    text = documented("screen_wait")
    unnamed = [(r.get("code", r.get("verdict")), k) for r in replies
               for k in r if k not in ENVELOPE and f"`{k}`" not in text]
    assert not unnamed, unnamed


class ConsoleFailsAfterRetrace(Frames):
    """The booted probe whose debugger, after the first retrace, answers `VGA DRAW` with nothing
    the reader can take: a refusal about the debugger, not about the screen."""

    def _do_vga(self, args: list[str]) -> tuple[bool, list[str]]:
        if args == ["DRAW"] and vrts(self):
            self.asked.append("VGA DRAW")
            return True, []
        return super()._do_vga(args)


def test_a_refusal_about_the_debugger_mid_wait_is_passed_on_and_nothing_more_is_sent(
        tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 2, tmp_path, ConsoleFailsAfterRetrace)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["code"] == "unexpected_answer" and "stop_seq" not in r and "polls" not in r, r
    assert dstate.STATE.last_stop["seq"] == before and machine.asked[-1] == "VGA DRAW"


def test_a_refused_wait_whose_stop_survey_fails_says_so_and_records_nothing(
        tmp_path: Path, ahead: list[float]) -> None:
    """Ended by the bound at a retrace of its own, the stop reply's survey failing: no stop is
    recorded, so no `stop_seq`; `enrichment` says why."""
    machine = costly(["probe-booted"], 3, tmp_path, ahead, 1.0)
    cut_surveys(machine)
    before = dstate.STATE.last_stop["seq"]
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=0.5))
    assert r["verdict"] == "TIMEOUT" and r["polls"] == 1 and "stop_seq" not in r, r
    assert r["enrichment"]["available"] is False and dstate.STATE.last_stop["seq"] == before


def test_the_picture_reaches_the_client_attached_beside_the_json(tmp_path: Path) -> None:
    """Through the MCP layer: the 256-colour screen comes back as the JSON and, after it, the
    PNG itself, the file the body names, hashed again."""
    import base64

    from mcp.types import CallToolResult, ImageContent
    screen_bench("screen-13h", tmp_path)
    res = asyncio.run(server.mcp.call_tool("screen_view", {}))
    assert isinstance(res, CallToolResult) and isinstance(res.structured_content, dict)
    shown = res.content[-1]
    assert isinstance(shown, ImageContent) and shown.mime_type == "image/png"
    image = res.structured_content["image"]
    assert hashlib.sha256(base64.b64decode(shown.data)).hexdigest() == image["sha256"]
    screen_bench("probe-booted", tmp_path)
    text = asyncio.run(server.mcp.call_tool("screen_view", {}))
    assert all(not isinstance(c, ImageContent) for c in text.content), "text has no picture"


def test_the_sessions_scratch_goes_with_the_session(tmp_path: Path) -> None:
    screen_bench("screen-13h", tmp_path)
    image = Path(cast(dict[str, Any], server.screen_view())["image"]["path"])
    scratch = dstate.STATE.session_dir
    assert scratch is not None and image.is_file() and image.is_relative_to(scratch)
    dstate.STATE.clear_running_state()
    assert not scratch.exists() and dstate.STATE.session_dir is None


def test_a_dest_whose_write_fails_part_way_leaves_nothing(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """The picture is written to a file created new and taken away again when the write fails
    part-way (a full disk), so no half picture is left where the caller will look."""
    screen_bench("screen-13h", tmp_path)
    real_open: Any = Path.open
    dest = tmp_path / "half.png"

    class Full:
        def __init__(self, f: Any) -> None:
            self.f = f

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *exc: object) -> None:
            self.f.close()

        def write(self, data: bytes) -> int:
            raise OSError(28, "No space left on device")

    def full_open(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        f = real_open(self, mode, *a, **k)
        return Full(f) if self == dest else f
    monkeypatch.setattr(Path, "open", full_open)
    r = cast(dict[str, Any], server.screen_view(dest=str(dest)))
    assert r["code"] == "host_failed" and "No space left" in r["message"], r
    assert not dest.exists()


def test_a_dac_entry_a_pixel_shows_moves_the_256_colour_signature(tmp_path: Path) -> None:
    """The 13h ramp draws every entry, so a fade of entry 0x40 alone is a new signature."""
    plain = signature_of(ScreenBench("screen-13h", tmp_path / "x.log"))["signature"]
    row = vga("screen-13h", "VGA DACPAL").splitlines()
    line = next(x for x in row if x.startswith("40:"))
    first = line.split()[1]
    other = f"{(int(first[:2], 16) ^ 1):02x}{first[2:]}"
    edit = ("VGA DACPAL", line, line.replace(first, other, 1))
    moved = signature_of(Edited("screen-13h", tmp_path / "x.log", None, edit))["signature"]
    assert moved != plain


def test_a_description_placeholder_nothing_fills_fails_at_registration() -> None:
    with pytest.raises(TypeError, match=r"names \['\{NOPE\}'\], which nothing fills"):
        docs.filled("t", "a {PICTURE} and a {NOPE}")
    assert "{" not in "".join(t.description or "" for t in server.mcp._tool_manager.list_tools()
                              if t.name in ("palette", "screen_view", "series_capture"))


def test_an_attribute_controller_listing_of_another_shape_is_an_unexpected_answer() -> None:
    with pytest.raises(ds.Invalid, match="`VGA AC` lacks a word") as e:
        screen.text_cells(bytes([0x41, 0x07]), {"palette": ["00"] * 16}, ["000000"] * 256)
    assert e.value.code == "unexpected_answer"


def lands_at_the_bound(machine: Frames) -> Frames:
    """The race the bound can lose: the wait gives up with the `VRT` out, and its stop lands
    before the interrupt looks, so nothing is interrupted and the retrace is spent."""
    session = cast(ds.Session, dstate.STATE.session)
    real = session.retrace

    def gave_up(began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        real(began, deadline, progress)
        return True, 0.0
    session.retrace = gave_up  # type: ignore[method-assign]
    return machine


def test_a_retrace_that_lands_as_the_wait_expires_is_spent_not_pending(tmp_path: Path) -> None:
    machine = lands_at_the_bound(waiting(["probe-park", "probe-park"], 1, tmp_path))
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["verdict"] == "TIMEOUT" and "BREAK" not in machine.sent, (r, machine.sent)
    assert r["retrace_pending"] is False and dstate.STATE.retrace_pending is False, r
    assert "stop_seq" in r, "the retrace's stop landed: it is surveyed"


def test_a_breakpoint_that_lands_as_the_wait_expires_ends_it_naming_it(tmp_path: Path) -> None:
    """The bound's race lost to a declared breakpoint: the `VRT` is still armed, and the wait
    ends as a cut inside it does."""
    machine = lands_at_the_bound(cut_by_breakpoint(tmp_path))
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", seconds=5))
    assert r["code"] == "wait_stopped" and r["retrace_pending"] is True, r
    assert "breakpoint 0814:0108 " in r["cause"] and "BREAK" not in machine.sent, r


def test_a_wait_ended_at_a_stop_whose_survey_was_cut_keeps_the_placement_it_made(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop reply that fell back to its base still says the symbols it placed, once: the
    refusal that ends the wait carries it with the enrichment mark."""
    placed = {"placed": 3}
    cut = {"stop_seq": 7, "enrichment": {"available": False, "why": "cut"},
           "symbols_placed": placed}
    monkeypatch.setattr(retrace, "_stop_reply", lambda session, base: dict(cut))
    ended = retrace._ended_at(cast(ds.Session, None))
    assert ended["symbols_placed"] == placed and ended["stop_seq"] == 7, ended


def test_a_wait_refused_at_a_retrace_carries_the_stop_it_ended_at_with_its_cause(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A screen that can no longer be read after a retrace ends the wait at that stop: the
    refusal carries the stop's `stop_seq` AND its `cause`, the pair a sequence counts a stop
    by, so its account never files a stop under no cause."""
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    reads = iter([None])

    def rows(self: object) -> list[str] | None:
        try:
            return next(reads)
        except StopIteration:
            raise ds.Invalid("no_channel", "the screen's listing is gone") from None

    monkeypatch.setattr(retrace.TextWatch, "rows", rows)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "INVALID" and r["code"] == "no_channel", r
    assert "stop_seq" in r and isinstance(r.get("cause"), str), r


def test_a_wait_names_exactly_one_predicate(tmp_path: Path) -> None:
    """`text`, `screen` and `palette` are one wait's three predicates: none or several is
    refused before the machine moves, so the caller learns what it asked for."""
    machine = waiting(["probe-booted"], 0, tmp_path)
    for kw in ({}, {"text": "X", "screen": "prompt"}, {"text": "X", "palette": "black"},
               {"screen": "prompt", "palette": "black"}):
        r = cast(dict[str, Any], server.screen_wait(**kw))
        assert r["status"] == "INVALID" and r["code"] == "bad_argument", (kw, r)
        assert "exactly one of" in r["message"], r["message"]
    assert vrts(machine) == []


def test_a_wait_on_a_mapped_screen_answers_at_once_when_it_is_the_one_in_front(
        tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 0, tmp_path)
    dstate.STATE.maps = screen_map.Maps()
    added = cast(dict[str, Any], server.screen_map_write("add", screen="prompt",
                                                         match=[[0, 3, 4, 1]]))
    assert added["status"] == "ok", added
    got = cast(dict[str, Any], server.screen_wait(screen="prompt", seconds=5))
    assert got["status"] == "ok" and got["verdict"] == "TARGET" and got["already"] is True, got
    assert got["predicate"] == "screen" and got["screen"]["name"] == "prompt", got
    assert vrts(machine) == [], "already there: the machine is not moved"


def test_a_wait_on_a_mapped_screen_runs_the_frames_until_the_map_names_it(
        tmp_path: Path) -> None:
    waiting(["probe-booted"], 0, tmp_path)
    dstate.STATE.maps = screen_map.Maps()
    added = cast(dict[str, Any], server.screen_map_write("add", screen="prompt",
                                                         match=[[0, 3, 4, 1]]))
    assert added["status"] == "ok", added
    machine = waiting(["probe-park", "probe-booted"], 1, tmp_path)
    got = cast(dict[str, Any], server.screen_wait(screen="prompt", seconds=10))
    assert got["status"] == "ok" and got["verdict"] == "TARGET", got
    assert got["already"] is False and got["polls"] == 1 and got["screen"]["name"] == "prompt", got
    assert len(vrts(machine)) == 1


def test_a_wait_on_a_palette_reads_the_dac_at_every_poll_and_times_out_saying_so(
        tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 2, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(palette="black", seconds=0.5))
    assert r["status"] == "ok" and r["verdict"] == "TIMEOUT", r
    assert r["predicate"] == "palette" and r["sampled_every"] == 0, r
    assert machine.asked.count("VGA DACPAL") == 3, "the opening judge and one per retrace"


def test_a_palette_that_is_black_is_the_hit_and_the_machine_is_not_moved(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    machine = waiting(["probe-booted"], 0, tmp_path)
    monkeypatch.setattr(vgadac, "read_dac",
                        lambda session: ({"pel_mask": "ff"}, ["000000"] * vgadac.DAC_ENTRIES))
    r = cast(dict[str, Any], server.screen_wait(palette="black", seconds=5))
    assert r["status"] == "ok" and r["verdict"] == "TARGET" and r["already"] is True, r
    assert vrts(machine) == []


def test_a_sampled_wait_judges_every_nth_retrace_and_says_the_step(tmp_path: Path) -> None:
    machine = waiting(["probe-booted"], 3, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="NEVER ON SCREEN", every=3, seconds=0.5))
    assert r["status"] == "ok" and r["verdict"] == "TIMEOUT", r
    assert r["sampled_every"] == 3 and r["polls"] == 3, r
    assert len(machine.dumps) == 2, "the opening judge and one after the three retraces"
