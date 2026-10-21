#!/usr/bin/env bash
# Re-make the DJGPP fixtures: `mapdemo.sym` (an `nm` listing) and `mapdemo.ld.map` (a
# GNU `ld` link map), from `mapdemo.c` in this directory.
#
# WHY THE RECIPE SHIPS WITH THE FIXTURE. A captured artefact whose generator is lost
# cannot be re-captured, so any question about it -- was that column really `B`, does
# this toolchain still emit that shape -- becomes unanswerable. MEASURED as a real cost
# on this package: an earlier session's Watcom map went missing from disk, and a
# discrepancy in its transcription can no longer be settled by anybody.
#
# THE TOOLCHAIN IS NOT IN THIS REPOSITORY and is not vendored here: it is a DJGPP cross
# compiler, installed separately. `DJGPP_BIN` says where its `bin` is. Without it this
# stops loudly rather than producing a fixture from the HOST compiler, which would be a
# different program's symbol table under this program's name.
set -euo pipefail
cd "$(dirname "$0")"
# NO APOSTROPHE IN THIS MESSAGE. bash parses the text of a `${VAR:?msg}` expansion, so
# "toolchain's" opened a quote and the whole script died with `unexpected EOF while
# looking for matching quote` -- at LOAD time, before line 1 ran. MEASURED here.
bin="${DJGPP_BIN:?set DJGPP_BIN to the bin directory of the DJGPP cross toolchain}"
# COMPILED THEN LINKED, so the map names `mapdemo.o` and not the compiler's temporary object
# under the host's per-user temporary directory.
"$bin/i586-pc-msdosdjgpp-gcc" -O0 -c -o mapdemo.o mapdemo.c
"$bin/i586-pc-msdosdjgpp-gcc" -O0 -Wl,-Map,mapdemo.ld.map -o mapdemo.exe mapdemo.o
"$bin/i586-pc-msdosdjgpp-nm" mapdemo.exe > mapdemo.sym
# The executable is NOT kept: this package reads TEXT and never a binary, so a 148 KB
# .exe in the fixtures would be 148 KB nothing reads.
rm -f mapdemo.exe mapdemo.o
# `|| true` ON THE COUNT, because `grep -c` exits 1 on zero matches and `set -e` would
# then kill the script at the moment it had something to report. The count itself is
# what says whether the run produced anything: a 0 here is a fixture with no symbols.
n=$(grep -cE '^[0-9a-f]+ [A-Za-z] ' mapdemo.sym || true)
[ "${n:-0}" -gt 0 ] || { echo "INVALID: mapdemo.sym carries no addressed symbol line" >&2; exit 3; }
echo "mapdemo.sym: $n addressed symbols"
echo "mapdemo.ld.map: $(wc -l < mapdemo.ld.map) lines"
