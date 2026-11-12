---
paths:
  - "src/scry_dosbox_x/**"
  - "tests/live/**"
---

# The DOSBox-X fork this server is built against

- The DOSBox-X `scry` link is shared by every session, and a session binds its server's Python at
  its own start. Repointing the link at a build whose debugger output changed shape (a new token
  on `RUNSTATE`, a frame on a TAP row) makes a session bound earlier answer `unexpected_answer`
  and list nothing, because its parser ends at the old shape. The parser takes a new token as
  optional in the commit that lands before the link moves, and the handover says the interactive
  sessions must restart to bind the new servers.
- The fork's `scry` branch (what every live run builds) sits on upstream `main-ai`
  (joncampbell123/dosbox-x), well ahead of the fork's own `origin/main-ai`.
  Rebuilding `scry` as `origin/main-ai` plus the capability branches silently drops what
  upstream added, and the rebuilt branch compiles and passes: `git log origin/scry ^<rebuilt>
  --no-merges` is the loss check. The fork needs these branches: each capability goes upstream on
  its own, so it lives on its own branch, and that is the project's structure, not a licence to
  branch. A session opens one only for a capability its plan or card names, never as a safety
  net or a scratch copy. A new capability branch starts from `origin/main-ai`, so it
  stays offerable upstream; `scry` is the published `origin/scry` plus a merge of it, and
  `git diff --stat origin/scry <new>` shows only that branch's files before the force-push with a
  lease. Edit on the capability branch and let the scry tree only build merges: a fix made in the
  build tree after the merge is not carried back. Windows builds the same SHA from
  `scry-sha.txt`.
- New fork work that depends on several branches goes on its own branch off `scry` (as
  `debugger-tap-frame` and `debugger-registerpoint-hit` did), merged back into `scry`; a
  capability that needs nothing of the others starts from `origin/main-ai`. A helper defined on
  an older branch collides when the presence branch merges: swapping the hand-rolled file-name
  code for upstream's `RawCommandArgument` is a rebase task, on its two cards, not before the
  rebase.
- A push of a capability branch runs upstream's own workflows on the fork, and several are
  already red on upstream `main-ai` at the branch's base, so the owner gets failure mails for
  code the branch never touched. Compare `gh run list -R joncampbell123/dosbox-x -b main-ai` at
  the merge-base before touching the branch: only a workflow green upstream and red on ours is
  ours. Disabling Actions on the fork is the owner's call.
- `~/Code/dosbox-x` is a partial clone (`blob:none`): a fresh clone for a from-nothing build fails
  with `--no-local` on a missing promisor blob and works with `git clone --local --branch <name>`.
  `./autogen.sh` first (configure is not tracked); delete the clone after measuring, a heavy build
  is gigabytes on a disk with little room.
- For DOSBox-X a capability matures on the fork and everything goes upstream together when the
  work closes: one branch per capability, used by the server and proved by the live matrices on
  both hosts, so upstream gets no noise before the implementation is proved and no work waits on
  a merge. Before writing a branch, search upstream's pull requests, its issues and the forks
  they mention for the same capability, and use what is already there. A step that touches a
  branch rebases it and reruns the matrices, because the debugger changes often upstream. The
  server names the capability (the command, the build option), never the fork, and what is
  posted upstream is the owner's text, translated.
- On Windows DOSBox-X needs a console of its own: started as a pipe-fed child with none it exits within seconds with `0xC0000409`, and under a ConPTY it stays up but no byte of the debugger's screen arrives, because the debugger draws to the console it owns. So the Windows server starts it with `CREATE_NEW_CONSOLE` and reads everything through the channel. The same exit code has a second cause: `LINES` or `COLUMNS` in the environment make the release build resize its console and die at the debugger's first request.
