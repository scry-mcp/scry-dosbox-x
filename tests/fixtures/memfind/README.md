# Output-pane tails of the debugger's `MEMFIND` / `MEMS` commands

Captured from a live DOSBox-X (Homebrew build, `probe.conf`, parked at the reset vector)
through the server's own `debug` tool, one file per command, the Output pane's tail as the
screen delta carried it. The whole delta is a repaint of the ncurses screen, so each file
holds the pane's LAST lines including what EARLIER commands printed: that is the property the
parser is tested against, and why it reads the last matching line rather than the first.

`memfind_list_page.txt` is the first page of a paged `MEMFIND L` (the marker at its end is
the debugger's own); `memfind_list_last.txt` is what the final page shows with the closing
`Matched values` line.
