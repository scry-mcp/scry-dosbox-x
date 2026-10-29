"""Count and capture watches through the debugger's `TAP`, which records every guest access to a
place without stopping (`docs/reference/declarations.md`). Its rows and tables are files the
debugger flushes when `TAPLIST` asks, once per stop survey while a tap is declared."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scry_core import bus_writes, judges
from scry_core import value_format as vf
from scry_core.reply_contract import Invalid, unavailable

import dosbox_debugger as dbg
import dosbox_declarations as dec
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

TAP = "TAP"
#: The debugger's `TAP_ROWS_MAX`: past it a row is counted only.
ROWS_MAX = 100_000
DATA_WIDTH, ENDIANNESS = 32, "little"
NO_FRAME_WHY = ("this build's `TAP` writes a row's time and line, not the display frame it was "
                "made in")
NO_LINE_WHY = "the display had timed no frame yet when the access was made"
DISPLACED_WHY = ("the page's handler was replaced since the tap went in (a video mode set remaps "
                 "video memory): the tap sees nothing more; declare it again to tap the page as it "
                 "is now")
#: The file is the one the server named: the line can be cut after `success` by the debugger's
#: message buffer.
_ANSWER = re.compile(r"^DEBUG: TAP (\d+) ([WRC]) PHYS=([0-9A-F]+) LEN=([0-9A-F]+) success")
_LISTED = re.compile(r"^DEBUG: TAP (\d+) ([WRC]) PHYS=([0-9A-F]+) LEN=([0-9A-F]+) "
                     r"INSTALLED=([01]) TOTAL=(\d+) ROWS=(\d+) OVERFLOW_ROWS=(\d+) VALUES=(\d+) "
                     r"OVERFLOW_VALUES=(\d+) PCS=(\d+) OVERFLOW_PCS=(\d+)$")
_ROW = re.compile(r"^r (\d+) (?:(\d+) )?(-?\d+) (\d+\.\d+) ([0-9A-F]{4}) ([0-9A-F]{8}) "
                  r"([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9a-f]*)$")
_VALUE = re.compile(r"^v ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8}) (\d+)$")
_PC = re.compile(r"^p ([0-9A-F]{4}) ([0-9A-F]{8}) (\d+)$")


@dataclass
class Tap:
    """One tap the debugger holds for a declaration: its id, the physical address and the
    `SEG:OFF` of the place it covers, and its file."""
    id: int
    kind: str
    phys: int
    length: int
    seg: int
    off: int
    path: Path
    trigger: tuple[int, int] | None = None
    last_total: int = 0


def _seg_off(seg: int, off: int) -> str:
    return f"{seg:04X}:{off:08X}"


def place(decl: dec.Declaration, session: ds.Session) -> tuple[int, int]:
    """Where a tap's place resolves now, or the refusal saying why it does not."""
    res = placement.resolve_ref(decl, "DS", session)
    if res["state"] != "armable":
        raise Invalid("unknown_ref" if res["state"] in ("unresolved", "ambiguous")
                      else "not_stopped" if not session.at_debugger() else "bad_argument",
                      f"{decl.ref} cannot be tapped now ({res['state']}): "
                      f"{res.get('why', 'it names no address')}")
    return int(res["seg"]), int(res["off"])


