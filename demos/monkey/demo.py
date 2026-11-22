"""The Monkey Island demo: LucasArts' The Secret of Monkey Island, the 1992 Enhanced CD, driven by
name off a screen map with the guest's own mouse, then written into while it is stopped: the
lookout on the opening cliff answers with a conversation of ours, and the CD plays the opening
theme from the bar where the logo enters, every answer checked. `--help` says how to run it.

Nothing of the game is in this repository: `--cwd` names the directory holding the reader's
disc image (`monkey.cue` and its BINs), mounted as the CD drive with its audio tracks, and the
demo refuses any other pressing, because the script's addresses and the theme's sectors are
that disc's.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import wave
from pathlib import Path
from typing import Any

from scry_core.demo import (
    DISPLAY,
    Demo,
    Lead,
    Moment,
    Reply,
    Run,
    Step,
    recording,
    window_args,
)
from scry_core.verdict import Invalid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import decorated, host  # noqa: E402
from demos.host import VOLATILE, expect, isolated_store, started  # noqa: E402
from demos.monkey import lookout  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: The layers that exist for this demo: its calls, the keys and the mouse it sends.
LAYERS = decorated.ALL
#: The disc's files the demo reads, with their sha256: the CUE sheet, the data track (the game)
#: and track 18 (the opening theme), as the 1992 Enhanced CD, multilingual OEM, pressed them.
DISC = {"monkey.cue": "6a28d6f905010caef6b0582aaa0e0b60218d5aa3a5b2cc20a7b6265b5f996351",
        "monkey01.bin": "73cd16ea87fd65af852d06730bdd75cdf3260d0415173deb039af55c17ab5fc8",
        "monkey18.bin": "bebb584e1a2b8a03a4945c379576c631ba8915f1df6d696d7d86c23447189d5a"}
THEME = "monkey18.bin"
RAW_SECTOR = 2352
#: Red Book's lead-in: sector 0 of the first track is 2 seconds into the disc.
LEAD_IN = 150
#: Where the Monkey Island logo enters the intro, in CD sectors (75 a second) into the theme.
LOGO = 1567
#: Retraces the theme is recorded for once the drive is told where to start.
THEME_FRAMES = 560
#: The least SNR, in dB, at which a recording is the disc's own samples.
MIN_SNR_DB = 40
#: Samples DOSBox-X's mixer takes to hand out the drive's first one, the same on every run: the
#: reference is laid that late, and the two are held sample for sample, since aligning by onset
#: cannot place the theme's soft first bar to the sample.
MIXER_LAG = 2
#: Why a stop's place is hidden in the transcript: the game paces itself by where the CD has
#: played to, which follows the host's audio clock, so a retrace lands at another instruction of
#: the same wait loop from one run to the next while every screen and sample stays the same.
WAIT_LOOP = "where in the game's wait loop the stop landed, which follows the CD's playback"
#: Where a stop in the game's wait loop landed, as a reply shows it: a recording ends on such a
#: stop, and a state saved at one carries it to the first read after the load.
STOP_PLACE = {key: WAIT_LOOP for key in ("pc", "regs", "instruction", "cause")}
#: What a step that stops in the game's wait loop shows of where it stopped, its summary too.
STOP_IN_LOOP = {"summary": WAIT_LOOP, **STOP_PLACE}
#: Where the game keeps its own pointer, in its 320 x 200 units: two words of `MONKEY.EXE`'s main
#: block, this pressing and conf. Declared once the game runs, since the launcher's language menu
#: is another program and holds other data there.
GAME_POINTER = {"x": "2000:94EA", "y": "2000:94EC", "bytes": 2}
#: Where the pointer waits while a screen is judged: over the sky, off every region the map signs.
SKY = {"op": "send_mouse", "x": 250, "y": 20}
#: Where the pointer goes once a line is picked: above the menu, so the next one is judged whole.
AWAY = {"op": "send_mouse", "x": 160, "y": 60}
#: How long a step waits for the screen it brings: a walk or a speech ends well inside it on a
#: host of any speed, and the wait ends at the screen, never at the bound.
ARRIVE_S = 180
#: The launcher's language menu and the lookout's lines are judged every so many retraces: the
#: launcher has no symbols and no log, and the lines are paced by the CD (`line`); each judgement
#: stops the machine and reads the frame.
JUDGED_EVERY = 7
#: Where SCUMM leaves the loop that waits for its next tick (`MONKEY.EXE`'s code segment, this
#: pressing): by then it has copied the frame it built to the screen and set its palette, so a
#: screen judged after it is whole. The code segment is the program's PSP plus 0x10.
TICK_OFFSET = 0x011E
#: SCUMM's variables in its data segment (the PSP plus 0x10 plus `DATA_PARAGRAPHS`, this
#: pressing): the room is variable 4, two bytes each from `VARS`.
DATA_PARAGRAPHS, VARS = 0x1886, 0x73E2
ROOM = VARS + 4 * 2
#: The values the room variable takes from the double click to the intro's first scene, room 10
#: (the first ones are what SCUMM writes there while it starts, before any room), then the title
#: card, room 96. SCUMM takes a key that skips a scene only once the scene has begun, which no stop
#: marks, so from room 10 an Escape goes in after the first of `SKIP_TICKS` SCUMM ticks and every
#: `SKIP_EVERY`th past it: each lands at the same tick of the game's clock, so the same scenes are
#: skipped.
INTRO_ROOMS = (0x8B50, 0x8B50, 0, 0, 10)
TITLE_ROOM = 96
SKIP_EVERY, SKIP_TICKS = 5, 24
#: The bound of each wait for a write of the room variable: the intro's longest scene ends well
#: inside it on any host, and the wait ends at the write.
INTRO_S = 300
#: The retraces the game takes to answer the pointer once a screen is up, counted from the
#: screen and so the same on any host.
SETTLE = {"op": "run_for", "frames": 10}


def disc(run: Run) -> Path:
    return Path(run.options["cwd"]).expanduser()


def disc_check(run: Run) -> str:
    """Why the game cannot be run: no `--cwd`, a relative one, a file missing, another disc's."""
    where = run.options.get("cwd")
    if not where:
        return ("pass --cwd with the directory holding the Enhanced CD's monkey.cue and its BINs; "
                "this repository carries none of the game")
    if not Path(where).expanduser().is_absolute():
        return f"the server takes absolute or ~-led paths only: --cwd {where}"
    for name, want in DISC.items():
        path = disc(run) / name
        if not path.is_file():
            return f"no {name} in {where}: --cwd names the directory holding the disc image"
        with path.open("rb") as f:
            got = hashlib.file_digest(f, "sha256").hexdigest()
        if got != want:
            return (f"{path} is not the one this demo was written for (sha256 {got}): the "
                    "script's addresses and the theme's sectors are those of the 1992 Enhanced "
                    "CD as this CUE sheet lays it out")
    return ""


