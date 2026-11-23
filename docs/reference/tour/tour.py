"""The reference tour: one session on `BRICKS.COM`, the game this repository builds, that calls
every tool the game can exercise, in the order of one investigation, every reply checked. The
reference pages take each tool's example from its normalised transcript. `guest_file` alone is
left out: the game writes no file, so the tool could only refuse.

Run it from the repository's root; `--display` names the display the window opens on:

    uv run python docs/reference/tour/tour.py --display 1

The investigation: check the build, start the game and wait for its screen, place its symbols,
read the machine, run to the first brick and change what it is worth, export what was done so
far, watch the score, film the second brick, break on the third and save the machine there,
play by keyboard and mouse until a ball is lost, load the saved machine and leave the game
through its own quit flag. The file tools that need no machine run after the close.

It is deterministic for the reason the Bricks demo is: the game has no random number and is
paced by the retrace of a machine whose clock its conf pins, so a place reached by a symbol, a
breakpoint or a watch is the same place on every run. The game is left to the wall clock only
after the first key, where the ball waits on the paddle and nothing depends on when.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from scry_core.demo import DISPLAY, Demo, Reply, Run, Step, main, recorded, window_args
from scry_core.verdict import Invalid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))  # so `demos` imports as it checks
from demos.bricks.demo import (  # noqa: E402
    BREAK_STOP,
    FIRST_COL,
    FIRST_ROW,
    MOUSE_AT,
    PADDLE_W,
    low_byte,
    word,
)
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    RETRACE_STOP,
    VOLATILE,
    expect,
    isolated_store,
    loaded,
    pictured,
    precheck,
    seen,
    started,
)

BRICKS = ROOT / "demos" / "bricks"
#: The symbol table the build wrote, as offsets from the program's segment.
OFFSETS = {name: int(offset, 16) for offset, _kind, name in (
    line.split() for line in (BRICKS / "bricks.sym").read_text(encoding="ascii").splitlines())}
#: The region the committed screen map signs first: the SCORE label.
SIGNED = json.loads((BRICKS / "bricks-screen-map.json").read_text(
    encoding="utf-8"))["screens"][0]["match"][0]
#: What the debugger must carry for the steps below; `build_check` names the ones it has.
NEEDED = frozenset({"RUNSTATE", "VGAMEMDUMP", "BPIF", "CAPTURE", "PORTINFO", "PIC", "A20",
                    "SAVESTATE", "LOADSTATE", "TAP"})

#: These mirror bricks.asm: `row_colours` as the DAC holds it, GLOW_PEN, the wall and LIVES.
ROW_RGB = ["3f0808", "3f2400", "3f3c0c", "103a10", "08343a", "14183f", "303034"]
ROW_PEN, GLOW_PEN, BRICKS_ALL, LIVES = 32, 39, 60, 3
#: What the fixed serve does, read off the runs this tour was written from: the ball where the
#: first brick falls, the columns of the second and third, and the frame of the film (counted
#: from 0) that first shows the wall without the second brick.
BALL_AT_FIRST = {"x": 230, "y": 78, "dx": 2, "dy": -2}
SECOND_COL, THIRD_COL = 6, 0
FILM_FRAMES, SERIES, GONE_AT = 110, (95, 108), 104
#: The emulator films mode 13h with every pixel doubled, 640 x 400.
SECOND_RECT = [2 * side for side in (SECOND_COL * 32 + 1, 24 + FIRST_ROW * 10, 30, 8)]
#: The first brick is made a top-row one, worth (6 - 0) * 10; the second adds 10, which is the
#: score the third brick finds.
TOP_ROW_POINTS = 60
SCORE_AT_THIRD = TOP_ROW_POINTS + 10
#: With the paddle under the pointer and nobody moving it, the served ball takes one brick and
#: is lost: the lines the game logs, in order.
PLAYED = ["HIT 0 7", "HIT 5 6", "HIT 5 0", "SERVE", "HIT 5 9", "LOST"]
COMMENT = "AL = row, BL = column of the brick that falls"
REGPOINT = "DX==3DA"
STATE = "third-brick"
WAIT_S = 60

#: A stop on a retrace, whose instruction the host's cycles decide; the game's state is the same.
RETRACE = {**RETRACE_STOP,
           "emulated_before_s": "the emulated clock at a retrace drifts with the host's cycles",
           "emulated_after_s": "the emulated clock at a retrace drifts with the host's cycles"}
NAMES_STOP = {"summary": "it names the instruction the retrace stop landed on"}
#: What a stop shows once the game has run by the wall clock: how many stops and frames that
#: took is the host's.
AFTER_PLAY = {"stop_seq": "it counts the stops, and an input's post takes as many as the host "
                          "needs to deliver it",
              "frame": "the frames the game ran while the wall clock paced it"}
WINDOW = {"window": VOLATILE["window"]}
ZLIB = "a compressed file is the size the host's zlib makes it"
ROWS = {"rows_path": "a file in the session's own temporary directory"}


def files(run: Run) -> Path:
    """Where the tour's calls write, a folder of the run's own."""
    return run.dir / "files"


def segment(run: Run) -> str:
    """The segment DOS loaded the game at, off the memory block `machine_map` listed for it."""
    held = [row["psp_seg"] for row in run.replies["memory"]["mcbs"]
            if row["filename"] == "BRICKS"]
    expect(len(set(held)) == 1, f"the memory blocks name BRICKS at {held}")
    return str(held[0])


def at(run: Run, name: str) -> str:
    """A symbol's address as the server spells one."""
    return f"{segment(run)}:{OFFSETS[name]:08X}"


