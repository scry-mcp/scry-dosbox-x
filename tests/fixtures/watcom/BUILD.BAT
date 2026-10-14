@ECHO OFF
REM Build MAPDEMO.C 32-bit with Open Watcom and leave its linker map beside it.
REM
REM OPTION STATICS is what puts the static symbols in the map. Without it the map lists
REM only publics, and the mark this artefact exists to capture -- the one GLUED to the
REM address -- never appears.
REM
REM The switcher is CALLed BY FULL PATH: this runs from a build-only config that does not
REM run the tree's own AUTOEXEC.BAT, so C:\UTIL is not on the PATH yet and a bare name
REM finds nothing, in silence.
CALL C:\UTIL\OW20.BAT
D:
CD \
IF EXIST MAPDEMO.OBJ DEL MAPDEMO.OBJ
IF EXIST MAPDEMO.EXE DEL MAPDEMO.EXE
IF EXIST MAPDEMO.MAP DEL MAPDEMO.MAP
IF EXIST BUILD.LOG DEL BUILD.LOG
ECHO --- WCC386 --- > BUILD.LOG
WCC386 -4 -mf -oc MAPDEMO.C >> BUILD.LOG
ECHO --- WLINK --- >> BUILD.LOG
WLINK SYSTEM DOS4G NAME MAPDEMO FILE MAPDEMO.OBJ OPTION MAP=MAPDEMO.MAP, STATICS, VERBOSE >> BUILD.LOG
