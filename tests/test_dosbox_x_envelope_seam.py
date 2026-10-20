"""A wrong-typed argument is refused by the schema before the tool runs, and the refusal still
arrives in this server's envelope: `summary`, `status: INVALID`, `code: bad_argument`, a
`message` naming the argument, `session` last. ONE seam in the dispatch and no validation of
our own: the schema keeps judging the type, the seam only gives the refusal the shape every
other refusal has, so a caller reads one shape and not two."""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from threading import Event, Thread
from time import monotonic
from typing import Annotated, Any, get_args, get_origin

import pytest
from mcp.server.mcpserver.exceptions import UnexpectedToolError
from pydantic import TypeAdapter, ValidationError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import dosbox_mcp  # noqa: E402
import dosbox_state as st  # noqa: E402
import dosbox_x_server as s  # noqa: E402


def _call(name: str, args: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    res = asyncio.run(s.mcp.call_tool(name, args))
    text = "".join(c.text for c in res.content if getattr(c, "text", None))
    return res, json.loads(text)


def test_a_wrong_typed_argument_answers_the_envelope_and_not_the_sdks_text() -> None:
    res, reply = _call("read_memory", {"ref": "F000:0000", "length": "dieciseis"})
    assert res.is_error is not True, "a refusal is a reply, as every other refusal here is"
    assert reply["status"] == "INVALID" and reply["code"] == "bad_argument", reply
    assert reply["summary"].startswith("read_memory: INVALID (bad_argument)"), reply["summary"]
    assert "length" in reply["message"] and "integer" in reply["message"], reply["message"]
    assert "pydantic" not in reply["message"] and "errors.pydantic.dev" not in reply["message"]
    assert list(reply)[-1] == "session", list(reply)


def test_the_tools_own_refusal_still_flows_through_the_seam_unchanged() -> None:
    _res, reply = _call("log", {"channel": "bogus", "pattern": "x"})
    assert reply["code"] == "bad_argument" and list(reply)[-1] == "session", reply


@pytest.mark.parametrize("defect", [
    AttributeError("a real defect"),
    # A body's own validation failing is a defect too, though its cause is the type the
    # schema's refusal carries: what tells them apart is the SDK's wrapper, not the cause.
    pytest.param(None, id="a-validation-error-of-the-body"),
])
def test_a_genuine_defect_is_not_dressed_up_as_a_refusal(defect: Exception | None) -> None:
    """The seam translates the SCHEMA's refusal only: an exception out of a tool body keeps
    the SDK's error path, so a broken instrument is never read as a clean refusal."""

    async def boom() -> dict[str, Any]:
        if defect is None:
            TypeAdapter(int).validate_python("a real defect")
        raise defect or AssertionError("unreachable")

    s.mcp._tool_manager.add_tool(boom)
    try:
        with pytest.raises(UnexpectedToolError) as raised:
            asyncio.run(s.mcp.call_tool("boom", {}))
    finally:
        s.mcp._tool_manager._tools.pop("boom", None)
    # The SDK keeps a crash's own text off the wire and hangs it on the cause, so the defect is
    # found there and nowhere in the message: a client reads the generic line, the log the cause.
    assert "a real defect" not in str(raised.value), raised.value
    assert isinstance(raised.value.__cause__, (type(defect) if defect else ValidationError)), \
        raised.value.__cause__
    assert "a real defect" in str(raised.value.__cause__)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))


# ------------------------------------------------------------ strict arguments at the surface
#
# The SDK builds each tool's argument model LAX: a convertible type is coerced, an unknown
# name dropped, and a JSON string parsed into the list or object it spells before the model
# sees it. The contract says a wrong type or an unknown name is REFUSED, so the server swaps
# in a strict model and turns that rescue off; these cases hold the swap to the SDK it rides.


def test_the_sdk_hooks_the_strict_arguments_ride_on_still_exist() -> None:
    """The swap reads three things off the SDK: a tool's `fn_metadata`, its `arg_model`, and
    `validate_arguments` going through `pre_parse_json` before the model. An SDK that moves
    any of them fails HERE, by name, instead of leaving the surface lax in silence."""
    import inspect as _inspect

    from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata

    assert "arg_model" in FuncMetadata.model_fields
    source = _inspect.getsource(FuncMetadata.validate_arguments)
    assert "self.pre_parse_json(" in source and "self.arg_model.model_validate(" in source
    for t in s.mcp._tool_manager.list_tools():
        config = t.fn_metadata.arg_model.model_config
        assert config.get("strict") is True and config.get("extra") == "forbid", t.name
    # And what a client is TOLD is what is enforced: the published schema closes too.
    published = asyncio.run(s.mcp.list_tools())
    assert published and all(
        t.input_schema.get("additionalProperties") is False for t in published), [
        t.name for t in published if t.input_schema.get("additionalProperties") is not False]


@pytest.mark.parametrize("name,args,names", [
    ("status", {"nope": 1}, "nope"),
    ("watch_add", {"ref": "0:0", "mode": "change", "width": 2}, "width"),
    ("read_memory", {"ref": "F000:0000", "length": "16"}, "length"),
    ("perform", {"steps": '[{"op": "status"}]'}, "steps"),
])
def test_a_wrong_type_an_encoded_list_and_an_unknown_name_are_refused(
    name: str, args: dict[str, Any], names: str,
) -> None:
    _res, reply = _call(name, args)
    assert reply["status"] == "INVALID" and reply["code"] == "bad_argument", reply
    assert reply["message"].startswith("refused by the schema") and names in reply["message"], \
        reply["message"]


