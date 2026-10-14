#!/usr/bin/env bash
# Re-make the Open Watcom fixture `MAPDEMO.MAP` from `MAPDEMO.C` in this directory, by
# running WCC386 and WLINK in DOSBox-X.
#
# WHY THE RECIPE SHIPS WITH THE FIXTURE: see `../djgpp/build.sh`. A captured artefact
# whose recipe is lost cannot be re-captured, and this package has already paid that
# cost -- the sentence recording it said an earlier Watcom map had "gone missing from
# disk", which turned out to be false, and it stayed uncorrected precisely because
# nobody could re-make the thing and check.
#
# THE TOOLCHAIN IS NOT IN THIS REPOSITORY. Open Watcom lives inside a DOS image;
# `OW_IMAGE` points at the directory mounted as C:, which must hold `UTIL\OW20.BAT`.
# Without it this stops rather than emitting a fixture from something else.
#
# IT RUNS HEADLESS: nobody watches a fixture being rebuilt, so it must not be able to
# throw a window over whoever is.
set -euo pipefail
cd "$(dirname "$0")"
here="$PWD"
image="${OW_IMAGE:?set OW_IMAGE to the DOS image directory that holds UTIL/OW20.BAT}"
dosbox="${DOSBOX_X:-dosbox-x}"
command -v "$dosbox" >/dev/null 2>&1 || { echo "INVALID: no $dosbox on PATH" >&2; exit 3; }
[ -f "$image/UTIL/OW20.BAT" ] || {
    echo "INVALID: $image holds no UTIL/OW20.BAT" >&2; exit 3; }

conf="$(mktemp -t owfixture)" && trap 'rm -f "$conf"' EXIT
cat > "$conf" <<CONF
[dosbox]
title=watcom fixture build
memsize=32
[cpu]
cputype=pentium
cycles=fixed 20000
[dos]
ver=6.22
[autoexec]
mount c "$image"
mount d "$here"
c:
call d:\\build.bat
exit
CONF
rm -f MAPDEMO.MAP MAPDEMO.EXE MAPDEMO.OBJ BUILD.LOG
SDL_VIDEODRIVER=dummy "$dosbox" -conf "$conf" >/dev/null 2>&1 || true
# THE EMULATOR'S EXIT CODE IS NOT THE BUILD'S. DOSBox-X exits 0 having run a guest whose
# compiler failed, so the only honest verdict is the ARTEFACT.
[ -s MAPDEMO.MAP ] || { echo "INVALID: no MAPDEMO.MAP was produced; see BUILD.LOG" >&2; exit 3; }
# THE MARK, NOT THE HEADING, and the difference is the whole guard. The `Memory Map`
# box is emitted by `OPTION MAP`; `OPTION STATICS` is what adds the static rows and the
# `s` glued to the address -- the one shape this artefact exists to capture. A rebuild
# that lost STATICS still prints that heading and still has symbol rows, so the old check
# exited 0, reported a symbol count, and committed a fixture that could no longer express
# the property, while its own message named the option it was not testing.
grep -q "Memory Map" MAPDEMO.MAP || {
    echo "INVALID: MAPDEMO.MAP has no Memory Map section; OPTION MAP missing?" >&2
    exit 3; }
grep -qE '^[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}s ' MAPDEMO.MAP || {
    echo "INVALID: MAPDEMO.MAP carries no static (\`s\`) row, so the glued mark this" >&2
    echo "         fixture exists for is absent. OPTION STATICS missing from BUILD.BAT?" >&2
    exit 3; }
rm -f MAPDEMO.EXE MAPDEMO.OBJ BUILD.LOG
echo "MAPDEMO.MAP: $(grep -cE '^[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}' MAPDEMO.MAP || true) symbol rows"
# THIS FIXTURE IS NOT BYTE-REPRODUCIBLE, and that is the linker and not this script.
# MEASURED across two runs three quarters of a minute apart: the ONLY difference is line
# 4, `Created on:       26/08/25 09:05:39`, which WLINK stamps from the guest clock. The
# Borland fixture next door has no such line and does come back byte-identical.
#
# So the honest check after a re-make is a diff that ignores that one line:
#     diff <(sed 4d old.MAP) <(sed 4d MAPDEMO.MAP)
# It is written here rather than left for somebody to rediscover as a spurious failure.
