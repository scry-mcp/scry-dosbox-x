"""Section V of the live matrix: a stop in virtual-8086 mode, on the package's v86 guest
(`tests/guest/v86.asm`), which leaves DOS for VM86 and writes `V86 nnnn` lines on E9 there. The
pane names such a stop `VM86`, and its segments are real-mode ones."""
from __future__ import annotations

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
)


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
