"""What `scry_core.probe` judges with this server's own surface: the task set and its captures,
the server's pre-gate check, and the texts the client delivers.

The engine and the checks every server runs (`scry_core.probe_checks`) are the core's; what is
dosbox-x's own (its `check`) is judged here on the real server. `captured/dosbox-x/` holds every
task as real runs answered it, one file per task.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scry_core import probe, probe_checks

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mcp_probe"

# At collection: `servers.load` says why.
REPO = probe_checks.repository(ROOT)
SURFACE = probe.load_surface(REPO, "dosbox-x")


def _tasks() -> list[dict[str, Any]]:
    text = (FIXTURES / "tasks" / "dosbox-x.json").read_text()
    doc: dict[str, list[dict[str, Any]]] = json.loads(text)
    return doc["tasks"]


def _judge(task_id: str, line: str) -> probe.Verdict:
    return probe_checks.judge_line(SURFACE, _tasks(), task_id, line)


def test_the_tasks_cover_the_server() -> None:
    assert probe_checks.refused(REPO, "dosbox-x") == []


def test_every_task_is_captured_and_judged_as_it_was() -> None:
    assert probe_checks.captures_misjudged(REPO, "dosbox-x") == []


def test_the_probe_reads_the_server_the_suite_imports() -> None:
    import dosbox_checks
    import dosbox_x_server

    assert REPO.modules["dosbox-x"] is dosbox_x_server
    assert REPO.checks["dosbox-x"] is dosbox_checks.probe_check


def test_every_instructions_and_tool_description_fits_the_client_cap() -> None:
    if over := probe_checks.over_cap(REPO):
        pytest.fail("\n".join(over), pytrace=False)


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
