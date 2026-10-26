"""`disassemble`: the decoder over the package's own guests, the code pane as its control, the
width of a segment, the operands it names, and its refusals.

The guests' bytes and every pane were captured from a real session (`fixtures/disasm/`, its
`PROVENANCE.txt`); where a case needs a shape no capture holds it changes one field of one of
them and says which, and the few instructions written out as bytes cite the SDM's encoding.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import disasm_control as control
import pytest
from dosbox_x_server_support import FakeSession, clean_session, install  # noqa: F401
from test_dosbox_x_machine import listing

import dosbox_code as code
import dosbox_comments as dcomments
import dosbox_disasm as disasm
import dosbox_grammar as grammar
import dosbox_machine as machine
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as sym
import dosbox_x_server as server

FIX = Path(__file__).resolve().parent / "fixtures" / "disasm"
GUEST = Path(__file__).resolve().parent / "guest"
TRACE = Path(__file__).resolve().parent / "fixtures" / "trace"
#: Where DOS loaded both guests in every capture: segment 0814, so offset 0100 is linear 8240.
LOAD = 0x0814
COM_START = 0x100
PROBE_BASE = "8140"


def text(path: Path) -> str:
    got = path.read_text(encoding="utf-8", errors="surrogateescape")
    assert got.strip(), f"{path.name} is empty, so this case would examine nothing"
    return got


def code_guest() -> bytes:
    return (FIX / "code-0814-0100.bin").read_bytes()


def probe_guest() -> bytes:
    return (FIX / "probe-0814-0100.bin").read_bytes()


def at(insns: list[disasm.Insn], offset: int) -> disasm.Insn:
    found = [i for i in insns if i.offset == offset]
    assert len(found) == 1, f"no single line at {offset:04X}: {[hex(i.offset) for i in insns]}"
    return found[0]


# ------------------------------------------------------------------- the decoder alone

def test_the_dump_is_the_committed_guest() -> None:
    """The bytes the session read are the bytes `code.com` holds."""
    com = (GUEST / "code.com").read_bytes()
    assert code_guest()[:len(com)] == com


def test_every_routine_of_the_code_guest_starts_a_line() -> None:
    """`code.sym`'s code rows are instruction boundaries of the listing, so a decoder that lost
    its place anywhere before one of them misses it."""
    insns = disasm.decode(code_guest(), COM_START, 16)
    starts = {i.offset for i in insns}
    rows = [ln.split() for ln in (GUEST / "code.sym").read_text(encoding="ascii").splitlines()]
    routines = [int(a, 16) for a, kind, _name in rows if kind == "T"]
    assert routines, "code.sym carries no routine: this case examined nothing"
    assert [r for r in routines if r not in starts] == []


@pytest.mark.skipif(shutil.which("nasm") is None, reason="no `nasm` on PATH for the listing")
def test_the_code_guest_decodes_on_every_boundary_of_its_listing(tmp_path: Path) -> None:
    """The assembler's listing is a referee neither decoder controls."""
    listing = tmp_path / "code.lst"
    r = subprocess.run(["nasm", "-f", "bin", "-l", str(listing), str(GUEST / "code.asm"),
                        "-o", str(tmp_path / "code.com")], capture_output=True, text=True,
                       check=False)
    assert r.returncode == 0, r.stderr
    placed: dict[int, str] = {}
    for line in listing.read_text(encoding="latin-1").splitlines():
        m = re.match(r"^\s*\d+ ([0-9A-F]{8}) ([0-9A-F\[\]()]+)-?\s+(?:\w+:)?\s*([a-z]\w*)", line)
        if m and m.group(3) not in ("db", "dw", "dd") and int(m.group(1), 16) < 0x75:
            placed[COM_START + int(m.group(1), 16)] = m.group(3)
    assert len(placed) > 20, f"the listing gave {len(placed)} instructions: the pattern drifted"
    insns = {i.offset: i for i in disasm.decode(code_guest(), COM_START, 16)}
    missing = sorted(f"{a:04X}" for a in placed if a not in insns)
    assert missing == [], f"the listing starts instructions capstone does not: {missing}"


@pytest.mark.parametrize(("offset", "flow"), [
    (0x100, disasm.SEQUENTIAL),      # xor bp, bp
    (0x102, disasm.CALL),            # int 3: a trap comes back, as a call does
    (0x136, disasm.CALL),            # call [ptr_outer]
    (0x149, disasm.CALL),            # call far [ptr_middle]
    (0x13A, disasm.BRANCH),          # jmp park
    (0x16E, disasm.BRANCH),          # jz .done
    (0x14E, disasm.RETURN),          # ret
    (0x15D, disasm.RETURN),          # retf
    (0x13C, disasm.UNKNOWN),         # FE /7
])
def test_each_line_says_what_it_does_to_the_flow(offset: int, flow: str) -> None:
    assert at(disasm.decode(code_guest(), COM_START, 16), offset).flow == flow


def test_loop_is_a_branch_though_capstone_files_it_under_relative_branches_only() -> None:
    """The probe's settle `loop` at 0106: capstone puts `loop` in no jump group."""
    insns = disasm.decode(probe_guest(), COM_START, 16)
    line = at(insns, 0x106)
    assert line.mnemonic == "loop" and line.flow == disasm.BRANCH


def test_a_byte_nothing_decodes_is_a_line_and_decoding_resumes_at_the_next() -> None:
    insns = disasm.decode(code_guest(), COM_START, 16)
    bad, after = at(insns, 0x13C), at(insns, 0x13D)
    assert (bad.data, bad.text, bad.flow) == (b"\xfe", ".byte 0xfe", disasm.UNKNOWN)
    assert after.text == "clc"


def test_the_386_prefixes_are_decoded_in_a_16_bit_segment() -> None:
    insns = disasm.decode(code_guest(), COM_START, 16)
    assert at(insns, 0x118).text == "mov eax, 0x12345678"
    scaled = at(insns, 0x122)
    assert scaled.data.hex().upper() == "67668B0C9D79010000"
    assert scaled.text == "mov ecx, dword ptr [ebx*4 + 0x179]"


def test_a_listing_completes_the_instruction_that_straddles_its_end() -> None:
    """`length` 1 on the probe's three-byte `mov si, 0156` at 010B is one line of three bytes."""
    probe = probe_guest()
    insns = disasm.decode(probe[0x0B:0x0B + 1 + disasm.INSN_MAX], 0x10B, 16, 1)
    assert [(i.offset, i.data.hex().upper()) for i in insns] == [(0x10B, "BE5601")]


def test_a_near_target_wraps_inside_a_16_bit_segment() -> None:
    """IP wraps at 64 KiB and capstone's sum does not."""
    line = disasm.decode(bytes.fromhex("E80010"), 0xFFF0, 16)[0]
    assert line.targets[0].offset == 0x0FF3 and line.text == "call 0xff3"


