# The Names tools

<!-- scry-reference:begin symbols_load -->
## `symbols_load`

*Load a symbol table*

```text
symbols_load(path, base="", base_from="CS", pattern="", keep_noise=false, section_bases=null, types="")
```

Load a toolchain's TEXT symbol list into the debugger and the server, so every other tool
takes NAMES. Wants the machine stopped INSIDE the program whose symbols these are (a breakpoint
on INT 0x21, or INT 0x31 with ah=2 for a DJGPP program). With an explicit `base` it also works
while the guest RUNS: the table answers at once and the debugger's list loads at the next stop
(`pending: true`).

Arguments: `path`, a file (an absolute path): `nm` output, a GNU `ld` map, a
Borland TLINK/TASM map, or an Open Watcom map. A FLAT list (`nm`, GNU, real-mode Borland) takes
`base`: measured by default off the selector named by `base_from` (default `CS`, right under
DPMI), REQUIRED in real mode as HEX TEXT, `load_segment * 16` (segment 0x0800 is `"0x8000"`).
A SECTIONED map (32-bit Borland, Watcom) takes `section_bases`, hex per section index.
`types`: a UTF-8 file typing symbols in the value grammar. `pattern`: a regex SEARCHED in the
full name (`^_snd` keeps a prefix); `keep_noise` keeps section and compiler-label symbols.

Refused (INVALID): both `base` and `section_bases`; a sectioned map with no `section_bases`; a
real-mode map with no `base`; a running machine with no explicit base; a file whose symbol rows
were mostly unreadable; a table the COFF symbols of the `<stem>.exe` beside it contradict.

A second load at the same base ADDS to the first; at another base it REPLACES the table here
(`table_mode`), the debugger keeping every row until `close`.

Reply: `parsed`, `kept`, `loaded` (the debugger's own count), `table_mode`,
`table_total`, `renamed` (names loaded cut or with `~n`), the parse's other
accounts (`truncated_names`, `disambiguated`, `unreadable`, `excluded_*`, `overlay_idle`,
`unencodable*`, `symbols_typed`, `bytes`), `descriptor`, `pending`, `base_from`, `base`,
`limit`, `checked` (`against`, `agree`, or why not), and `declarations` (the re-arm by
state, `rearmed` to `unarmable`, each a list row, `why` on the last three).

Reference: REFERENCE.md, Names for addresses.

| argument | type | default |
|---|---|---|
| `path` | string | required |
| `base` | string | `""` |
| `base_from` | string (matching `^([cC][sS]\|[dD][sS]\|[eE][sS]\|[sS][sS]\|[fF][sS]\|[gG][sS])$`) | `"CS"` |
| `pattern` | string | `""` |
| `keep_noise` | boolean | `false` |
| `section_bases` | object or null | `null` |
| `types` | string | `""` |

| reply field | type |
|---|---|
| `base` | integer |
| `base_from` | string |
| `bytes` | integer |
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
  "declarations": {
    "rearmed": [],
    "stale": [],
    "unresolved": [],
    "ambiguous": [],
    "unarmable": []
  },
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

**The name field has 15 usable characters.** A collision keeps all its members, shortened for an index (`__poly_scan~0`). **Read `renamed`, not `truncated_names`**: a name that fitted is mutilated too when it carries a `~n`.

**Counts that keep the accounting honest.** `parsed` and `unreadable` sit beside the buckets, so a half-unreadable file does not produce a plan whose every count adds up (`nm -C` demangles into names with spaces). `overlay_idle` is a subset of `kept`, not a bucket, and those symbols are loaded, not filtered: dropping a quarter of a table is the worse failure. What the linker's `idle` mark means is open, since maps contradict the reading "not resident"; it is matched per format (TLINK writes `idle`, ILINK32 `Idle`).

**A 32-bit Borland row is a SECTION INDEX and an offset inside it**, so `seg * 16` would invent an address. The vendor's documentation suggests the `Start` column is a full address, but every `Start` offset in an ILINK32 map is zero, so under a flat model the sections overlap. The bases live in the linked image, which this server does not read, hence `section_bases`. Such a map describes a Win32 program: it is read anyway, so if every breakpoint refuses afterwards, that is why.

**`LV` appends**, so `loaded` can exceed `kept`. A load that MOVES the program replaces the table, because carrying the old offsets across would re-place them at addresses nobody measured; on a replace the old rows stay in the debugger, invisible to `symbols_find`, until `close` and a fresh `start`. A load that fails after `LV` leaves the debugger holding the list while the reply is INVALID, and retrying adds a second copy there; a guest that runs another program at another base is not re-measured. `SV` cannot save more than 65535 names, so a load that would pass it is refused before `LV`.

**`loaded` is read back with `SV`** because a `SV`/`LV` filename is silently cut to twelve characters and reported `ok`; both files live in the emulator's working directory, an existing one is refused, and both are removed on exit.

**A table is checked against its build**, because a stale table resolves every name a few bytes off and nothing in it can say so. Which of table and executable is stale it cannot know.

**A file most of which was discarded is refused**, for the anchored readers only (Borland, Watcom): a GNU `ld` map is mostly not symbols by construction, so one ratio over both would refuse every one.

**Producing the text is your build's job**, with *your* toolchain's `nm`, written to a temporary and moved: `>` truncates before `nm` runs, and a partial file is what the debugger is then told to trust.

```make
symbols:
	@$(XPREFIX)nm build/APP.EXE > $@.tmp || { rm -f $@.tmp; exit 3; }
	@grep -qE '^[0-9a-f]+ [A-Za-z] ' $@.tmp || { rm -f $@.tmp; exit 3; }
	@mv $@.tmp build/APP.SYM
```

<!-- scry-reference:begin symbols_find -->
## `symbols_find`

*Look a symbol up*

```text
symbols_find(name="", offset=null, section=null, linear="", limit=10)
```

Look a symbol up in the table `symbols_load` kept (names untruncated; what its `pattern`
and noise filters excluded is not in it).

`name`: exact match, else prefix matches, up to `limit` (`truncated` says if it
bit). `offset` (a toolchain offset) or `linear` (a linear address as hex text, `0x1000`;
a `SEG:OFF` is `read_memory`'s, not this one's),
optionally with `section`: what am I inside? -- the nearest symbol AT OR BELOW and the
distance above it (this table carries no sizes). One question per call.

Reply: by name, `query`, `symbols_total` (how many) and `symbols`, a list with `name`, `offset`,
`addr` (linear), `section`, `idle` (Borland's own mark on that row, always false for `nm`/GNU);
by offset or linear, the nearest symbol's own fields and `delta`. INVALID with no table
loaded, or `limit` out of range on the `name` question (a prefix matching
more is a listing, not a lookup).

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
