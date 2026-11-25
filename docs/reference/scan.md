# The Scan tools

A scan finds where a program keeps a value when no symbol names it: the lives left, a score, a timer. It starts from every byte of a range and narrows the list each time the value changes.

<!-- scry-reference:begin scan -->
## `scan`

Find the byte that holds a value nobody has named: start from a whole range and keep only what changes as the value does.

```text
scan(method, ref="", length=null, cell_bytes=null, operator=null, value=null, limit=null)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen with its symbols loaded. The example session filters after its first brick falls, when the score reads 60.

Ask:

> Find the byte that holds the score: scan the 214 bytes from row_colours, and filter once a brick has fallen.

Call:

```text
scan(method="start", ref="row_colours", cell_bytes=1, length=214)
```

Reply, 5 of 9 fields:

```json
{
  "summary": "scan start: row_colours, 214 cells of 1 byte",
  "seg_off": "08DF:00000544",
  "length": 214,
  "cell_bytes": 1,
  "hits_total": 214
}
```

Then, with the score at 60 after the first brick:

Call:

```text
scan(method="filter", value=60)
```

Reply, 4 of 9 fields:

```json
{
  "summary": "scan filter: = 60, 2 left",
  "iterations": 1,
  "hits": [
    {"seg_off": "08DF:0000054B", "addr": "0x0000933b", "value": "0x3c"},
    {"seg_off": "08DF:000005C9", "addr": "0x000093b9", "value": "0x3c"}
  ],
  "hits_total": 2
}
```

Of 214 bytes, two hold 60 (`0x3c`). One of them, `08DF:000005C9`, is where `read_memory` finds the symbol `score`.

<details><summary>The two replies, whole</summary>

The first call's:

```json
{
  "summary": "scan start: row_colours, 214 cells of 1 byte",
  "status": "ok",
  "ref": "row_colours",
  "seg_off": "08DF:00000544",
  "length": 214,
  "cell_bytes": 1,
  "addr": "0x00009334",
  "hits_total": 214,
  "names": [
    {"field": "given.ref", "number": "0x00009334", "kind": "symbol", "name": "row_colours"}
  ]
}
```

The second call's:

```json
{
  "summary": "scan filter: = 60, 2 left",
  "status": "ok",
  "operator": "=",
  "value": "0x3c",
  "iterations": 1,
  "closed": false,
  "hits": [
    {"seg_off": "08DF:0000054B", "addr": "0x0000933b", "value": "0x3c"},
    {"seg_off": "08DF:000005C9", "addr": "0x000093b9", "value": "0x3c"}
  ],
  "hits_total": 2,
  "truncated": false
}
```

</details>

### The three methods

| method | what it does |
|---|---|
| `start` | Opens a scan: every cell of the range is a candidate. |
| `filter` | Keeps the candidates whose value passes a comparison. |
| `clear` | Ends the scan. |

### Arguments

- `method` (one of `"start"`, `"filter"`, `"clear"`, required): `start`, `filter` or `clear`, as above.
- `ref` (string, default `""`): Where the range begins, for `start`: a `SEG:OFF` address or a symbol.
- `length` (integer, optional): How many bytes to scan, for `start`: at most `0xFFFFFF`, and a whole number of candidates.
- `cell_bytes` (one of `1`, `2`, `4`, optional): The size of each candidate: 1, 2 or 4 bytes, low byte first. Left out, one byte.
- `operator` (one of `"="`, `"!"`, `">"`, `">="`, `"<"`, `"<="`, optional): The comparison a `filter` makes. Left out, `=`.
- `value` (integer or string, optional): What each candidate is compared with: an integer or a `0x` string. Left out, what it held at `start`.
- `limit` (integer (>= 1, <= 400), optional): How many of the candidates left the reply lists: 1 to 400. Left out, 40.

### What comes back

- `hits_total`: How many candidates are left.
- `hits`: The first `limit` of them, each with its address and its value now. None are listed while more than 400 are left.
- `iterations`: How many filters this scan has taken.
- `closed`: `true` when a filter left no candidate, which ends the scan.
- `truncated`: `true` when there are more candidates than `hits` lists.

<details><summary>All 13 reply fields</summary>

- `addr` (string)
- `cell_bytes` (integer)
- `cleared` (boolean)
- `closed` (boolean)
- `hits` (array)
- `hits_total` (integer)
- `iterations` (integer or object)
- `length` (integer)
- `operator` (string)
- `ref` (string)
- `seg_off` (string)
- `truncated` (boolean)
- `value` (string or object)

</details>

### What it refuses

- An argument the method does not take.
- A second `start` while a scan is open, or a `filter` with none (`needs_call`).
- A `value` wider than the scan's candidates (`bad_argument`).
- A range that runs past the memory the debugger addresses (`bad_argument`).

### Why it works this way

The candidates live in the debugger's own value scanner, `MEMFIND`, not in the reply. So a scan over a large range costs one command, and the addresses are listed only once few enough are left.

That scanner holds one scan at a time, which is why a second `start` is refused until you `clear`.

Without a `value`, a filter compares each candidate with what it held at `start`: `!` keeps the ones that changed, `>` the ones that grew. A few rounds leave the one address.

### Related tools

- [`watch_add`](breakpoints.md#watch_add)
- [`find`](read.md#find)
- [`read_memory`](read.md#read_memory)
- [`send_keys`](input.md#send_keys)

<details><summary>The contract your client receives</summary>

```text
Value scan: find a variable no map names (the debugger's `MEMFIND`). One scan at a time.

`start`: every cell of `cell_bytes` (little-endian) over `length` bytes from `ref` is a
candidate. Reply: `ref`, `seg_off`, `length`, `cell_bytes`, `addr`, `hits_total`.

`filter`: keep the cells whose content satisfies `operator` (`=` default) against `value`
(an integer or a `0x` string), or with no `value` against what each held at `start`; none
left closes the scan. Reply: `operator`, `value`, `iterations`, `closed`, `hits` (the first
`limit`, default 40), `hits_total`, `truncated`, `note`.

`clear`: cancel the open scan. Reply: `cleared`.

Refused: an argument the method does not take; a scan already open, in the debugger's
words; a `value` wider than the cell.

Reference: REFERENCE.md, Reading and writing.
```

</details>
<!-- scry-reference:end scan -->