def arm(session: ds.Session, decl: dec.Declaration) -> Tap:
    """Install the tap `decl` asks for and remember it; the debugger's own refusal is raised with
    its words."""
    if not session.has(TAP):
        raise dbg.missing(TAP, f"a {decl.watch_mode} watch")
    session.require_stopped(f"a {decl.watch_mode} watch")
    seg, off = place(decl, session)
    trigger: tuple[int, int] | None = None
    # Numbered by the files the session's taps already left, which outlive a removed tap.
    scratch = STATE.session_scratch()
    path = scratch / f"tap-{len(list(scratch.glob('tap-*'))) + 1}-{seg:04X}{off:08X}"
    if decl.watch_mode == "count":
        command = f"{TAP} C {seg:04X}:{off:X} {decl.width:X} {path}.tab"
    elif decl.trigger_type == "r":
        command = f"{TAP} R {seg:04X}:{off:X} {path}.rows"
    else:
        trigger_decl = dec.Declaration("watch", placement.decide_by(str(decl.trigger)),
                                       str(decl.trigger), width=1, fmt="u8", watch_mode="show")
        trigger = place(trigger_decl, session)
        command = (f"{TAP} W {trigger[0]:04X}:{trigger[1]:X} {seg:04X}:{off:X} {decl.width:X} "
                   f"{path}.rows")
    ok, lines = session.exec(command)
    found = next((m for line in lines if (m := _ANSWER.match(line))), None)
    if not ok or found is None:
        raise Invalid("unexpected_answer" if ok else "bad_argument",
                      f"`{command}` was not taken: {' / '.join(lines) or 'nothing'}")
    file = Path(f"{path}.tab" if decl.watch_mode == "count" else f"{path}.rows")
    tap = Tap(int(found.group(1)), found.group(2), int(found.group(3), 16),
              int(found.group(4), 16), seg, off, file, trigger)
    STATE.taps[decl.ref] = tap
    try:
        held = listed(session).get(tap.id, {}).get("installed")
    except Invalid:
        held = None
    if not held:
        drop(session, decl.ref)
        raise Invalid("readback_refused", f"`{command}` answered success, and `TAPLIST` does not "
                      f"list tap {tap.id} installed: nothing is armed or stored")
    return tap


def drop(session: ds.Session, ref: str) -> None:
    """The tap under `ref` taken out and forgotten whatever the debugger answers: one the server
    gives up on records nothing it reads."""
    tap = STATE.taps.pop(ref, None)
    if tap is not None:
        session.exec(f"TAPDEL {tap.id}")


def installed(session: ds.Session, ref: str) -> bool:
    """Whether the tap under `ref` is in and still holds its page, by one `TAPLIST`."""
    tap = STATE.taps.get(ref)
    return tap is not None and bool(listed(session).get(tap.id, {}).get("installed"))


def remove(session: ds.Session, ref: str, tap_id: int | None = None) -> str | None:
    """`TAPDEL` of the tap under `ref` (only if it is still tap `tap_id`, when given), read back;
    the row's spelling when one was removed."""
    tap = STATE.taps.get(ref)
    if tap is None or (tap_id is not None and tap.id != tap_id):
        return None
    ok, lines = session.exec(f"TAPDEL {tap.id}")
    if not ok or not any(line == "DEBUG: TAPDEL 1 removed" for line in lines):
        raise Invalid("unexpected_answer", f"`TAPDEL {tap.id}` answered "
                      f"{' / '.join(lines) or 'nothing'}, not that it removed the tap")
    STATE.taps.pop(ref)
    return f"TAP {tap.id}"


def listed(session: ds.Session) -> dict[int, dict[str, int]]:
    """One `TAPLIST`: each tap's counts by id, its files flushed. Empty with no tap declared."""
    if not STATE.taps:
        return {}
    ok, lines = session.exec("TAPLIST")
    out: dict[int, dict[str, int]] = {}
    for line in lines:
        m = _LISTED.match(line)
        if m is not None:
            names = ("installed", "total", "rows", "overflow_rows", "values", "overflow_values",
                     "pcs", "overflow_pcs")
            out[int(m.group(1))] = dict(zip(names, (int(g) for g in m.groups()[4:]), strict=True))
    if not ok:
        raise Invalid("unexpected_answer", f"`TAPLIST` answered {' / '.join(lines) or 'nothing'}")
    return out


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="ascii", errors="replace").splitlines()
    except FileNotFoundError:
        return []


def first_rows(tap: Tap, decl: dec.Declaration, shown: int) -> list[dict[str, Any]]:
    """The capture's first `shown` rows; a line of another shape (one cut mid-write) ends them."""
    out: list[dict[str, Any]] = []
    for line in _lines(tap.path)[:shown]:
        m = _ROW.match(line)
        if m is None:
            break
        n, frame, beam, ms, cs, ip, data, mask, block = m.groups()
        row: dict[str, Any] = {
            "n": int(n), "frame": int(frame) if frame is not None else unavailable(NO_FRAME_WHY),
            "line": int(beam) if int(beam) >= 0 else unavailable(NO_LINE_WHY),
            "time_s": float(ms) / 1000, "pc": _seg_off(int(cs, 16), int(ip, 16)),
            "data": judges.hex_at_width(int(data, 16), DATA_WIDTH),
            "mask": judges.hex_at_width(int(mask, 16), DATA_WIDTH)}
        if decl.trigger_type == "w":
            raw = bytes.fromhex(block)
            row["raw_hex"] = raw.hex()
            try:
                row["block"] = vf.parse(str(decl.fmt)).decode(raw, ENDIANNESS, len(raw))
            except vf.FormatError as e:
                row["block"] = unavailable(str(e))
        _name(row, int(cs, 16), int(ip, 16))
        out.append(row)
    return out