def test_the_operands_a_name_can_be_claimed_for() -> None:
    insns = disasm.decode(code_guest(), COM_START, 16)
    assert at(insns, 0x146).targets == (disasm.Target("0x16b", 0x16B, None),)
    assert at(insns, 0x107).memory == (disasm.Memory("word ptr [0x175]", 0x175, "DS"),)
    assert at(insns, 0x112).memory == ()           # [bx+2]: the register's at run time
    assert at(insns, 0x149).memory[0].offset == 0x17F
    overridden = disasm.decode(bytes.fromhex("2EA17301"), 0x100, 16)[0]
    assert overridden.memory[0].segment_register == "CS"


def test_a_16_bit_displacement_past_7fff_is_an_offset_not_a_negative_number() -> None:
    """`mov bx, [8004]` (8B 1E 04 80, the SDM's ModRM form)."""
    modrm = disasm.decode(bytes.fromhex("8B1E0480"), 0x100, 16)[0]
    moffs = disasm.decode(bytes.fromhex("A10480"), 0x100, 16)[0]
    assert modrm.memory[0].offset == moffs.memory[0].offset == 0x8004


def test_a_far_pointer_names_its_segment_and_an_offset_as_wide_as_its_operand() -> None:
    """`jmp 1234:5678` and, with 66h in 16-bit code, `call 1234:12345678` (the SDM's EA and 9A
    encodings): the segment is the pointer's, the offset keeps its 32 bits."""
    near = disasm.decode(bytes.fromhex("EA78563412"), 0x100, 16)[0].targets[0]
    wide = disasm.decode(bytes.fromhex("669A785634123412"), 0x100, 16)[0].targets[0]
    assert (near.far_segment, near.offset) == (0x1234, 0x5678)
    assert (wide.far_segment, wide.offset) == (0x1234, 0x12345678)


def test_an_instruction_starting_at_the_end_is_not_listed() -> None:
    """`length` 3 on `mov si, 0156` then `call`."""
    insns = disasm.decode(probe_guest()[0x0B:0x0B + 3 + disasm.INSN_MAX], 0x10B, 16, 3)
    assert [i.offset for i in insns] == [0x10B]


# --------------------------------------------------------------------------- the pane

def test_the_pane_is_read_off_the_last_repaint_its_first_line_glued_to_its_header() -> None:
    lines = control.pane_lines(text(FIX / "code-C-00-00000100.txt"))
    assert len(lines) == 11
    assert lines[0] == control.PaneLine("0814", 0x100, bytes.fromhex("31ED"), "xor  bp,bp")
    assert lines[-1].offset == 0x122 and lines[-1].data == bytes.fromhex("67668B0C9D79010000")


def test_two_repaints_in_one_delta_read_as_the_later() -> None:
    """Two captured deltas joined, as one command's delta carries every repaint it caused."""
    screen = text(FIX / "code-C-00-00000100.txt") + text(FIX / "code-C-02-00000149.txt")
    assert control.pane_lines(screen)[0].offset == 0x149


def test_a_pane_line_whose_bytes_were_cut_has_none() -> None:
    """The capture's line at 0122 with its last byte replaced by the pane's `..` mark."""
    screen = text(FIX / "code-C-00-00000100.txt").replace("67668B0C9D79010000",
                                                          "67668B0C9D790100..")
    line = [p for p in control.pane_lines(screen) if p.offset == 0x122][0]
    assert line.data is None and line.text.startswith("mov")


# ------------------------------------------------------------------------ the control

def test_the_code_pane_agrees_with_capstone_over_the_whole_code_guest() -> None:
    insns = disasm.decode(code_guest(), COM_START, 16)
    compared, excepted, wrong = 0, [], []
    for path in sorted(FIX.glob("code-C-0*.txt")):
        v = control.compare(control.pane_lines(text(path)), "0814", insns)
        compared += v.compared
        excepted += v.excepted
        wrong += v.disagreements
    assert compared > 80, f"{compared} lines compared: the walk did not cover the guest"
    assert wrong == []
    assert excepted == ["0814:0000013C"]        # FE /7, the pane's `callback`


def test_the_code_pane_agrees_with_capstone_on_the_probe() -> None:
    probe = probe_guest()
    insns = disasm.decode(probe[0x0B:], 0x10B, 16)
    for name in ("probe-C-start.txt", "probe-C-emit.txt"):
        v = control.compare(control.pane_lines(text(FIX / name)), "0814", insns)
        assert v.compared == 11 and v.disagreements == [], (name, v)


def test_a_32_bit_pane_agrees_decoded_32_bit_and_not_16() -> None:
    """dos-djgpp32's `_engine_pos` in `Pr32`, from the committed trace capture, its bytes the pane's
    own (every line printed all of them). Decoded 16-bit the same bytes disagree: the width is
    what the control is checking, not a formality."""
    pane = control.pane_lines(text(TRACE / "dos-djgpp32-engine-survey-before.txt"))
    assert all(p.data for p in pane), "a cut line: the bytes are not all there"
    data = b"".join(cast(bytes, p.data) for p in pane)
    wide = control.compare(pane, "00A7", disasm.decode(data, pane[0].offset, 32))
    narrow = control.compare(pane, "00A7", disasm.decode(data, pane[0].offset, 16))
    assert wide.compared == 11 and wide.disagreements == []
    assert narrow.disagreements, "decoded 16-bit it agreed: the comparison is blind to width"


def _one_line(segment: str, offset: int, data: str, pane: str) -> list[control.PaneLine]:
    return [control.PaneLine(segment, offset, bytes.fromhex(data), pane)]


def test_a_segment_load_from_a_16_bit_register_agrees_in_16_bit_code() -> None:
    """`mov ds, ax` (8E D8) as both decoders print it in real mode."""
    v = control.compare(_one_line("0814", 0x100, "8ED8", "mov  ds,ax"), "0814",
                        disasm.decode(bytes.fromhex("8ED8"), 0x100, 16))
    assert v.compared == 1 and v.disagreements == [], v


@pytest.mark.parametrize(("pane", "why"), [
    ("mov  cx,[bx-02]", "the sign of a displacement"),
    ("mov  [bx+02],cx", "the order of the operands"),
    ("mov  dx,[bx+02]", "a register"),
    ("mov  cx,[bx+04]", "a number"),
])
def test_the_control_sees_an_operand_that_differs(pane: str, why: str) -> None:
    """The captured pane line `mov  cx,[bx+02]` at 0112 with one field changed, so each part of
    the operand comparison is seen biting on its own."""
    insns = disasm.decode(code_guest(), COM_START, 16)
    assert control.compare(_one_line("0814", 0x112, "8B4F02", "mov  cx,[bx+02]"), "0814",
                           insns).disagreements == []
    v = control.compare(_one_line("0814", 0x112, "8B4F02", pane), "0814", insns)
    assert v.disagreements, f"{why} changed and the comparison did not see it"


def test_a_direct_far_call_agrees_though_the_two_spell_its_pointer_apart() -> None:
    """dos-real16's `call 0895:0006` (9A 06 00 95 08) as its pane printed it in the live matrix."""
    insns = disasm.decode(bytes.fromhex("9A06009508"), 0xE, 16)
    good = [control.PaneLine("0892", 0xE, bytes.fromhex("9A06009508"), "call 0895:0006")]
    assert control.compare(good, "0892", insns).disagreements == []
    bad = [control.PaneLine("0892", 0xE, bytes.fromhex("9A06009508"), "call 0895:0007")]
    assert control.compare(bad, "0892", insns).disagreements


