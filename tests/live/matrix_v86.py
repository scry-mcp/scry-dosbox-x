"""Section V of the live matrix: a stop in virtual-8086 mode, on the package's v86 guest
(`tests/guest/v86.asm`), which leaves DOS for VM86 and writes `V86 nnnn` lines on E9 there. The
pane names such a stop `VM86`, and its segments are real-mode ones."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from matrix_common import (
    GUEST,
    M,
    boot,
    cells,
    close_whatever,
    hexint,
    must,
    ok,
    read_bytes,
    release_running,
    said,
    server,
)

V86_CONF = GUEST / "v86.conf"
V86_COM = GUEST / "v86.com"

V_CELLS = cells(
    ("V the guest reaches VM86 and writes its lines there",
     "tests/guest/v86.asm: `V86 nnnn` on E9 from inside VM86"),
    ("V a stop in VM86 is read under the pane's own word, VM86",
     "REFERENCE.md, What a stop returns: `cpu_mode` `VM86`, off the pane's mode word"),
    ("V status says VM86 and where the machine is",
     "status docstring: `pc` where it is now, read off the pane; `cpu_mode` `VM86`"),
    ("V CS:IP is a real-mode segment: the bytes there are the guest's own code",
     "REFERENCE.md, Advancing the machine: a `VM86` stop is read as a real-mode one"),
    ("V a change watch through a raw base is armed again when the mode changes, same numbers",
     "declarations.md, Through a pointer; known: v86.asm's twin at 0010:0000 in both modes"),
)

#: The stops `pm` may come after: a memory row just armed fires at its first check.
STOPS_TO_PM = 8
_LABEL = re.compile(r"^\s*\d+ ([0-9A-F]{8})\s+(?:\S+\s+)?(\w+):")


@M.section("V", "a stop in virtual-8086 mode, on the package's own v86 guest", V_CELLS)
def section_v() -> None:
    boot(conf=V86_CONF)
    release_running()
    w = M.call(server.log_wait, pattern=r"V86 000[1-9]", channel="guest", seconds=20)
    M.judge(V_CELLS[0].label, ok(w), said(w))
    s = M.call(server.stop)
    M.judge(V_CELLS[1].label, ok(s) and s.get("cpu_mode") == "VM86"
            and str(s.get("pc", "")).count(":") == 1, said(s))
    st = M.call(server.status)
    M.judge(V_CELLS[2].label, ok(st) and st.get("cpu_mode") == "VM86"
            and hexint(str(st.get("pc", "")).split(":")[0])
            == hexint((s.get("regs") or {}).get("CS")), said(st))
    regs = must(M.call(server.registers), "reading the VM86 stop's registers")["regs"]
    cs, ip = hexint(regs.get("CS")) or 0, (hexint(regs.get("EIP")) or 0) & 0xFFFF
    image = V86_COM.read_bytes()
    here = read_bytes(f"{cs:04X}:{ip:04X}", 8)
    at = ip - 0x100                     # a COM is loaded at offset 0x100 of its segment
    M.judge(V_CELLS[3].label, at >= 0 and image[at:at + 8] == here,
            f"{cs:04X}:{ip:04X} holds {here.hex()}, the image there {image[at:at + 8].hex()}")
    close_whatever()
    _twin(cs)


def _labels() -> dict[str, int] | None:
    """Each global label of v86.asm at its offset in the loaded COM, off nasm's listing."""
    if shutil.which("nasm") is None:
        return None
    with tempfile.TemporaryDirectory(prefix="matrix-v86-") as scratch:
        listing = Path(scratch) / "v86.lst"
        subprocess.run(["nasm", "-f", "bin", "-l", str(listing), str(GUEST / "v86.asm"),
                        "-o", str(Path(scratch) / "v86.com")], check=True, timeout=60)
        rows = listing.read_text(encoding="latin-1").splitlines()
    return {m.group(2): 0x100 + int(m.group(1), 16) for row in rows if (m := _LABEL.match(row))}


def _twin(cs: int) -> None:
    """Declared at `twin` (real), the watch meets the same numbers at `pm` (protected)."""
    label = V_CELLS[4].label
    at = _labels()
    if at is None or not {"twin", "pm", "twin_byte"} <= at.keys():
        M.block(label, "no `nasm` on PATH to list v86.asm" if at is None
                else f"v86.asm's listing lacks `twin`, `pm` or `twin_byte`: {sorted(at)[:8]}")
        return
    boot(conf=V86_CONF)
    must(M.call(server.breakpoint_at, ref=f"{cs:04X}:{at['twin']:04X}"), "arming twin")
    real = M.call(server.resume, seconds=20)
    w = M.call(server.watch_add, ref="[0010:0000]", mode="change", length=1)
    # Placed by its linear address: the code descriptor's base is this segment's.
    must(M.call(server.breakpoint_at, ref=f"{cs:04X}:{at['pm']:04X}"), "arming pm")
    stops = []
    for _ in range(STOPS_TO_PM):
        prot = M.call(server.resume, seconds=20)
        stops.append(str(prot.get("pc")))
        if not ok(prot) or str(prot.get("pc")) == f"0008:{at['pm']:08X}":
            break
    # The debugger's list: a declaration's `entry` is spelt for the mode it is read in.
    listed = str(M.call(server.debug, command="BPLIST").get("output", ""))
    twin = at["twin_byte"]
    M.judge(label, ok(real) and real.get("cpu_mode") == "real" and ok(w)
            and w.get("state") == "armed" and ok(prot) and prot.get("cpu_mode") == "protected"
            and f"BPPM 0010:{twin:08X}" in listed and f"BPMEM 0010:{twin:04X}" not in listed,
            f"{said(real, 80)}; {said(w, 80)}; stops {stops}; {said(prot, 80)}; "
            f"{' | '.join(listed.split(chr(10))[-4:])}")
    close_whatever()