def _name(row: dict[str, Any], cs: int, ip: int) -> None:
    """A writer's `symbol`, the nearest below it, when a table is loaded and its address is one
    the table places (a real-mode `CS:IP`)."""
    if not STATE.table:
        return
    found = placement.nearest_symbol(cs * 16 + ip) if ip <= 0xFFFF else None
    if found is not None:
        row["symbol"] = f"{found['name']}+0x{found['delta']:x}" if found["delta"] else found["name"]


def _tables(tap: Tap, decl: dec.Declaration, shown: int) -> dict[str, Any]:
    """A count's value and writer tables, most frequent first."""
    values: list[tuple[int, int, int, int]] = []
    writers: list[tuple[int, int, int]] = []
    for line in _lines(tap.path):
        if (v := _VALUE.match(line)) is not None:
            values.append((int(v.group(1), 16), int(v.group(2), 16), int(v.group(3), 16),
                           int(v.group(4))))
        elif (p := _PC.match(line)) is not None:
            writers.append((int(p.group(1), 16), int(p.group(2), 16), int(p.group(3))))

    def at(phys: int) -> str:
        return _seg_off(tap.seg, tap.off + phys - tap.phys)

    rows = bus_writes.value_rows(values, tap.phys, decl.width or 1, str(decl.fmt), DATA_WIDTH,
                                 ENDIANNESS, shown, at)
    out: list[dict[str, Any]] = []
    for cs, ip, count in sorted(writers, key=lambda w: (-w[2], w[0], w[1]))[:shown]:
        row: dict[str, Any] = {"pc": _seg_off(cs, ip), "count": count}
        _name(row, cs, ip)
        out.append(row)
    return {"values": rows, "values_total": len(values), "writers": out,
            "writers_total": len(writers)}


def evaluate(decl: dec.Declaration, counts: dict[int, dict[str, int]], at_stop: bool
             ) -> dict[str, Any]:
    """What a stop survey (`at_stop`) or `declaration_list(kind="watch")` says of the tap under
    `decl`: its account, or the state that says why there is none. Only a stop moves the
    `since_last_stop` baseline."""
    tap = STATE.taps.get(decl.ref)
    if tap is None:
        return {"state": "unarmed", "installed": False,
                "why": "no tap is installed for this declaration in this session: it is armed "
                       "when declared on a stopped machine, and again at `start` and after "
                       "`symbols_load`"}
    item: dict[str, Any] = {"tally_id": str(tap.id), "addr": _seg_off(tap.seg, tap.off)}
    if tap.trigger is not None:
        item["trigger_addr"] = _seg_off(*tap.trigger)
    if decl.watch_mode == "capture":
        item["trigger_type"] = decl.trigger_type
    got = counts.get(tap.id)
    if got is None:
        return {**item, "state": "unlisted", "installed": False,
                "why": f"`TAPLIST` did not list tap {tap.id}"}
    item.update(installed=bool(got["installed"]),
                state=("captured" if decl.watch_mode == "capture" else "tallied")
                if got["installed"] else "displaced", total=got["total"])
    if not got["installed"]:
        item["why"] = DISPLACED_WHY
    if at_stop:
        if got["total"] < tap.last_total:
            item["since_last_stop"], item["reset"] = got["total"], True
        else:
            item["since_last_stop"] = got["total"] - tap.last_total
        tap.last_total = got["total"]
    if decl.watch_mode == "count":
        item.update(overflow_values=got["overflow_values"], overflow_pcs=got["overflow_pcs"])
        if not at_stop:
            item.update(_tables(tap, decl, st.ROWS_SHOWN))
        return item
    item.update(rows_path=str(tap.path), rows_kept=got["rows"],
                overflow_rows=got["overflow_rows"], rows_max=ROWS_MAX)
    if not at_stop:
        item["first_rows"] = first_rows(tap, decl, st.ROWS_SHOWN)
    return item
