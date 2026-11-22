"""What this server supports."""

from __future__ import annotations

from scry_core.knowledge import Scope, Support, shared

PINS = {
    "dosbox-x": shared.PINS["dosbox-x"],
    "mame": shared.PINS["mame"],
    "rbil61": "release 61, 16 July 2000",
}

SUPPORT = Support(scopes=(Scope("ibm-pc", written=("call", "error")), *shared.CPUS),
                  chips=shared.CHIPS)
