# The Knowledge tools

The knowledge base holds what a machine's documentation says about a number, and what this server measured the emulator doing about it.

Ask `knowledge_find` when a number appears and its meaning is not in your program: a vector, a call, a port, an error code. It answers one entry whole: the document's rows with the lines each was read at, and the emulator's verdict beside any row it does not follow. No session is needed for what the base holds.

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
  "summary": "kind call key 0x21/0x4C: terminate with code",
  "entries_total": 1,
  "examined": 668
}
```

One entry matches, so `entries` answers it whole: the exit call, what DOSBox-X does when it is taken, and its source lines. `examined` counts the entries the search read.

<details><summary>The whole reply</summary>

```json
{
  "summary": "kind call key 0x21/0x4C: terminate with code",
  "status": "ok",
  "query": {"kind": "call", "key": "0x21/0x4C"},
  "scope": ["ibm-pc"],
  "entries_total": 1,
  "entries": [
    {
      "id": "ibm-pc:call:0x21/0x4C",
      "kind": "call",
      "key": "0x21/0x4C",
      "name": "terminate with code",
      "scope": "ibm-pc",
      "rows": [
        {
          "n": "1",
          "on": "is",
          "of": "doc",
          "text": "Terminate with a return code, a DOS 2+ call (EXIT).",
          "cites": [
            {"document": "Ralf Brown's Interrupt List, INTERRUP.G", "lines": "6163"}
          ]
        },
        {
          "n": "2",
          "on": "in AL",
          "of": "doc",
          "text": "AL holds the return code.",
          "cites": [
            {"document": "Ralf Brown's Interrupt List, INTERRUP.G", "lines": "6165"}
          ],
          "verdicts": {"dosbox-x": "as documented"}
        },
        {
          "n": "3",
          "on": "out none",
          "of": "doc",
          "text": "The call never returns.",
          "cites": [
            {"document": "Ralf Brown's Interrupt List, INTERRUP.G", "lines": "6166"}
          ],
          "verdicts": {"dosbox-x": "differs"}
        },
        {
          "n": "5",
          "on": "does",
          "of": "doc",
          "text": "Unless the process is its own parent, all its open files are closed.",
          "cites": [
            {"document": "Ralf Brown's Interrupt List, INTERRUP.G", "lines": "6167-6168"}
          ],
          "verdicts": {"dosbox-x": "unfollowed"}
        },
        {
          "n": "6",
          "on": "does",
          "of": "doc",
          "text": "Unless the process is its own parent, all the memory belonging to it is freed.",
          "cites": [
            {"document": "Ralf Brown's Interrupt List, INTERRUP.G", "lines": "6167-6169"}
          ],
          "verdicts": {"dosbox-x": "unfollowed"}
        },
        {
          "n": "4",
          "on": "out none",
          "of": "dosbox-x",
          "vs": "differs",
          "row": "3",
          "text": "A process that is its own parent returns before closing anything; otherwise control goes to the parent's INT 22 address, and the handler sets AX to 0x3E01 and ends normally.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "118-124"},
            {"file": "src/dos/dos_execute.cpp", "lines": "150-152"},
            {"file": "src/dos/dos.cpp", "lines": "2507-2517"}
          ]
        },
        {
          "n": "7",
          "on": "place",
          "of": "dosbox-x",
          "vs": "place",
          "text": "The INT 21h handler reaches it by its case 0x4c.",
          "cites": [
            {"file": "src/dos/dos.cpp", "lines": "2495"}
          ]
        },
        {
          "n": "8",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "The return code and the termination type, exit or TSR, are stored in the DOS state.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "114-115"}
          ]
        },
        {
          "n": "9",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "The UTF-8 modes of the AMIS providers are told that the process ended.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "119-121"}
          ]
        },
        {
          "n": "10",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "The directory search snapshots of the process are closed with its files.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "123-126"}
          ]
        },
        {
          "n": "11",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "The parent PSP becomes current and its saved registers and stack are restored, with INT 22's address as the return point.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "129-140"},
            {"file": "src/dos/dos_execute.cpp", "lines": "141-152"},
            {"file": "src/dos/dos_execute.cpp", "lines": "153-155"}
          ]
        },
        {
          "n": "12",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "The process name is updated and the error code cleared.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "158"},
            {"file": "src/dos/dos_execute.cpp", "lines": "160"}
          ]
        },
        {
          "n": "13",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "If the CPU core or cycles were auto-determined, they are put back, and the title updated.",
          "cites": [
            {"file": "src/dos/dos_execute.cpp", "lines": "162-173"},
            {"file": "src/dos/dos_execute.cpp", "lines": "174-175"},
            {"file": "src/dos/dos_execute.cpp", "lines": "176-186"}
          ]
        },
        {
          "n": "14",
          "on": "does",
          "of": "dosbox-x",
          "vs": "extra",
          "text": "A termination while an INT 23h break is in progress throws int(9000).",
          "cites": [
            {"file": "src/dos/dos.cpp", "lines": "2497-2501"}
          ]
        }
      ],
      "sources": [
        {
          "where": "Ralf Brown's Interrupt List, INTERRUP.G",
          "url": "https://www.cs.cmu.edu/~ralf/files.html"
        },
        {
          "where": "src/dos/dos_execute.cpp",
          "url": "https://github.com/joncampbell123/dosbox-x/blob/2a43c7335efd91f87bf5582245abdd5b3f18d5d4/src/dos/dos_execute.cpp"
        },
        {
          "where": "src/dos/dos.cpp",
          "url": "https://github.com/joncampbell123/dosbox-x/blob/2a43c7335efd91f87bf5582245abdd5b3f18d5d4/src/dos/dos.cpp"
        }
      ]
    }
  ],
  "truncated": false,
  "examined": 668,
  "served": 2244,
  "held_back": 0
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
- `held_back`: How many entries the base holds without serving.
- `unconfirmed`: The ids of the held-back entries the question matched.
- `nearest`: When nothing matched: the entries next to the number or the words.

