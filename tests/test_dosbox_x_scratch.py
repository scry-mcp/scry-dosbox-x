"""The host scratch this server and its suite make, and where each goes: a session's with the
session, through `close`; the server process's batches and a session it never closed with the
process; the suite's own declaration store with the test run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)

from scry_dosbox_x import server
from scry_dosbox_x import state as dstate

ROOT = Path(__file__).resolve().parents[1]


def _left(tmp: Path, prefix: str) -> list[str]:
    return sorted(p.name for p in tmp.iterdir() if p.name.startswith(prefix))


def _exits(tmp: Path, body: str) -> str:
    """`body` run in a process of its own whose TMPDIR is `tmp`, ending normally: its stdout."""
    env = {**os.environ, "TMPDIR": f"{tmp}{os.sep}"}
    code = f"import sys; sys.path[:0] = {[str(ROOT / 'tests')]!r}\n{body}"
    run = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, capture_output=True,
                         text=True, timeout=120, check=False)
    assert run.returncode == 0, run.stderr
    return run.stdout


def test_close_takes_the_sessions_scratch_with_it() -> None:
    install()
    scratch = dstate.STATE.session_scratch()
    (scratch / "frame.png").write_bytes(b"x")
    got = cast(dict[str, Any], server.close())
    assert got["closed"] is True
    assert not scratch.exists() and dstate.STATE.session_dir is None


def test_a_server_process_leaves_neither_its_batches_nor_an_unclosed_session_behind(
        tmp_path: Path) -> None:
    made = _exits(tmp_path, "from scry_dosbox_x import state as d\n"
                            "(d.STATE.batch_scratch() / 'b.bat').write_text('x')\n"
                            "(d.STATE.session_scratch() / 'f.png').write_bytes(b'x')\n"
                            "print(d.STATE.scratch.parent, d.STATE.session_dir.parent)\n")
    assert made.split() == [str(tmp_path)] * 2, "the scratch was not made where it is looked for"
    assert _left(tmp_path, "dosbox-x-") == []


def test_the_suites_declaration_store_goes_with_the_test_run(tmp_path: Path) -> None:
    made = _exits(tmp_path, "import dosbox_x_server_support as t\nt.install()\n"
                            "print(__import__('pathlib').Path(t._STORE_TMP).parent)\n")
    assert made.split() == [str(tmp_path)], "the store was not made where it is looked for"
    assert _left(tmp_path, "dosbox-x-") == []
