# The Comments tools

A comment is one line of text on an address of the program. The server saves it with the breakpoints and watches, and `disassemble` and a stop's `instruction` show it beside the code as `comment`.

A comment sits on a linear address, and a `SEG:OFF` is read in the CPU mode the machine is in. One meant to survive a switch between real and protected mode is made by symbol.

By symbol a comment follows the symbol through a rebuild; by `SEG:OFF` it is `stale` once the build changes. What it shares with a saved breakpoint is in [REFERENCE.md, Breakpoints and watches](../../REFERENCE.md#breakpoints-and-watches).

<!-- scry-reference:begin comment_list -->
## `comment_list`

List every saved comment of this program, each with its address and whether it resolves now.

```text
comment_list()
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen, right after the comment of the entry below was added.

Ask:

> Which comments are saved for this game?

Call:

```text
comment_list()
```

Reply, 4 of 6 fields:

```json
{
  "summary": "comment_list: 1 comment",
  "status": "ok",
  "comments_total": 1,
  "truncated": false
}
```

One comment is saved, and `truncated` is `false`: the reply lists every one.

<details><summary>The whole reply</summary>

```json
{
  "summary": "comment_list: 1 comment",
  "status": "ok",
  "comments": [
    {
      "ref": "brick_hit",
      "by": "symbol",
      "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
      "created_at": "<volatile>",
      "origin": "<volatile>",
      "inherited": false,
      "age_s": "<volatile>",
      "text": "AL = row, BL = column of the brick that falls",
      "addr": "0x00009095",
      "state": "resolved"
    }
  ],
  "comments_total": 1,
  "truncated": false,
  "declarations": {"persistent": true, "path": "<volatile>"}
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `comments`: The comments this reply shows. Each row has `ref`, `text`, `addr` once resolved, `state`, and `why` when it does not resolve.
- `comments_total`: How many comments are saved, listed or not.
- `truncated`: `true` when there are more comments than the reply lists. `comment_write(method="save")` writes them all.
- `declarations`: The saved breakpoints file the comments live in: its `path`, and `persistent`, which is `true` for a file on disk.

<details><summary>All 4 reply fields</summary>

- `comments` (array)
- `comments_total` (integer)
- `declarations` (object)
- `truncated` (boolean)

</details>

### Why it works this way

It reads the saved comments and types nothing at the debugger, so it answers while the program runs. Rows come in the order they were saved.

<details><summary>More on why</summary>

What `state` says of a comment:

- `resolved`: its `ref` resolves to an address now.
- `unresolved`: no such symbol in the loaded symbol table.
- `ambiguous`: its name matches several symbols.
- `stale`: a raw `SEG:OFF` not known to be this build's.
- `unarmable`: its address cannot be worked out now, for instance a protected-mode `SEG:OFF` until a stop reads its selector's base.

- Each row also carries `by`, `cpu`, `created_at`, `origin`, `inherited` and `age_s`, as a saved breakpoint's row does.
- A row's `cpu` is always an object with `available` set to `false` and a `why`: a DOS machine has one cpu.
- `orphan: true` is on a row saved with no record of its session.
- While the program runs the reply adds `last_stop`.

</details>

### Related tools

- [`comment_write`](#comment_write)
- [`disassemble`](read.md#disassemble)
- [`declaration_list`](breakpoints.md#declaration_list)

<details><summary>The contract your client receives</summary>

```text
Every comment of this conf, in store order. Answers on a running guest too.

Reply: `comments` (each `ref`, `text`, `addr`, `state`, `why`),
`comments_total`, `truncated`, `declarations`.

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end comment_list -->

<!-- scry-reference:begin comment_write -->
## `comment_write`

Change the saved comments: add or delete one, or save them all to a file and load them back.

```text
comment_write(method, ref="", text="", dest="", path="")
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen with `bricks.sym` loaded, which names the routine `brick_hit`.

Ask:

> Leave a note on the routine that removes a brick: AL is the row, BL the column.

Call:

```text
comment_write(method="add", ref="brick_hit", text="AL = row, BL = column of the brick that falls")
```

Reply, 3 of 6 fields:

```json
{
  "summary": "comment_write add: brick_hit at 0x00009095 (brick_hit), stored",
  "status": "ok",
  "replaced_comments": []
}
```

The comment is saved on `brick_hit`, which is the linear address `0x00009095`. Nothing was there before, so `replaced_comments` is empty.

<details><summary>The whole reply</summary>

```json
{
  "summary": "comment_write add: brick_hit at 0x00009095 (brick_hit), stored",
  "status": "ok",
  "comment": {
    "ref": "brick_hit",
    "by": "symbol",
    "cpu": {"available": false, "why": "a DOS machine has one cpu, and every row acts on it"},
    "created_at": "<volatile>",
    "origin": "<volatile>",
    "inherited": false,
    "age_s": "<volatile>",
    "text": "AL = row, BL = column of the brick that falls",
    "addr": "0x00009095",
    "state": "resolved"
  },
  "replaced_comments": [],
  "declarations": {"persistent": true, "path": "<volatile>"},
  "names": [
    {"field": "given.ref", "number": "0x00009095", "kind": "symbol", "name": "brick_hit"}
  ]
}
```

</details>

### The four methods

| method | what it does |
|---|---|
| `add` | Puts `text` on `ref`. A comment already there is replaced. |
| `delete` | Removes the comment at `ref`. |
| `save` | Writes every comment to the file `dest`. |
| `load` | Reads the comment file at `path` into the saved comments, all or nothing. |

### Arguments

- `method` (one of `"add"`, `"delete"`, `"save"`, `"load"`, required): `add`, `delete`, `save` or `load`, as above.
- `ref` (string, default `""`): For `add` and `delete`: a symbol or a `SEG:OFF`.
- `text` (string, default `""`): For `add`: one printable line, at most 237 UTF-8 bytes.
- `dest` (string, default `""`): For `save`: the file to write, an absolute or `~`-led path. A comment file already there is replaced; any other file is refused.
- `path` (string, default `""`): For `load`: the comment file to read, an absolute path.

### What comes back

- `comment`: `add`: the comment as saved, a row as `comment_list` gives it.
- `replaced_comments`: `add` and `load`: the comments whose text was replaced, as they were.
- `deleted`: `delete`: the comment removed.
- `dropped_comments`: `save`: comments only the replaced file held, each by `ref`. They are gone from the file.
- `added`: `load`: how many comments are new. `unchanged` counts those already saved with the same text, `parsed` the rows read.

<details><summary>All 13 reply fields</summary>

- `added` (integer)
- `comment` (object)
- `comments_total` (integer)
- `declarations` (object)
- `deleted` (object)
- `dropped_comments` (array)
- `dropped_total` (integer)
- `parsed` (integer)
- `path` (string)
- `replaced_comments` (array)
- `replaced_total` (integer)
- `truncated` (boolean)
- `unchanged` (integer)

</details>

### What it refuses

- An argument the method does not take (`bad_argument`).
- `add`, `delete` or `load` while the program runs (`not_stopped`).
- A `ref` that is a pointer or adds an offset, or a `text` that is empty, too long or not one printable line (`bad_argument`).
- A name the symbol table defines twice (`ambiguous_ref`).
- A `delete` whose `ref` matches no comment (`unknown_ref`).
- A `dest` that is the saved breakpoints file itself, a link, or a file that is not a comment file (`bad_argument`).
- A `save` while two comments sit on one address: delete one first (`bad_argument`).
- A saved breakpoints file that cannot be written: nothing changes (`host_failed`).

### Why it works this way

One address shows one comment, however it is spelled: `start`, `0824:000B` and `0814:010B` can name one byte. An `add` where a comment exists replaces its text.

`save` and `load` are how a project keeps its comments under version control beside its symbol file. `load` is all or nothing, and the file wins where both comment an address.

<details><summary>More on why</summary>

- A comment sets nothing in the debugger, so it never stops the program.
- A symbol the loaded symbol table lacks is saved `unresolved`, and resolves once a table has it.
- A raw `SEG:OFF` comment is `stale` while the build it was written over is not the one loaded, as a raw breakpoint is.
- Comments a rebuild or a `load` brought to one address are all kept. A call reaches the one whose `ref` it spells.
- The file's `cpu` column is written empty, since a DOS machine has one processor. A file that fills it is refused.
- The file has no build column: a raw address is trusted for the build it is loaded into.
- A file saved before `symbols_load`, or while the program runs, can hold two rows that a later stop resolves to one byte.
- A `load` keeps both such rows and names them in `note`. A `save` refuses them until one is deleted.
- A `load` that gives a `stale` raw comment the text it already holds adopts it into this session and build.
- A row a `load` cannot resolve at this stop is kept `unarmable`, its `why` naming the stop it waits for. An `add` refuses such an address.
- `comments_total`, `dropped_total` and `replaced_total` count the whole lists; `truncated` says a list was cut. `declarations` names the saved breakpoints file, as in `comment_list`.

</details>

### Related tools

- [`comment_list`](#comment_list)
- [`disassemble`](read.md#disassemble)
- [`symbols_load`](symbols.md#symbols_load)
- [`declaration_list`](breakpoints.md#declaration_list)

<details><summary>The contract your client receives</summary>

```text
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
does not take, a misshapen `ref` or `text`, a `save` `dest` that is the declaration store's
file, compared without regard to case on any volume (`bad_argument`), a name defined twice
(`ambiguous_ref`), an unknown `ref` (`unknown_ref`), an unwritable store (`host_failed`).

Reference: REFERENCE.md, Breakpoints and watches.
```

</details>
<!-- scry-reference:end comment_write -->
