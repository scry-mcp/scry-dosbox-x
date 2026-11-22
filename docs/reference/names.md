# The Names tools

A symbol table gives names to the addresses of a program: its routines and its variables. With one loaded, a tool that takes an address takes a name as well.

Here `symbols_load` loads the table from a text file your toolchain writes, and `symbols_find` looks a name or an address up in it. `start` can load one too, with its `symbols` argument.

<!-- scry-reference:begin symbols_load -->
## `symbols_load`

Load your program's symbol table from a file your toolchain writes, so that other tools take names in place of addresses.

```text
symbols_load(path, base=null, base_from="CS", pattern="", keep_noise=false, section_bases=null,
    types="")
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at its play screen, where DOS has loaded it at segment 08DF.

Ask:

> Load the game's symbols from `demos/bricks/bricks.sym`; DOS loaded it at segment 08DF.

Call:

```text
symbols_load(path="./demos/bricks/bricks.sym", base="0x8df0")
```

Reply, 7 of 26 fields:

```json
{
  "base": "0x00008df0",
  "parsed": 65,
  "kept": 65,
  "loaded": 65,
  "renamed": 0,
  "table_mode": "replaced",
  "pending": false
}
```

All 65 symbols of the file are in the debugger, none renamed, at linear `0x8df0`, which is segment 08DF times 16. `replaced` means this table stands alone: any earlier one is gone.

<details><summary>The whole reply</summary>

```json
{
  "summary": "symbols_load: 65 loaded of 65 parsed, base 0x00008df0, not checked against a build: no executable named bricks.exe beside the table, so it could not be checked against its build",
  "status": "ok",
  "base": "0x00008df0",
  "limit": {
    "available": false,
    "why": "no descriptor was read: the base was given, or each section has its own"
  },
  "descriptor": {
    "available": false,
    "why": "no descriptor was read: the base was given, or each section has its own"
  },
  "declarations": {"rearmed": [], "stale": [], "unresolved": [], "ambiguous": [], "unarmable": []},
  "pending": false,
  "checked": {
    "available": false,
    "why": "no executable named bricks.exe beside the table, so it could not be checked against its build"
  },
  "base_from": "caller",
  "parsed": 65,
  "kept": 65,
  "excluded_sections": 0,
  "excluded_pattern": 0,
  "excluded_unplaceable": 0,
  "unencodable": [],
  "unencodable_total": 0,
  "truncated_names": 0,
  "disambiguated": 0,
  "renamed": 0,
  "unreadable": 0,
  "overlay_idle": 0,
  "table_mode": "replaced",
  "table_total": 65,
  "loaded": 65,
  "bytes": 1302,
  "symbols_typed": 0
}
```

</details>

### Arguments

- `path` (string, required): The symbol file, by absolute path: the output of `nm`, or a link map from GNU `ld`, Borland or Open Watcom.
- `base` (integer or string, optional): The linear address the program is loaded at, for a file without sections: an integer or `0x` text. Left out, it is measured through `base_from`.
- `base_from` (string (matching `^([cC][sS]|[dD][sS]|[eE][sS]|[sS][sS]|[fF][sS]|[gG][sS]|[0-9A-Fa-f]{4})$`), default `"CS"`): Where the base is measured when `base` is left out: a segment register, or a selector as four hex digits such as `00AF`. Left out, `CS`.
- `pattern` (string, default `""`): A regular expression: only the symbols whose full name matches are loaded. Left empty, all are.
- `keep_noise` (boolean, default `false`): `true` keeps the section labels, the names that start with a dot. Left out, they are dropped.
- `section_bases` (object, optional): For a map with sections: the linear address of each section by its index, as `{"1": "0x401000"}`. Never together with `base`.
- `types` (string, default `""`): A file, by absolute path, that says what type some symbols are, so a watch on one needs no format. Left empty, none is typed.

### What comes back

- `loaded`: How many symbols this load put into the debugger, counted from the list the debugger saves back.
- `renamed`: How many names were cut or numbered to fit the debugger's 15 characters. Lookups still take the full name.
- `table_mode`: `accumulated` when the load added to the table already there, `replaced` when it took its place because the base changed.
- `checked`: The executable the table was compared with (`against`) and how many symbols `agree`, or why it could not be checked.
- `pending`: `true` when the program was running: the table reaches the debugger at the next stop.
- `declarations`: What became of the saved breakpoints and watches under the new table: `rearmed`, `stale`, `unresolved`, `ambiguous` or `unarmable`.

<details><summary>All 25 reply fields</summary>

- `base` (string or object)
- `base_from` (string)
- `bytes` (integer)
- `debugger_holds` (integer)
- `declarations` (object)
- `descriptor` (string or object)
- `disambiguated` (integer)
- `excluded_pattern` (integer)
- `excluded_sections` (integer)
- `excluded_unplaceable` (integer)
- `kept` (integer)
- `limit` (string or object)
- `loaded` (integer)
- `overlay_idle` (integer)
- `parsed` (integer)
- `pending` (boolean)
- `checked` (object)
- `renamed` (integer)
- `symbols_typed` (integer)
- `table_mode` (string)
- `table_total` (integer)
- `truncated_names` (integer)
- `unencodable` (array)
- `unencodable_total` (integer)
- `unreadable` (integer)

</details>

### What it refuses

- Both `base` and `section_bases`, or a map with sections and no `section_bases` (`bad_argument`).
- A file without sections at a real-mode stop, with neither `base` nor a selector number in `base_from` (`bad_argument`).
- A program that is running, with no `base` (`not_stopped`).
- A Borland or Watcom map most of whose rows cannot be read (`bad_argument`).
- A table that disagrees with the executable beside it: one of the two is another build's (`bad_argument`).
- Two names that differ only in case; the message names both lines (`bad_argument`).
- Filters that leave no symbol, or more names than the debugger's list holds (`bad_argument`).

### Why it works this way

The base is measured from the stopped machine, through the descriptor of `base_from`: under DPMI, the DOS protected-mode interface, it is only decided when the program loads. In real mode a register has no descriptor, so a file without sections needs `base` there. At base 0 every symbol would load without complaint, at its raw offset.

The table is checked against the executable beside it, the file of the same name ending in `.exe`. An old table puts every name a few bytes off and nothing in it says so. Which of the two is out of date the check cannot know; once that executable is written again, every reply carries `image_changed_on_disk`.

The debugger keeps 15 characters of a name, so a longer one is cut, and names that would then be equal get a `~n`; read `renamed`, which counts both. Lookups on the server take the full names and ignore case, which is why two names that differ only in case are refused.

<details><summary>More on why</summary>

The debugger only adds to its list. A second load at the same base adds to the table. A load at another base replaces the server's table, and the old rows stay in the debugger, unseen by `symbols_find`, until `close` and a new `start`.

A load that fails after the debugger took the list leaves the rows there while the reply is `INVALID`, and a second try adds a copy. The list holds 65535 names at most, so a load that would pass that is refused before it begins. A program that later runs another program at another base is not measured again.

Loading writes two temporary files, `SYMS.BIN` and `SYMSBK.BIN`, in the emulator's working directory and removes them; a file already there under either name is refused. `loaded` is counted from the second, which the debugger saves back, because the debugger reports success even for a file name it cut short.

A row of a 32-bit Borland map is a section index and an offset inside that section, and its `Start` column is no help: every section starts at zero there. The server does not read the linked program, hence `section_bases`. Such a map describes a Win32 program: if every breakpoint is refused afterwards, that is why.

- `parsed` counts the symbols the file holds and `kept` the ones that passed the filters.
- `unreadable` counts the lines that could not be read, as `nm -C` writes when a name has spaces.
- `excluded_sections`, `excluded_pattern` and `excluded_unplaceable` count what the filters dropped. `unencodable` lists names the debugger cannot hold and `unencodable_total` counts them.
- `overlay_idle` counts the loaded symbols a Borland map marks `idle`. They are part of `kept`, and what the linker means by the mark is not settled.
- `truncated_names` counts the cut names and `disambiguated` the ones given a `~n`.
- `base`, `limit` and `descriptor` are what was measured; `base_from` says `caller` when you gave the base.
- `debugger_holds` is every row the debugger holds now, given when that is more than `loaded`.
- `table_total` is the size of the server's table now, `bytes` the size of the file given to the debugger, `symbols_typed` the names `types` typed.

Writing the file is your build's job, with your toolchain's `nm`. Write it to a temporary file and move it: `>` empties the file before `nm` runs, and a half-written table would be trusted.

```make
symbols:
	@$(XPREFIX)nm build/APP.EXE > $@.tmp || { rm -f $@.tmp; exit 3; }
	@grep -qE '^[0-9a-f]+ [A-Za-z] ' $@.tmp || { rm -f $@.tmp; exit 3; }
	@mv $@.tmp build/APP.SYM