def lines_of(lines: list[str]) -> list[str]:
    """The guest's log lines without the port's own prefix."""
    return [line.split(": ", 1)[-1] for line in lines]


def says(what: str) -> Callable[[Reply, Run], str]:
    return lambda reply, run: what


def boot(run: Run) -> dict[str, Any]:
    """A fresh folder for the run's files: the server writes no file over an existing one."""
    shutil.rmtree(files(run), ignore_errors=True)
    files(run).mkdir(parents=True)
    return {**window_args(run), "conf": BRICKS / "bricks.conf", "cwd": BRICKS,
            "session_seconds": 900, "logfile": files(run) / "e9.log",
            "state_dir": files(run) / "states", "captures_dir": files(run) / "captures"}


def built(reply: Reply, run: Run) -> str:
    missing = sorted(NEEDED - set(reply.get("debugger_commands", [])))
    if missing or reply["heavy_debug"] is not True:
        raise Invalid(f"this DOSBox-X lacks what the tour's steps need: {missing or 'no command'}"
                      f", heavy_debug {reply['heavy_debug']}")
    return "a debugger with every command the tour needs"


def parked(reply: Reply, run: Run) -> str:
    expect(reply["session"]["running"] is False and reply["pc"] == "F000:0000FFF0",
           f"parked at {reply['pc']}")
    return "stopped at the reset vector, before the BIOS has run"


def on_screen(reply: Reply, run: Run) -> str:
    expect(reply["window"]["onscreen"] is True, f"the window is {reply['window']}")
    return "the session's window is on screen"


def mapped(reply: Reply, run: Run) -> str:
    expect((reply["application"], reply["screens"], reply["controls"]) == ("bricks", 1, 1),
           f"the map holds {reply['screens']} screens of {reply['application']}")
    return "the game's screen map loaded: 1 screen, 1 control"


def play_shown(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "TARGET" and reply["screen"]["name"] == "play"
           and reply["already"] is False, f"{reply['verdict']} on {reply.get('screen')}")
    return f"the play screen is up after {reply['polls']} retraces"


def identified(reply: Reply, run: Run) -> str:
    named = [control["name"] for control in reply.get("controls", [])]
    expect(reply["matched"] is True and reply["screen"] == "play" and named == ["court"],
           f"matched {reply['matched']}, controls {named}")
    return "the play screen, its control court"


def owned(reply: Reply, run: Run) -> str:
    return f"DOS holds BRICKS at segment {segment(run)}"


def placed(run: Run) -> dict[str, Any]:
    return {"path": BRICKS / "bricks.sym", "base": f"0x{int(segment(run), 16) * 16:x}"}


def found_ball(reply: Reply, run: Run) -> str:
    names = [row["name"] for row in reply["symbols"]]
    expect(reply["symbols_total"] == 5 and "ball_x" in names, f"found {names}")
    return "five names begin with ball: " + ", ".join(names)


def mouse_vector(reply: Reply, run: Run) -> str:
    vector = reply["vectors"][0]
    expect(vector["number"] == "0x33", f"vector {vector['number']}")
    return f"INT 33h points at {vector['seg_off']}"


def row_colours(reply: Reply, run: Run) -> str:
    expect(reply["rgb"][:len(ROW_RGB)] == ROW_RGB, f"the DAC holds {reply['rgb']}")
    return "entries 32 to 38 hold the game's own row colours"


