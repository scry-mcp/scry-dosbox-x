"""The DPMI guest as the live tier starts it."""
from __future__ import annotations

from live_private import guest_dir

GUEST = guest_dir()
CONF = GUEST / "dpmi.conf"
EXE = GUEST / "dpmi.exe"
SYM = GUEST / "dpmi.sym"
PROGRAM = "DPMI.EXE D:\\DPMI.C"

BOOT_MARK = "BOOT  . start"
SETTLED_MARK = r"TICK\s+\.\s+ticks="
KEY_MARK = "key_cue_a="
ARRIVAL_MARK = "key down F11"
MOUSE_MARK = "mouse btn="
E9_STAMP = r"\[\+(\d+\.\d+)\]"

ASK_MARK = "ask opens"
ANSWER_MARK = r"ask res=1"

#: `nm` prefixes C names with `_`.
STOP = "_tick"
WATCHES = ("_g_ticks", "_g_file_bytes")
LOADED_ONCE = "_load_file"