```

| symbol file | where its addresses come from |
|---|---|
| `nm` output, a GNU `ld` map, a real-mode Borland map | one `base`, given or measured through `base_from` |
| a 32-bit Borland map, an Open Watcom map | `section_bases`, one address per section |

The file is read leniently: a byte that is not UTF-8, such as a code page 437 character in a DOS map, is replaced and the rest is read. `base` and `section_bases` are two arguments because one value cannot honestly be a number for one file and a table for another.

The names come from a text listing your toolchain writes. A DJGPP executable's own COFF symbols serve only to check it. The debugger's own `IV` command takes one address typed at its console, so the whole list goes in as the file the debugger loads. A function the compiler inlined, such as a `static` one at `-O3`, has no symbol.

</details>

### Related tools

- [`symbols_find`](#symbols_find)
- [`start`](session.md#start)
- [`breakpoint_at`](breakpoints.md#breakpoint_at)
- [`watch_add`](breakpoints.md#watch_add)
- [`declaration_list`](breakpoints.md#declaration_list)
- [`comment_write`](comments.md#comment_write)

<details><summary>The contract your client receives</summary>

```text
Load a toolchain's symbol list so other tools take names. Stop inside the program first;
with an explicit `base` a running guest works too (`pending: true`).

`path`: `nm` output or a GNU `ld`, Borland or Watcom map. Flat lists take `base` or
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
```

</details>
<!-- scry-reference:end symbols_load -->

<!-- scry-reference:begin symbols_find -->
## `symbols_find`

Find a symbol's address by its name, or find which symbol an address falls in.

```text
symbols_find(name="", offset=null, section=null, linear=null, limit=10)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds, stopped at its play screen with its symbols loaded.

