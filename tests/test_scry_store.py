"""The repository's own `.scry/` store: every recipe reads, and none carries this host's paths."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from scry_core import project_store

from scry_dosbox_x import lifecycle, server

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / ".scry" / "start"

#: What a DOSBox-X profile may set: `start`'s own arguments but for the profile itself.
KEYS = tuple(name for name in inspect.signature(server.start).parameters
             if name not in ("ctx", "profile"))

#: The directories a recipe names through `${env:...}`, as a live run exports them.
ENVIRON = {"DOSBOX_X_LIVE_GUEST_DIR": str(ROOT / "tests" / "guest"),
           "DOSBOX_X_LIVE_BRICKS_DIR": str(ROOT / "demos" / "bricks"),
           "DOSBOX_X_LIVE_BENCH": str(ROOT / "tests" / "guest")}

RECIPES = ("bricks", "dpmi", "mines", "mouse", "probe")

#: An absolute path, POSIX or Windows: a tracked recipe never carries one.
HOST_PATH = re.compile(r"^(/|[A-Za-z]:[\\/])")


def test_the_store_declares_exactly_these_recipes() -> None:
    assert sorted(path.stem for path in STORE.glob("*.json")) == list(RECIPES)


def test_every_entry_of_the_store_is_found_by_its_own_name() -> None:
    assert project_store.misnamed(ROOT / ".scry") == []


def test_the_mines_recipe_runs_the_game_its_conf_leaves_at_the_prompt() -> None:
    """`mines.conf` stops at the prompt so that a session can record the game it starts; a
    recipe on that conf names the program, or its session boots to an empty prompt."""
    recipe = json.loads((STORE / "mines.json").read_text(encoding="utf-8"))
    autoexec = (ROOT / recipe["conf"]).read_text(encoding="utf-8").split("[autoexec]", 1)[1]
    assert "MINES.COM" not in autoexec, "the conf runs the game, and so would `program`"
    assert recipe.get("program") == "MINES.COM", recipe


@pytest.mark.parametrize("name", RECIPES)
def test_every_path_inside_the_repository_it_names_exists(name: str) -> None:
    values = project_store.read(STORE / f"{name}.json", KEYS, lifecycle.START_PATHS,
                                state="/scratch", environ=ENVIRON)
    for key in ("conf", "cwd"):
        held = Path(str(values.get(key) or ""))
        if held.is_absolute() and held.is_relative_to(ROOT):
            assert held.exists(), f"{name}.{key} names {held}, which is not there"


@pytest.mark.parametrize("name", RECIPES)
def test_a_recipe_is_located_by_its_own_name_from_the_repository(name: str) -> None:
    assert project_store.locate([ROOT], name) == STORE / f"{name}.json"


@pytest.mark.parametrize("name", RECIPES)
def test_a_recipe_reads_with_the_servers_own_keys(name: str) -> None:
    values = project_store.read(STORE / f"{name}.json", KEYS, lifecycle.START_PATHS,
                                state="/scratch", environ=ENVIRON)
    assert values, f"{name} declared nothing"


@pytest.mark.parametrize("name", RECIPES)
def test_a_recipe_carries_no_host_path(name: str) -> None:
    for key, value in json.loads((STORE / f"{name}.json").read_text(encoding="utf-8")).items():
        if isinstance(value, str):
            assert not HOST_PATH.match(value), f"{name}.{key} is {value!r}"


@pytest.mark.parametrize("name", RECIPES)
def test_a_recipe_resolves_every_named_directory_inside_what_it_declares(name: str) -> None:
    values = project_store.read(STORE / f"{name}.json", KEYS, lifecycle.START_PATHS,
                                state="/scratch", environ=ENVIRON)
    for key in ("conf", "cwd"):
        held = str(values.get(key) or "")
        if held:
            assert Path(held).is_absolute(), f"{name}.{key} did not resolve: {held!r}"
