"""`tests/live/bench_programs.py` on no machine: a session conf derived from a project's run conf
on a bench of the test's own, and the refusal when the conf is not the shape the edits expect."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

LIVE = Path(__file__).resolve().parent / "live"

RUN_CONF = """[dosbox]
memsize = 16
[autoexec]
mount c "."
set PATH=C:\\UTILS
c:
cd SOURCE
..\\exes\\real.exe
exit
"""

#: An identity of the test's own, in the bench's shape: the values are invented here, so nothing
#: a test asserts depends on what the developer's bench names.
IDENTITY: dict[str, dict[str, str]] = {
    "dos-real16": {"dir": "real", "exe": "EXES/REAL.EXE", "map": "EXES/REAL.MAP",
                   "launch": "..\\exes\\real.exe", "process": "REAL", "e9_line": "real: up"},
    "dos-real16-alt": {"dir": "alt", "exe": "EXES/ALT.EXE", "map": "EXES/ALT.MAP",
                       "launch": "EXES\\ALT.EXE", "process": "ALT", "e9_line": "alt: up"},
}


def _programs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
              identity: object = IDENTITY) -> ModuleType:
    """The module loaded with its bench at `tmp_path / "bench"` holding `identity` as its
    `identity.json` (None: no file; a string: the file's text), and the real-mode program's run
    conf on it."""
    monkeypatch.setenv("DOSBOX_X_LIVE_BENCH", str(tmp_path / "bench"))
    (tmp_path / "bench").mkdir()
    if identity is not None:
        text = identity if isinstance(identity, str) else json.dumps(identity)
        (tmp_path / "bench/identity.json").write_text(text)
    spec = importlib.util.spec_from_file_location("bench_programs", LIVE / "bench_programs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "bench_programs", module)
    spec.loader.exec_module(module)
    conf = tmp_path / "bench/real/SCRIPTS/dosbox-run.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text(RUN_CONF)
    return module


def test_a_session_conf_runs_the_stub_before_the_path_and_launches_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    out = bp.session_conf(bp.DOS_REAL16, tmp_path / "scratch")
    assert out.parent == tmp_path / "scratch"
    assert out.read_text().split("[autoexec]\n")[1] == (
        f'mount c "."\nmount g "{bp.STUB_DIR}"\nG:\\INJECT.COM\nset PATH=C:\\UTILS\nc:\n'
        "cd SOURCE\n\n")


@pytest.mark.parametrize(("old", "new", "what"), [
    ("..\\exes\\real.exe\n", "", "real"),
    ("exit\n", "", "exit"),
    ("set PATH=C:\\UTILS\n", "", "set"),
    ("exit\n", "exit\nexit\n", "exit"),
    ("..\\exes\\real.exe\n", "..\\exes\\real.exe\n..\\exes\\real.exe\n", "real"),
])
def test_a_run_conf_not_of_the_expected_shape_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str, what: str,
) -> None:
    """An edit that matched nothing, or a line the edits expect once found twice, would run the
    project's conf under the session's name: refused, naming the line."""
    bp = _programs(monkeypatch, tmp_path)
    conf = tmp_path / "bench/real/SCRIPTS/dosbox-run.conf"
    conf.write_text(RUN_CONF.replace(old, new, 1))
    with pytest.raises(RuntimeError, match=what):
        bp.session_conf(bp.DOS_REAL16, tmp_path / "scratch")


def test_a_public_is_read_off_the_map_with_its_mark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    mapf = tmp_path / "bench/real/EXES/REAL.MAP"
    mapf.parent.mkdir(parents=True)
    mapf.write_text("  Address         Publics by Name\n\n 0DB5:00E25 idle  ACTIVEIMAN\n"
                    " 0D11:00000       COMPOSE_FRAME\n")
    assert bp.public(bp.DOS_REAL16, "ACTIVEIMAN") == (0xDB5, 0xE25, True)
    assert bp.public(bp.DOS_REAL16, "COMPOSE_FRAME") == (0xD11, 0, False)
    with pytest.raises(RuntimeError, match="no public NOPE"):
        bp.public(bp.DOS_REAL16, "NOPE")


def test_a_program_off_its_pins_is_a_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    assert tmp_path / "bench/bench.json" == bp.BENCH_MANIFEST, "the manifest is the bench's own"
    (tmp_path / "bench/bench.json").write_text(
        '[{"path": "real/EXES/REAL.EXE", "sha256": "", "source_repo": "s", '
        '"source_path": "EXES/REAL.EXE", "source_commit": ""}]')
    assert bp.missing(bp.DOS_REAL16).startswith("bench MISSING real/EXES/REAL.EXE")


def test_every_value_naming_a_program_comes_from_the_benchs_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The tracked code names a program by its label; its directory, build, launch line, memory
    block and E9 line are the identity's."""
    bp = _programs(monkeypatch, tmp_path)
    p = bp.DOS_REAL16
    held = (p.root, p.exe, p.map, p.launch, p.process, p.e9_line)
    assert held == (tmp_path / "bench/real", "EXES/REAL.EXE", "EXES/REAL.MAP",
                    "..\\exes\\real.exe", "REAL", "real: up")
    assert bp.DOS_REAL16_ALT.root == tmp_path / "bench/alt"


@pytest.mark.parametrize(("identity", "why"), [
    (None, r"identity ABSENT: write .*identity\.json beside bench\.json"),
    ("{", r"identity UNREADABLE .*: write .*identity\.json"),
    ([], r"identity NOT AN OBJECT OF OBJECTS: write"),
    ({"dos-real16-alt": IDENTITY["dos-real16-alt"]},
     r"identity names no 'dos-real16': add it to .*identity\.json with dir, exe"),
    ({**IDENTITY,
      "dos-real16": {k: v for k, v in IDENTITY["dos-real16"].items() if k != "e9_line"}},
     r"identity dos-real16\.e9_line is None, not a non-empty string: set it in"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "launch": ["x"]}},
     r"identity dos-real16\.launch is \['x'\], not a non-empty string"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "launch": ""}},
     r"identity dos-real16\.launch is '', not a non-empty string"),
    ({**IDENTITY, "dos-real16": "real"}, r"identity NOT AN OBJECT OF OBJECTS: write"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "dir": "a/real"}},
     r"identity dos-real16\.dir is 'a/real', not one directory name"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "process": "Real"}},
     r"identity dos-real16\.process is 'Real', not a DOS name of at most eight capitals"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "process": "REALPROGS"}},
     r"identity dos-real16\.process is 'REALPROGS', not a DOS name"),
    ({**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "e9_line": "r\u00e9al \u2192 up"}},
     r"identity dos-real16\.e9_line is not Latin-1"),
])
def test_an_identity_that_cannot_name_a_program_blocks_it_with_the_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, identity: object, why: str,
) -> None:
    """A missing file, a missing key and a wrong type each make the program a reason naming what
    to write where, and no value it would run on is a guess."""
    bp = _programs(monkeypatch, tmp_path, identity)
    assert re.match(why, bp.missing(bp.DOS_REAL16)), bp.missing(bp.DOS_REAL16)
    assert (bp.DOS_REAL16.exe, bp.DOS_REAL16.launch, bp.DOS_REAL16.process) == ("", "", "")


