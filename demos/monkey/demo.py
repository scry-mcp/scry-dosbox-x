"""The Monkey Island demo: LucasArts' The Secret of Monkey Island, the 1992 Enhanced CD, driven by
name off a screen map with the guest's own mouse, then rewritten while it runs: the lookout on
the opening cliff answers with a conversation of ours, and the CD plays the opening theme from
the bar where the logo enters, every answer checked. `--help` says how to run it.

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

from scry_core.demo import Demo, Reply, Run, Step, main
from scry_core.verdict import Invalid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import host  # noqa: E402
from demos.host import VOLATILE, expect, isolated_store, started  # noqa: E402
from demos.monkey import lookout  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
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
#: Where the pointer waits while a screen is judged: over the sky, off every region the map signs.
SKY = {"op": "send_mouse", "x": 250, "y": 20}
#: Where the pointer goes once a line is picked: above the menu, so the next one is judged whole.
AWAY = {"op": "send_mouse", "x": 160, "y": 60}
#: Retraces from a click to the menu it brings, on the conf's fixed clock, plus ten: the menus
#: are picked from as they come, as a player would. After a line is picked the pointer moves
#: away first; after the lookout is clicked it stays on him, off the menu.
GREET_FRAMES, ASK_FRAMES, TELL_FRAMES = 77 + 10, 1036 + 10, 1253 + 10


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
    """The conf with the reader's CUE and the run's own C: written in, a fresh log, and the
    saved states kept in the run's directory too."""
    drive_c = run.dir / "c"
    shutil.rmtree(drive_c, ignore_errors=True)
    drive_c.mkdir()
    conf = run.dir / "monkey.conf"
    conf.write_text((HERE / "monkey.conf").read_text(encoding="utf-8")
                    .replace("@CD@", str(disc(run) / "monkey.cue"))
                    .replace("@RUN@", str(drive_c)), encoding="utf-8")
    for stale in ("monkey-e9.log", "theme.wav", "theme-disc.wav", "screen.png"):
        (run.dir / stale).unlink(missing_ok=True)
    shutil.rmtree(run.dir / "monkey-states", ignore_errors=True)
    return {"conf": conf, "session_seconds": 1800, "shared": True, "program": "D:\\MONKEY.COM",
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
    return Step(step, "perform", {"steps": ops, "summaries": True}, performed(what))


def go(step: str, ops: list[dict[str, Any]], screen: str) -> Step:
    """A gesture and the screen it lands on, in one call: the last reply is
    `screen_map_find`'s, and it must name `screen`."""
    def check(reply: Reply, run: Run) -> str:
        performed("")(reply, run)
        said: str = found(screen)(Reply(reply["ran"][-1]["reply"]), run)
        return said
    return Step(step, "perform", {"steps": [*ops, {"op": "screen_map_find"}],
                                  "summaries": True}, check)


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
    """The pointer over a control, then the retraces the game takes to answer it."""
    return [{"op": "send_mouse", "target": target}, {"op": "run_for", "frames": 5}]


def click(target: str, action: str = "click") -> dict[str, Any]:
    return {"op": "send_mouse", "target": target, "button": "left", "action": action}


def ran(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "ELAPSED", f"verdict {reply['verdict']}")
    return f"{reply['emulated_after_s'] - reply['emulated_before_s']:.1f} s of the guest's time"


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


def rewrite(run: Run) -> dict[str, Any]:
    h = needle_at(run)
    ops = []
    for start, data in lookout.layout():
        for a, b in spans(0, len(data)):
            ops.append({"op": "write", "ref": ref(h + start + a), "data_hex": data[a:b].hex()})
    return {"steps": ops, "summaries": True}


def rewritten(reply: Reply, run: Run) -> str:
    expect(all(r["verified"] for r in replies(reply)), "a write did not read back")
    total = sum(len(data) for _, data in lookout.layout())
    return (f"{len(lookout.TALK)} speeches, {total} bytes of bytecode over "
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


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("menu", "run_for", {"milliseconds": 11000, "seconds": 120}, ran),
    Step("map", "screen_map_write", {"method": "load", "path": HERE / "monkey-screen-map.json"},
         lambda reply, run: f"{reply['screens']} screens, {reply['controls']} controls"),
    find("languages", "language"),
    act("english", [click("english", "double"), {"op": "run_for", "milliseconds": 24000}],
        "a double click on English, and the intro run on"),
    act("skip", [{"op": "send_keys", "keys": ["escape"]}, {"op": "run_for", "milliseconds": 6000},
                 {"op": "send_keys", "keys": ["escape"]}, {"op": "run_for", "milliseconds": 3000},
                 {"op": "send_mouse", "x": 319, "y": 199}, {"op": "send_mouse", "x": 0, "y": 0},
                 SKY], "Escape twice, as a player skips the credits and the opening scene; "
                       "behind the title card, the pointer swept to both corners so the game's "
                       "own pointer and the driver's agree"),
    go("dock", [{"op": "run_for", "milliseconds": 16000}], "dock"),
    go("hover poster", hover("poster"), "dock: walk to poster"),
    go("to the poster", [click("poster"), {"op": "run_for", "milliseconds": 8000}],
       "by the poster"),
    go("look at", [click("look_at"), *hover("poster")], "by the poster: look at poster"),
    go("read", [click("poster"), {"op": "run_for", "milliseconds": 1500}],
       "poster: re-elect governor marley"),
    go("read on", [{"op": "run_for", "milliseconds": 2000}], "poster: only one candidate"),
    go("done reading", [{"op": "run_for", "milliseconds": 3500}],
       "by the poster: walk to poster"),
    go("way back", [click("way_back"), {"op": "run_for", "milliseconds": 4000}],
       "dock: walk to cliffside"),
    go("climb", [click("cliffside"), {"op": "run_for", "milliseconds": 8000}, SKY,
                 {"op": "run_for", "frames": 10}], "cliff"),
    go("talk to", [click("talk_to"), *hover("lookout")], "cliff: talk to lookout"),
    go("greet", [click("lookout"), {"op": "run_for", "frames": GREET_FRAMES}],
       "greeting choices"),
    go("hover novel", hover("characters_in_a_novel"), "greeting: characters in a novel"),
    go("ask", [click("characters_in_a_novel"), AWAY, {"op": "run_for", "frames": ASK_FRAMES}],
       "name choices"),
    go("hover name", hover("im_guybrush_threepwood"), "name: im guybrush threepwood"),
    go("tell", [click("im_guybrush_threepwood"), AWAY, {"op": "run_for", "frames": TELL_FRAMES}],
       "name choices again"),
    go("hover heck", hover("whats_wrong_with_my_name"), "name: whats wrong with my name"),
    Step("save", "state_write", {"method": "save", "name": "comeback"},
         lambda reply, run: "the machine saved with the comeback under the pointer",
         volatile={"summary": "it carries the state's size and time",
                   "bytes": "the state is compressed, and its size follows what the guest holds"}),
    go("before", [click("whats_wrong_with_my_name"), {"op": "run_for", "milliseconds": 4000}],
       "lookout: sell shoes"),
    Step("restore", "state_write", {"method": "load", "name": "comeback"},
         lambda reply, run: "the machine back to before the click"),
    find("heck again?", "name: whats wrong with my name"),
    Step("needle", "find", {"data_hex": lookout.NEEDLE.hex(), "ref": "0000:0000",
                            "length": 0xA0000}, needle_found),
    Step("script", "perform", originals, originals_held,
         volatile={"ran": "the game's own bytes, which this repository does not carry: the "
                          "step's line gives their sha256 verdict"}),
    Step("rewrite", "perform", rewrite, rewritten,
         highlight=("The game's own script is data in memory, so the demo rewrites it. It found "
                    "the lookout's line with `find` and read the original bytes back, and this "
                    "`perform` writes a new conversation of SCUMM bytecode over three stretches of "
                    "the script the game no longer needs, chained by jumps, reading each write "
                    "back. The lookout then says what the demo wrote, in the game's own voice.")),
    Step("arm", "breakpoint_interrupt", {"number": 0x2F, "ah": 0x15},
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
         highlight=("The game asks the CD driver for audio through interrupt 2Fh. "
                    "`breakpoint_interrupt` stops the machine on every such request, and "
                    "`read_memory` reads the request block the call points at: this one is PLAY "
                    "AUDIO, with the sector the theme starts at. The next step writes a different "
                    "start sector into that block, so the same game call plays the theme from the "
                    "bar where the logo enters.")),
    Step("to the logo", "write", to_the_logo, moved),
    Step("disarm", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the stop on the CD driver cleared"),
    Step("theme", "audio_record", lambda run: {"frames": THEME_FRAMES,
                                               "dest": run.dir / "theme.wav"}, recorded),
    Step("the disc", "audio_compare", reference, same_track,
         highlight=("The theme the game played is recorded off the emulated mixer and compared "
                    "with the same track read off the disc image. The reply says whether the two "
                    "are equal (`exact`) and, when they are not, how far apart (`snr_db`, "
                    "`class`), so what the demo claims about the music is a measurement, not a "
                    "listening test.")),
    find("music?", "guybrush: a debugger that plays music"),
    go("talk 1", [{"op": "run_for", "milliseconds": 28000}], "lookout: the orange tycoon"),
    go("talk 2", [{"op": "run_for", "milliseconds": 16000}], "lookout: those files"),
    go("talk 3", [{"op": "run_for", "milliseconds": 12000}], "lookout: still not a wave"),
    go("talk 4", [{"op": "run_for", "milliseconds": 12000}], "lookout: humor first"),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png", "scale": 2},
         host.pictured),
    go("goodbye", [{"op": "run_for", "milliseconds": 30000}, SKY,
                   {"op": "run_for", "frames": 10}], "cliff"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]

DEMO = Demo(
    name="monkey", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS, capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"cwd"}), reads=frozenset({"cwd"}), precheck=precheck,
    host_args={"cwd": "the directory holding the reader's disc image",
               "binary": "the host's own DOSBox-X"},
    volatile={**VOLATILE, "saved_at": "the wall-clock time a state was saved at",
              **{key: WAIT_LOOP for key in ("summary", "pc", "regs", "instruction", "cause",
                                            "stop_seq", "stops", "polls",
                                            "output_bytes_dropped")},
              "session": "it counts the debugger's output dropped while the game ran, when any "
                         "was, which follows the host's clock"})


if __name__ == "__main__":
    isolated_store("monkey")
    sys.exit(main(DEMO))
