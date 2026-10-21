"""A pooled live job works in copies of its own, the bricks demo's included (`live_private`): two
jobs started side by side never hand their emulators one working directory."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

LIVE = Path(__file__).resolve().parent / "live"
REPO = LIVE.parents[1]
#: What a job prints of its copies: the guests' and the demo's directories, whether the demo's
#: conf is there, and whether its `../../guest` mount reaches the stub.
ASK = ("import live_private as p; print(p.guest_dir()); print(p.bricks_dir()); "
       "print((p.bricks_dir() / 'bricks.conf').is_file()); "
       "print((p.bricks_dir() / '..' / '..' / 'guest' / 'INJECT.COM').resolve().is_file())")
#: The one live file that names the repository's own demo directory: it runs the demo whole,
#: windowed, alone after the pool, and compares its output with the files committed there.
SERIAL_DEMO = "test_bricks_demo_live.py"


def _env(tmp_path: Path, private: bool) -> dict[str, str]:
    """This process's environment with no live variable of its own, the bench an empty
    directory (a job copies the bench it is pointed at), and the pool's mark when `private`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DOSBOX_X_LIVE_")}
    (tmp_path / "bench").mkdir(exist_ok=True)
    env["DOSBOX_X_LIVE_BENCH"] = str(tmp_path / "bench")
    if private:
        env["DOSBOX_X_LIVE_PRIVATE"] = "1"
    return env


def _job(tmp_path: Path, private: bool) -> list[str]:
    done = subprocess.run([sys.executable, "-c", ASK], cwd=LIVE, env=_env(tmp_path, private),
                          capture_output=True, text=True, check=True)
    return done.stdout.splitlines()


def test_two_pooled_jobs_start_their_emulators_in_directories_of_their_own(
        tmp_path: Path) -> None:
    one, two = _job(tmp_path, True), _job(tmp_path, True)
    assert one[0] != two[0] and one[1] != two[1], (one, two)
    for job in (one, two):
        assert not Path(job[1]).is_relative_to(REPO), job
        assert job[2:] == ["True", "True"], f"the copy is not a runnable demo: {job}"
        assert not Path(job[1]).exists(), "a job's copies outlived it"


def test_outside_the_pool_the_tests_start_in_the_repository(tmp_path: Path) -> None:
    alone = _job(tmp_path, False)
    assert alone[:2] == [str(REPO / "tests" / "guest"), str(REPO / "demos" / "bricks")]


def _bricks_users() -> list[str]:
    """Every live file that names the bricks demo's directory, read off the files themselves."""
    named = re.compile(r'"demos"\s*/\s*"bricks"|bricks_dir\(\)|\bBRICKS\b')
    return sorted(p.stem for p in LIVE.glob("test_*.py")
                  if p.name != SERIAL_DEMO and named.search(p.read_text(encoding="utf-8")))


def test_every_pooled_live_file_that_uses_the_demo_takes_the_jobs_copy(tmp_path: Path) -> None:
    users = _bricks_users()
    assert len(users) >= 4, f"the scan found too few bricks users to be reading the files: {users}"
    for stem in users:
        text = (LIVE / f"{stem}.py").read_text(encoding="utf-8")
        assert '"demos" / "bricks"' not in text, f"{stem} spells the repository's own directory"
    env = _env(tmp_path, True)
    env["PYTHONPATH"] = os.pathsep.join([str(LIVE), str(REPO), env.get("PYTHONPATH", "")])
    ask = "; ".join(f"import {m}; print({m}.BRICKS)" for m in users)
    done = subprocess.run([sys.executable, "-c", ask], cwd=REPO, env=env, capture_output=True,
                          text=True, check=True)
    used = done.stdout.splitlines()
    assert len(used) == len(users), done.stdout
    shared = [m for m, u in zip(users, used, strict=True) if Path(u).is_relative_to(REPO)]
    assert not shared, f"started in the repository's own directory: {shared}"