def test_a_bench_with_no_manifest_says_it_is_kept_only_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`fill` and `check` both read the manifest, so neither can be the remedy for its absence;
    an eight-capital name and a Latin-1 line are a usable identity."""
    held = {**IDENTITY, "dos-real16": {**IDENTITY["dos-real16"], "process": "REALPROG",
                                       "e9_line": "r\u00e9al: up"}}
    bp = _programs(monkeypatch, tmp_path, held)
    assert bp.missing(bp.DOS_REAL16).startswith(
        f"bench manifest ABSENT: {tmp_path / 'bench/bench.json'} pins every copy and is kept "
        "only in the bench")


def _pinned(tmp_path: Path, files: tuple[str, ...]) -> None:
    """`files`, each under the bench with two bytes of its own, as the bench's whole manifest."""
    pins = []
    for f in files:
        path = tmp_path / "bench" / f
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(b"MZ")
        pins.append({"path": f, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "source_repo": "s", "source_path": f, "source_commit": ""})
    (tmp_path / "bench/bench.json").write_text(json.dumps(pins))


@pytest.mark.parametrize("left_out", ["real/EXES/REAL.EXE", "real/EXES/REAL.MAP",
                                      "real/SCRIPTS/dosbox-run.conf"])
def test_a_file_the_program_opens_that_the_manifest_does_not_pin_is_a_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, left_out: str,
) -> None:
    """A file opened unpinned would be read unchecked: the build, the map and the run conf must
    each be one the manifest pins; with all three pinned the program can run."""
    bp = _programs(monkeypatch, tmp_path)
    every = ("real/EXES/REAL.EXE", "real/EXES/REAL.MAP", "real/SCRIPTS/dosbox-run.conf")
    _pinned(tmp_path, tuple(f for f in every if f != left_out))
    assert bp.missing(bp.DOS_REAL16) == (
        f"program dos-real16 opens {left_out}, which {bp.BENCH_MANIFEST} does not pin: pin it "
        "there, or name a file it pins")
    bp._reasons.clear()
    _pinned(tmp_path, every)
    assert bp.missing(bp.DOS_REAL16) == ""