def signed(reply: Reply, run: Run) -> str:
    expect(reply["signature"] == SIGNED["signature"],
           f"signature {reply['signature']}, the map says {SIGNED['signature']}")
    return "the SCORE label signs as the committed map says"


def worth(points: int, why: str) -> Callable[[Reply, Run], str]:
    def check(reply: Reply, run: Run) -> str:
        expect(word(reply) == points, f"score {word(reply)}, not {points}")
        return f"score {points}: {why}"
    return check


def wall_dumped(reply: Reply, run: Run) -> str:
    held = Path(reply["path"]).read_bytes()
    expect(held == b"\x01" * BRICKS_ALL, f"the dump holds {held.hex()}")
    return f"the wall's {BRICKS_ALL} bytes, every brick standing"


def text_found(reply: Reply, run: Run) -> str:
    expect(reply["hits"] == [at(run, "msg_score")], f"hits {reply['hits']}")
    return f"the text SCORE once, at {reply['hits'][0]}"


def listed(reply: Reply, run: Run) -> str:
    first = reply["lines"][0]
    expect("mov bh, bl" in first and first.endswith(f" // {COMMENT}"), f"line 1 is {first!r}")
    return "brick_hit opens with mov bh, bl, the comment beside it"


def commented(reply: Reply, run: Run) -> str:
    refs = [row["ref"] for row in reply["comments"]]
    expect(refs == ["brick_hit"], f"comments on {refs}")
    return "one comment, on brick_hit"


def scan_open(reply: Reply, run: Run) -> str:
    expect(reply["hits_total"] == reply["length"], f"{reply['hits_total']} candidates")
    return f"{reply['hits_total']} one-byte cells are candidates"


def dac_index(reply: Reply, run: Run) -> str:
    expect(int(reply["value"], 16) == GLOW_PEN + 1, f"the DAC write index is {reply['value']}")
    return f"the next DAC entry to write is {GLOW_PEN + 1}: the game just set its frame's pen"


def lines_open(reply: Reply, run: Run) -> str:
    masked = [row["irq"] for row in reply["irqs"] if row["masked"]]
    expect(len(reply["irqs"]) == 16 and not {0, 1} & set(masked), f"masked {masked}")
    return "the timer and the keyboard lines are open"


def gate(reply: Reply, run: Run) -> str:
    expect(reply["enabled"] is True, f"enabled {reply['enabled']}")
    return "the A20 gate is on"


def fpu(reply: Reply, run: Run) -> str:
    expect("st(7)" in reply["output"] and reply["clipped"] is False, "no FPU listing")
    return "the FPU's eight registers, which no typed tool reads"


def at_brick(verdict: str, row: int, col: int) -> Callable[[Reply, Run], str]:
    def check(reply: Reply, run: Run) -> str:
        where = reply["instruction"]
        got = (reply["verdict"], where["symbol"], where["delta"], low_byte(reply, "EAX"),
               low_byte(reply, "EBX"))
        expect(got == (verdict, "brick_hit", 0, row, col), f"stopped as {got}")
        return f"at brick_hit for the brick at row {row} column {col}"
    return check


def first_brick(reply: Reply, run: Run) -> str:
    said = at_brick("TARGET", FIRST_ROW, FIRST_COL)(reply, run)
    ball = reply["watches"][0]["value"]
    expect(ball == BALL_AT_FIRST, f"the ball at {ball}")
    return f"{said}, after {reply['control_hits']} retraces"


def in_registers(reply: Reply, run: Run) -> str:
    got = (low_byte(reply, "EAX"), low_byte(reply, "EBX"))
    expect(got == (FIRST_ROW, FIRST_COL), f"AL and BL hold {got}")
    return f"AL {FIRST_ROW} and BL {FIRST_COL}: the row and the column"


def one_row(reply: Reply, run: Run) -> str:
    expect(reply["heuristic"] is True and reply["calls"][0]["symbol"] == "brick_hit",
           f"row 0 is {reply['calls'][0]}")
    return f"{len(reply['calls'])} row, the stop itself: the game keeps no frame pointer"


def forced(reply: Reply, run: Run) -> str:
    expect(reply["verified"] is True, f"read back {reply['readback']}")
    return "AX forced to 0: the brick now counts as one of the top row"