def precheck(run: Run) -> str:
    return disc_check(run) or host.precheck(run)


def boot(run: Run) -> dict[str, Any]:
    """The conf with the reader's CUE written in, the emulator started in the run's directory
    (where the conf's C: is), a fresh log, and the saved states kept there too."""
    drive_c = run.dir / "c"
    shutil.rmtree(drive_c, ignore_errors=True)
    drive_c.mkdir()
    conf = run.dir / "monkey.conf"
    conf.write_text((HERE / "monkey.conf").read_text(encoding="utf-8")
                    .replace("@CD@", str(disc(run) / "monkey.cue")), encoding="utf-8")
    for stale in ("monkey-e9.log", "theme.wav", "theme-disc.wav", "screen.png"):
        (run.dir / stale).unlink(missing_ok=True)
    shutil.rmtree(run.dir / "monkey-states", ignore_errors=True)
    return {**window_args(run), "conf": conf, "cwd": run.dir, "session_seconds": 1800,
            "program": "D:\\MONKEY.COM",
            "logfile": run.dir / "monkey-e9.log", "state_dir": run.dir / "monkey-states"}


def found(name: str) -> Any:
    """`screen_map_find` names screen `name`."""
    def check(reply: Reply, run: Run) -> str:
        expect(reply["matched"] is True and reply.get("screen") == name,
               f"screen_map_find answered {reply.get('screen', 'no screen')}, not {name}")
        return f"the map says: {name}"
    return check


def find(step: str, screen: str) -> Step:
    return Step(step, "screen_map_find", {}, found(screen))


def performed(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["failed_at"].get("available") is False,
               f"{reply['steps_completed']} steps, failed at {reply['failed_at']}")
        return what
    return check


