"""What this server supports."""

from __future__ import annotations

from scry_core.knowledge import Scope, Support

#: Where each source scheme is pinned.
PINS = {
    "dosbox-x": "2a43c7335efd91f87bf5582245abdd5b3f18d5d4",
    "rbil61": "release 61, 16 July 2000",
}

SUPPORT = Support(scopes=(Scope("ibm-pc", written=("call", "error")),))