def stepped(reply: Reply, run: Run) -> str:
    where = reply["instruction"]
    got = (where["symbol"], where["delta"], int(reply["regs"]["EBX"], 16) & 0xFFFF)
    expect(got == ("brick_hit", 4, FIRST_COL << 8), f"stepped to {got}")
    return f"two instructions on, BH holds column {FIRST_COL} and BL row 0"


def exported(reply: Reply, run: Run) -> str:
    expect(reply["steps"] > 0 and reply["checks"] > 0 and "call" not in reply["cut"],
           f"{reply['steps']} steps, {reply['checks']} checks, cut {reply['cut']}")
    return (f"{reply['steps']} steps and {reply['checks']} checks written, "
            f"{reply['dropped_total']} reads left out, nothing cut")


def reviewed(reply: Reply, run: Run) -> str:
    entries = [row["entry"] for row in reply["candidates"]]
    expect("start/bricks" in entries and "written" not in reply, f"candidates {entries}")
    return "reviewed and nothing written: " + ", ".join(entries)


def traced(reply: Reply, run: Run) -> str:
    ran = [row["symbol"] for row in reply["trace"]["symbols"]]
    expect(reply["verdict"] == "ELAPSED" and {"brick_index", "brick_rect", "fill_rect"}
           <= set(ran) and Path(reply["trace"]["path"]).is_file(), f"traced {ran}")
    return "40 instructions traced through " + ", ".join(ran)


def state_is(state: str, what: str) -> Callable[[Reply, Run], str]:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["state"] == state, f"state {reply['state']}")
        return what
    return check


def score_changed(reply: Reply, run: Run) -> str:
    score = next(row for row in reply["watches"] if row["ref"] == "score")
    got = (reply["verdict"], reply["instruction"]["symbol"], score["value"])
    expect(got == ("OTHER_STOP", "brick_hit", TOP_ROW_POINTS), f"stopped as {got}")
    return f"stopped inside brick_hit, the score just written: {TOP_ROW_POINTS}"


def narrowed(reply: Reply, run: Run) -> str:
    expect(at(run, "score") in [row["seg_off"] for row in reply["hits"]],
           f"survivors {reply['hits']}")
    return f"{reply['hits_total']} cells hold {TOP_ROW_POINTS}, score among them"


def cleared(count: int) -> Callable[[Reply, Run], str]:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["declarations_cleared"] == count,
               f"{reply['declarations_cleared']} cleared")
        return f"{count} cleared"
    return check


def at_retrace(reply: Reply, run: Run) -> str:
    got = (reply["regpoint_hit"]["ref"], reply["instruction"]["symbol"])
    expect(got == (REGPOINT, "retrace"), f"stopped as {got}")
    return "stopped in retrace, the routine that loads DX with the VGA status port"


def declared(reply: Reply, run: Run) -> str:
    expect(reply["breakpoints"] == [] and reply["regpoints"] == []
           and [row["ref"] for row in reply["watches"]] == ["ball_x", "score", "paddle_x"],
           f"declared {reply['breakpoints']}, {reply['regpoints']}, {reply['watches']}")
    _shown, tally, reads = reply["watches"]
    writer = tally["writers"][0]["symbol"]
    reader = reads["first_rows"][0]["symbol"]
    got = (tally["total"], tally["values"][0]["value"], writer.split("+")[0],
           reads["state"], reader.split("+")[0])
    expect(got == (1, SCORE_AT_THIRD, "brick_hit", "captured", "draw_paddle")
           and reads["total"] >= FILM_FRAMES - 1, f"the accounts say {got}, {reads['total']}")
    return (f"the score was written once, {SCORE_AT_THIRD} by {writer}; the paddle was read "
            f"{reads['total']} times, by {reader}")


def stilled(reply: Reply, run: Run) -> str:
    expect(reply["frame"] == GONE_AT and Path(reply["path"]).is_file(), f"frame {reply['frame']}")
    return f"frame {GONE_AT} of the film as a PNG"


def series_of(reply: Reply, run: Run) -> str:
    expect(reply["count"] == SERIES[1] - SERIES[0] + 1 and Path(reply["manifest"]).is_file(),
           f"{reply['count']} frames")
    return f"{reply['count']} frames of the film and their manifest"


def silent(reply: Reply, run: Run) -> str:
    got = (reply["verdict"], reply["sample_min"], reply["sample_max"])
    expect(got == ("ELAPSED", 0, 0) and Path(reply["path"]).is_file(), f"recorded {got}")
    return "a WAV of silence: the game makes no sound"


