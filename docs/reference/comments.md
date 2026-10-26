# The Comments tools



The place is the LINEAR address, and a `SEG:OFF` is read in the mode the machine is in, so a
comment meant to survive a mode switch is made by symbol. Comments a rebuild or a load brought to
one place are all kept, and a call reaches the one whose ref it spells.

<!-- scry-reference:begin comment_list -->
## `comment_list`

*List the comments*

```text
comment_list()
```

Every comment of this conf, in store order. Answers on a running guest too.

Reply: `comments` (each `ref`, `text`, `addr`, `state`, `why`),
`comments_total`, `truncated`, `declarations`.

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
  "summary": "comment_list: 0 comments",
  "status": "ok",
  "comments": [],
  "comments_total": 0,
  "truncated": false,
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/N/dosbox-x-live-matrix-N-56609c3p/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_list -->





The `cpu` column is the format's and is written empty (one processor); a file that fills it is
refused. There is no build column: a raw address is trusted for the build it is loaded into.



A file saved before `symbols_load`, or on a running guest, can hold two rows a later stop places at
one byte. Which refs alias depends on the table and the stop's mode, so a file is refused for
neither: both rows are kept and named in `note`, and a save refuses them until one is deleted.

`state` meanings: `resolved`, `unresolved` (no such symbol now), `ambiguous`, `stale` (a raw `SEG:OFF` not known to be this build's), `unarmable` (its place cannot be worked out now, for instance a protected-mode `SEG:OFF` until a stop reads its selector's base). `orphan` marks a row from a store that kept no origin; a running reply also carries `last_stop`. Each row also carries `by`, `cpu`, `created_at`, `origin`, `inherited` and `age_s`.

<!-- scry-reference:begin comment_write -->
## `comment_write`

*Write the comments*

```text
comment_write(method, ref="", text="", dest="", path="")
```

Change this conf's comments.

`add`: `text` (one printable line, at most 237 UTF-8 bytes) on `ref`,
a symbol or a `SEG:OFF`; a second there replaces it. Reply: `comment`, `replaced_comments`,
`declarations`, `note`.

`delete`: the comment `ref` names. Reply: `deleted`, `declarations`, `note`.

`save`: every comment to `dest`, an absolute or `~`-led path, replacing a comment file
there (rows only it held in `dropped_comments`); any other file is refused; answers on a
running machine. Reply: `path`, `comments_total`, `dropped_comments`, `dropped_total`,
`truncated`, `note`.

`load`: the comment file at `path`, all or nothing, the file winning. Reply: `path`,
`parsed`, `added`, `replaced_comments`, `replaced_total`, `truncated`, `unchanged`,
`comments_total`, `declarations`, `note`.

`add`, `delete` and `load` need the machine stopped. Refused: an argument the method
does not take, a misshapen `ref` or `text` (`bad_argument`), a name defined twice
(`ambiguous_ref`), an unknown `ref` (`unknown_ref`), an unwritable store (`host_failed`).

Reference: REFERENCE.md, Declarations.

| argument | type | default |
|---|---|---|
| `method` | one of `"add"`, `"delete"`, `"save"`, `"load"` | required |
| `ref` | string | `""` |
| `text` | string | `""` |
| `dest` | string | `""` |
| `path` | string | `""` |

| reply field | type |
|---|---|
| `added` | integer |
| `comment` | object |
| `comments_total` | integer |
| `declarations` | object |
| `deleted` | object |
| `dropped_comments` | array |
| `dropped_total` | integer |
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
  "method": "add",
  "ref": "start",
  "text": "entry"
}
```

```json
{
  "summary": "comment_write add: start at 0x0000824b, stored",
  "status": "ok",
  "comment": {
    "ref": "start",
    "by": "symbol",
    "cpu": {
      "available": false,
      "why": "a DOS machine has one cpu, and every row acts on it"
    },
    "created_at": "2026-10-26T07:36:15+00:00",
    "origin": "2026-10-26T07:36:15+00:00#47090.1",
    "inherited": false,
    "age_s": 0,
    "text": "entry",
    "addr": "0x0000824b",
    "state": "resolved"
  },
  "replaced_comments": [],
  "declarations": {
    "persistent": true,
    "path": "$TMPDIR/dosbox-x-live-matrix-253332ee682a/jobs-scratch/N/dosbox-x-live-matrix-N-56609c3p/dosbox-x-debug/declarations.json"
  }
}
```
<!-- scry-reference:end comment_write -->

By symbol a comment follows the symbol through a rebuild; by `SEG:OFF` it is `stale` once the build changes. `dropped_comments` lists each `ref` the replaced file held that the store does not.
