from pathlib import Path
from types import ModuleType

from scry_dosbox_x import checks as dosbox_checks
from scry_dosbox_x import server as dosbox_x_server

ROOT = Path(__file__).resolve().parent.parent
CAPTURED = ("dosbox-x",)


def load() -> dict[str, ModuleType]:
    return {"dosbox-x": dosbox_x_server}


CHECKS = {"dosbox-x": dosbox_checks.probe_check}
