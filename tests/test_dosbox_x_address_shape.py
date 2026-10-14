"""A raw address is judged, segment included, before anything stores or addresses it.

The store deliberately tolerates a malformed address it ALREADY holds (a hand-edited file must stay
listable and clearable), which is exactly why a new one has to be refused at the door: past it, a
five-digit segment was written to by `memdump` in silence, persisted by `breakpoint_at` as a
declaration nothing could ever arm or clear, and reported by the clear as "the guest is running"
on a stopped machine.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dosbox_arming as arming  # noqa: E402
import dosbox_checks as checks  # noqa: E402
import dosbox_find as finder  # noqa: E402
import dosbox_placement as placement  # noqa: E402
import dosbox_session as ds  # noqa: E402


@pytest.mark.parametrize("ref", ["12345:0010", "10000:0000", "FFFFF:0001"])
def test_a_segment_past_sixteen_bits_is_refused_by_the_one_parser(ref: str) -> None:
    with pytest.raises(ds.Invalid, match="a segment is 0x0000 to 0xFFFF"):
        placement.parse_seg_off(ref)


@pytest.mark.parametrize("ref", ["0000:0000", "FFFF:FFFF", "0040:0100"])
def test_a_sixteen_bit_segment_is_accepted(ref: str) -> None:
    """THE POSITIVE CONTROL: without it a parser that refused every segment would pass above."""
    assert placement.parse_seg_off(ref) == (int(ref[:4], 16), int(ref[5:], 16))


def test_address_shape_judges_a_forced_address_and_leaves_a_symbol_alone() -> None:
    with pytest.raises(ds.Invalid):
        placement.address_shape("12345:0010", "address")
    with pytest.raises(ds.Invalid):
        placement.address_shape("12345:0010")            # decided as an address by its shape
    placement.address_shape("_engine_tick", "symbol")     # a symbol is judged at its step
    placement.address_shape("_engine_tick")


@pytest.mark.parametrize("tool", ["breakpoint_at", "watch_add"])
def test_the_arming_tools_refuse_a_bad_segment_before_touching_the_session(tool: str) -> None:
    """THE CALL SITES, held: the shape is judged before the session is used at all, so `None`
    stands in for one and a mutation that drops the call fails here on an AttributeError."""
    with pytest.raises(ds.Invalid, match="a segment is 0x0000 to 0xFFFF"):
        if tool == "breakpoint_at":
            arming.breakpoint_at(None, "12345:0010", "auto")  # type: ignore[arg-type]
        else:
            arming.watch_add(None, "12345:0010", "show", 2, "u16", "auto")  # type: ignore[arg-type]


def test_a_step_with_a_non_string_value_is_refused_not_deferred() -> None:
    """A hand-written step may carry an int where a string belongs; refusing it before the list
    runs is the whole point of the pre-flight, and a skip would let earlier steps run first."""
    with pytest.raises(ds.Invalid, match="is not a string"):
        checks.address_shape(1234)
    with pytest.raises(ds.Invalid, match="whole number of hex bytes"):
        finder.hex_bytes("data_hex", 1234, verb="write")  # type: ignore[arg-type]


def test_a_forced_by_travels_through_the_batch_check() -> None:
    """A step declaring `by="symbol"` for a name with a colon in it is the documented escape, and
    `by="address"` on a bare name is refused in the batch as it is at the surface."""
    checks._breakpoint_at(ref="ns::fn", by="symbol")
    with pytest.raises(ds.Invalid):
        checks._breakpoint_at(ref="_main", by="address")
