# The Comments tools

<!-- scry-reference:begin comment_add -->
## `comment_add`

*Add a comment*

```text
comment_add(ref, text)
```

A comment on a place in the program, kept with this conf's declarations: by symbol it
follows the symbol through a rebuild, by raw `SEG:OFF` it is `stale` once the build changes.
One comment per place: a second at the same linear address, in any spelling, replaces the
text and keeps the held row's `ref`. Nothing is written to the machine.

Arguments: `ref`, a symbol or a `SEG:OFF` (read in the mode the machine is in); `text`, one
printable line, no edge blanks, at most 237 UTF-8 bytes. Needs the machine
STOPPED. Refused `bad_argument` before anything is stored: an empty, blank or `#` ref, a pointer
(`[g]+2`), `symbol+offset`, a `0x` number, a malformed `SEG:OFF`, an offset past its
segment's limit, a bad text; `ambiguous_ref`, a name this table defines twice.

Reply: `comment` (the row: `ref`, `by`, `cpu`, `created_at`, `origin`, `inherited`, `age_s`,
`text`, `addr` once
placed, `state`, `why`), `replaced_comments` (the rows replaced, whole), `declarations`
(`persistent`, true: the store is a file, and `path`, that file), `note` (why the place is
not `resolved`).
A store that cannot be written is `host_failed`, nothing changed.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `text` | string | required |

| reply field | type |
|---|---|
| `comment` | object |
| `declarations` | object |
| `note` | string |
| `replaced_comments` | array |

Example, from a live run:

```json
{
  "ref": "8000:0100",
  "text": "matrix A"
}
```

