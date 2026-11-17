# The Scan tools

<!-- scry-reference:begin scan -->
## `scan`

*Value scan*

```text
scan(method, ref="", length=null, cell_bytes=null, operator=null, value=null, limit=null)
```

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

| argument | type | default |
|---|---|---|
| `method` | one of `"start"`, `"filter"`, `"clear"` | required |
| `ref` | string | `""` |
| `length` | integer or null | `null` |
| `cell_bytes` | one of `1`, `2`, `4` or null | `null` |
| `operator` | one of `"="`, `"!"`, `">"`, `">="`, `"<"`, `"<="` or null | `null` |
| `value` | integer or string or null | `null` |
| `limit` | integer (>= 1, <= 400) or null | `null` |

| reply field | type |
|---|---|
| `addr` | string |
| `cell_bytes` | integer |
| `cleared` | boolean |
| `closed` | boolean |
| `hits` | array |
| `hits_total` | integer |
| `iterations` | integer or object |
| `length` | integer |
| `operator` | string |
| `ref` | string |
| `seg_off` | string |
| `survivors` | integer |
| `truncated` | boolean |
| `value` | string or object |

Example, from a live run:

```json
{
  "method": "start",
  "ref": "8000:0000",
  "length": 16
}
```

```json
{
  "summary": "scan start: 8000:0000, 16 cells of 1 byte",
  "status": "ok",
  "ref": "8000:0000",
  "seg_off": "8000:00000000",
  "length": 16,
  "cell_bytes": 1,
  "addr": "0x00080000",
  "hits_total": 16
}
```
<!-- scry-reference:end scan -->