def test_the_alt_program_opens_its_clock_conf_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    assert bp.opened(bp.DOS_REAL16_ALT) == ["alt/EXES/ALT.EXE", "alt/EXES/ALT.MAP",
                                    "alt/SCRIPTS/dosbox-x-run.conf",
                                    "alt/SCRIPTS/dosbox-x-gold.conf"]


@pytest.mark.parametrize("key", list(IDENTITY["dos-real16"]))
def test_every_key_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str) -> None:
    held = {lb: dict(v) for lb, v in IDENTITY.items()}
    del held["dos-real16"][key]
    bp = _programs(monkeypatch, tmp_path, held)
    assert bp.missing(bp.DOS_REAL16) == (
        f"identity dos-real16.{key} is None, not a non-empty string: set it in "
        f"{tmp_path / 'bench/identity.json'}")


def test_a_label_or_key_the_code_does_not_declare_is_its_mistake_on_every_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """With no identity at all a misspelt label must not pass for one the bench lacks."""
    bp = _programs(monkeypatch, tmp_path, None)
    with pytest.raises(KeyError, match="dos-real61"):
        bp.missing(bp.Program("dos-real61", "x.conf"))
    with pytest.raises(KeyError, match=r"dos-real16\.e9\b"):
        bp.value("dos-real16", "e9")


DOS_REAL16_ALT_RUN = """[cpu]
core     = dynamic
cycles   = max
[autoexec]
mount c "."
set PATH=C:\\BC\\BIN
c:
EXES\\ALT.EXE
exit
"""


def _dos_real16_alt(bp: ModuleType, tmp_path: Path, gold: str) -> None:
    scripts = tmp_path / "bench/alt/SCRIPTS"
    scripts.mkdir(parents=True)
    (scripts / "dosbox-x-run.conf").write_text(DOS_REAL16_ALT_RUN)
    (scripts / "dosbox-x-gold.conf").write_text(gold)


def test_line_up_takes_its_fixed_clock_from_its_gold_conf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Its run conf plays at `cycles = max`; a session asks questions whose answer is the guest's
    clock, so it takes the gold conf's fixed one, as its project's own session conf does."""
    bp = _programs(monkeypatch, tmp_path)
    _dos_real16_alt(bp, tmp_path, "[cpu]\ncycles   = fixed 50000\n")
    text = bp.session_conf(bp.DOS_REAL16_ALT, tmp_path / "scratch").read_text()
    assert "cycles   = fixed 50000" in text and "max" not in text
    assert "EXES\\ALT.EXE" not in text and "\nexit" not in text


@pytest.mark.parametrize("gold", ["[cpu]\ncycles = max\n", "[cpu]\n",
                                  "cycles = fixed 1\ncycles = fixed 2\n"])
def test_a_clock_conf_without_one_fixed_cycles_line_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gold: str,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    _dos_real16_alt(bp, tmp_path, gold)
    with pytest.raises(RuntimeError, match="one fixed `cycles` line"):
        bp.session_conf(bp.DOS_REAL16_ALT, tmp_path / "scratch")
