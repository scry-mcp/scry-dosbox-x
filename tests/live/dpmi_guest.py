"""The package's DPMI guest (`tests/guest/dpmi.c`) as the live tier knows it: its files, how it is
started, and the marks it writes on E9, each one written by `dpmi.c` itself. Shared by the matrix
and the pytest live files; runs nothing at import."""
from __future__ import annotations

from pathlib import Path

GUEST = Path(__file__).resolve().parents[1] / "guest"
CONF = GUEST / "dpmi.conf"
EXE = GUEST / "dpmi.exe"
SYM = GUEST / "dpmi.sym"
#: The command line `start(program=...)` types: the guest, and the file it reads at its start,
#: its own source through the second drive.
PROGRAM = "DPMI.EXE D:\\DPMI.C"

#: The first line the guest writes, which says it STARTED and no more.
BOOT_MARK = "BOOT  . start"
#: Written every so many retraces once the input loop runs.
SETTLED_MARK = r"TICK\s+\.\s+ticks="
#: Written only by the `a` key's handler.
KEY_MARK = "key_cue_a="
#: F11's arrival line: every key is announced, and F11 is answered by nothing else.
ARRIVAL_MARK = "key down F11"
#: Written on a button press, with the guest's own pointer position.
MOUSE_MARK = "mouse btn="
#: Every line opens with the guest's own clock, `[+SSSS.mmm]`.
E9_STAMP = r"\[\+(\d+\.\d+)\]"

#: alt+x opens the quit question; `right` then `enter` answers it, quit.
ASK_MARK = "ask opens"
ANSWER_MARK = r"ask res=1"

#: The function called once a retrace, after the guest has logged; and the globals it keeps
#: (`nm` prints a C name with its leading underscore).
STOP = "_tick"
WATCHES = ("_g_ticks", "_g_file_bytes")
#: The function called once, at the start, and done by the first `_tick` stop.
LOADED_ONCE = "_load_file"