def test_a_32_bit_popa_agrees_though_the_pane_says_popad_and_capstone_popal() -> None:
    """The DPMI guest's `_tick` at 00A7:2081 as its pane printed it in the live matrix."""
    pane = [control.PaneLine("00A7", 0x2081, bytes.fromhex("61"), "popad")]
    v = control.compare(pane, "00A7", disasm.decode(bytes.fromhex("61"), 0x2081, 32))
    assert v.disagreements == [], v
    v16 = control.compare(pane, "00A7", disasm.decode(bytes.fromhex("61"), 0x2081, 16))
    assert v16.disagreements, v16


def test_in_real_mode_the_pane_decodes_segment_0000_as_32_bit_code() -> None:
    """The second way the pane is wrong about x86."""
    pane = [p for p in control.pane_lines(text(FIX / "code-C-elsewhere.txt")) if p.offset == 0]
    assert pane and pane[0].text.startswith("pushad"), pane
    v = control.compare(pane, "0000", disasm.decode(cast(bytes, pane[0].data), 0, 16))
    assert v.disagreements, v


def test_the_control_sees_a_byte_that_differs() -> None:
    """One byte of the dump changed (the immediate of `mov ax, 1234` at 0104)."""
    blob = bytearray(code_guest())
    blob[0x105 - COM_START] ^= 0xFF
    v = control.compare(control.pane_lines(text(FIX / "code-C-00-00000100.txt")), "0814",
                        disasm.decode(bytes(blob), COM_START, 16))
    assert [d.split(":")[0] + ":" + d.split(":")[1][:8] for d in v.disagreements] \
        == ["0814:00000104"]


# ------------------------------------------------------------------- the tool, on a double

class CodeMachine(FakeSession):
    """A stopped machine holding the captured guest bytes at their linear addresses, whose
    `MEMDUMPBIN` hands back those bytes; its register pane is a captured one."""

    def __init__(self, registers: dict[str, str], *, mode: str = "Real",
                 selectors: dict[str, dict[str, int]] | None = None,
                 logfile: Path | None = None, memory: int = 0x110000) -> None:
        super().__init__(mode=mode)
        self.regs = registers
        self.mem = bytearray(memory)
        self.selectors = selectors or {}
        self.launch = SimpleNamespace(cwd=Path("/"), logfile=logfile, watched=False,
                                      input_port=None, captures_dir=None)
        self.asked_selinfo: list[str] = []
        self.d_reads: list[tuple[int, int, int]] = []

    def where(self) -> dict[str, str]:
        return {"cs": self.regs["CS"], "eip": self.regs["EIP"], "mode": self.mode}

    def registers(self) -> dict[str, str]:
        return dict(self.regs)

    def selector(self, reg: str) -> dict[str, int]:
        self.asked_selinfo.append(reg)
        return self.selectors[reg]

    def _memdump_candidates(self) -> list[Path]:
        return ds.Session._memdump_candidates(cast(ds.Session, self))

    def _base(self, seg: int) -> int:
        return seg * 16 if self.mode == grammar.REAL_MODE else self.selectors.get(
            next(r for r in ds.SELINFO_REGS if int(self.regs[r], 16) == seg), {}).get("base", 0)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.memdump_calls.append((seg, off, length))
        base = self._base(seg)
        dest.write_bytes(bytes(self.mem[base + off:base + off + length]))
        return dest

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        self.d_reads.append((seg, off, n))
        base = self._base(seg)
        return bytes(self.mem[base + off:base + off + n])


def probe_machine() -> CodeMachine:
    regs = json.loads((FIX / "probe-registers.json").read_text(encoding="utf-8"))
    s = CodeMachine(regs)
    data = probe_guest()
    s.mem[LOAD * 16 + COM_START:LOAD * 16 + COM_START + len(data)] = data
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


def load_probe_symbols() -> None:
    dstate.STATE.install_table(sym.parse_nm((GUEST / "probe.sym").read_text(encoding="ascii")))
    dstate.STATE.base = {"base": int(PROBE_BASE, 16)}


def test_disassemble_lists_start_and_names_its_calls_and_its_counter() -> None:
    probe_machine()
    load_probe_symbols()
    r = cast(dict[str, Any], server.disassemble(ref="start", length=16))
    assert r["status"] == "ok", r
    assert (r["seg_off"], r["code_bits"], r["code_bits_from"]) \
        == (f"{LOAD:04X}:0000010B", 16, "real mode")
    assert r["lines"][0].startswith("0814:0000010B BE5601") and r["lines"][0].endswith(
        "mov si, 0x156")
    assert r["flow"][:3] == ["sequential", "call", "call"] and r["flow_source"] == "capstone"
    named = {(row["line"], row["kind"]): row for row in r["resolved"]}
    assert (named[(1, "target")]["symbol"], named[(1, "target")]["delta"]) == ("emit", 0)
    assert (named[(2, "target")]["symbol"], named[(2, "target")]["delta"]) == ("bump", 0)
    cnt = named[(3, "memory")]
    assert (cnt["symbol"], cnt["delta"], cnt["register"], cnt["addr"]) \
        == ("cnt", 1, "DS", "0x0000829a")
    assert cnt["seg_off"].startswith("0814:"), cnt
    assert r["summary"] == "disassemble start: 5 lines at 0814:0000010B, 16-bit"


def test_a_comment_ends_the_disassembly_line_it_is_placed_on() -> None:
    probe_machine()
    load_probe_symbols()
    assert cast(dict[str, Any], server.comment_write("add", ref="start", text="entry"))[
        "status"] == "ok"
    r = cast(dict[str, Any], server.disassemble(ref="start", length=16))
    assert r["status"] == "ok", r
    assert r["lines"][0].endswith("mov si, 0x156 // entry"), r["lines"][0]
    assert not any(" // " in line for line in r["lines"][1:]), r["lines"]


def test_without_a_table_there_is_nothing_resolved_and_outside_its_span_no_name() -> None:
    probe_machine()
    bare = cast(dict[str, Any], server.disassemble(ref="0814:0106", length=8))
    assert bare["status"] == "ok" and "resolved" not in bare, bare
    load_probe_symbols()
    named = cast(dict[str, Any], server.disassemble(ref="0814:0106", length=8))
    below = [row for row in named["resolved"] if row["kind"] == "target"]
    assert below and all(not row["symbol"]["available"] and not row["delta"]["available"]
                         for row in below), below


def test_an_operand_above_the_last_symbol_is_not_named_after_it() -> None:
    """`probe.sym` without its data rows, so the table ends at `bump`."""
    probe_machine()
    load_probe_symbols()
    dstate.STATE.install_table([s for s in dstate.STATE.table if s.name in
                                ("start", "emit", "bump")])
    r = cast(dict[str, Any], server.disassemble(ref="start", length=16))
    rows = [row for row in r["resolved"] if row["kind"] == "memory"]
    assert rows and all(not row["symbol"]["available"] and not row["delta"]["available"]
                        for row in rows), rows