def saved(reply: Reply, run: Run) -> str:
    expect(Path(reply["path"]).is_file(), f"no state at {reply['path']}")
    return f"the machine saved as {Path(reply['path']).name}"


def one_state(reply: Reply, run: Run) -> str:
    names = [row["name"] for row in reply["states"]]
    expect(names == [STATE], f"states {names}")
    return f"one state, {STATE}"


def three_frames(reply: Reply, run: Run) -> str:
    ran = reply["frame_after"] - reply["frame_before"]
    expect(reply["verdict"] == "ELAPSED" and ran == 3, f"{reply['verdict']} after {ran} frames")
    return "three frames on, stopped again"


def pinned(reply: Reply, run: Run) -> str:
    expect((reply["state"], reply["frozen_hex"]) == ("armed", f"{LIVES:02x}"),
           f"{reply['state']} at {reply.get('frozen_hex')}")
    return f"the lives pinned at {LIVES}"


def lives_held(reply: Reply, run: Run) -> str:
    expect(reply["hex"] == f"{LIVES:02x}", f"lives read {reply['hex']}")
    return f"a ball was lost and the lives still read {LIVES}: the freeze undid the write"


def running(reply: Reply, run: Run) -> str:
    expect(reply["session"]["running"] is True and "verdict" not in reply, "it is not running")
    return "the game runs"


def pointed(reply: Reply, run: Run) -> str:
    screen = reply["pointer"]["screen"]
    expect(reply["driver_arrived"] is True and (screen["x"], screen["y"]) == MOUSE_AT
           and reply["verify"]["seen"] is True, f"the pointer at {screen}, {reply['verify']}")
    return (f"the pointer on the map's court, pixel {MOUSE_AT[0]},{MOUSE_AT[1]}: the paddle "
            f"centres under it, at x {MOUSE_AT[0] - PADDLE_W // 2}")


def still_taken(reply: Reply, run: Run) -> str:
    expect(reply["route"] == "guest" and Path(reply["path"]).is_file(), f"route {reply['route']}")
    return "a still taken while the game runs"


def performed(reply: Reply, run: Run) -> str:
    expect(reply["steps_completed"] == 2, f"{reply['steps_completed']} steps of 2")
    return "the mouse given back and the ball served, in one call"


def lost(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "TARGET" and lines_of([reply["line"]]) == ["LOST"],
           f"{reply['verdict']}: {reply.get('line')}")
    return "the game logged LOST: nobody moved the paddle"


def broken_in(reply: Reply, run: Run) -> str:
    expect(reply["interrupted"] is True, f"interrupted {reply['interrupted']}")
    return "stopped through the debugger"


def logged(reply: Reply, run: Run) -> str:
    got = lines_of(reply["lines"])
    expect(got == PLAYED, f"the game logged {got}")
    return "the game logged " + ", ".join(got)


def written(reply: Reply, run: Run) -> str:
    expect(reply["verified"] is True and reply["readback"] == "01", f"read back {reply}")
    return "the game's quit flag set"


def exit_armed(reply: Reply, run: Run) -> str:
    expect(reply["armed"] is True and [n["name"] for n in reply["names"]] == ["exit"],
           f"armed {reply['armed']}, names {reply['names']}")
    return f"armed as {reply['ref']}, which the reply names exit"


def base_exit(reply: Reply, run: Run) -> str:
    entry = reply["entries"][0]
    expect(reply["entries_total"] == 1 and entry["id"] == "ibm-pc:call:0x21/0x4C",
           f"entries {reply['entries']}")
    return f"the base names INT 21h AH=4Ch {entry['name']}, read in {entry['sources'][0]['where']}"


def leaving(reply: Reply, run: Run) -> str:
    where = reply["instruction"]
    got = (reply["verdict"], where["text"], where["symbol"], int(reply["regs"]["EAX"], 16),
           where.get("note"), where.get("note_live"))
    expect(got == ("OTHER_STOP", "int 0x21", "main_loop", 0x4C00, "exit (0x4C)", True),
           f"stopped as {got}")
    return "stopped at the game's own exit call, INT 21h with AX 4C00h, which the base names exit"


def exit_listing(reply: Reply, run: Run) -> str:
    last = len(reply["lines"]) - 1
    expect(reply["lines"][last].endswith("int 0x21")
           and reply["line_notes"] == [{"line": last, "note": "exit (0x4C)", "live": True}],
           f"notes {reply.get('line_notes')}")
    return "the exit call's line carries its note, named from the registers of the stop"