Ask:

> Which symbols start with "ball"?

Call:

```text
symbols_find(name="ball")
```

Reply, 3 of 6 fields:

```json
{
  "summary": "symbols_find ball: 5 symbols",
  "symbols_total": 5,
  "truncated": false
}
```

Five symbols start with `ball`, and all five came back. The whole reply, below, lists each with its offset and its linear address.

<details><summary>The whole reply</summary>

```json
{
  "summary": "symbols_find ball: 5 symbols",
  "status": "ok",
  "query": "ball",
  "symbols_total": 5,
  "symbols": [
    {
      "name": "ball_rect",
      "kind": "T",
      "offset": "0x398",
      "section": -1,
      "addr": "0x00009188",
      "idle": false
    },
    {
      "name": "ball_x",
      "kind": "D",
      "offset": "0x621",
      "section": -1,
      "addr": "0x00009411",
      "idle": false
    },
    {
      "name": "ball_y",
      "kind": "D",
      "offset": "0x623",
      "section": -1,
      "addr": "0x00009413",
      "idle": false
    },
    {
      "name": "ball_dx",
      "kind": "D",
      "offset": "0x625",
      "section": -1,
      "addr": "0x00009415",
      "idle": false
    },
    {
      "name": "ball_dy",
      "kind": "D",
      "offset": "0x627",
      "section": -1,
      "addr": "0x00009417",
      "idle": false
    }
  ],
  "truncated": false
}
```

</details>

### Arguments

- `name` (string, default `""`): The symbol to look up, case ignored. An exact match wins; with none, every symbol that starts with it is listed, by section and offset.
- `offset` (integer or string, optional): An offset as the toolchain wrote it, before any base. The reply is the nearest symbol at or below it.
- `section` (integer, optional): The section `offset` is in, by its index, for a table loaded with `section_bases`. A table without sections needs none.
- `linear` (integer or string, optional): A linear address, never a `SEG:OFF`: an integer or `0x` text. The reply is the nearest symbol at or below it.
- `limit` (integer (>= 1, <= 50), default `10`): How many symbols a name lookup lists: 1 to 50. Left out, 10; a lookup by address does not use it.

### What comes back

- `symbols`: By name: the first `limit` matches, each with `name`, `kind`, `offset`, `section`, `addr` and `idle`.
- `symbols_total`: By name: how many symbols matched.
- `truncated`: By name: `true` when more matched than `symbols` lists.
- `name`: By address: the nearest symbol at or below the address, with the fields of a row of `symbols`.
- `delta`: By address: how many bytes the address is past that symbol's start.
- `addr`: The symbol's linear address: its `offset` plus the base the table was loaded at.

<details><summary>All 11 reply fields</summary>

