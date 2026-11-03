"""However the server ends (stdin closed, SIGTERM, SIGHUP), its DOSBox-X ends with it."""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import live_private  # isort: skip -- first: a pooled job's working copies
import pytest
from scry_core import guardian, process_tree

from scry_dosbox_x import process as dprocess

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
BRICKS = live_private.bricks_dir()
#: Past the close's own grace (`Session.close`), with room for the server to get there.
GONE_WITHIN_S = 20.0
#: A silent server fails the case instead of hanging it.
ANSWER_WITHIN_S = 90.0


def _rpc(proc: subprocess.Popen[bytes], mid: int, method: str, params: dict[str, Any]) -> Any:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                  "params": params}) + "\n").encode())
    proc.stdin.flush()
    while line := proc.stdout.readline():
        message = json.loads(line)
        if message.get("id") == mid:
            return message
    raise AssertionError(f"the server closed its stdout before answering {method}")


def _call(proc: subprocess.Popen[bytes], mid: int, tool: str, **arguments: Any) -> dict[str, Any]:
    body: dict[str, Any] = _rpc(proc, mid, "tools/call", {
        "name": tool, "arguments": arguments})["result"]["structuredContent"]
    return body


def _guardians_of(server_pid: int) -> list[int]:
    """The pids of the server's children named as the guardian is: the process table's own
    answer, so another server on this machine is never counted."""
    table = subprocess.run(["ps", "-c", "-axo", "pid=,ppid=,comm="], capture_output=True,
                           text=True, check=True).stdout.splitlines()
    rows = [line.split(None, 2) for line in table]
    return [int(r[0]) for r in rows
            if len(r) == 3 and r[1] == str(server_pid) and r[2] == dprocess.GUARDIAN_NAME]


def _put_in_state(proc: subprocess.Popen[bytes], state: str) -> None:
    """`start` parks the session stopped; the other two states are made from it."""
    if state == "running":
        assert _call(proc, 10, "resume")["status"] == "ok"
    elif state == "altered":
        got = _call(proc, 10, "set_register", name="ax", value=0x1234)
        assert got["status"] == "ok" and got["session"]["altered"] is True, got


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals and process sessions")
@pytest.mark.parametrize("state", ["stopped", "running", "altered"])
@pytest.mark.parametrize("ended_by, code", [("close", 0), ("stdin", 0),
                                             ("SIGTERM", 128 + signal.SIGTERM),
                                             ("SIGHUP", 128 + getattr(signal, "SIGHUP", 0))])
def test_the_emulator_ends_with_the_server(ended_by: str, code: int, state: str,
                                           tmp_path: Path) -> None:
    errors = tmp_path / "server.stderr"
    with errors.open("wb") as err:
        proc = subprocess.Popen([sys.executable, "-m", "scry_dosbox_x.server"], cwd=ROOT,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
    silent = threading.Timer(ANSWER_WITHIN_S, proc.kill)
    silent.start()
    pid = None
    try:
        _rpc(proc, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "exit-live", "version": "0"}})
        assert proc.stdin is not None
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        started = _rpc(proc, 2, "tools/call", {"name": "start", "arguments": {
            "conf": str(BRICKS / "bricks.conf"), "cwd": str(BRICKS), "session_seconds": 120}})
        body = started["result"]["structuredContent"]
        assert body["status"] == "ok", body.get("summary")
        pid = body["pid"]
        assert process_tree.pid_alive(pid), "the emulator the start reported is not running"
        # the control: the table must show the guardian while the session is up, or its absence
        # after the end proves nothing
        guards = _guardians_of(proc.pid)
        assert guards, "no guardian beside a live session"
        _put_in_state(proc, state)
        if ended_by == "close":
            closed = _call(proc, 11, "close")
            assert closed["closed"] is True and closed["exit_code"] == 0, (state, closed)
            proc.stdin.close()
        elif ended_by == "stdin":
            proc.stdin.close()
        else:
            proc.send_signal(getattr(signal, ended_by))
        deadline = time.monotonic() + GONE_WITHIN_S
        while process_tree.pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        # `Z` in ps is an emulator gone and not yet reaped; a live server is an unfinished close.
        seen = subprocess.run(["ps", "-o", "pid=,stat=,etime=", "-p", f"{pid},{proc.pid}"],
                              capture_output=True, text=True, check=False).stdout.strip()
        assert not process_tree.pid_alive(pid), (
            f"DOSBox-X {pid} outlived a server ended by {ended_by} in state {state} by "
            f"{GONE_WITHIN_S:g} s; ps: {seen or 'nothing'}; "
            f"server: {errors.read_text(errors='replace')[-600:]}")
        assert proc.wait(GONE_WITHIN_S) == code, errors.read_text(errors="replace")[-600:]
        # by the pid seen while the server lived: a guardian that outlives it is reparented, so
        # a lookup by parent would no longer list it
        left = [g for g in guards if process_tree.pid_alive(g)]
        assert not left, f"a guardian outlived the server, state {state}: {left}"
    finally:
        silent.cancel()
        if pid is not None and process_tree.pid_alive(pid):
            dprocess.signal_group(pid, guardian.KILL)
        if proc.poll() is None:
            proc.kill()
