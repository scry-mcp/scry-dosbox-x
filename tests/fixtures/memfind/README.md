# What the debugger printed to the scan family over its channel

`scry-scan.json` is one live run of the probe guest (`probe.conf`), broken into while it ticks,
on a build carrying the `RUNSTATE` debugger command, with `debugger headless=true` and no terminal: every `MEMFIND` and
`MEMS` the scan tools send, and the ones they refuse, sent through the debugger channel in order
and each reply recorded whole. Each command's reply holds only its own lines, so a parser that
reads the last line of the family reads the one this command printed.