def test_a_listing_past_the_end_of_a_16_bit_segment_is_refused_naming_what_fits() -> None:
    s = probe_machine()
    r = cast(dict[str, Any], server.disassemble(ref="0814:FFF8", length=16))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
    assert "at most 8 bytes" in r["message"] and s.memdump_calls == []
    fits = cast(dict[str, Any], server.disassemble(ref="0814:FFF8", length=8))
    assert fits["status"] == "ok" and s.memdump_calls == [(LOAD, 0xFFF8, 8)], fits


@pytest.mark.parametrize("length", [0, -1, code.LENGTH_MAX + 1, True, "16", 1.5])
def test_a_length_out_of_its_range_is_refused_with_no_machine(length: object) -> None:
    tool: Any = server.disassemble
    r = cast(dict[str, Any], tool(ref="0814:0100", length=length))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and not r["session"]["alive"], r


def pr32_machine(logfile: Path | None = None) -> CodeMachine:
    """dos-djgpp32's registers at its `_engine_pos` stop (the committed trace capture's pane)."""
    regs = {"EAX": "00000000", "ESI": "0048D908", "DS": "00AF", "ES": "00AF", "FS": "00AF",
            "GS": "00BF", "SS": "00AF", "EBX": "00000000", "EDI": "00000000", "CS": "00A7",
            "EIP": "0005E9C0", "ECX": "FFFFFFFF", "EBP": "002B86C8", "EDX": "00000000",
            "ESP": "002B609C"}
    selinfo = {"CS": {"base": 0x400000, "limit": 0x2CFFFF, "type": 0x1B, "big": 1},
               "DS": {"base": 0x400000, "limit": 0x2CFFFF, "type": 0x13, "big": 1},
               "GS": {"base": 0x8240, "limit": 0xFFFF, "type": 0x13, "big": 0}}
    s = CodeMachine(regs, mode="Pr32", selectors=selinfo, logfile=logfile, memory=0x500000)
    s.listing = lambda command: listing("dos-djgpp32", command)  # type: ignore[method-assign]
    pane = control.pane_lines(text(TRACE / "dos-djgpp32-engine-survey-before.txt"))
    data = b"".join(cast(bytes, p.data) for p in pane)
    s.mem[0x400000 + 0x5E9C0:0x400000 + 0x5E9C0 + len(data)] = data
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return s


def test_the_width_of_a_segment_is_read_where_it_is_held() -> None:
    s = pr32_machine()
    stop = code.Segments(cast(ds.Session, s), s.where(), s.registers())
    assert stop.bits(0xA7) == (32, "the stop's Pr32")
    assert stop.bits(0xBF) == (16, "SELINFO GS")
    assert s.asked_selinfo == ["GS"]                       # CS's width cost no round trip
    assert stop.bits(0x8F) == (32, "the LDT listing")


def test_a_selector_no_register_holds_takes_its_width_from_the_listing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = {"ldt": [{"selector": "008C", "base": "00000000", "limit": "0000FFFF",
                     "type": "1B", "b": 0}], "gdt": []}
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: SimpleNamespace(found=rows,
                                                                           notes=[]))
    s = pr32_machine(tmp_path / "x.log")
    stop = code.Segments(cast(ds.Session, s), s.where(), s.registers())
    assert stop.bits(0x8F) == (16, "the LDT listing")
    with pytest.raises(ds.Invalid, match="names no descriptor"):
        stop.bits(0x97)


