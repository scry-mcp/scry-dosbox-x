"""`tests/live/bench_programs.py` on no machine: a session conf derived from a project's run conf
on a bench of the test's own, and the refusal when the conf is not the shape the edits expect."""
from __future__ import annotations

import importlib.util
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
..\\exes\\speedf.exe
exit
"""


def _programs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """The module loaded with its bench at `tmp_path / "bench"`, Speed Fight's run conf on it."""
    monkeypatch.setenv("DOSBOX_X_LIVE_BENCH", str(tmp_path / "bench"))
    spec = importlib.util.spec_from_file_location("bench_programs", LIVE / "bench_programs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "bench_programs", module)
    spec.loader.exec_module(module)
    conf = tmp_path / "bench/speedf/SCRIPTS/dosbox-run.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text(RUN_CONF)
    return module


def test_a_session_conf_runs_the_stub_before_the_path_and_launches_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    out = bp.session_conf(bp.SPEEDF, tmp_path / "scratch")
    assert out.parent == tmp_path / "scratch"
    assert out.read_text().split("[autoexec]\n")[1] == (
        f'mount c "."\nmount g "{bp.STUB_DIR}"\nG:\\INJECT.COM\nset PATH=C:\\UTILS\nc:\n'
        "cd SOURCE\n\n")


@pytest.mark.parametrize(("old", "new", "what"), [
    ("..\\exes\\speedf.exe\n", "", "speedf"),
    ("exit\n", "", "exit"),
    ("set PATH=C:\\UTILS\n", "", "set"),
    ("exit\n", "exit\nexit\n", "exit"),
    ("..\\exes\\speedf.exe\n", "..\\exes\\speedf.exe\n..\\exes\\speedf.exe\n", "speedf"),
])
def test_a_run_conf_not_of_the_expected_shape_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str, what: str,
) -> None:
    """An edit that matched nothing, or a line the edits expect once found twice, would run the
    project's conf under the session's name: refused, naming the line."""
    bp = _programs(monkeypatch, tmp_path)
    conf = tmp_path / "bench/speedf/SCRIPTS/dosbox-run.conf"
    conf.write_text(RUN_CONF.replace(old, new, 1))
    with pytest.raises(RuntimeError, match=what):
        bp.session_conf(bp.SPEEDF, tmp_path / "scratch")


def test_a_public_is_read_off_the_map_with_its_mark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    mapf = tmp_path / "bench/speedf/EXES/SPEEDF.MAP"
    mapf.parent.mkdir(parents=True)
    mapf.write_text("  Address         Publics by Name\n\n 0DB5:00E25 idle  ACTIVEIMAN\n"
                    " 0D11:00000       COMPOSE_FRAME\n")
    assert bp.public(bp.SPEEDF, "ACTIVEIMAN") == (0xDB5, 0xE25, True)
    assert bp.public(bp.SPEEDF, "COMPOSE_FRAME") == (0xD11, 0, False)
    with pytest.raises(RuntimeError, match="no public NOPE"):
        bp.public(bp.SPEEDF, "NOPE")


def test_a_program_off_its_pins_is_a_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    monkeypatch.setattr(bp, "BENCH_MANIFEST", tmp_path / "bench.json")
    (tmp_path / "bench.json").write_text(
        '[{"path": "speedf/EXES/SPEEDF.EXE", "sha256": "", "source_repo": "s", '
        '"source_path": "EXES/SPEEDF.EXE", "source_commit": ""}]')
    assert bp.missing(bp.SPEEDF).startswith("bench MISSING speedf/EXES/SPEEDF.EXE")


LINEUP_RUN = """[cpu]
core     = dynamic
cycles   = max
[autoexec]
mount c "."
set PATH=C:\\BC\\BIN
c:
EXES\\LINEUP.EXE
exit
"""


def _lineup(bp: ModuleType, tmp_path: Path, gold: str) -> None:
    scripts = tmp_path / "bench/lineup/SCRIPTS"
    scripts.mkdir(parents=True)
    (scripts / "dosbox-x-run.conf").write_text(LINEUP_RUN)
    (scripts / "dosbox-x-gold.conf").write_text(gold)


def test_line_up_takes_its_fixed_clock_from_its_gold_conf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Its run conf plays at `cycles = max`; a session asks questions whose answer is the guest's
    clock, so it takes the gold conf's fixed one, as its project's own session conf does."""
    bp = _programs(monkeypatch, tmp_path)
    _lineup(bp, tmp_path, "[cpu]\ncycles   = fixed 50000\n")
    text = bp.session_conf(bp.LINEUP, tmp_path / "scratch").read_text()
    assert "cycles   = fixed 50000" in text and "max" not in text
    assert "EXES\\LINEUP.EXE" not in text and "\nexit" not in text


@pytest.mark.parametrize("gold", ["[cpu]\ncycles = max\n", "[cpu]\n",
                                  "cycles = fixed 1\ncycles = fixed 2\n"])
def test_a_clock_conf_without_one_fixed_cycles_line_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gold: str,
) -> None:
    bp = _programs(monkeypatch, tmp_path)
    _lineup(bp, tmp_path, gold)
    with pytest.raises(RuntimeError, match="one fixed `cycles` line"):
        bp.session_conf(bp.LINEUP, tmp_path / "scratch")