def all_present(reply: Reply, run: Run) -> str:
    absent = [row["path"] for row in reply["captures"] if not row["present"]]
    expect(not absent and len(reply["captures"]) > 0, f"absent: {absent}")
    return f"{len(reply['captures'])} files written by the session, all there"


def brick_gone(reply: Reply, run: Run) -> str:
    frame, changed = max(reply["transitions"], key=lambda row: int(row[1]))
    expect(frame == GONE_AT, f"the region changes most at frame {frame}: {reply['transitions']}")
    return (f"{changed} pixels of the second brick's rectangle change at frame {GONE_AT} of "
            "the film: the brick is gone")


def heard(reply: Reply, run: Run) -> str:
    left = reply["measures"][0]
    expect(left["silent"] is False and reply["sample_rate_hz"] == 48000, f"measured {left}")
    return f"a sound, peaking at {left['peak_dbfs']} dBFS"


def out(name: str, **args: Any) -> Callable[[Run], Mapping[str, Any]]:
    """Arguments whose `dest` is `name` in the run's folder."""
    return lambda run: {**args, "dest": files(run) / name}


def film(run: Run) -> Path:
    return files(run) / "second-brick.avi"


#: A row's stamps, in the lists of comments and declarations.
STAMPS = {"created_at": "the wall-clock time the row was declared at",
          "origin": "the session that declared the row, named by its time and process",
          "age_s": "wall-clock time since the row was declared"}
STORE = {"path": "the run's own declaration store, a temporary directory"}

