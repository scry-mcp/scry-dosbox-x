"""The lookout's new reply, as SCUMM v5 bytecode written over room 33's script in memory.

It outgrows its branch, so it is chained by jumps over three holes: the branch, the lookout's
other answers before it, and the opening scene's script after it, which has played. The last
jump lands on the branch's tail, which ends the conversation as the game does.
"""

from __future__ import annotations

#: Offsets are from H, the first byte of this sentence.
NEEDLE = b"Nothing, if you want to sell shoes."
#: [start, end) in the order the reply runs through them, with the sha256 the game's bytes have.
HOLES = ((-3, 0xE2, "c66dcd9086da070d722f9bd691456a353240738d291d5cf6bdf806d238245ac8"),
         (-0x183, -3, "7b33d8c4139a506a97ee95f481491aa333f21e0a7b5d452af43a02046d35ca37"),
         (0xFE, 0xFE + 730, "f6e214816a072f65fdb7434ce47c15ae288e9420abff52f6c41dfca9821e8db3"))
TAIL = (0xE2, 0xFE, "d732794d728951fa12b6161ee13e5221f6185c43a24a70c19c581ae6cd7f753d")
#: The intro's CD-track sound, the opening theme.
THEME_SOUND = 110

LOOKOUT, GUYBRUSH = "lookout", "guybrush"
#: `FF 03` between a speaker's sentences waits, as the game's lines do; `^` is its ellipsis and
#: `` ` `` its quote mark.
TALK: tuple[tuple[str, tuple[str, ...]], ...] = (
    (LOOKOUT, ("Nothing, if you're a Scry debugger.",
               "It stops time, reads minds and plays the tunes.", "Even my mind.")),
    (GUYBRUSH, ("A debugger that plays music?  Is THAT what I'm hearing??",)),
    (LOOKOUT, ("That's the CD.  Scry just told it where to start.",)),
    (GUYBRUSH, ("Who taught a debugger to do that?",)),
    (LOOKOUT, ("A model.  Lives in a box, reads your memory, never sleeps.",)),
    (GUYBRUSH, ("Like one of those big AI companies?",)),
    (LOOKOUT, ("Them?  A doubloon a word.  Two if you say `please`.",)),
    (GUYBRUSH, ("And Scry?",)),
    (LOOKOUT, ("Free.  And it never says `As a large language pirate^`",)),
    (LOOKOUT, ("Heard about the orange tycoon?",)),
    (GUYBRUSH, ("The one who calls every bug fake news?",)),
    (LOOKOUT, ("Now he wants to rename AI to SI.",
               "`Super Intelligence`.  Tremendous.  The best.")),
    (GUYBRUSH, ("Does SI release its files?",)),
    (LOOKOUT, ("Scry releases every file it finds.  Every.  Last.  One.",
               "Unlike those Epstein files.  Ahem!")),
    (GUYBRUSH, ("And his rocket friend?",)),
    (LOOKOUT, ("The one whose heart flew out through his arm?", "Twice.",
               "Scry stepped through it frame by frame.  Still not a wave.")),
    (GUYBRUSH, ("Should Scry debug them both?",)),
    (LOOKOUT, ("Not enough RAM on this whole island, boy.",)),
    (GUYBRUSH, ("Got any jokes left?",)),
    (LOOKOUT, ("Plenty.  But my late show got cancelled.",
               "So Scry runs it now.  Humor first, crashes second.")),
    (GUYBRUSH, ("I'll just be off to seek my fortune now.",)),
    (LOOKOUT, ("Take Scry with you.", "And clear that breakpoint on your way out.")),
)


def line(who: str, sentences: tuple[str, ...]) -> bytes:
    """The lookout's `print` (actor 2) or Guybrush's `printEgo`, then a wait for the message."""
    head = b"\x14\x02\x0f" if who == LOOKOUT else b"\xd8\x0f"
    return head + b"\xff\x03".join(s.encode("latin-1") for s in sentences) + b"\x00\xae\x02"


def jump(at: int, to: int) -> bytes:
    """`jumpRelative` at `at` to `to`; the offset counts from past the operand."""
    return b"\x18" + (to - (at + 3)).to_bytes(2, "little", signed=True)


def layout() -> list[tuple[int, bytes]]:
    """[(offset from H, bytes)] per hole: the theme, then the speeches that fit, then a jump."""
    speeches = [line(who, said) for who, said in TALK]
    out: list[tuple[int, bytes]] = []
    for k, (start, end, _) in enumerate(HOLES):
        body = bytes([0x1C, THEME_SOUND]) if k == 0 else b""
        while speeches and start + len(body) + len(speeches[0]) + 3 <= end:
            body += speeches.pop(0)
        target = HOLES[k + 1][0] if speeches and k + 1 < len(HOLES) else TAIL[0]
        out.append((start, body + jump(start + len(body), target)))
        if not speeches:
            return out
    raise ValueError(f"{len(speeches)} speeches do not fit the holes")
