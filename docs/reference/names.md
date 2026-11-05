# The Names tools

<!-- scry-reference:begin symbols_load -->
## `symbols_load`

*Load a symbol table*

```text
symbols_load(path, base="", base_from="CS", pattern="", keep_noise=false, section_bases=null, types="")
```

Load a toolchain's symbol list so other tools take names. Stop inside the program first;
with an explicit `base` a running guest works too (`pending: true`).

`path`: `nm` output or a GNU `ld`, Borland or Watcom map. Flat lists take `base` (hex text) or
`base_from`, a register or a selector as four hex digits (`00AF`), whose descriptor the
debugger reads in any CPU mode, so a real-mode stop can load a protected-mode program's table;
sectioned maps take `section_bases`. `types`, `pattern`, `keep_noise` filter and type rows.

Refused (INVALID): both `base` and `section_bases`; a sectioned map without
`section_bases`; real mode or a running machine without `base` or a selector number; a
mostly unreadable file;
a table the `<stem>.exe` contradicts; a table in which two names differ only in case, naming
both lines.

Reply: `parsed`, `kept`, `loaded`, `table_mode`, `table_total`, `renamed`, `pending`,
`base`, `checked`, `declarations`, and `debugger_holds` when an earlier load's rows are
still in the debugger.

Reference: REFERENCE.md, Names for addresses.

| argument | type | default |
|---|---|---|
| `path` | string | required |
| `base` | string | `""` |
| `base_from` | string (matching `^([cC][sS]\|[dD][sS]\|[eE][sS]\|[sS][sS]\|[fF][sS]\|[gG][sS]\|[0-9A-Fa-f]{4})$`) | `"CS"` |
| `pattern` | string | `""` |
| `keep_noise` | boolean | `false` |
| `section_bases` | object or null | `null` |
| `types` | string | `""` |

| reply field | type |
|---|---|
| `base` | integer |
| `base_from` | string |
| `bytes` | integer |
| `debugger_holds` | integer |
| `declarations` | object |
| `descriptor` | integer |
| `disambiguated` | integer |
| `excluded_pattern` | integer |
| `excluded_sections` | integer |
| `excluded_unplaceable` | integer |
| `kept` | integer |
| `limit` | integer |
| `loaded` | integer |
| `overlay_idle` | integer |
| `parsed` | integer |
| `pending` | boolean |
| `checked` | object |
| `renamed` | integer |
| `symbols_typed` | integer |
| `table_mode` | string |
| `table_total` | integer |
| `truncated_names` | integer |
| `unencodable` | array |
| `unencodable_total` | integer |
| `unreadable` | integer |

Example, from a live run:

```json
{
  "path": "/path/to/scry-dosbox-x/tests/fixtures/borland-tlink16/MAPDEMO.MAP",
  "base": "8000"
}
```

```json
{
  "summary": "symbols_load: 5 loaded of 5 parsed, base 32768",
  "status": "ok",
  "base": 32768,
  "limit": -1,
  "descriptor": -1,
  "declarations": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []},
  "pending": false,
  "checked": {
    "available": false,
    "why": "no executable named MAPDEMO.exe beside the table, so it could not be checked against its build"
  },
  "base_from": "caller",
  "parsed": 5,
  "kept": 5,
  "excluded_sections": 0,
  "excluded_pattern": 0,
  "excluded_unplaceable": 0,
  "unencodable": [],
  "unencodable_total": 0,
  "truncated_names": 4,
  "disambiguated": 1,
  "renamed": 4,
  "unreadable": 0,
  "overlay_idle": 3,
  "table_mode": "replaced",
  "table_total": 5,
  "loaded": 5,
  "bytes": 102,
  "symbols_typed": 0
}
```
<!-- scry-reference:end symbols_load -->

**The debugger's file format is documented nowhere**: a `u16` count, then records of a 16-byte NUL-padded name and a `u32` **linear** address. `IV 1234:5678` stores `0x000179B8`, which is `0x12340 + 0x5678`.

**The base is measured off the running machine.** Under a DPMI host the selector base is decided at load time, so it is read with `SELINFO`. In real mode `SELINFO` prints no answer, so a flat map with no `base` is refused before asking, rather than taken as base 0, which would load cleanly and place every symbol at its raw offset. An all-zero descriptor in protected mode is refused for the same reason.

**A lookup ignores case, and a table in which two names differ only in case is refused.** `symbols_find`, a symbol `ref` and a comment's symbol all find `ShowCredits` by `showcredits`; `symbols_find` answers the name as the map spells it, and a declaration keeps the `ref` as it was typed. Two names that fold to one could not be told apart, so the load is refused naming both lines; the same spelling twice is an ambiguous name, which lookups already report.

**The name field has 15 usable characters.** A collision keeps all its members, shortened for an index (`__poly_scan~0`). **Read `renamed`, not `truncated_names`**: a name that fitted is mutilated too when it carries a `~n`.

**Counts that keep the accounting honest.** `parsed` and `unreadable` sit beside the buckets, so a half-unreadable file does not produce a plan whose every count adds up (`nm -C` demangles into names with spaces). `overlay_idle` is a subset of `kept`, not a bucket, and those symbols are loaded, not filtered: dropping a quarter of a table is the worse failure. What the linker's `idle` mark means is open, since maps contradict the reading "not resident"; it is matched per format (TLINK writes `idle`, ILINK32 `Idle`).