def act(step: str, ops: list[dict[str, Any]], what: str) -> Step:
    return Step(step, "perform", {"steps": ops, "summaries": True}, performed(what),
                volatile=STOP_IN_LOOP)


def psp(run: Run) -> int:
    """`MONKEY.EXE`'s PSP: the launcher is a MONKEY too, with far less memory."""
    owners = [(m["size_bytes"], m["psp_seg"]) for m in run.replies["placed"]["mcbs"]
              if m.get("filename") == "MONKEY" and m.get("notes") != "free"]
    expect(bool(owners), "no memory block of MONKEY.EXE in the machine's map")
    return int(max(owners)[1], 16)


def tick(run: Run) -> str:
    """SCUMM's tick, at the code segment DOS loaded `MONKEY.EXE` at."""
    return f"{psp(run) + 0x10:04X}:{TICK_OFFSET:04X}"


def room(run: Run) -> str:
    """SCUMM's room variable."""
    return f"{psp(run) + 0x10 + DATA_PARAGRAPHS:04X}:{ROOM:04X}"


def intro(run: Run) -> dict[str, Any]:
    """A change watch on the room to the intro's first scene, then SCUMM's tick with an Escape
    after the first and every `SKIP_EVERY`th past it, and the room read at the end."""
    read = {"op": "read_memory", "ref": room(run), "length": 2}
    ticks: list[dict[str, Any]] = []
    for t in range(SKIP_TICKS):
        ticks.append({"op": "resume", "seconds": ARRIVE_S})
        if t % SKIP_EVERY == 0:
            ticks.append({"op": "send_keys", "keys": ["escape"]})
    return {"steps": [{"op": "watch_add", "ref": room(run), "mode": "change", "fmt": "u16"},
                      *[{"op": "resume", "seconds": INTRO_S}, read] * len(INTRO_ROOMS),
                      {"op": "declaration_clear", "kind": "watch", "all": True},
                      {"op": "breakpoint_at", "ref": tick(run)}, *ticks, read,
                      {"op": "declaration_clear", "kind": "breakpoint", "all": True}],
            "settle_seconds": INTRO_S, "summaries": True}


def roomed(reply: Reply, run: Run) -> str:
    rows = [r for r in replies(reply) if "hex" in r]
    got = tuple(int.from_bytes(bytes.fromhex(r["hex"]), "little") for r in rows)
    want = (*INTRO_ROOMS, TITLE_ROOM)
    expect(got == want, f"the room variable read {got}, not {want}")
    return (f"the room variable read {', '.join(map(str, got[:-1]))} up to the first scene; "
            f"Escapes at SCUMM's ticks skipped it to the title card, room {got[-1]}")


def at_tick(screen: str, seconds: float, run: Run) -> list[dict[str, Any]]:
    """Wait for `screen`, judged only at the frame after a SCUMM tick, the stop declared for the
    wait alone."""
    return [{"op": "breakpoint_at", "ref": tick(run)},
            {"op": "screen_wait", "screen": screen, "on_breakpoint": tick(run),
             "seconds": seconds},
            {"op": "declaration_clear", "kind": "breakpoint", "all": True}]


def placed(reply: Reply, run: Run) -> str:
    return f"SCUMM's tick at {tick(run)}"


def line(step: str, screen: str) -> Step:
    """A line of the lookout's, which the CD's audio paces: the game waits for the track while the
    line is up, and the track plays only while the machine runs, so a judgement at every SCUMM
    tick (a stop each) costs hundreds of stops a line; the screen is sampled instead."""
    def check(reply: Reply, run: Run) -> str:
        performed("")(reply, run)
        said: str = found(screen)(Reply(reply["ran"][-1]["reply"]), run)
        return said
    return Step(step, "perform",
                {"steps": [{"op": "screen_wait", "screen": screen, "every": JUDGED_EVERY,
                            "seconds": ARRIVE_S}, SETTLE, {"op": "screen_map_find"}],
                 "summaries": True}, check, volatile=STOP_IN_LOOP)


def go(step: str, ops: list[dict[str, Any]], screen: str) -> Step:
    """A gesture and the screen it brings, in one call: the machine runs until the map names
    `screen` at a SCUMM tick, however long this host takes to get there, and the last reply,
    `screen_map_find`'s, must name it."""
    def check(reply: Reply, run: Run) -> str:
        performed("")(reply, run)
        said: str = found(screen)(Reply(reply["ran"][-1]["reply"]), run)
        return said
    return Step(step, "perform",
                lambda run: {"steps": [*ops, *at_tick(screen, ARRIVE_S, run), SETTLE,
                                       {"op": "screen_map_find"}], "summaries": True},
                check, volatile=STOP_IN_LOOP)