STEPS = [
    Step("build", "build_check", {}, built, options=frozenset({"binary"}),
         volatile={"summary": "it names where the host installed DOSBox-X"}),
    Step("start", "start", boot, started, options=frozenset({"binary", "display"}),
         volatile={**WINDOW, "summary": "it carries how long the debugger took to answer"}),
    Step("status", "status", {}, parked),
    Step("window", "window", {}, on_screen,
         volatile={**WINDOW, "summary": "it names the display the host put the window on"}),
    Step("map", "screen_map_write",
         {"method": "load", "path": BRICKS / "bricks-screen-map.json"}, mapped),
    # Sampled by retrace: nothing of the game can be named before DOS has loaded it, and this
    # wait ends at the first retrace whose screen the map knows, the wall and its labels drawn.
    Step("ready", "screen_wait", {"screen": "play", "seconds": WAIT_S}, play_shown,
         volatile=RETRACE_STOP),
    Step("screen", "screen_map_find", {}, identified),
    Step("memory", "machine_map", {"sections": ["mcbs"]}, owned),
    Step("symbols", "symbols_load", placed, loaded),
    Step("names", "symbols_find", {"name": "ball"}, found_ball),
    Step("vector", "interrupt_vectors", {"number": "0x33"}, mouse_vector),
    Step("picture", "screen_view", out("wall.png"), pictured),
    Step("palette", "palette", out("palette.png", first=ROW_PEN, count=GLOW_PEN - ROW_PEN + 1),
         row_colours),
    Step("signature", "screen_signature", {"crop": SIGNED["crop"]}, signed),
    Step("score", "read_memory", {"ref": "score", "length": 2},
         worth(0, "no brick has fallen")),
    Step("dump", "memdump", out("wall.bin", ref="bricks", length=BRICKS_ALL), wall_dumped),
    Step("find", "find", {"data_hex": b"SCORE".hex(), "ref": "start",
                          "length": (BRICKS / "BRICKS.COM").stat().st_size}, text_found),
    Step("comment", "comment_write", {"method": "add", "ref": "brick_hit", "text": COMMENT},
         says("a comment on brick_hit"), volatile={**STAMPS, **STORE}),
    Step("base", "knowledge_find", {"kind": "call", "key": "0x21/0x4C"}, base_exit),
    Step("listing", "disassemble", {"ref": "brick_hit", "length": 12}, listed),
    Step("comments", "comment_list", {}, commented, volatile={**STAMPS, **STORE}),
    Step("scan", "scan", {"method": "start", "ref": "row_colours", "cell_bytes": 1,
                          "length": OFFSETS["bricks"] + BRICKS_ALL - OFFSETS["row_colours"]},
         scan_open),
    Step("port", "port", {"method": "read", "port": "0x3C8"}, dac_index),
    Step("lines", "pic", {"method": "read"}, lines_open),
    Step("gate", "a20", {"method": "read"}, gate),
    Step("fpu", "debug", {"command": "FPU"}, fpu),
    Step("ball", "watch_add",
         {"ref": "ball_x", "mode": "show", "fmt": "{x:i16,y:i16,dx:i16,dy:i16}"},
         state_is("evaluated", "the ball shown at every stop, as a struct")),
    Step("first brick", "run_to", {"ref": "brick_hit", "control": "retrace", "seconds": WAIT_S},
         first_brick),
    Step("registers", "registers", {}, in_registers),
    Step("callers", "call_stack", {}, one_row),
    Step("force", "set_register", {"name": "ax", "value": 0}, forced),
    Step("step", "step", {"count": 2}, stepped),
    Step("export", "perform_export", out("session.json"), exported),
    Step("review", "promote", {"dry_run": True}, reviewed),
    Step("trace", "trace", {"instructions": 40}, traced),
    Step("watch", "watch_add", {"ref": "score", "mode": "change", "fmt": "u16"},
         state_is("armed", "a stop armed on any change of the score")),
    Step("score changes", "resume", {"seconds": WAIT_S}, score_changed),
    Step("survivors", "scan", {"method": "filter", "value": TOP_ROW_POINTS}, narrowed),
    Step("unwatch", "declaration_clear", {"kind": "watch", "ref": "score"}, cleared(1)),
    Step("regpoint", "regpoint_add", {"condition": REGPOINT},
         state_is("armed", "a stop armed on DX holding 3DAh")),
    Step("status port", "resume", {"seconds": WAIT_S}, at_retrace),
    Step("unregpoint", "declaration_clear", {"kind": "regpoint", "all": True}, cleared(1)),
    Step("tally", "watch_add", {"ref": "score", "mode": "count", "fmt": "u16"},
         state_is("armed", "every write of the score counted, with its writer")),
    Step("reads", "watch_add", {"ref": "paddle_x", "mode": "capture", "trigger_type": "r"},
         state_is("armed", "every read of the paddle's place captured, with the beam line")),
    Step("film", "record", lambda run: {"frames": FILM_FRAMES, "dest": film(run),
                                        "seconds": WAIT_S},
         recorded(FILM_FRAMES, says(f"{FILM_FRAMES} retraces filmed, the second brick's fall "
                                    "among them")),
         volatile={**RETRACE, **ROWS, "bytes": ZLIB}),
    Step("declared", "declaration_list", {}, declared, volatile={**STAMPS, **ROWS}),
    Step("untap", "declaration_clear", {"kind": "watch", "all": True}, cleared(3)),
    Step("still", "capture_frame", lambda run: {"frame": GONE_AT, "capture_path": film(run),
                                                "dest": files(run) / "brick-gone.png"},
         stilled,
         volatile={"summary": "it carries the picture's size, which the host's zlib decides"}),
    Step("series", "series_capture", lambda run: {"first": SERIES[0], "last": SERIES[1],
                                                  "capture_path": film(run),
                                                  "dest": files(run) / "series"}, series_of),
    Step("sound", "audio_record", out("sound.wav", frames=20), silent, volatile=RETRACE),
    Step("break", "breakpoint_at", {"ref": "brick_hit"},
         state_is("armed", "a breakpoint on brick_hit")),
    Step("third brick", "resume", {"seconds": WAIT_S},
         at_brick("OTHER_STOP", FIRST_ROW, THIRD_COL)),
    Step("save", "state_write", {"method": "save", "name": STATE}, saved,
         volatile={"summary": "it carries the state's size and time", "bytes": ZLIB}),
    Step("states", "state_list", {}, one_state, volatile={"bytes": ZLIB}),
    Step("unbreak", "declaration_clear", {"kind": "breakpoint", "all": True}, cleared(1)),
    Step("frames", "run_for", {"frames": 3}, three_frames, volatile={**RETRACE, **NAMES_STOP}),
    Step("pin", "watch_add", {"ref": "lives", "mode": "freeze", "length": 1}, pinned),
    # From here the wall clock paces the game. The first key makes the ball wait on the paddle,
    # so what the steps below check does not depend on when each one lands.
    Step("key", "send_keys", {"keys": ["right"], "expect": "KEY R$", "seconds": 10},
         seen("the right arrow took the paddle from the game: it logged KEY R"),
         volatile={**RETRACE, **NAMES_STOP, **INPUT_TIMING, **AFTER_PLAY,
                   "polls": "the retraces the input's post took, which the host's delivery "
                            "decides"}),
    Step("play", "resume", {}, running),
    Step("mouse on", "drive", {"act": [{"op": "send_keys", "keys": ["m"]}],
                               "expect": "MOUSE ON$", "seconds": 10},
         seen("M handed the paddle to the mouse: the game logged MOUSE ON"),
         volatile=INPUT_TIMING),
    Step("mouse", "send_mouse", {"target": "court", "expect": "MOUSE$", "seconds": 10},
         pointed, volatile=INPUT_TIMING),
    Step("snapshot", "snapshot", out("held.png"), still_taken,
         volatile={"summary": "it carries the picture's size, and the frame a running game is "
                              "caught at is the host's"}),
    Step("serve", "perform",
         {"steps": [{"op": "send_keys", "keys": ["m"], "expect": "MOUSE OFF$", "seconds": 10},
                    {"op": "send_keys", "keys": ["space"], "expect": "SERVE$", "seconds": 10}]},
         performed, volatile=INPUT_TIMING),
    Step("lost", "log_wait", {"pattern": "LOST$", "channel": "guest", "seconds": WAIT_S}, lost,
         volatile={**INPUT_TIMING,
                   "summary": "it carries how long the wait took",
                   "already": "whether the line came before the call is the host's speed",
                   "arrived_during": "the lines that came while it waited, which the host's "
                                     "speed decides",
                   "lines_examined": "the lines read, which the host's speed decides"}),
    Step("wait", "wait", {"seconds": 1}, running,
         volatile={"summary": "it carries how long the wait took"}),
    Step("stop", "stop", {}, broken_in, volatile={**BREAK_STOP, **AFTER_PLAY}),
    Step("log", "log", {"pattern": "SERVE|HIT|LOST", "channel": "guest"}, logged),
    Step("lives", "read_memory", {"ref": "lives", "length": 1}, lives_held),
    Step("load", "state_write", {"method": "load", "name": STATE},
         says(f"the machine of {STATE} loaded"),
         volatile={"summary": "it carries how long the load took"}),
    Step("restored", "read_memory", {"ref": "score", "length": 2},
         worth(SCORE_AT_THIRD, "the third brick is not counted yet, as when the state was saved")),
    Step("quit", "write", {"ref": "quit", "data_hex": "01"}, written),
    Step("exit", "breakpoint_interrupt", {"number": "0x21", "ah": "0x4C"}, exit_armed),
    Step("leaving", "resume", {"seconds": WAIT_S}, leaving, volatile=AFTER_PLAY),
    Step("exit listing", "disassemble", {"ref": "main_loop", "length": 35}, exit_listing),
    Step("captures", "captures", {}, all_present,
         volatile={"bytes": "a compressed file is the size the host's zlib makes it, and the "
                            "replay document carries the host's paths"}),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
    Step("compare", "image_compare",
         lambda run: {"method": "region", "manifest": files(run) / "series" / "manifest.json",
                      "crop": SECOND_RECT, "measure": "changed_pixels"}, brick_gone),
    Step("measure", "audio_compare",
         {"method": "measure", "path": ROOT / "demos" / "mines" / "boom.wav"}, heard),
]