```json
{
  "summary": "comment_add 8000:0100: 0x00080100, stored",
  "status": "ok",
  "comment": {
    "ref": "8000:0100",
    "by": "address",
    "cpu": {
      "available": false,
      "why": "a DOS machine has one cpu, and every row acts on it"
    },
    "created_at": "2026-10-24T16:10:40+00:00",
    "origin": "2026-10-24T16:09:51+00:00#42835.1",
    "inherited": false,
    "age_s": 0,
    "text": "matrix A",
    "addr": "0x00080100",
    "state": "resolved"
  },
  "replaced_comments": [],
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/dosbox-x-live-matrix-A-n5_zipfr/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_add -->

The place is the LINEAR address, and a `SEG:OFF` is read in the mode the machine is in, so a
comment meant to survive a mode switch is made by symbol. Comments a rebuild or a load brought to
one place are all kept, and a call reaches the one whose ref it spells.

<!-- scry-reference:begin comment_list -->
## `comment_list`

*List the comments*

```text
comment_list()
```

Every comment of this conf, in the order the store holds them, each placed now. Answers
on a RUNNING guest too, typing nothing: then a protected-mode `SEG:OFF` is `unarmable` until
a stop reads its selector's base.

Reply: `comments`, each row with `ref`, `by`, `cpu`, `created_at`, `origin`, `inherited`,
`age_s`, `text`, `addr`
(the linear address, once placed), `state` (`resolved`, `unresolved` no such symbol now,
`ambiguous`, `stale` a raw address not known to be this build's, `unarmable` its place cannot be
worked out now), `why`, and `orphan` on a row from a store that kept no origin;
`comments_total`, `truncated`, `declarations` (`persistent`, `path`); running, also
`last_stop`.

Reference: REFERENCE.md, Declarations.

Takes no argument.

| reply field | type |
|---|---|
| `comments` | array |
| `comments_total` | integer |
| `declarations` | object |
| `truncated` | boolean |

Example, from a live run:

```json
{}
```

```json
{
  "summary": "comment_list: 1 comment",
  "status": "ok",
  "comments": [
    {
      "ref": "8000:0100",
      "by": "address",
      "cpu": {
        "available": false,
        "why": "a DOS machine has one cpu, and every row acts on it"
      },
      "created_at": "2026-10-24T16:10:40+00:00",
      "origin": "2026-10-24T16:09:51+00:00#42835.1",
      "inherited": false,
      "age_s": 0,
      "text": "matrix A",
      "addr": "0x00080100",
      "state": "resolved"
    }
  ],
  "comments_total": 1,
  "truncated": false,
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/dosbox-x-live-matrix-A-n5_zipfr/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_list -->

<!-- scry-reference:begin comment_delete -->
## `comment_delete`

*Delete a comment*

```text
comment_delete(ref)
```

Delete one comment: the one whose own `ref` this spells, else the one at the place it
names. There is no delete-all. Needs the machine STOPPED. Refused `bad_argument` on a ref
no comment could have (empty, a pointer, `+`, `0x`); `unknown_ref` when nothing matches,
naming the refs held.

Reply: `deleted` (the row), `declarations` (`persistent`, `path`), `note`. A store that
cannot be written is `host_failed`, nothing changed.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `ref` | string | required |

| reply field | type |
|---|---|
| `declarations` | object |
| `deleted` | object |
| `note` | string |

Example, from a live run:

```json
{
  "ref": "8000:0100"
}
```

```json
{
  "summary": "comment_delete 8000:0100: 0x00080100 deleted",
  "status": "ok",
  "deleted": {
    "ref": "8000:0100",
    "by": "address",
    "cpu": {
      "available": false,
      "why": "a DOS machine has one cpu, and every row acts on it"
    },
    "created_at": "2026-10-24T16:10:40+00:00",
    "origin": "2026-10-24T16:09:51+00:00#42835.1",
    "inherited": false,
    "age_s": 1,
    "text": "matrix A",
    "addr": "0x00080100",
    "state": "resolved"
  },
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/dosbox-x-live-matrix-A-n5_zipfr/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_delete -->

<!-- scry-reference:begin comment_save -->
## `comment_save`

*Save the comments to a file*

```text
comment_save(dest)
```

Write every comment of this conf to `dest`, an absolute path, as a comment file (`# comments
v1:` header, one sorted tab-separated row each; convention `<symbol file stem>.comments.tsv`
beside the symbol file), whole or not at all. Answers on a running guest too.

Refused `bad_argument`, the path left as it is: relative, a link, a directory or any
other non-regular file, a missing directory, an existing file that is not a comment file,
the declaration store's own file; two comments at one place, which a file names once (named,
so one can be deleted). A file the host will not let it write is `host_failed`.

Reply: `path` (the file written), `comments_total`, `dropped_comments` (each `ref` of the
replaced file that the store does not hold), `dropped_total`, `truncated`, `note`.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `dest` | string | required |

| reply field | type |
|---|---|
| `comments_total` | integer |
| `dropped_comments` | array |
| `dropped_total` | integer |
| `note` | string |
| `path` | string |
| `truncated` | boolean |

Example, from a live run:

```json
{
  "dest": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1058.comments.tsv"
}
```

```json
{
  "summary": "comment_save: 1 comment to $TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1058.comments.tsv",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1058.comments.tsv",
  "comments_total": 1,
  "dropped_comments": [],
  "dropped_total": 0,
  "truncated": false
}
```
<!-- scry-reference:end comment_save -->

The `cpu` column is the format's and is written empty (one processor); a file that fills it is
refused. There is no build column: a raw address is trusted for the build it is loaded into.

<!-- scry-reference:begin comment_load -->
## `comment_load`

*Load comments from a file*

```text
comment_load(path)
```

Read a comment file (an absolute `path`) into this conf's comments, all or nothing: the
file is parsed and every row placed first, and a row the format refuses or one address in
two spellings refuses the whole file (`bad_argument`). Then the file wins: a place the store
does not comment is added, one with another text replaced, one with the same text unchanged
(a raw one taken into this session's build, ref and stamp kept); rows only the store holds stay.
Two rows this stop places at one byte are both kept, and `note` names them; so is a raw row
this stop's mode cannot place (past FFFF in real mode, the null selector in protected mode),
kept `unarmable` until a load at a stop whose mode holds it places it. Needs the machine
STOPPED.

Reply: `path` (the file read), `parsed`, `added`, `replaced_comments` (the store's old rows,
whole), `replaced_total`, `truncated`, `unchanged`, `comments_total`, `declarations`
(`persistent`, `path`), `note`. A store that cannot be written is `host_failed`, nothing
changed.

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `path` | string | required |

| reply field | type |
|---|---|
| `added` | integer |
| `comments_total` | integer |
| `declarations` | object |
| `note` | string |
| `parsed` | integer |
| `path` | string |
| `replaced_comments` | array |
| `replaced_total` | integer |
| `truncated` | boolean |
| `unchanged` | integer |

Example, from a live run:

```json
{
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1069.comments.tsv"
}
```

```json
{
  "summary": "comment_load: 0 read, 0 added, 0 replaced",
  "status": "ok",
  "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/n1069.comments.tsv",
  "parsed": 0,
  "added": 0,
  "replaced_comments": [],
  "replaced_total": 0,
  "truncated": false,
  "unchanged": 0,
  "comments_total": 1,
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-f9cacb318bc7/jobs-scratch/A/dosbox-x-live-matrix-A-n5_zipfr/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_load -->

A file saved before `symbols_load`, or on a running guest, can hold two rows a later stop places at
one byte. Which refs alias depends on the table and the stop's mode, so a file is refused for
neither: both rows are kept and named in `note`, and a save refuses them until one is deleted.