<details><summary>All 11 reply fields</summary>

- `entries` (array of object)
- `entries_total` (integer)
- `examined` (integer)
- `held_back` (integer)
- `kinds` (array of string)
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

Each entry was checked against its source, and an answer says where it was read. A key the base has not confirmed answers `unconfirmed` and stays a number. The base is the server's own copy: it answers while the program runs.

### Related tools

- [`symbols_find`](symbols.md#symbols_find)
- [`interrupt_vectors`](machine.md#interrupt_vectors)
- [`disassemble`](read.md#disassemble)
- [`breakpoint_interrupt`](breakpoints.md#breakpoint_interrupt)

<details><summary>The contract your client receives</summary>

```text
What a number is called on the machine and what the base knows of it: a port, vector,
DOS or BIOS call, IRQ, memory address, input, device, register or command. One match, or an
`id`, answers the entry: its `rows`, the document's first with each emulator's `verdicts`,
then the emulators' notes (`vs`); `id=<id>#<n>`: a row, with URLs. More: a list. No session
is needed except for a device by tag, inputs and memory.

`id`: an entry's id. `kind`: `vector`, `call`, `error`, `port`, `irq`, `memory`, `input`,
`device`, `register` or `command`; empty searches all. `key`: the number as a reply prints it,
or a range. `text`: words in names, aliases, rows; `*` ends a prefix. `device`: all of
that device. `scope`: the system, cpu or device; empty, the live session's. `limit` 1..50.

Examples: `key=0x3C8`; `kind=vector key=0xFFF8 scope=<scope>`; `kind=call key=0x21/0x4C`,
a variant `kind=call key=0x10/0x12/BL=0x36`;
a live device by tag `kind=device key=:maincpu`; its registers
`kind=register device=<device>`; `text=palette*`.

Refused (INVALID): nothing to look up, a bad `key`, or a `scope` it lacks
(`bad_argument`; `6809` is read as `m6809`); an `id` or `device` it
lacks (`unknown_ref`); a kind it holds none of (`no_channel`); a tag or live kind with no
session (`no_session`).

Reply: `query`, `scope`, `entries_total`, `entries`, `truncated`, `examined`, `served`,
`held_back`; nothing matched: no entry, `nearest` and a `note`: it stays a number.
`unconfirmed` lists ids held back.

Scopes: am9517a, chip, disney, fdc, gameblaster, gameport, ibm-pc, ide, imfc, innova, ins8250, kbc8042, keys, lpt, mc146818, mc6845, mpu401, pas, pci, pic8259, pit8253, ps1, saa1099, sblaster, sn76496, tandy, vattr, vcrtc, vga_ati, vga_paradise, vga_s3, vga_tseng, vga_xga, vgfx, vmisc, vother, vseq, wss, ym3812, ymf262, z80.

Reference: REFERENCE.md, Knowledge base.
```

</details>
<!-- scry-reference:end knowledge_find -->