- `addr` (string)
- `delta` (integer)
- `idle` (boolean)
- `kind` (string)
- `name` (string)
- `offset` (string)
- `query` (string)
- `section` (integer)
- `symbols` (array)
- `symbols_total` (integer)
- `truncated` (boolean)

</details>

### What it refuses

- More or fewer than one of `name`, `offset` and `linear`: one question per call (`bad_argument`).
- A session with no table loaded (`no_channel`).
- An `offset` with no `section` on a table with sections, or a `section` on a table without (`bad_argument`).
- An address below every symbol, or a section the table does not have (`unknown_ref`).

### Why it works this way

The table is the server's own copy, not read from the machine, so the lookup answers while the program runs. Its names are whole, never cut to the debugger's 15 characters, and leave out what the load's filters dropped.

`delta` is a distance past the symbol's start because the table holds no sizes. `kind` is `nm`'s letter for the symbol's type, mostly `?` from a link map. `idle` is Borland's own mark on a row, always `false` for `nm` and GNU maps.

### Related tools

- [`symbols_load`](#symbols_load)
- [`read_memory`](read.md#read_memory)
- [`breakpoint_at`](breakpoints.md#breakpoint_at)
- [`watch_add`](breakpoints.md#watch_add)
- [`disassemble`](read.md#disassemble)
- [`interrupt_vectors`](machine.md#interrupt_vectors)

<details><summary>The contract your client receives</summary>

```text
Look a symbol up in the table `symbols_load` kept. `name`: exact, else prefix matches by
section and offset, case ignored, each in the spelling the map gave, up to `limit`.
`offset` or `linear` (each `0x` hex or an integer), with `section`: the nearest symbol
at or below.

Reply: `query`; by name, `symbols_total`, `symbols` (`name`, `offset` as `0x` hex, `addr`),
`truncated`;
by address, the symbol's fields and `delta`. INVALID: no table.
```

</details>
<!-- scry-reference:end symbols_find -->
<!-- scry-reference:begin knowledge_find -->
## `knowledge_find`

Ask what a number is called on this machine and what the server knows about it: a DOS or BIOS call, a DOS error.

```text
knowledge_find(id="", kind="", key="", text="", device="", scope="", limit=10)
```

### Try it

On [Bricks](../../demos/bricks/README.md), the game this repository builds. The base needs no session for what it holds.

Ask:

> What does INT 21h with AH=4Ch do?

Call:

```text
knowledge_find(kind="call", key="0x21/0x4C")
```

Reply, 3 of 10 fields:

```json
{
  "summary": "kind call key 0x21/0x4C: exit",
  "entries_total": 1,
  "examined": 518
}
```

One entry matches, so `entries` answers it whole: the exit call, what DOSBox-X does when it is taken, and its source lines. `served` and `held_back` count what the base serves and holds back.

<details><summary>The whole reply</summary>

```json
{
  "summary": "kind call key 0x21/0x4C: exit",
  "status": "ok",
  "query": {"kind": "call", "key": "0x21/0x4C"},
  "scope": ["ibm-pc"],
  "entries_total": 1,
  "entries": [
    {
      "id": "ibm-pc:call:0x21/0x4C",
      "kind": "call",
      "key": "0x21/0x4C",
      "name": "exit",
      "scope": "ibm-pc",
      "description": "Ends the program with return code AL.",
      "behaviour": "The emulator terminates the current PSP with AL as the return code, clears the running program's name and arguments, and sets AX=3E01h for the parent, as the source comment says real MS-DOS appears to return on leaving AH=4Bh.",
      "checked": true,
      "sources": [
        {
          "role": "documentation",
          "ref": "rbil61:INTERRUP.G D-214C",
          "cites": "INT 21 - DOS 2+ - \"EXIT\" - TERMINATE WITH RETURN CODE",
          "url": "https://www.cs.cmu.edu/~ralf/files.html"
        },
        {
          "role": "emulator",
          "ref": "dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c",
          "cites": "        case 0x4c:                  /* EXIT Terminate with return code */",
          "url": "https://github.com/joncampbell123/dosbox-x/blob/2a43c7335efd91f87bf5582245abdd5b3f18d5d4/src/dos/dos.cpp"
        }
      ]
    }
  ],
  "truncated": false,
  "examined": 518,
  "served": 630,
  "held_back": 235
}
```

</details>

### Arguments

- `id` (string, default `""`): An entry's id, as another reply cites it, such as `ibm-pc:call:0x21/0x4C`. Answers that entry whole.
- `kind` (one of `""`, `"vector"`, `"call"`, `"error"`, `"port"`, `"irq"`, `"memory"`, `"input"`, `"device"`, `"register"`, `"command"`, default `""`): What the number is: `vector`, `call`, `error`, `port`, `irq`, `memory`, `input`, `device`, `register` or `command`. Left empty, every kind.
- `key` (string, default `""`): The number as a reply prints it: a call is `INT/AH` or `INT/AH/AL`, such as `0x21/0x4C`.
- `text` (string, default `""`): Words looked for in names, aliases, descriptions and behaviour. A word ending in `*` matches by prefix.
- `device` (string, default `""`): A device's key: everything that belongs to it.
- `scope` (string, default `""`): `ibm-pc`, the only system this server names. Left empty, all.
- `limit` (integer, default `10`): How many entries are listed: 1 to 50. Left out, 10.

### What comes back

- `entries`: Rows with `id`, `kind`, `key`, `name`; one match, or an `id`, answers whole with `description`, `behaviour` and `sources`.
- `entries_total`: How many entries matched.
- `examined`: How many entries were searched, so a zero says what it is a zero of.
- `held_back`: How many entries exist and are not confirmed, so are not served.
- `unconfirmed`: The ids of the held-back entries the question matched.
- `nearest`: When nothing matched: the entries next to the number or the words.

<details><summary>All 10 reply fields</summary>

- `entries` (array of object)
- `entries_total` (integer)
- `examined` (integer)
- `held_back` (integer)
- `nearest` (array of object)
- `query` (object)
- `scope` (array of string)
- `served` (integer)
- `truncated` (boolean)
- `unconfirmed` (array of string)

</details>

### What it refuses

- None of `id`, `kind`, `key`, `text`, `device` (`bad_argument`).
- A `key` that is no number of that `kind`, or a `scope` the server does not hold (`bad_argument`).
- An `id` or a `device` the base does not hold (`unknown_ref`).

### Why it works this way

The base serves an entry only once a second check confirmed it against the source, and an answer says where it was read. A key whose entry is held back says so (`unconfirmed`) and stays a number. The base is the server's own copy: it answers while the program runs.

### Related tools

- [`symbols_find`](#symbols_find)
- [`interrupt_vectors`](machine.md#interrupt_vectors)
- [`disassemble`](read.md#disassemble)
- [`breakpoint_interrupt`](breakpoints.md#breakpoint_interrupt)

<details><summary>The contract your client receives</summary>

```text
What a number is called on this machine, and what the base knows of it: a port, interrupt
vector, DOS or BIOS call, IRQ, memory address, input, device, its registers and commands. One
match, or an `id`, answers the whole entry (`description`, `behaviour`, `sources`); more,
rows. No session is needed except for a device by tag, inputs and memory.

`id`: an entry's id. `kind`: `vector`, `call`, `error`, `port`, `irq`, `memory`, `input`,
`device`, `register` or `command`; empty searches all. `key`: the number as a reply prints it,
or a range. `text`: words in names, aliases, descriptions; `*` ends a prefix. `device`: all of
that device. `scope`: the system, cpu or device; empty, the live session's. `limit` 1..50.

Examples: `key=0x3C8`; `kind=port key=0x3C0..0x3CF`; `kind=vector key=0xFFF8 scope=<scope>`;
`kind=call key=0x21/0x4C`, its variant by a register `kind=call key=0x10/0x12/BL=0x36`;
a running machine's device by tag `kind=device key=:maincpu`; its registers
`kind=register device=<device>`; `text=palette*`.

Refused (INVALID): nothing to look up, a bad `key`, or a `scope` it lacks
(`bad_argument`; `6809` is read as `m6809`); an `id` or `device` it
lacks (`unknown_ref`); a kind it holds none of (`no_channel`); a tag or live kind with no
session (`no_session`).

Reply: `query`, `scope`, `entries_total`, `entries`, `truncated`, `examined`, `served`,
`held_back`; nothing matched: no entry, `nearest` and a `note`: it stays a number.
`unconfirmed` lists ids held back.

Scopes: am9517a, chip, ibm-pc, ins8250, mc146818, mc6845, pic8259, saa1099, sn76496, ym3812, ymf262, z80.

Reference: REFERENCE.md, Names for numbers.
```

</details>
<!-- scry-reference:end knowledge_find -->