def replies(reply: Reply) -> list[dict[str, Any]]:
    """Every step's whole reply, which a `perform` with `summaries` keeps in a file beside it."""
    performed("")(reply, Run(dir=Path()))
    if not isinstance(reply["replies_path"], str):
        raise Invalid(f"the call kept no replies to check: {reply['replies_path']}")
    rows = [json.loads(line)["reply"] for line in
            Path(reply["replies_path"]).read_text(encoding="utf-8").splitlines()]
    expect(len(rows) == reply["steps_completed"],
           f"{len(rows)} replies kept for {reply['steps_completed']} steps")
    return rows


def hover(target: str) -> list[dict[str, Any]]:
    """The pointer over a control."""
    return [{"op": "send_mouse", "target": target}]


def click(target: str, action: str = "click") -> dict[str, Any]:
    return {"op": "send_mouse", "target": target, "button": "left", "action": action}


def arrived(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}")
    return f"the machine run until the map names {reply['screen']}"


# ---------------------------------------------------------------- the lookout's script

def needle_at(run: Run) -> int:
    """H, the linear address of the sentence `find` located."""
    seg, off = (int(v, 16) for v in run.replies["needle"]["hits"][0].split(":"))
    return seg * 16 + off


def ref(linear: int) -> str:
    return f"{linear >> 4:04X}:{linear & 15:04X}"


def spans(start: int, end: int) -> list[tuple[int, int]]:
    """[start, end) in reads or writes of at most 128 bytes, the tools' own limit."""
    return [(a, min(a + 128, end)) for a in range(start, end, 128)]


def needle_found(reply: Reply, run: Run) -> str:
    expect(reply["hits_total"] == 1, f"{reply['hits_total']} copies of the line, not one")
    return f"the lookout's line, once, at {reply['hits'][0]}"


def originals(run: Run) -> dict[str, Any]:
    h = needle_at(run)
    holes = [*lookout.HOLES, lookout.TAIL]
    return {"steps": [{"op": "read_memory", "ref": ref(h + a), "length": b - a}
                      for start, end, _ in holes for a, b in spans(start, end)],
            "summaries": True}


def originals_held(reply: Reply, run: Run) -> str:
    data = b"".join(bytes.fromhex(r["hex"]) for r in replies(reply))
    at = 0
    for start, end, want in [*lookout.HOLES, lookout.TAIL]:
        got = hashlib.sha256(data[at:at + end - start]).hexdigest()
        expect(got == want, f"the game's bytes at H{start:+#x} hash {got}, not the disc's")
        at += end - start
    return f"{at} bytes around the line are the disc's own script, hole by hole"


def writes(run: Run) -> list[dict[str, Any]]:
    """The new conversation as `write`s: the first holds the lookout's new line."""
    h = needle_at(run)
    ops = []
    for start, data in lookout.layout():
        for a, b in spans(0, len(data)):
            ops.append({"ref": ref(h + start + a), "data_hex": data[a:b].hex()})
    return ops


def new_line(reply: Reply, run: Run) -> str:
    expect(reply["verified"] is True, f"read back {reply['readback']}")
    return "the lookout's new line written over his script, read back"


def rewrite(run: Run) -> dict[str, Any]:
    return {"steps": [{"op": "write", **op} for op in writes(run)[1:]], "summaries": True}


def rewritten(reply: Reply, run: Run) -> str:
    expect(all(r["verified"] for r in replies(reply)), "a write did not read back")
    total = sum(len(data) for _, data in lookout.layout())
    return (f"with the new line, {len(lookout.TALK)} speeches, {total} bytes of bytecode over "
            f"{len(lookout.layout())} holes, each read back")


# ---------------------------------------------------------------- the drive's requests

def request_ref(stop: str) -> Any:
    """The MSCDEX device request ES:BX points at, at the stop of step `stop`."""
    def args(run: Run) -> dict[str, Any]:
        regs = run.replies[stop]["regs"]
        return {"ref": f"{int(regs['ES'], 16):04X}:{int(regs['EBX'], 16) & 0xFFFF:04X}",
                "length": 22}
    return args


