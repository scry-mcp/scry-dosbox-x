"""The Minesweeper demo's plan, without an emulator: what it flags and what it clicks."""

from __future__ import annotations

from pathlib import Path

from scry_core.demo import Reply, Run

from demos.mines import demo

MINES = [(0, 0), (0, 4), (3, 3), (5, 8), (8, 1), (8, 8)]


def test_the_plan_never_clicks_a_mine_and_opens_every_safe_cell() -> None:
    clicks = demo.plan(MINES)
    assert not set(clicks) & set(MINES), clicks
    reached: set[tuple[int, int]] = set()
    for cell in clicks:
        todo = [cell]
        while todo:
            r, c = todo.pop()
            on_board = 0 <= r < demo.ROWS and 0 <= c < demo.COLS
            if not on_board or (r, c) in reached or (r, c) in MINES:
                continue
            reached.add((r, c))
            near = [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
            if not any(n in MINES for n in near):
                todo.extend(near)
    assert len(reached) == demo.ROWS * demo.COLS - len(MINES), len(reached)


def test_the_demo_flags_only_mines() -> None:
    run = Run(dir=Path("."))
    run.replies["mines"] = Reply({"hex": "".join("01" if divmod(i, demo.COLS) in MINES else "00"
                                                 for i in range(demo.ROWS * demo.COLS))})
    run.replies["origin"] = Reply({"hex": "3200" + "3200"})
    steps = demo.flags(run)["steps"]
    assert len(steps) == demo.FLAGGED and {s["button"] for s in steps} == {"right"}
    cells = [((s["y"] - 50) // demo.CELL, (s["x"] - 50) // demo.CELL) for s in steps]
    assert all(cell in MINES for cell in cells), cells