_SAMPLE: dict[Any, Any] = {str: "0", int: 2, float: 1.0, bool: False, list[str]: ["a"]}


def test_every_tool_that_takes_ctx_still_accepts_a_valid_call() -> None:
    """THE INJECTED-ARGUMENT HAZARD: `ctx` is handed in by the SDK and kept out of the model,
    so a model that forbids unknown names must still let every such tool through. With no
    session a valid call is the tool's own answer, never the schema's refusal."""
    import inspect as _inspect

    seen = []
    for t in s.mcp._tool_manager.list_tools():
        params = _inspect.signature(t.fn, eval_str=True).parameters
        if "ctx" not in params:
            continue
        args: dict[str, Any] = {}
        for p in params.values():
            if p.name == "ctx" or p.default is not _inspect.Parameter.empty:
                continue
            # A RANGED OR CLOSED ARGUMENT is its scalar under `Annotated`'s schema half.
            ann = (get_args(p.annotation)[0] if get_origin(p.annotation) is Annotated
                   else p.annotation)
            args[p.name] = _SAMPLE.get(ann, [{"op": "status"}])
        _res, reply = _call(t.name, args)
        assert not reply.get("message", "").startswith("refused by the schema"), (t.name, reply)
        seen.append(t.name)
    assert seen, "no tool takes ctx, so this case examined nothing"


# ------------------------------------------ the refusal waits for the machine like any call
#
# Building the refusal is a write to what the machine's calls share, so it waits for the
# machine like any call (`dosbox_mcp.refusal` says why).

_WRONG_TYPE = ("read_memory", {"ref": "F000:0000", "length": "dieciseis"})


class _AnotherCall:
    """A second thread holding `LOCK` as a tool body does, until `release`. Another THREAD is
    the point: `LOCK` is an `RLock`, so a hold taken on this one would prove nothing about a
    second call."""

    def __init__(self) -> None:
        self._taken, self._release = Event(), Event()
        self.released_at = 0.0
        self._thread = Thread(target=self._hold, daemon=True)
        self._thread.start()
        assert self._taken.wait(5.0), "the lock was never taken, so nothing below measures"

    def _hold(self) -> None:
        with dosbox_mcp.LOCK:
            self._taken.set()
            self._release.wait(5.0)
            self.released_at = monotonic()

    def release(self) -> None:
        self._release.set()
        self._thread.join(5.0)


def test_a_schema_refusal_waits_while_another_call_holds_the_machine() -> None:
    other = _AnotherCall()
    answered: list[dict[str, Any]] = []
    refusal = Thread(target=lambda: answered.append(_call(*_WRONG_TYPE)[1]), daemon=True)
    refusal.start()
    refusal.join(0.3)
    assert not answered, "the refusal was built while another call held the machine"
    other.release()
    refusal.join(5.0)
    assert answered, "and it is answered once the machine is free"
    reply = answered[0]
    assert (reply["status"], reply["code"]) == ("INVALID", "bad_argument"), reply
    assert list(reply)[-1] == "session", list(reply)


def test_the_event_loop_keeps_turning_while_a_refusal_waits() -> None:
    """AND THE WAIT IS NOT A PLAIN `with LOCK:` IN THE COROUTINE, which deadlocks
    (`scry_core.envelope.Envelope.call_tool` says why): the loop still turning while the
    refusal is pending is what shows the wait is elsewhere."""
    other = _AnotherCall()
    turns: list[float] = []

    async def meanwhile() -> Any:
        refusal = asyncio.ensure_future(s.mcp.call_tool(*_WRONG_TYPE))
        while len(turns) < 5:
            await asyncio.sleep(0.02)
            turns.append(monotonic())
        other.release()
        return await refusal

    res = asyncio.run(meanwhile())
    assert res.is_error is not True
    assert turns and other.released_at, (turns, other.released_at)
    assert turns[0] < other.released_at, (
        "the event loop stood still while the refusal waited for the lock")


def _free_elsewhere() -> bool:
    """Whether another thread could take `LOCK` right now."""
    got: list[bool] = []

    def attempt() -> None:
        took = dosbox_mcp.LOCK.acquire(blocking=False)
        if took:
            dosbox_mcp.LOCK.release()
        got.append(took)

    probe = Thread(target=attempt, daemon=True)
    probe.start()
    probe.join(5.0)
    return got == [True]


def test_the_refusal_reply_is_built_while_the_machine_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WAITING FOR THE LOCK IS NOT HOLDING IT: a refusal that took and let go of `LOCK` before
    building its reply passes both cases above, so this one looks at the moment `st.reply`
    runs, which is the write."""
    held: list[bool] = []
    real = st.reply

    def spy(status: str = "ok", **fields: Any) -> dict[str, Any]:
        held.append(not _free_elsewhere())
        return real(status, **fields)

    monkeypatch.setattr(st, "reply", spy)
    _res, reply = _call(*_WRONG_TYPE)
    assert reply["code"] == "bad_argument", reply
    assert held == [True], "the refusal's reply was built with the machine free"