**A 32-bit Borland row is a SECTION INDEX and an offset inside it**, so `seg * 16` would invent an address. The vendor's documentation suggests the `Start` column is a full address, but every `Start` offset in an ILINK32 map is zero, so under a flat model the sections overlap. The bases live in the linked image, which this server does not read, hence `section_bases`. Such a map describes a Win32 program: it is read anyway, so if every breakpoint refuses afterwards, that is why.

**`LV` appends**, and the reply keeps the two counts apart: `loaded` is what this load put in, `debugger_holds` is every row the debugger holds now, said only when it is larger. A load that MOVES the program replaces the table, because carrying the old offsets across would re-place them at addresses nobody measured; on a replace the old rows stay in the debugger, invisible to `symbols_find`, until `close` and a fresh `start`. A load that fails after `LV` leaves the debugger holding the list while the reply is INVALID, and retrying adds a second copy there; a guest that runs another program at another base is not re-measured. `SV` cannot save more than 65535 names, so a load that would pass it is refused before `LV`.

**`loaded` is read back with `SV`** because a `SV`/`LV` filename is silently cut to twelve characters and reported `ok`; both files live in the emulator's working directory, an existing one is refused, and both are removed on exit.

**A table is checked against its build**, because a stale table resolves every name a few bytes off and nothing in it can say so. Which of table and executable is stale it cannot know. The session keeps the executable it checked, as the disk held it, and every reply then carries `image_changed_on_disk` once that file is written again: a relink under a live session leaves the guest running the image on screen.

**A file most of which was discarded is refused**, for the anchored readers only (Borland, Watcom): a GNU `ld` map is mostly not symbols by construction, so one ratio over both would refuse every one.

**Producing the text is your build's job**, with *your* toolchain's `nm`, written to a temporary and moved: `>` truncates before `nm` runs, and a partial file is what the debugger is then told to trust.

```make
symbols:
	@$(XPREFIX)nm build/APP.EXE > $@.tmp || { rm -f $@.tmp; exit 3; }
	@grep -qE '^[0-9a-f]+ [A-Za-z] ' $@.tmp || { rm -f $@.tmp; exit 3; }
	@mv $@.tmp build/APP.SYM
```

The debugger's list stores a `u16` count then 16-byte NUL-padded names with `u32` linear addresses, so long names are cut and collisions get `~n`. Real mode cannot report a selector base, so a flat map without `base` is refused: base 0 would load cleanly at wrong addresses. A 32-bit Borland row is a section index plus an offset, so its bases cannot come from the map, and such a map describes a Win32 program (breakpoints may refuse afterwards). A second load at the same base adds; at another base it replaces the server's table while the debugger keeps every row until `close`. A stale table places names a few bytes off silently, hence the check against the build. Base is measured off `base_from` (default `CS`, right under DPMI); `section_bases` is hex per section index; `pattern` is searched in the full name; the table carries no sizes, so address lookups give the nearest symbol below.

<!-- scry-reference:begin symbols_find -->
## `symbols_find`

*Look a symbol up*

```text
symbols_find(name="", offset=null, section=null, linear="", limit=10)
```

Look a symbol up in the table `symbols_load` kept. `name`: exact, else prefix matches by
section and offset, case ignored, each in the spelling the map gave, up to `limit`. `offset` (an
integer) or `linear` (hex text), with `section`: the nearest symbol at or below.

Reply: `query`; by name, `symbols_total`, `symbols` (`name`, `offset`, `addr`), `truncated`;
by address, the symbol's fields and `delta`. INVALID: no table.

| argument | type | default |
|---|---|---|
| `name` | string | `""` |
| `offset` | integer or null | `null` |
| `section` | integer or null | `null` |
| `linear` | string | `""` |
| `limit` | integer (>= 1, <= 50) | `10` |

| reply field | type |
|---|---|
| `addr` | string |
| `delta` | integer |
| `idle` | boolean |
| `kind` | string |
| `name` | string |
| `offset` | integer |
| `query` | string |
| `section` | integer |
| `symbols` | array |
| `symbols_total` | integer |
| `truncated` | boolean |

Example, from a live run:

```json
{
  "name": "MAP_DATA_SYMBOL"
}
```

```json
{
  "summary": "symbols_find MAP_DATA_SYMBOL: 1 symbol",
  "status": "ok",
  "query": "MAP_DATA_SYMBOL",
  "symbols_total": 1,
  "symbols": [
    {
      "name": "MAP_DATA_SYMBOL",
      "kind": "?",
      "offset": 32,
      "section": -1,
      "addr": "0x00008020",
      "idle": true
    }
  ],
  "truncated": false
}
```
<!-- scry-reference:end symbols_find -->

A `SEG:OFF` is `read_memory`'s, not `linear`'s. A prefix matching more than `limit` is a listing, not a lookup, so `limit` is range-checked on the name question. `idle` is Borland's own mark on a row, always false for `nm`/GNU; names are untruncated and exclude what `pattern` and the noise filters dropped.
