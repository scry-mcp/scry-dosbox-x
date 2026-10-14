"""What `scry_core.probe` judges with this server's own surface: the task set and its captures,
the server's pre-gate check, and the texts the client delivers.

The engine itself is the core's and is judged there on frozen surfaces; what needs the real server
(its whole roster, its own `check`, every task as real runs answered it) is judged here.
`captured/dosbox-x/` holds every task as real runs answered it, one file per task.
"""

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scry_core import probe
from scry_core.client_cap import over_the_cap

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mcp_probe"

# At collection: `servers.load` says why.
probe.configure(ROOT / "mcp_probe" / "servers.py", ROOT / "mcp_probe" / "tasks")
SURFACE = probe.load_surface("dosbox-x")


def _tasks() -> list[dict[str, Any]]:
    text = (FIXTURES / "tasks" / "dosbox-x.json").read_text()
    doc: dict[str, list[dict[str, Any]]] = json.loads(text)
    return doc["tasks"]


def _narrowed() -> probe.Surface:
    """The real surface, narrowed to the tools the fixture tasks name: real descriptions, real
    signatures, the server's real `check`."""
    names = {probe.on_tool(t) for t in _tasks()}
    tools = {n: t for n, t in SURFACE.tools.items() if n in names}
    return dataclasses.replace(SURFACE, tools=tools)


def _judge(task_id: str, line: str) -> probe.Verdict:
    task = next(t for t in _tasks() if t["id"] == task_id)
    return probe.judge(_narrowed(), task, probe.parse(line, [task_id])[task_id])


def test_the_tasks_cover_the_server(capsys: pytest.CaptureFixture[str]) -> None:
    assert probe.check(("dosbox-x",)) == probe.EXIT_PASS, capsys.readouterr().out


def test_every_task_is_captured_and_judged_as_it_was() -> None:
    """Every task of the server, at the size a real run answers: each task's capture, judged
    again against the whole surface and the server's own check, gives back the verdicts
    recorded when it ran, and a task with no capture is named."""
    assert probe.capture_problems("dosbox-x", probe.CAPTURED_ROOT / "dosbox-x",
                                  probe.TASKS_DIR / "dosbox-x.json") == []


@pytest.mark.parametrize(("line", "refusal"), [
    ('D1: {"tool": "step", "args": {"mode": "into", "count": 3}}', None),
    ('D1: {"tool": "step", "args": {"mode": "into", "count": 3, "e9": "sideways"}}',
     "the server's check refuses it"),
])
def test_the_servers_own_check_judges_the_call(line: str, refusal: str | None) -> None:
    verdict = _judge("D1", line)
    assert verdict.right is (refusal is None), verdict
    if refusal:
        assert verdict.why.startswith(refusal)


def test_every_instructions_and_tool_description_fits_the_client_cap() -> None:
    from mcp_probe import servers

    over = [line for name, module in servers.load().items()
            for line in over_the_cap(name, module.mcp)]
    assert servers.load()["dosbox-x"] is probe._modules()["dosbox-x"], (
        "the cap measured another copy")
    if over:
        pytest.fail("\n".join(over), pytrace=False)
