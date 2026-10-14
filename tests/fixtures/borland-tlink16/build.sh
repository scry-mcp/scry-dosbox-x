#!/usr/bin/env bash
# Re-make the Borland TLINK 16-bit fixture `MAPDEMO.MAP` from `MAPMAIN.ASM` and
# `MAPOVL.ASM` in this directory, by running TASM and TLINK in DOSBox-X.
#
# WHY THE RECIPE SHIPS WITH THE FIXTURE: see `../djgpp/build.sh`. The short version is
# that a captured artefact whose generator is lost cannot be re-captured, and this
# package has already paid that cost once.
#
# THE TOOLCHAIN IS NOT IN THIS REPOSITORY. TASM 3.1 and TLINK 3.01 are Borland's and are
# not redistributable here, so `TASM_DIR` says where a copy of them lives. Without it
# this stops rather than emitting a fixture from something else.
#
# IT RUNS HEADLESS. Nobody is watching a fixture being rebuilt, so it must not be able to
# throw a window over whoever is.
set -euo pipefail
cd "$(dirname "$0")"
here="$PWD"
tasm="${TASM_DIR:?set TASM_DIR to a directory holding TASM.EXE and TLINK.EXE}"
dosbox="${DOSBOX_X:-dosbox-x}"
command -v "$dosbox" >/dev/null 2>&1 || { echo "INVALID: no $dosbox on PATH" >&2; exit 3; }
[ -f "$tasm/TASM.EXE" ] && [ -f "$tasm/TLINK.EXE" ] || {
    echo "INVALID: $tasm holds no TASM.EXE and TLINK.EXE" >&2; exit 3; }

conf="$(mktemp -t mapfixture)" && trap 'rm -f "$conf"' EXIT
cat > "$conf" <<CONF
[dosbox]
title=map fixture build
memsize=16
[cpu]
cputype=pentium
cycles=fixed 20000
[dos]
ver=6.22
[autoexec]
mount d "$here"
mount e "$tasm"
d:
call build.bat
exit
CONF
rm -f MAPDEMO.MAP MAPDEMO.EXE MAPMAIN.OBJ MAPOVL.OBJ TASM1.TXT TASM2.TXT TLINK.TXT
SDL_VIDEODRIVER=dummy "$dosbox" -conf "$conf" >/dev/null 2>&1 || true
# THE EMULATOR'S EXIT CODE IS NOT THE BUILD'S. MEASURED: DOSBox-X exits 0 having run a
# guest whose assembler failed, so the only honest verdict is the ARTEFACT. That is why
# the checks below are on the file and not on `$?`.
[ -s MAPDEMO.MAP ] || { echo "INVALID: no MAPDEMO.MAP was produced" >&2; exit 3; }
grep -q "Publics by Name" MAPDEMO.MAP || {
    echo "INVALID: MAPDEMO.MAP has no publics section; see TASM1.TXT/TLINK.TXT" >&2
    exit 3; }
# The intermediates are not kept: only the .MAP is the fixture.
rm -f MAPDEMO.EXE MAPMAIN.OBJ MAPOVL.OBJ TASM1.TXT TASM2.TXT TLINK.TXT
# COUNTED INSIDE THE PUBLICS SECTIONS, not over the whole file. The bare pattern also
# matches the six "Detailed map of segments" rows, which open with the same `seg:off`
# pair -- so this line printed 16 for a file holding 10 publics rows. A false number
# printed by the thing that makes the fixture is a small lie in the worst place.
echo "MAPDEMO.MAP: $(awk '/Publics by/{f=1;next} /^[A-Za-z]/{f=0} f' MAPDEMO.MAP |
    grep -cE '^ [0-9A-Fa-f]{4}:[0-9A-Fa-f]{4,5}' || true) publics rows"