def at_mscdex(reply: Reply, run: Run) -> str:
    expect(reply["instruction"]["text"] == "int 0x2f" and reply["regs"]["EAX"].endswith("1510"),
           f"stopped at {reply['instruction']['text']} with AX {reply['regs']['EAX']}")
    return "stopped on INT 2Fh AX=1510h, a request to the CD driver"


def track_start(run: Run) -> int:
    """The theme's first sector on the disc: every BIN before it, plus the lead-in."""
    names = sorted(p.name for p in disc(run).glob("monkey*.bin"))
    before = names[:names.index(THEME)]
    return LEAD_IN + sum((disc(run) / n).stat().st_size // RAW_SECTOR for n in before)


def red_book(sector: int) -> bytes:
    """A sector as Red Book addresses it in a request: frame, second, minute, 0."""
    return bytes([sector % 75, sector // 75 % 60, sector // 4500, 0])


def stop_request(reply: Reply, run: Run) -> str:
    command = bytes.fromhex(reply["hex"])[2]
    expect(command == 0x85, f"the request's command is {command:#04x}, not STOP AUDIO")
    return "STOP AUDIO (85h), let through"


def play_request(reply: Reply, run: Run) -> str:
    raw = bytes.fromhex(reply["hex"])
    expect(raw[2] == 0x84 and raw[13] == 1, f"command {raw[2]:#04x} in addressing mode "
           f"{raw[13]}, not PLAY AUDIO (84h) by Red Book address (mode 1)")
    start = track_start(run)
    expect(raw[14:18] == red_book(start), f"it starts at {raw[14:18].hex()}, not the theme's "
           f"first sector {red_book(start).hex()}")
    count = int.from_bytes(raw[18:22], "little")
    return (f"PLAY AUDIO (84h) from {start // 4500:02}:{start // 75 % 60:02}:{start % 75:02}, "
            f"the theme's first sector, for {count} sectors")


def to_the_logo(run: Run) -> dict[str, Any]:
    """The request moved to the logo's bar, its count shortened by as much."""
    raw = bytes.fromhex(run.replies["request 3"]["hex"])
    count = int.from_bytes(raw[18:22], "little") - LOGO
    req = request_ref("third")(run)["ref"]
    seg, off = (int(v, 16) for v in req.split(":"))
    return {"ref": f"{seg:04X}:{off + 14:04X}",
            "data_hex": (red_book(track_start(run) + LOGO) + count.to_bytes(4, "little")).hex()}


def moved(reply: Reply, run: Run) -> str:
    expect(reply["verified"] is True, f"read back {reply['readback']}")
    s = track_start(run) + LOGO
    return f"the drive will start at {s // 4500:02}:{s // 75 % 60:02}:{s % 75:02}, the logo's bar"


def reference(run: Run) -> dict[str, Any]:
    """The same span of the reader's own track 18, as a WAV, beside the recording."""
    samples = run.replies["theme"]["samples"]
    dest = run.dir / "theme-disc.wav"
    with (disc(run) / THEME).open("rb") as f:
        f.seek(LOGO * RAW_SECTOR)
        pcm = bytes(4 * MIXER_LAG) + f.read((samples - MIXER_LAG) * 4)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(pcm)
    return {"method": "diff", "a": run.replies["theme"]["path"], "b": dest, "align": False}


def recorded(reply: Reply, run: Run) -> str:
    expect(reply["sample_rate_hz"] == 44100 and reply["sample_max"] > 0,
           f"{reply['sample_rate_hz']} Hz, peak {reply['sample_max']}")
    return f"{reply['emulated_s']:.1f} s of the mixer at {reply['sample_rate_hz']} Hz"


def same_track(reply: Reply, run: Run) -> str:
    """The recording is the disc's own samples through DOSBox-X's mixer, which touches them on
    the way: past MIN_SNR_DB, sample for sample. Another bar of the track, or the drive's volume
    applied twice, lands far below it."""
    if reply["exact"] is True:
        return "the reader's own track 18 from the logo's bar, identical sample for sample"
    expect(reply["snr_db"] >= MIN_SNR_DB,
           f"the recording is not the disc's track from the logo's bar (SNR {reply['snr_db']} "
           f"dB, envelope {reply['envelope_correlation']}); if your DOSBox-X scales the drive's "
           "volume by its 0-255 value, it plays the track four times as loud, clipped")
    return (f"the reader's own track 18 from the logo's bar, compared sample against sample with "
            f"no realigning, SNR {reply['snr_db']} dB")


#: The retraces recorded while the lookout says his own line, and his new one, for the loop.
LINE_FRAMES, NEW_LINE_FRAMES = 150, 240

STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer",
                   "kept": "it names the run's directory when the run lies in no project with a "
                           "`.scry/`"}),
    Step("map", "screen_map_write", {"method": "load", "path": HERE / "monkey-screen-map.json"},
         lambda reply, run: f"{reply['screens']} screens, {reply['controls']} controls"),
    Step("menu", "screen_wait", {"screen": "language", "every": JUDGED_EVERY,
                                 "seconds": ARRIVE_S}, arrived,
         volatile={key: "a sampled stop lands where the launcher's loop is, which drifts with the "
                        "host's cycles" for key in ("pc", "regs", "instruction", "cause")}),
    find("languages", "language"),
    Step("placed", "machine_map", {}, placed,
         volatile={"eflags": "the flags at the sampled stop before it, which drift with the "
                             "host's cycles"}),
    act("english", [click("english", "double")], "a double click on English"),
    Step("intro", "perform", intro, roomed, volatile=STOP_IN_LOOP,
         title="Follow the intro by the game's own variable",
         ask="Skip the intro, stopping at each room the game enters, until its title card.",
         shown=("steps_completed", "steps_total", "failed_at"),
         reads=("A change watch on the game's room number stops it at each room the intro "
                "enters. The Escapes that skip it go in at the game's own ticks, so the run "
                "arrives at any speed.")),
    Step("title", "perform", lambda run: {"steps": at_tick("part one", ARRIVE_S, run),
                                          "summaries": True},
         performed("the title card, judged at SCUMM's tick"), volatile=STOP_IN_LOOP),
    Step("pointer", "screen_map_write", {"method": "pointer", "pointer": GAME_POINTER},
         lambda reply, run: "the game's own pointer declared: each move is steered onto it"),
    go("dock", [], "dock"),
    go("hover poster", hover("poster"), "dock: walk to poster"),
    go("to the poster", [click("poster")], "by the poster"),
    go("look at", [click("look_at"), *hover("poster")], "by the poster: look at poster"),
    go("read", [click("poster")], "poster: re-elect governor marley"),
    go("read on", [], "poster: only one candidate"),
    go("done reading", [], "by the poster: walk to poster"),
    go("way back", [click("way_back")], "dock: walk to cliffside"),
    go("climb", [click("cliffside"), SKY], "cliff"),
    go("talk to", [click("talk_to"), *hover("lookout")], "cliff: talk to lookout"),
    go("greet", [click("lookout")], "greeting choices"),
    go("hover novel", hover("characters_in_a_novel"), "greeting: characters in a novel"),
    go("ask", [click("characters_in_a_novel"), AWAY], "name choices"),
    go("hover name", hover("im_guybrush_threepwood"), "name: im guybrush threepwood"),
    go("tell", [click("im_guybrush_threepwood"), AWAY], "name choices again"),
    go("hover heck", hover("whats_wrong_with_my_name"), "name: whats wrong with my name"),
    Step("save", "state_write", {"method": "save", "name": "comeback"},
         lambda reply, run: "the machine saved with the comeback under the pointer",
         volatile={"summary": "it carries the state's size and time",
                   "bytes": "the state is compressed, and its size follows what the guest holds"}),
    go("before", [click("whats_wrong_with_my_name")], "lookout: sell shoes"),
    recording("own line", LINE_FRAMES),
    go("said", [], "name choices left"),
    Step("restore", "state_write", {"method": "load", "name": "comeback"},
         lambda reply, run: "the machine back to before the click"),
    Step("heck again?", "screen_map_find", {}, found("name: whats wrong with my name"),
         volatile=STOP_PLACE),
    Step("needle", "find", {"data_hex": lookout.NEEDLE.hex(), "ref": "0000:0000",
                            "length": 0xA0000}, needle_found),
    Step("script", "perform", originals, originals_held,
         volatile={"ran": "the game's own bytes, which this repository does not carry: the "
                          "step's line gives their sha256 verdict"}),
    Step("line written", "write", lambda run: writes(run)[0], new_line),
    Step("rewrite", "perform", rewrite, rewritten,
         title="Write a new conversation into the game",
         ask="Write the new lines over the lookout's script, and read each write back.",
         shown=("summary", "steps_completed"),
         reads=("The game's script is data in memory. This call writes new bytecode over three "
                "stretches the game no longer needs, and reads each `write` back.")),
    Step("arm", "breakpoint_interrupt", {"number": "0x2F", "ah": "0x15"},
         lambda reply, run: "a stop on every request to the CD driver"),
    act("pick", [click("whats_wrong_with_my_name")], "the same comeback, picked again"),
    Step("first", "resume", {"seconds": 30}, at_mscdex),
    Step("request 1", "read_memory", request_ref("first"), stop_request),
    act("pass 1", [{"op": "step", "mode": "over"}], "the request answered"),
    Step("second", "resume", {"seconds": 30}, at_mscdex),
    Step("request 2", "read_memory", request_ref("second"), stop_request),
    act("pass 2", [{"op": "step", "mode": "over"}], "the request answered"),
    Step("third", "resume", {"seconds": 30}, at_mscdex),
    Step("request 3", "read_memory", request_ref("third"), play_request,
         title="Read what the game asks the CD drive",
         ask="The game stopped on a request to the CD driver. Read the request block.",
         shown=("summary", "length"),
         reads=("`breakpoint_interrupt` stops the game on every call to the CD driver. This "
                "block is its PLAY AUDIO request, with the sector the theme starts at.")),
    Step("to the logo", "write", to_the_logo, moved),
    Step("disarm", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the stop on the CD driver cleared"),
    Step("theme", "audio_record", lambda run: {"frames": THEME_FRAMES,
                                               "dest": run.dir / "theme.wav"}, recorded,
         volatile=STOP_PLACE),
    Step("the disc", "audio_compare", reference, same_track,
         title="Check the music against the disc",
         ask="Compare the theme you recorded with the same track read from the disc image.",
         shown=("summary", "exact"),
         reads=("The reply says whether the two recordings are equal (`exact`) and, if not, how "
                "far apart (`class`). What the demo says about the music is a measurement.")),
    find("music?", "guybrush: a debugger that plays music"),
    line("talk 1", "lookout: the orange tycoon"),
    line("talk 2", "lookout: those files"),
    line("talk 3", "lookout: still not a wave"),
    line("talk 4", "lookout: humor first"),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png", "scale": 2},
         host.pictured),
    recording("new line", NEW_LINE_FRAMES),
    go("goodbye", [SKY], "cliff"),
    go("walk off", [click("way_out")], "dark"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]

DEMO = Demo(
    name="monkey", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS, capture=lambda run: run.dir / "screen.png",
    moments=(Moment("before", "own line",
                    "`record` films the lookout answering a comeback as the game wrote him.",
                    frames=LINE_FRAMES),
             Moment("screen", "new line", "After `write` puts new bytecode over his script, he "
                                          "says a line the game never had.", frames=180)),
    alt="Monkey Island's lookout answering as written, then with a line written into memory",
    lead=Lead(front=ROOT / "README.md", step="line written",
              ask='Make the lookout say "Nothing, if you\'re a Scry debugger."',
              caption="The Secret of Monkey Island under this server: the lookout answers as "
                      "written, then with a line written over his script in memory.",
              answer=("bytes_written", "verified")),
    offers=frozenset({"cwd", "display"}), reads=frozenset({"cwd"}), precheck=precheck,
    host_args={"display": DISPLAY,
               "binary": "the host's own DOSBox-X"},
    volatile={**VOLATILE, "saved_at": "the wall-clock time a state was saved at",
              **{key: WAIT_LOOP for key in ("stop_seq", "stops", "polls",
                                            "output_bytes_dropped")},
              **{key: "the emulator's own count, a few cycles apart from run to run: the "
                      "host's events reach the guest when the host delivers them"
                 for key in ("cycles", "emulated_s", "emulated_before_s", "emulated_after_s")},
              **{key: "the retrace a wait saw its screen at, which follows the host"
                 for key in ("frame", "frame_before", "frame_after", "identified_at_stop",
                             "retrace_pending")},
              "conf_digest": "the conf names the reader's own directories",
              "window": "the host's display and the window it fits",
              "session": "it counts the debugger's output dropped while the game ran, when any "
                         "was, which follows the host's clock"})


if __name__ == "__main__":
    isolated_store("monkey")
    sys.exit(decorated.main(DEMO, LAYERS))