def test_disassemble_in_pr32_decodes_32_bit_past_offset_ffff_through_the_listings(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Past offset FFFF in protected mode the bytes come by `memdump`'s route, which judges the
    selector's limit off the descriptor listings: read once, here, and handed to the dump."""
    rows = {"gdt": [], "ldt": [{"selector": "00A4", "base": "00400000", "limit": "002CFFFF",
                                "type": "1B", "b": 1}]}
    reads: list[object] = []

    def read(*a: object, **_k: object) -> SimpleNamespace:
        reads.append(a)
        return SimpleNamespace(found=rows, notes=[])
    monkeypatch.setattr(machine, "read", read)
    pr32_machine(tmp_path / "x.log")
    dstate.STATE.install_table([sym.Symbol("_engine_pos", 0x5E9C0),
                                sym.Symbol("_engine_end", 0x5EA00)])
    dstate.STATE.base = {"base": 0x400000}
    r = cast(dict[str, Any], server.disassemble(ref="_engine_pos", length=8))
    assert r["status"] == "ok" and r["code_bits"] == 32, r
    assert len(r["lines"]) == 5, r["lines"]
    assert r["lines"][0].endswith("push ebp") and r["lines"][2].endswith(
        "mov eax, dword ptr [ebp + 8]")
    assert len(reads) == 1, "the listings were read more than once for one listing"


def test_disassemble_in_pr32_past_offset_ffff_reads_the_descriptor_listings() -> None:
    s = pr32_machine()
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0005E9C0", length=8))
    assert r["status"] == "ok" and r["lines"][0].endswith("push ebp"), r
    assert [c[:2] for c in s.memdump_calls] == [(0xA7, 0x5E9C0)], s.memdump_calls


def test_only_the_range_asked_for_needs_the_listings_past_offset_ffff() -> None:
    """At 00A7:FFF0 eight bytes stay below 64 KiB while the read-ahead would cross."""
    s = pr32_machine()
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0000FFF0", length=8))
    assert r["status"] == "ok", r
    assert s.memdump_calls == [(0xA7, 0xFFF0, 0x10)]
    assert s.d_reads == [(0xA7, 0x10000, 8 + disasm.INSN_MAX - 0x10)]


def test_a_32_bit_line_that_straddles_offset_ffff_completes_off_the_data_view() -> None:
    """Eight bytes from 00A7:FFF8 stay below 64 KiB, and the `mov eax, imm32` at FFFC (B8 and
    four bytes, the SDM's encoding) runs past it: the dump stops at FFFF without the listings,
    and the bytes that complete the line come off one `D` at 10000."""
    s = pr32_machine()
    s.mem[0x400000 + 0xFFF8:0x400000 + 0x10001] = bytes.fromhex("90909090B878563412")
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0000FFF8", length=8))
    assert r["status"] == "ok", r
    assert r["lines"][-1].endswith("mov eax, 0x12345678") and "unknown" not in r["flow"], r
    assert s.memdump_calls == [(0xA7, 0xFFF8, 8)]
    assert s.d_reads == [(0xA7, 0x10000, disasm.INSN_MAX)]


def test_a_straddle_whose_bytes_past_ffff_cannot_be_read_is_refused_not_decoded_short() -> None:
    s = pr32_machine()

    def refused(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        raise ds.Invalid("unexpected_answer", "no data view came back")
    s.read_bytes = refused  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0000FFF8", length=8))
    assert r["status"] == "INVALID" and "no data view came back" in r["message"], r


def test_a_32_bit_line_is_not_completed_past_a_selectors_limit_of_ffff() -> None:
    """The straddle above in a 32-bit CS whose limit is FFFF."""
    s = pr32_machine()
    s.selectors["CS"] = {**s.selectors["CS"], "limit": 0xFFFF}
    s.mem[0x400000 + 0xFFF8:0x400000 + 0x10001] = bytes.fromhex("90909090B878563412")
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0000FFF8", length=8))
    assert r["status"] == "ok", r
    assert s.d_reads == [] and s.asked_selinfo == ["CS"], (s.d_reads, s.asked_selinfo)
    assert not r["lines"][-1].endswith("mov eax, 0x12345678"), r["lines"]


def test_a_32_bit_listing_is_cut_at_the_selectors_limit(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With the limit 0005E9C7 (the captured row's limit changed), eight bytes from 0005E9C0
    are the last of the segment: the read stops there and does not run on past it."""
    rows = {"gdt": [], "ldt": [{"selector": "00A4", "base": "00400000", "limit": "0005E9C7",
                                "type": "1B", "b": 1}]}
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: SimpleNamespace(found=rows, notes=[]))
    s = pr32_machine(tmp_path / "x.log")
    r = cast(dict[str, Any], server.disassemble(ref="00A7:0005E9C0", length=8))
    assert r["status"] == "ok", r
    assert s.memdump_calls == [(0xA7, 0x5E9C0, 8)]


def test_a_protected_mode_segment_is_judged_by_what_holds_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A `Pr16` pane makes CS 16-bit."""
    s = pr32_machine()
    narrow = code.Segments(cast(ds.Session, s), {**s.where(), "mode": "Pr16"}, s.registers())
    assert narrow.bits(0xA7) == (16, "the stop's Pr16")
    segs = code.Segments(cast(ds.Session, s), s.where(), s.registers())
    assert segs.bits(0xAF) == (32, "SELINFO DS") and s.asked_selinfo == ["DS"]
    with pytest.raises(ds.Invalid, match="null selector"):
        segs.bits(0)
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: SimpleNamespace(
        found={"gdt": []}, notes=["`ldt` is absent: `LDT` answered nothing"]))
    with pytest.raises(ds.Invalid, match="could not be read") as e:
        code.Segments(cast(ds.Session, s), s.where(), s.registers()).bits(0x8F)
    assert e.value.code == "unexpected_answer" and "answered nothing" in str(e.value)


def test_a_memory_operand_through_a_register_the_pane_did_not_show_is_unplaced() -> None:
    """The probe's pane with no GS (a cut repaint keeps CS and EIP)."""
    s = probe_machine()
    del s.regs["GS"]
    s.mem[LOAD * 16 + 0x200:LOAD * 16 + 0x204] = bytes.fromhex("65A01000")
    load_probe_symbols()
    r = cast(dict[str, Any], server.disassemble(ref="0814:0200", length=4))
    row = [x for x in r["resolved"] if x["kind"] == "memory"][0]
    assert r["status"] == "ok" and "GS" in row["addr"]["why"], r


def test_in_protected_mode_an_operand_is_placed_through_its_selectors_base() -> None:
    """`mov eax, [00062340]` and `jmp 008F:00001000` (A1 and EA with a 32-bit offset, the SDM's
    encodings) written at the double's `_engine_pos`: the memory operand is placed under DS's
    base as `SELINFO DS` gives it and named; the far target's selector no register holds needs
    the listings, which place it."""
    s = pr32_machine()
    at = 0x400000 + 0x5E9C0
    s.mem[at:at + 12] = bytes.fromhex("A140230600EA00100000" "8F00")
    dstate.STATE.install_table([sym.Symbol("_engine_pos", 0x5E9C0),
                                sym.Symbol("_g_eng_rate", 0x62340),
                                sym.Symbol("_engine_end", 0x70000)])
    dstate.STATE.base = {"base": 0x400000}
    segs = code.Segments(cast(ds.Session, s), s.where(), s.registers())
    insns = disasm.decode(bytes(s.mem[at:at + 12]), 0x5E9C0, 32)
    rows = code.resolve(segs, 0xA7, insns)
    memory = [x for x in rows if x["kind"] == "memory"][0]
    assert (memory["symbol"], memory["delta"], memory["addr"], memory["register"]) \
        == ("_g_eng_rate", 0, "0x00462340", "DS")
    far = [x for x in rows if x["kind"] == "target"][0]
    assert far["seg_off"].startswith("008F:") and far["addr"].startswith("0x"), far


def test_a_screen_with_no_pane_has_no_lines() -> None:
    assert control.pane_lines(text(FIX / "probe-C-start.txt").split("Code Overview")[0]) == []


def test_disassemble_is_a_step_of_perform_and_its_length_is_judged_with_the_list() -> None:
    probe_machine()
    ran = cast(dict[str, Any], server.perform(steps=[
        {"op": "disassemble", "ref": "0814:010B", "length": 3}]))
    assert ran["status"] == "ok" and ran["steps_completed"] == 1, ran
    refused = cast(dict[str, Any], server.perform(steps=[
        {"op": "registers"}, {"op": "disassemble", "ref": "0814:010B", "length": 0}]))
    assert refused["status"] == "INVALID" and refused["ran"] == [], refused


# ------------------------------------------------------------------- the stop's instruction

class StoppedCode(CodeMachine):
    """The code guest at one of its captured stops."""

    def __init__(self, stop: str) -> None:
        regs = json.loads((FIX / f"{stop}-registers.json").read_text(encoding="utf-8"))
        super().__init__(regs)
        data = code_guest()
        self.mem[LOAD * 16 + COM_START:LOAD * 16 + COM_START + len(data)] = data
        self.stop_count = 1

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        return self.where(), self.registers(), []


def picture(s: StoppedCode) -> dict[str, Any]:
    where, regs, _held = s.stop_survey()
    return code.stop_instruction(cast(ds.Session, s), where, regs)


def test_a_stop_takes_its_instruction_from_memory() -> None:
    s = StoppedCode("code-stop1")
    got = picture(s)["instruction"]
    assert got == {"seg_off": "0814:00000102", "bytes": "CD03", "text": "int 3", "flow": "call",
                   "code_bits": 16, "bytes_from": "memory",
                   "symbol": {"available": False, "why": "no symbol table is loaded"},
                   "delta": {"available": False, "why": "no symbol table is loaded"}}
    assert s.d_reads == [(LOAD, 0x102, disasm.INSN_MAX)]


def test_comments_that_cannot_be_placed_leave_the_listing_and_the_stop_whole(
        monkeypatch: pytest.MonkeyPatch) -> None:
    probe_machine()
    load_probe_symbols()

    def cannot(_segs: Any) -> dict[int, str]:
        raise ds.Invalid("unexpected_answer", "no SELINFO came back")

    monkeypatch.setattr(dcomments, "notes", cannot)
    r = cast(dict[str, Any], server.disassemble(ref="start", length=4))
    assert r["status"] == "ok" and r["lines"], r


def test_a_stop_on_a_commented_instruction_carries_the_comment() -> None:
    s = StoppedCode("code-stop1")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    assert cast(dict[str, Any], server.comment_write("add", ref="0814:0102", text="the trap"))[
        "status"] == "ok"
    assert running.stop_reply(cast(ds.Session, s))["instruction"]["comment"] == "the trap"
    assert "comment" not in picture(s)["instruction"], "a bare decode knows no comment"


def test_a_stop_reads_its_bytes_in_the_segments_own_width() -> None:
    """`8B 06 34 12` (the SDM's `8B /r` with a 16-bit displacement) at the first stop: in this
    16-bit segment it is one four-byte instruction, never `mov eax, [esi]`."""
    s = StoppedCode("code-stop1")
    s.mem[LOAD * 16 + 0x102:LOAD * 16 + 0x106] = bytes.fromhex("8B063412")
    got = picture(s)["instruction"]
    assert (got["text"], got["bytes"]) == ("mov ax, word ptr [0x1234]", "8B063412"), got


def test_a_stop_near_the_end_of_a_16_bit_segment_reads_no_byte_past_it() -> None:
    s = StoppedCode("code-stop2")
    s.regs["EIP"] = "0000FFFE"
    s.mem[LOAD * 16 + 0xFFFE:LOAD * 16 + 0x10000] = bytes.fromhex("CD03")
    got = picture(s)["instruction"]
    assert got["bytes"] == "CD03" and s.d_reads == [(LOAD, 0xFFFE, 2)]


def test_a_stop_with_no_bytes_to_read_says_why() -> None:
    s = StoppedCode("code-stop2")

    def refused(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        raise ds.Invalid("unexpected_answer", "the debugger did not report a successful dump")
    s.read_bytes = refused  # type: ignore[method-assign]
    got = picture(s)
    assert "did not report a successful dump" in got["instruction"]["why"], got


def test_a_stop_on_a_byte_no_instruction_starts_with_says_so() -> None:
    """The second stop's registers moved to 013C, the guest's `FE /7`."""
    s = StoppedCode("code-stop2")
    s.regs["EIP"] = "0000013C"
    got = picture(s)
    assert "start no instruction" in got["instruction"]["why"], got


def test_a_pr16_stop_decodes_16_bit_from_the_stops_mode() -> None:
    """The first stop read as a `Pr16` stop (its mode changed)."""
    s = StoppedCode("code-stop1")
    where, regs, _held = s.stop_survey()
    got = code.stop_instruction(cast(ds.Session, s), {**where, "mode": "Pr16"},
                                regs)["instruction"]
    assert (got["text"], got["code_bits"]) == ("int 3", 16) and s.asked_selinfo == []


def test_the_stop_names_its_routine_in_real_mode_and_asks_nothing_for_it() -> None:
    s = StoppedCode("code-stop2")
    dstate.STATE.install_table(sym.parse_nm((GUEST / "code.sym").read_text(encoding="ascii")))
    dstate.STATE.base = {"base": LOAD * 16}
    got = picture(s)["instruction"]
    assert (got["symbol"], got["delta"]) == ("inner", 0x167 - 0x15E)
    assert s.asked_selinfo == []


def test_in_protected_mode_the_stop_asks_selinfo_only_with_a_table() -> None:
    """dos-djgpp32's `_engine_pos` stop, its first byte `push ebp` written where it lies."""
    s = pr32_machine()
    where = {"cs": "00A7", "eip": "0005E9C0", "mode": "Pr32"}
    s.mem[0x400000 + 0x5E9C0] = 0x55
    bare = code.stop_instruction(cast(ds.Session, s), where, s.registers())["instruction"]
    assert (bare["text"], bare["code_bits"]) == ("push ebp", 32)
    assert bare["symbol"] == {"available": False, "why": "no symbol table is loaded"}, bare
    assert s.asked_selinfo == []
    dstate.STATE.install_table([sym.Symbol("_engine_pos", 0x5E9C0),
                                sym.Symbol("_engine_end", 0x5EA00)])
    dstate.STATE.base = {"base": 0x400000}
    named = code.stop_instruction(cast(ds.Session, s), where, s.registers())["instruction"]
    assert (named["symbol"], named["delta"]) == ("_engine_pos", 0) and s.asked_selinfo == ["CS"]


def test_every_stop_reply_carries_the_instruction_and_its_record_too() -> None:
    s = StoppedCode("code-stop1")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    reply = running.stop_reply(cast(ds.Session, s))
    assert reply["instruction"]["seg_off"] == "0814:00000102", reply
    recorded = running.recorded_stop_reply(cast(ds.Session, s), {"stop_seq": 1})
    assert recorded["instruction"] == {**reply["instruction"]}
    assert recorded["instruction"] is not reply["instruction"], "the record is handed out"


def test_a_stop_found_on_its_own_pays_for_its_instruction_only_when_a_reply_needs_it() -> None:
    """A stop `status` meets is surveyed and nothing more is read."""
    s = StoppedCode("code-stop1")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    s.stop_count = 2
    running.observe_stop(cast(ds.Session, s))
    assert not {"picture", "instruction"} & set(dstate.STATE.last_stop) and s.d_reads == []
    recorded = running.recorded_stop_reply(cast(ds.Session, s), {"stop_seq": 1})
    assert recorded["instruction"]["bytes_from"] == "memory"
    assert s.d_reads == [(LOAD, 0x102, disasm.INSN_MAX)]


def test_a_stop_found_on_its_own_after_a_replied_stop_carries_its_own_instruction() -> None:
    """The first stop answered by a reply, then the guest stopped on its own at `inner`'s
    `int 3` (the second captured stop): the tail that names that stop decodes it, and never
    hands back the instruction of the stop before."""
    s = StoppedCode("code-stop1")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    assert running.stop_reply(cast(ds.Session, s))["instruction"]["seg_off"] == "0814:00000102"
    s.regs = json.loads((FIX / "code-stop2-registers.json").read_text(encoding="utf-8"))
    s.stop_count = 2
    running.observe_stop(cast(ds.Session, s))
    recorded = running.recorded_stop_reply(cast(ds.Session, s), {"stop_seq": 2})
    assert recorded["instruction"]["seg_off"] == "0814:00000167", recorded["instruction"]
    assert (recorded["pc"], recorded["cpu_mode"]) == ("0814:00000167", "real"), recorded


def test_a_stop_whose_survey_was_cut_carries_no_instruction() -> None:
    s = StoppedCode("code-stop1")
    install()
    dstate.STATE.session = cast(ds.Session, s)

    def cut() -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        raise ds.Invalid("unexpected_answer", "no register pane came back")
    s.stop_survey = cut  # type: ignore[method-assign]
    reply = running.stop_or_base(cast(ds.Session, s), True, {"halted": True})
    assert "instruction" not in reply and reply["enrichment"]["available"] is False, reply


# ------------------------------------------------------------------------ the call stack

def walking(stop: str) -> StoppedCode:
    """The code guest at a captured stop, its stack from that stop's own dump in memory, and
    `code.sym` loaded at the load paragraph."""
    s = StoppedCode(stop)
    ss, sp = int(s.regs["SS"], 16), int(s.regs["ESP"], 16)
    stack = next(FIX.glob(f"{stop}-stack-*.bin")).read_bytes()
    s.mem[ss * 16 + sp:ss * 16 + sp + len(stack)] = stack
    install()
    dstate.STATE.session = cast(ds.Session, s)
    dstate.STATE.install_table(sym.parse_nm((GUEST / "code.sym").read_text(encoding="ascii")))
    dstate.STATE.base = {"base": LOAD * 16}
    return s


def rows(reply: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [(r["seg_off"], r["symbol"], r["via"]) for r in reply["calls"]]


def test_three_frames_deep_the_walk_lists_the_routines_the_guest_entered() -> None:
    """At `inner`'s `int 3`: `inner`, then `middle` (a near call), `outer` (a far call, its row
    in the far pointer's segment) and the main line, each return following a real call; the
    E9 log of the same capture entered `outer`, `middle`, `inner` in that order."""
    walking("code-stop2")
    r = cast(dict[str, Any], server.call_stack())
    assert r["status"] == "ok" and r["heuristic"] is True and r["code_bits"] == 16, r
    assert rows(r) == [("0814:00000167", "inner", "stop"),
                       ("0814:0000015C", "middle", "bp_chain"),
                       ("0814:0000014D", "outer", "bp_chain"),
                       ("0814:0000013A", "known", "bp_chain")]
    assert [c["call"] for c in r["calls"]][1:] == ["call 0x15e", "lcall [0x17f]",
                                                   "call word ptr [0x17d]"]
    assert r["calls"][0]["call"]["available"] is False, r["calls"][0]
    assert [c["bp"] for c in r["calls"]][1:] == ["FFEC", "FFF4", "FFFA"]
    assert r["calls"][0]["bp"]["available"] is False, r["calls"][0]
    assert "outermost" in r["ended_why"] and r["truncated"] is False
    assert r["summary"] == "call_stack: 4 calls, innermost inner, heuristic"


def test_at_a_routines_first_byte_the_caller_is_read_off_the_stack_pointer() -> None:
    """At the breakpoint on `middle`'s `enter`, before its frame exists."""
    walking("middle-bp")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r) == [("0814:0000014F", "middle", "stop"),
                       ("0814:0000014D", "outer", "entry"),
                       ("0814:0000013A", "known", "bp_chain")], r


def test_a_return_is_named_by_the_routine_its_call_is_in() -> None:
    """`call [ptr_outer]` is the last instruction of `known` and returns to `park`'s first byte."""
    walking("code-stop2")
    last = cast(dict[str, Any], server.call_stack())["calls"][-1]
    assert (last["symbol"], last["delta"], last["addr"]) == ("known", 0x13A - 0x104, "0x0000827a")


@pytest.mark.parametrize(("eip", "esp", "why"), [
    (0x140, 0xFFF0, "`push bp` at `outer`'s first byte: the return is at SP"),
    (0x141, 0xFFEE, "`mov bp, sp` right after it: the return is one slot up"),
    (0x14E, 0xFFF0, "`outer`'s `ret`, its frame already left: the return is at SP"),
])
def test_before_a_frame_exists_or_after_it_is_left_the_caller_is_read_off_sp(
        eip: int, esp: int, why: str) -> None:
    """The first stop's double (BP zero) placed in `outer`, its return to the main line written
    at FFF0, where `call [ptr_outer]` left it."""
    s = walking("code-stop1")
    s.regs.update(EIP=f"{eip:08X}", ESP=f"{esp:08X}")
    s.mem[LOAD * 16 + 0xFFF0:LOAD * 16 + 0xFFF2] = (0x13A).to_bytes(2, "little")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r)[1:] == [("0814:0000013A", "known", "entry")], (why, r)


def test_the_entry_rule_holds_with_no_table_and_not_at_a_wrong_delta() -> None:
    s = walking("code-stop1")
    s.regs.update(EIP="00000140", ESP="0000FFF0")
    s.mem[LOAD * 16 + 0xFFF0:LOAD * 16 + 0xFFF2] = (0x13A).to_bytes(2, "little")
    dstate.STATE.forget_symbols()
    assert len(cast(dict[str, Any], server.call_stack())["calls"]) == 2
    dstate.STATE.install_table([sym.Symbol("near_outer", 0x13F)])
    dstate.STATE.base = {"base": LOAD * 16}
    assert len(cast(dict[str, Any], server.call_stack())["calls"]) == 1


def test_a_far_return_is_placed_in_the_segment_its_pointer_named() -> None:
    """`middle`'s far return rewritten as 0813:015D, the same byte as 0814:014D."""
    s = walking("code-stop2")
    s.mem[LOAD * 16 + 0xFFF6:LOAD * 16 + 0xFFFA] = bytes.fromhex("5D011308")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r)[2] == ("0813:0000015D", "outer", "bp_chain"), r


def test_a_read_that_failed_is_said_as_one_not_as_a_missing_call() -> None:
    s = walking("code-stop2")
    stack = s.read_bytes

    def reads(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        if 0x140 <= off < 0x160:          # the code before the first frame's return
            raise ds.Invalid("unexpected_answer", "no data view came back")
        return stack(seg, off, n, mode)
    s.read_bytes = reads  # type: ignore[method-assign]
    r = cast(dict[str, Any], server.call_stack())
    assert r["ended_why"].startswith("a read failed"), r


def test_a_register_the_pane_did_not_show_is_refused_not_a_crash() -> None:
    s = walking("code-stop2")
    del s.regs["EBP"]
    r = cast(dict[str, Any], server.call_stack())
    assert r["status"] == "INVALID" and "EBP" in r["message"], r


def test_a_frame_whose_slots_end_exactly_at_ffff_is_walked() -> None:
    """BP at FFFC with its return at FFFE, the last word of the stack segment."""
    s = walking("code-stop1")
    s.regs["EBP"] = "0000FFFC"
    s.mem[LOAD * 16 + 0xFFFC:LOAD * 16 + 0x10000] = bytes.fromhex("00003A01")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r)[1:] == [("0814:0000013A", "known", "bp_chain")], r


def test_a_far_reading_whose_segment_slot_is_past_the_stack_end_is_no_call() -> None:
    """BP at FFFC, its return 015A at FFFE (inside `leave`, after no call)."""
    s = walking("code-stop1")
    s.regs["EBP"] = "0000FFFC"
    s.mem[LOAD * 16 + 0xFFFC:LOAD * 16 + 0x10000] = bytes.fromhex("00005A01")
    r = cast(dict[str, Any], server.call_stack())
    assert len(r["calls"]) == 1 and "follows no call" in r["ended_why"], r


def test_an_entry_return_one_slot_past_ffff_wraps_to_the_segments_start() -> None:
    """At `outer`'s `mov bp, sp` after its `push bp` with SP at FFFE."""
    s = walking("code-stop1")
    s.regs.update(EIP="00000141", ESP="0000FFFE", EBP="00000000")
    s.mem[LOAD * 16:LOAD * 16 + 2] = (0x13A).to_bytes(2, "little")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r)[1:] == [("0814:0000013A", "known", "entry")], r
    assert "frame pointer is zero" in r["ended_why"], r


def test_a_stop_with_no_frame_lists_itself_and_says_why() -> None:
    walking("code-stop1")
    r = cast(dict[str, Any], server.call_stack())
    assert rows(r) == [("0814:00000102", "start", "stop")]
    assert "frame pointer is zero" in r["ended_why"], r


def test_a_return_that_follows_no_call_ends_the_walk_without_its_row() -> None:
    """The inner stop's stack with `middle`'s return changed to 015A, after `call inner` and
    inside `leave`: no call ends there."""
    s = walking("code-stop2")
    s.mem[LOAD * 16 + 0xFFEE:LOAD * 16 + 0xFFF0] = (0x15A).to_bytes(2, "little")
    r = cast(dict[str, Any], server.call_stack())
    assert len(r["calls"]) == 1 and "follows no call" in r["ended_why"], r


def test_a_saved_frame_pointer_that_does_not_rise_ends_the_walk() -> None:
    """`middle`'s saved BP changed to FFEC, the frame it was read from."""
    s = walking("code-stop2")
    s.mem[LOAD * 16 + 0xFFF4:LOAD * 16 + 0xFFF6] = (0xFFEC).to_bytes(2, "little")
    r = cast(dict[str, Any], server.call_stack())
    assert [c["symbol"] for c in r["calls"]] == ["inner", "middle", "outer"], r
    assert "does not rise" in r["ended_why"], r


def test_a_frame_at_the_end_of_the_stack_segment_ends_the_walk() -> None:
    s = walking("code-stop1")
    s.regs["EBP"] = "0000FFFE"
    s.mem[LOAD * 16 + 0xFFFE:LOAD * 16 + 0x10000] = bytes(2)
    r = cast(dict[str, Any], server.call_stack())
    assert len(r["calls"]) == 1 and "past the end of the stack segment" in r["ended_why"], r


def test_a_return_outside_the_table_is_listed_and_ends_the_walk() -> None:
    """The table cut to `outer`, `middle` and `inner`: the main line's return lies below it."""
    walking("code-stop2")
    dstate.STATE.install_table([s for s in dstate.STATE.table
                                if s.name in ("outer", "middle", "inner")])
    r = cast(dict[str, Any], server.call_stack())
    assert r["calls"][-1]["seg_off"] == "0814:0000013A"
    assert r["calls"][-1]["symbol"]["available"] is False
    dstate.STATE.install_table([])
    bare = cast(dict[str, Any], server.call_stack())
    assert bare["summary"].startswith(f"call_stack: {len(bare['calls'])} calls, innermost "
                                      f"{bare['calls'][0]['seg_off']},"), bare["summary"]
    assert "outside the loaded symbol table" in r["ended_why"], r


def test_an_entry_return_outside_the_table_is_listed_and_ends_the_walk() -> None:
    """At `outer`'s first byte with the table cut to `outer`, `middle` and `inner`."""
    s = walking("code-stop1")
    s.regs.update(EIP="00000140", ESP="0000FFF0")
    s.mem[LOAD * 16 + 0xFFF0:LOAD * 16 + 0xFFF2] = (0x13A).to_bytes(2, "little")
    dstate.STATE.install_table([x for x in dstate.STATE.table
                                if x.name in ("outer", "middle", "inner")])
    r = cast(dict[str, Any], server.call_stack())
    assert [c["via"] for c in r["calls"]] == ["stop", "entry"]
    assert r["calls"][1]["symbol"]["available"] is False
    assert "outside the loaded symbol table" in r["ended_why"], r


def test_a_walk_that_never_ends_stops_at_its_bound() -> None:
    """A stack of frames each pointing one frame up and each returning past `call inner`,
    built from the inner stop's first frame repeated: the walk lists its bound and says so."""
    s = walking("code-stop2")
    for k in range(code.CALL_STACK_MAX + 2):
        at = 0x8000 + 4 * k
        s.mem[LOAD * 16 + at:LOAD * 16 + at + 4] = (at + 4).to_bytes(2, "little") + \
            (0x15C).to_bytes(2, "little")
    s.regs["EBP"] = "00008000"
    r = cast(dict[str, Any], server.call_stack())
    assert len(r["calls"]) == code.CALL_STACK_MAX and r["truncated"] is True, r


def test_a_call_site_is_checked_in_32_bit_code_as_well() -> None:
    """`call rel32` (E8, the SDM's encoding) ending at the return."""
    memory = {0x1000 - code.CALL_LONGEST + i: b for i, b in
              enumerate(bytes.fromhex("9090E810000000"))}

    def read_bytes(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        return bytes(memory.get(off + i, 0) for i in range(n))
    views = code._Views(cast(ds.Session, SimpleNamespace(read_bytes=read_bytes)), "Pr32", 1 << 32)
    near = code.call_ending_at(views, 0xA7, 0x1000, 32, far=False)
    assert near is not None and near.text == "call 0x1010"
    assert code.call_ending_at(views, 0xA7, 0x1000, 32, far=True) is None


def test_when_two_calls_end_at_a_return_the_longer_is_the_one_named() -> None:
    """`FF 16 FF D3` ends in `call bx` (FF D3) and is itself `call [D3FF]` (the SDM's FF /2
    forms): both end at the return, and the rule takes the longer one, the reading that starts
    further back."""
    memory = {0x100 - code.CALL_LONGEST + i: b for i, b in
              enumerate(bytes.fromhex("909090FF16FFD3"))}

    def read_bytes(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        return bytes(memory.get(off + i, 0) for i in range(n))
    views = code._Views(cast(ds.Session, SimpleNamespace(read_bytes=read_bytes)), "Real", 1 << 16)
    got = code.call_ending_at(views, LOAD, 0x100, 16, far=False)
    assert got is not None and got.text == "call word ptr [0xd3ff]"


def test_a_call_at_the_very_start_of_a_segment_is_found() -> None:
    """`call far 0895:0006` (9A, the SDM's ptr16:16 form) at offset 0000 returns to 0005."""
    memory = dict(enumerate(bytes.fromhex("9A06009508")))

    def read_bytes(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        return bytes(memory.get(off + i, 0) for i in range(n))
    views = code._Views(cast(ds.Session, SimpleNamespace(read_bytes=read_bytes)), "Real", 1 << 16)
    got = code.call_ending_at(views, LOAD, 5, 16, far=True)
    assert got is not None and got.offset == 0, got


def test_a_view_is_never_asked_past_the_end_of_its_segment() -> None:
    """Sixteen bytes asked at FFF8 of a 16-bit segment."""
    asked: list[tuple[int, int]] = []

    def read_bytes(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        asked.append((off, n))
        return bytes(range(1, n + 1))
    views = code._Views(cast(ds.Session, SimpleNamespace(read_bytes=read_bytes)), "Real", 1 << 16)
    assert views.read(LOAD, 0xFFF8, 16) == bytes(range(1, 9)) and asked == [(0xFFF8, 8)]


def test_reads_are_reused_while_one_view_covers_them() -> None:
    s = walking("code-stop2")
    server.call_stack()
    assert len(s.d_reads) == len(set(s.d_reads)), s.d_reads


def test_call_stack_is_a_step_of_perform_beside_disassemble() -> None:
    walking("code-stop2")
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "disassemble", "ref": "inner", "length": 8}, {"op": "call_stack"}]))
    assert r["status"] == "ok" and r["steps_completed"] == 2, r