#: Keys the demos hide in every reply and this run shows: the debugger's own listing is the
#: answer of the `debug` step, and `window` is also the span `audio_compare` measured, so the
#: host's window is hidden in the two steps that answer it.
SHOWN = ("output", "output_chars", "window")

DEMO = Demo(
    name="tour", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    steps=STEPS, precheck=precheck, offers=frozenset({"display"}),
    host_args={"display": DISPLAY},
    volatile={**{key: why for key, why in VOLATILE.items() if key not in SHOWN},
              "saved_at": "the wall-clock time a state was saved at"})


#: The committed copy of the run, which the reference reads its examples from.
TRANSCRIPT = HERE / "TRANSCRIPT.md"


def keep_transcript(code: int, argv: list[str]) -> int:
    """After a run where every step passed, copy its normalised transcript beside this file;
    a run sent elsewhere with `--transcript` is somebody's own and leaves the copy alone."""
    if code == 0 and not any(a.split("=", 1)[0] == "--transcript" for a in argv):
        shutil.copyfile(ROOT / "tmp" / "demos" / DEMO.name / "transcript-normalised.md",
                        TRANSCRIPT)
        print(f"kept: {TRANSCRIPT}")
    return code


if __name__ == "__main__":
    isolated_store("tour")
    sys.exit(keep_transcript(main(DEMO), sys.argv[1:]))
