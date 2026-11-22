# The Read tools

These tools read the program without writing to it: bytes of memory, the registers, the code at an address, the calls that led to a stop. They need the program stopped at the debugger; while it runs they refuse (`not_stopped`), except where an entry says otherwise. That refusal carries `last_stop` and names the tools that still answer.

An address is a `ref`: a symbol, once `symbols_load` has loaded a table, or a `SEG:OFF` pair such as `0814:0106`. A bare number is taken as a symbol.

Each tool reads what DOSBox-X's debugger prints for one command, and refuses an answer in a shape it does not know (`unexpected_answer`). For what these tools do not cover, [`debug`](write.md#debug) sends the debugger a command as typed.

<!-- scry-reference:begin registers -->
## `registers`

Read the cpu's registers, now or as they were at the last stop.

```text
registers(from_last_stop=false)
```

### Try it

On Bricks, the game this repository builds, stopped at `brick_hit` as the ball knocks out its first brick.

Ask:

> Show me the cpu's registers at this stop.

Call:

```text
registers()
```

Reply, 1 of 3 fields:

```json
{
  "summary": "registers: 15 registers"
}
```

Fifteen registers came back. The whole reply, folded below, lists each under `regs` as a hex string.

<details><summary>The whole reply</summary>

```json
{
  "summary": "registers: 15 registers",
  "status": "ok",
  "regs": {
    "EAX": "0x00000005",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002c8",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  }
}
```

</details>

### Arguments

- `from_last_stop` (boolean, default `false`): `true` returns the registers the last stop recorded, and answers while the program runs. Left out, the registers are read now.

### What comes back

- `regs`: Each register by name, as a hex string of its own width.
- `superseded`: `true` with `from_last_stop`: the values are the last stop's, which `last_stop` identifies, not the current ones.

<details><summary>All 2 reply fields</summary>

- `regs` (object)
- `superseded` (boolean)

</details>

### What it refuses

- `from_last_stop` before the session's first stop (`no_stop`).

### Why it works this way

`CR0`, `CR3` and the descriptor tables are not here: `machine_map(sections=["control"])` reads them.

### Related tools

- [`set_register`](write.md#set_register)
- [`machine_map`](machine.md#machine_map)
- [`step`](run.md#step)
- [`run_to`](run.md#run_to)
- [`call_stack`](#call_stack)

<details><summary>The contract your client receives</summary>

```text
The registers at this stop. `from_last_stop=True` returns the registers of the last stop,
never the current value; refused (`no_stop`) before any stop.

Reply: `regs` (hex strings), `superseded` (with `from_last_stop`). CR0, CR3 and descriptor
tables: `machine_map(sections=["control"])`.
```

</details>
<!-- scry-reference:end registers -->

<!-- scry-reference:begin read_memory -->
## `read_memory`

Read a few bytes of memory at an address, as hex text.

```text
read_memory(ref, length=16)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen before any brick falls, with its symbols loaded.

Ask:

> Read the two bytes of the score.

Call:

```text
read_memory(ref="score", length=2)
```

Reply, 4 of 6 fields:

```json
{
  "summary": "read_memory score: 2 bytes at 08DF:00000615: 0000",
  "seg_off": "08DF:00000615",
  "length": 2,
  "hex": "0000"
}
```

`score` is at `08DF:00000615` (`seg_off`) and holds `0000`: no point scored yet.

<details><summary>The whole reply</summary>

```json
{
  "summary": "read_memory score: 2 bytes at 08DF:00000615: 0000",
  "status": "ok",
  "ref": "score",
  "seg_off": "08DF:00000615",
  "length": 2,
  "hex": "0000"
}
```

</details>

### Arguments

- `ref` (string, required): The address to read: a symbol or a `SEG:OFF` address.
- `length` (integer (>= 1, <= 128), default `16`): How many bytes: 1 to 128. Left out, 16.

### What comes back

- `hex`: The bytes, two hex characters each, lowest address first.
- `seg_off`: The address `ref` resolved to, as segment and offset.

<details><summary>All 4 reply fields</summary>

- `hex` (string)
- `length` (integer)
- `ref` (string)
- `seg_off` (string)

</details>

### What it refuses

- A symbol the loaded table lacks (`unknown_ref`), or one it holds twice (`ambiguous_ref`).
- An offset the cpu's mode cannot address: past `0xFFFF` in real mode (`bad_argument`).
- A dump that is not the size asked for (`readback_refused`).

### Why it works this way

The bytes come from the debugger's `MEMDUMPBIN` of exactly that range, and a dump of any other size is refused, never handed back shifted. For more than 128 bytes, `memdump` writes a file.

### Related tools

- [`memdump`](#memdump)
- [`write`](write.md#write)
- [`watch_add`](breakpoints.md#watch_add)
- [`find`](#find)
- [`symbols_load`](names.md#symbols_load)

<details><summary>The contract your client receives</summary>

```text
`length` bytes (1..128) at `ref`, a symbol or `SEG:OFF` (a bare number is read as a
symbol).

Reply: `hex`, `length`, `seg_off`, `ref`; above 128 bytes use `memdump`. Needs the
machine stopped. An absent or ambiguous symbol is refused.
```

</details>
<!-- scry-reference:end read_memory -->

<!-- scry-reference:begin disassemble -->
## `disassemble`

Disassemble the code at an address, one instruction a line, each marked as a call, a branch, a return or none of those.

```text
disassemble(ref, length=16)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen with its symbols loaded and a comment written on `brick_hit`.

Ask:

> Show me the first instructions of the routine that runs when a brick is hit.

Call:

```text
disassemble(ref="brick_hit", length=12)
```

Reply, 4 of 11 fields:

```json
{
  "summary": "disassemble brick_hit: 4 lines at 08DF:000002C8, 16-bit",
  "code_bits": 16,
  "lines": [
    "08DF:000002C8 88DF                 mov bh, bl // AL = row, B ... (94 characters)",
    "08DF:000002CA 88C3                 mov bl, al",
    "08DF:000002CC E81FFF               call 0x1ee",
    "08DF:000002CF C6842C0600           mov byte ptr [si + 0x62c] ... (63 characters)"
  ],
  "flow": ["sequential", "sequential", "call", "sequential"]
}
```

Four 16-bit instructions from `brick_hit`; the first ends with the comment written on it. `flow` marks the third as a `call` and the others as `sequential`, plain instructions.

<details><summary>The whole reply</summary>

```json
{
  "summary": "disassemble brick_hit: 4 lines at 08DF:000002C8, 16-bit",
  "status": "ok",
  "ref": "brick_hit",
  "seg_off": "08DF:000002C8",
  "length": 12,
  "code_bits": 16,
  "code_bits_from": "real mode",
  "lines": ["08DF:000002C8 88DF                 mov bh, bl // AL = row, BL = column of the brick that falls", "08DF:000002CA 88C3                 mov bl, al", "08DF:000002CC E81FFF               call 0x1ee", "08DF:000002CF C6842C0600           mov byte ptr [si + 0x62c], 0"],
  "flow": ["sequential", "sequential", "call", "sequential"],
  "flow_source": "capstone",
  "resolved": [
    {
      "line": 2,
      "operand": "0x1ee",
      "kind": "target",
      "seg_off": "08DF:000001EE",
      "addr": "0x00008fde",
      "symbol": "brick_index",
      "delta": 0
    }
  ]
}
```

</details>

### Arguments

- `ref` (string, required): Where to start: a symbol or a `SEG:OFF` address.
- `length` (integer (>= 1, <= 1024), default `16`): How many bytes to decode, 1 to 1024; left out, 16. The last instruction is completed even when it runs past them.

### What comes back

- `lines`: One x86 instruction a line: `SSSS:OOOOOOOO`, its bytes, its text. A line with a comment ends ` // <text>`.
- `flow`: One word per line: `call`, `branch`, `return`, `sequential` or `unknown`, as the decoder (`flow_source`, `capstone`) classified it.
- `code_bits`: 16 or 32, the width the code was decoded in. `code_bits_from` says where that width was read.
- `resolved`: Only with symbols loaded: each direct call or branch target and memory operand, with its address and nearest symbol. Rows carry `line`, `operand`, `kind`, `register`, `seg_off`, `addr`, `symbol` and `delta`.
- `seg_off`: The address `ref` resolved to, as segment and offset.
- `line_notes`: Where the base names an operand: `line`, `note`, and `live` when a register named it. A person's comment stays on its line.

<details><summary>All 10 reply fields</summary>

- `code_bits` (integer)
- `code_bits_from` (string)
- `flow` (array)
- `flow_source` (string)
- `length` (integer)
- `line_notes` (array)
- `lines` (array)
- `ref` (string)
- `resolved` (array)
- `seg_off` (string)

</details>

### What it refuses

- A `length` that runs past the end of a 16-bit segment, where the cpu wraps; the refusal names the most bytes that fit (`bad_argument`).
- The null selector, or one with no descriptor, in protected mode (`bad_argument`).
- A symbol the loaded table lacks (`unknown_ref`), or one it holds twice (`ambiguous_ref`).
- Whatever `memdump` refuses: the bytes are read the same way.

### Why it works this way

The debugger has no disassembly command, so capstone decodes the bytes read from memory. A byte no instruction starts with is listed as `.byte 0x..` and marked `unknown`.

The width is the segment's own, never the cpu mode's alone. Real mode is 16-bit; protected mode takes it from the stop for `CS`, from `SELINFO` for a segment another register holds, and from the descriptor tables otherwise.

<details><summary>More on why</summary>

In `resolved`, `kind` is `target` or `memory`. A memory operand is read through the segment register named in `register`, as it stands at this stop. Outside the loaded table's range, `symbol` and `delta` are unavailable.

**Checked against the debugger's own disassembly**

Each listing is checked line by line against the debugger's own code pane, and its bytes against what `read_memory` reads. The two agree on address, length, bytes, mnemonic and operands, and may differ in spelling alone:

- One instruction under two names: `jc` and `jb`, `jnc` and `jae`, `popad` and `popal`, `call` and `lcall` for a far call.
- A string instruction's implicit operands, which the pane leaves out, and a size word it leaves out where a register fixes the size.
- A symbol the pane prints in place of an operand's number.
- `FE /7`, which is no x86 instruction: DOSBox-X enters its own code through `FE 38`, so the pane reads it as `callback`. Here it is a byte no instruction starts with.

</details>

### Related tools

- [`call_stack`](#call_stack)
- [`step`](run.md#step)
- [`symbols_load`](names.md#symbols_load)
- [`comment_write`](comments.md#comment_write)
- [`read_memory`](#read_memory)
- [`breakpoint_at`](breakpoints.md#breakpoint_at)

<details><summary>The contract your client receives</summary>

```text
Decode `length` bytes from `ref` (a symbol or `SEG:OFF`) as x86, one instruction a line. The
last is completed unless the segment ends first. A line a comment is placed on ends
` // <text>`.

Reply: `ref`, `seg_off`, `length`, `code_bits`, `code_bits_from`, `lines`, `flow` (per line:
`call`, `branch`, `return`, `sequential`, `unknown`), `flow_source`, and with symbols loaded
`resolved` (direct call/branch targets and memory operands: `line`, `operand`, `seg_off`,
`addr`, `symbol`, `delta`).

Refused: `length` out of range or past the end of a 16-bit segment; `memdump`'s refusals
apply.

Reference: REFERENCE.md, Reading and writing.
```

</details>
<!-- scry-reference:end disassemble -->

<!-- scry-reference:begin call_stack -->
## `call_stack`

Guess the chain of calls that led to the stop, by following the frame pointers on the stack.

```text
call_stack()
```

### Try it

On Bricks, the game this repository builds, stopped at `brick_hit` as the ball knocks out its first brick.

Ask:

> Who called the routine the game is stopped in?

Call:

```text
call_stack()
```

Reply, 4 of 7 fields:

```json
{
  "summary": "call_stack: 1 call, innermost brick_hit, heuristic",
  "heuristic": true,
  "truncated": false,
  "ended_why": "the return address beside the frame at SS:91C follows no call instruction"
}
```

One call, the stop itself in `brick_hit`. Bricks keeps no frame pointer, so no caller is found, and `ended_why` says where the chain broke.

<details><summary>The whole reply</summary>

```json
{
  "summary": "call_stack: 1 call, innermost brick_hit, heuristic",
  "status": "ok",
  "heuristic": true,
  "code_bits": 16,
  "calls": [
    {
      "seg_off": "08DF:000002C8",
      "via": "stop",
      "call": {"available": false, "why": "the stop itself: no call leads to it"},
      "bp": {"available": false, "why": "no frame was read beside it"},
      "addr": "0x000090b8",
      "symbol": "brick_hit",
      "delta": 0
    }
  ],
  "truncated": false,
  "ended_why": "the return address beside the frame at SS:91C follows no call instruction"
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `calls`: One row per call, innermost first; row 0 is the stop. Each has `seg_off`, `addr`, `symbol`, `delta`, `via`, `call` and `bp`.
- `heuristic`: Always `true`: the chain is a guess, never proof of who called whom.
- `ended_why`: Why the chain ends where it does.
- `truncated`: `true` when the chain was cut at the most rows a reply lists, with frames still to read.
- `code_bits`: 16 or 32, the width of the code at the stop.

<details><summary>All 5 reply fields</summary>

- `calls` (array)
- `code_bits` (integer)
- `ended_why` (string)
- `heuristic` (boolean)
- `truncated` (boolean)

</details>

### What it refuses

- A stop whose registers came back without `SS`, `ESP` or `EBP` (`unexpected_answer`).

### Why it works this way

A routine that keeps no frame pointer shows its caller's caller in its place, or nothing.

At a routine's `push bp` or `enter`, the `mov bp, sp` after it, or its `ret`, the stop is outside the frame. The caller is then read from the stack pointer, and its row says `via` `entry`. The other rows come from the frame chain (`bp_chain`), near or far as the call before each says.

The chain ends at a saved frame pointer that is zero or does not rise, or at a frame past the stack segment's end. A return address no call precedes ends it unlisted; one outside the loaded symbol table ends it listed.

<details><summary>More on why</summary>

`call` is unavailable on row 0, and `bp` on row 0 and on an `entry` row.

</details>

### Related tools

- [`disassemble`](#disassemble)
- [`registers`](#registers)
- [`trace`](run.md#trace)
- [`step`](run.md#step)
- [`symbols_load`](names.md#symbols_load)
- [`run_to`](run.md#run_to)

<details><summary>The contract your client receives</summary>

```text
A heuristic chain of the stop's callers, never a verdict: frame pointers walked (`push
bp`/`mov bp, sp`, `enter`), each return kept only when a call instruction ends there. Row 0
is the stop.

Reply: `heuristic`, `code_bits`, `calls` (innermost first: `seg_off`, `addr`, `symbol`,
`delta`, `via`, `call`, `bp`), `truncated`, `ended_why`. Refused when the registers come
back without SS, ESP or EBP. A routine with no frame pointer is invisible.

Reference: REFERENCE.md, Reading and writing.
```

</details>
<!-- scry-reference:end call_stack -->

<!-- scry-reference:begin memdump -->
## `memdump`

Write a range of memory to a file, for ranges too large to read into the conversation.

```text
memdump(ref, length, dest)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen before any brick falls, with its symbols loaded.

Ask:

> Save the 60 bytes of the wall of bricks to a file.

Call:

```text
memdump(ref="bricks", length=60, dest="./tmp/demos/tour/files/wall.bin")
```

Reply, 5 of 7 fields:

```json
{
  "summary": "memdump bricks: 60 bytes to ./tmp/demos/tour/files/wall.bin",
  "seg_off": "08DF:0000062C",
  "length": 60,
  "path": "./tmp/demos/tour/files/wall.bin",
  "bytes": 60
}
```

The file holds 60 bytes, as asked: `bytes` equals `length`. `path` is where it was written.

<details><summary>The whole reply</summary>

```json
{
  "summary": "memdump bricks: 60 bytes to ./tmp/demos/tour/files/wall.bin",
  "status": "ok",
  "ref": "bricks",
  "seg_off": "08DF:0000062C",
  "length": 60,
  "path": "./tmp/demos/tour/files/wall.bin",
  "bytes": 60
}
```

</details>

### Arguments

- `ref` (string, required): Where the range begins: a symbol or a `SEG:OFF` address.
- `length` (integer, required): How many bytes to write, 1 or more.
- `dest` (string, required): The file to create: an absolute or `~`-led path, not there yet.

### What comes back

- `path`: The file as written; a `note` says so when its name is not the one `dest` gave.
- `bytes`: The file's size, which equals `length`.
- `seg_off`: The address `ref` resolved to, as segment and offset.

<details><summary>All 5 reply fields</summary>

- `bytes` (integer)
- `length` (integer)
- `path` (string)
- `ref` (string)
- `seg_off` (string)

</details>

### What it refuses

- A dump file already in the emulator's working folder, or a file already at `dest` (`bad_argument`).
- A `dest` directly in the emulator's working folder, or at or under one of the debugger's own file names (`bad_argument`).
- In protected mode: a range past `0xFFFF` on a 16-bit segment, a range past the segment's limit, or a selector with no descriptor (`bad_argument`).
- In real mode: a range that ends past `FFFF:FFFF` (`bad_argument`).
- A symbol the loaded table lacks (`unknown_ref`), or one it holds twice (`ambiguous_ref`).
- A dump that is not `length` bytes (`readback_refused`).

### Why it works this way

The debugger writes the dump in the emulator's working folder, as `MCPDUMP.BIN`, and the server moves it to `dest`. A dump file already there is somebody's, so the call refuses it and deletes nothing; a dangling link counts. A `dest` in that folder is refused too: once moved, the file could not be told from a leftover.

Past offset `0xFFFF` the debugger would reread the start of a 16-bit segment, or write zeros past a segment's limit, and still report success. So in real mode a long range is read in 64 KiB pieces, up to `FFFF:FFFF`. In protected mode it is checked against the segment's descriptor first.

Inside offsets 0 to `0xFFFF` the segment's limit is not checked, and the debugger writes zeros past it.

<details><summary>More on why</summary>

Some builds of DOSBox-X name the file `MEMDUMP.BIN` themselves, in the working folder or in the captures folder, so a leftover of that name is refused in both. A `dest` is compared with those names on the file system, not by spelling. `captures_dir` is not where a dump lands.

Deleting a leftover first would not be safer. A delete that failed quietly would leave the old file, the debugger would still report success, and a stale dump would come back as new.

</details>

### Related tools

- [`read_memory`](#read_memory)
- [`find`](#find)
- [`guest_file`](files.md#guest_file)
- [`machine_map`](machine.md#machine_map)
- [`snapshot`](captures.md#snapshot)

<details><summary>The contract your client receives</summary>

```text
`length` bytes from `ref` (a symbol or `SEG:OFF`) to the new file `dest` (absolute or
`~`-led).

Reply: `ref`, `seg_off`, `length`, `path`, `bytes`. Refused: a dump file already where the
debugger writes or at `dest`, a `dest` directly in that directory, an absent or ambiguous
symbol; in protected mode a 16-bit segment, a range past its limit, or no descriptor.
```

</details>
<!-- scry-reference:end memdump -->

<!-- scry-reference:begin find -->
## `find`

Find every address in a range of memory that holds a given sequence of bytes.

```text
find(data_hex, ref, length)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen with its symbols loaded.

Ask:

> Find where the program holds the text SCORE.

Call:

```text
find(data_hex="53434f5245", ref="start", length=1384)
```

Reply, 5 of 9 fields:

```json
{
  "summary": "find start: 1 hit of 53434f5245 in 1384 bytes",
  "span": {"from": "08DF:00000100", "length": 1384, "source": "ref+length"},
  "hits": ["08DF:00000601"],
  "hits_total": 1,
  "truncated": false
}
```

The five bytes of `SCORE` are at one address, `08DF:00000601`. `span` says which bytes were searched: 1384 from `08DF:00000100`, the symbol `start`.

<details><summary>The whole reply</summary>

```json
{
  "summary": "find start: 1 hit of 53434f5245 in 1384 bytes",
  "status": "ok",
  "ref": "start",
  "seg_off": "08DF:00000100",
  "length": 1384,
  "span": {"from": "08DF:00000100", "length": 1384, "source": "ref+length"},
  "hits": ["08DF:00000601"],
  "hits_total": 1,
  "truncated": false
}
```

</details>

### Arguments

- `data_hex` (string, required): The bytes to look for, as hex: whole bytes, at least one.
- `ref` (string, required): Where the range begins: a symbol or a `SEG:OFF` address.
- `length` (integer, required): How many bytes to search from `ref`.

### What comes back

- `hits`: The addresses where the bytes begin, as `SEG:OFF`, at most 400; past that, the highest are kept.
- `hits_total`: How many addresses hold the bytes, listed or not.
- `truncated`: `true` when there are more hits than `hits` lists.
- `span`: The bytes that were searched, as `from`, `length` and `source`, so zero hits says where there are none. `source` is always `ref+length`.

<details><summary>All 7 reply fields</summary>

- `hits` (array)
- `hits_total` (integer)
- `length` (integer)
- `ref` (string)
- `seg_off` (string)
- `span` (object)
- `truncated` (boolean)

</details>

### What it refuses

- Hex that is not whole bytes, or a `length` shorter than the bytes to find (`bad_argument`).
- A symbol the loaded table lacks (`unknown_ref`), or one it holds twice (`ambiguous_ref`).
- Whatever `memdump` refuses: the range is read the same way.

### Why it works this way

The debugger has no search for bytes. So the range is read as `memdump` reads it, into a temporary file that is gone before the reply, and searched there.

In real mode a hit past offset `0xFFFF` is written with a segment of its own, since no offset reaches it from the segment you gave.

### Related tools

- [`scan`](scan.md#scan)
- [`read_memory`](#read_memory)
- [`memdump`](#memdump)
- [`watch_add`](breakpoints.md#watch_add)

<details><summary>The contract your client receives</summary>

```text
Every address holding `data_hex` (whole hex bytes) in `length` bytes from `ref`; both
required. `memdump`'s refusals apply. For a value narrowed over time use `scan`.

Reply: `ref`, `seg_off`, `length`, `span`, `hits` (`SEG:OFF`, at most 400, highest kept),
`hits_total`, `truncated`.
```

</details>
<!-- scry-reference:end find -->

<!-- scry-reference:begin screen_map_find -->
## `screen_map_find`

Name the screen your program is showing, from its screen map: a file of the program's screens and the named areas of each.

```text
screen_map_find()
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen with the game's own map loaded, as in the example of `screen_map_write` below.

Ask:

> Which screen is the game showing?

Call:

```text
screen_map_find()
```

Reply, 5 of 8 fields:

```json
{
  "summary": "screen_map_find: play (file), 1 control",
  "matched": true,
  "screen": "play",
  "layer": "file",
  "controls": [
    {"name": "court", "rect": [200, 80, 80, 40], "centre": [240, 100]}
  ]
}
```

The game shows `play`, a screen of the loaded file (`layer` `file`). Its area `court` is the rectangle at 200, 80, with its centre at 240, 100.

<details><summary>The whole reply</summary>

```json
{
  "summary": "screen_map_find: play (file), 1 control",
  "status": "ok",
  "matched": true,
  "screen": "play",
  "layer": "file",
  "kind": "pixel",
  "size": [320, 200],
  "controls": [
    {"name": "court", "rect": [200, 80, 80, 40], "centre": [240, 100]}
  ]
}
```

</details>

### Arguments

Takes no argument.

### What comes back

- `matched`: `true` when a screen of the map is the one showing.
- `screen`: The name of the screen that matched.
- `controls`: The matched screen's named areas, each with `name`, `rect` and `centre`, in the program's own units.
- `layer`: Where the screen was found: `session` for a screen added in this session, `file` for one of the loaded map.
- `screens_mapped`: When nothing matched: how many screens the map holds. `screens_tried` says how many had the right kind and size.
- `view_fits`: `false` when the picture's size cannot be the map's, seen through the `scale` and `margin` it was loaded with.

<details><summary>All 10 reply fields</summary>

- `controls` (array)
- `kind` (string)
- `layer` (string)
- `matched` (boolean)
- `screen` (string)
- `screens_mapped` (integer)
- `screens_tried` (integer)
- `screens_unjudged` (integer)
- `size` (array)
- `view_fits` (boolean)

</details>

### What it refuses

- No screen mapped yet: load a map or add a screen with `screen_map_write` (`needs_call`).
- A video mode `screen_view` cannot read (`no_channel`).

### Why it works this way

A screen matches when its kind and size are the ones showing and each of its regions has the fingerprint the map recorded. Screens added this session are tried first, then the loaded file's.

The areas of the matched screen are what `send_mouse(target=)` clicks by name. The click acts on the screen this tool last matched, and what is drawn is not compared again. After anything that may have changed the screen, call it again at a stop.

A screen added with `cells` `index` is compared by palette index, not by colour.

### Related tools

- [`screen_map_write`](#screen_map_write)
- [`send_mouse`](input.md#send_mouse)
- [`run_to`](run.md#run_to)
- [`screen_view`](screen.md#screen_view)
- [`screen_signature`](screen.md#screen_signature)

<details><summary>The contract your client receives</summary>

```text
Which mapped screen the machine shows. Reply: `matched`, `kind` and `size`; when matched,
`screen`, `layer`, `controls` (`name`, `rect`, `centre`), in the program's units; when not,
`screens_mapped` and, if the view fits the map, `screens_tried` and `screens_unjudged`
(signed by index on a screen whose pens cannot be read), else `view_fits` false. None mapped:
`needs_call`.

Reference: REFERENCE.md, Screen maps.
```

</details>
<!-- scry-reference:end screen_map_find -->

<!-- scry-reference:begin screen_map_write -->
## `screen_map_write`

Build the screen map, the file that names your program's screens and their areas: add the screen showing, load a file, or save one.

```text
screen_map_write(method, screen="", match=null, controls=null, cells="", anchor="", path="",
    scale=null, margin=null, dest="", overwrite=null, pointer=null)
```

### Try it

On Bricks, the game this repository builds, at any moment: a `load` reads a file, whether or not the game runs.

Ask:

> Load the screen map of Bricks.

Call:

```text
screen_map_write(method="load", path="./demos/bricks/bricks-screen-map.json")
```

Reply, 5 of 7 fields:

```json
{
  "summary": "screen_map_write load: 1 screen, 1 control of bricks",
  "application": "bricks",
  "mode": "verified",
  "screens": 1,
  "controls": 1
}
```

The map of `bricks` holds one screen and one named area. Its `mode` is `verified`: a screen is checked each time it is reached.

<details><summary>The whole reply</summary>

```json
{
  "summary": "screen_map_write load: 1 screen, 1 control of bricks",
  "status": "ok",
  "path": "./demos/bricks/bricks-screen-map.json",
  "application": "bricks",
  "mode": "verified",
  "screens": 1,
  "controls": 1
}
```

</details>

### The four methods

| method | what it does |
|---|---|
| `add` | Records the screen showing now under a name, with the regions that identify it and its named areas. Needs the program stopped. |
| `pointer` | Says where the program keeps its own mouse pointer, so a move can be checked against it. Works while the program runs. |
| `load` | Reads a map file; nothing is written to disk. Works while the program runs. |
| `save` | Writes the loaded map and the screens added since as one file, which becomes the loaded map. Works while the program runs. |

### Arguments

- `method` (one of `"add"`, `"pointer"`, `"load"`, `"save"`, required): `add`, `pointer`, `load` or `save`, as above.
- `screen` (string, default `""`): For `add`: the name the screen is recorded under.
- `match` (array of array of integer, optional): For `add`: 1 to 16 rectangles `[x, y, width, height]` that always look the same on this screen. They are what identifies it.
- `controls` (array of object, optional): For `add`: the screen's named areas, each `{"name", "rect"}`. Left out, none.
- `cells` (one of `""`, `"rgb"`, `"index"`, default `""`): For `add`: `index` compares palette indices, not the colours shown, so one map serves a program shown through two palettes. Left out, `rgb`.
- `anchor` (string, default `""`): For `add`: a symbol or an address the program reaches once the screen is fully drawn. `run_to(screen=)` runs to it.
- `path` (string, default `""`): For `load`: the map file, named `<application>-screen-map.json`, as an absolute or `~`-led path.
- `scale` (integer, optional): For `load`: how many times larger this machine shows the program's picture, 1 to 8. Left out, 1.
- `margin` (array of integer, optional): For `load`: `[x, y]`, the border in machine pixels on each side of the program's picture. Left out, none.
- `dest` (string, default `""`): For `save`: the file to write, named `<application>-screen-map.json`, as an absolute or `~`-led path.
- `overwrite` (boolean, optional): For `save`: `true` replaces a file already at `dest`. Left out, an existing file is refused.
- `pointer` (object, optional): For `pointer`: `{"x": ref, "y": ref, "bytes": 2}`, a symbol or a `SEG:OFF` address for each axis. `bytes` is 1, 2 or 4; left out, 2.

### What comes back

- `match`: `add`: each region as recorded, with its `crop` and its `signature`, the fingerprint taken from the screen.
- `replaced`: `add`: `true` when a screen of that name was already added this session. `shadows_file` is `true` when the loaded file has one too.
- `kept`: `add`: reads `N saved for promote` once the map is a candidate that `promote` can write into your repository's `.scry/` folder.
- `screens`: `load` and `save`: how many screens the map holds; `controls` counts their named areas.
- `mode`: `load` and `save`: `verified` when a screen is checked each time it is reached, `consolidated` when it is trusted without a check.
- `promoted`: `save`: the names of the screens added this session that the file now holds.

<details><summary>All 16 reply fields</summary>

- `anchor` (string)
- `application` (string)
- `cells` (string)
- `controls` (integer)
- `kind` (string)
- `kept` (string)
- `match` (array)
- `mode` (string)
- `path` (string)
- `pointer` (object)
- `promoted` (array)
- `replaced` (boolean)
- `screen` (string)
- `screens` (integer)
- `shadows_file` (boolean)
- `size` (array)

</details>

### What it refuses

- An argument the method does not take.
- A name, rectangle, area, pointer or file that is not well formed, or a rectangle outside the screen (`bad_argument`).
- An `add` without `anchor` when the loaded map is `consolidated`, or a `save` of one holding a screen with none (`bad_argument`).
- A `pointer` on a map loaded with a `scale` or a `margin` (`bad_argument`).
- `cells` `index` in a mode with no palette (15-, 16- or 32-bit colour), or a video mode `screen_view` cannot read (`no_channel`).
- A `save` with nothing mapped and no pointer (`needs_call`).

### Why it works this way

A screen is recognised by a few regions that never change, not by the whole picture: a cursor or a moving ball would change a fingerprint of the whole screen.

The map has two layers. Screens you `add` live in the session and win over a loaded file's screen of the same name; `save` writes both as one file. A new `start` empties the session layer and keeps the file.

A map's `mode` says who keeps it true. In a `verified` map, `run_to(screen=)` checks the screen's regions on reaching it and refuses a map that no longer matches (`stale_map`). In a `consolidated` map the screen is trusted at its `anchor`, which lets one map serve two versions of a program whose pixels differ.

<details><summary>More on why</summary>

The mode is the file's own: `save` keeps the loaded map's, and writes `verified` when none was loaded. `screen_map_find` checks the regions in either mode.

Rectangles are in the program's units: character cells in a text mode, pixels in a graphics mode. With `scale` and `margin`, this machine's picture is the program's size times the scale, plus the margin on each side. A read is sampled back to the program's size before it is compared.

A map file is kept in the program's repository, as `.scry/maps/<application>-screen-map.json`, and looks like this.

```json
{"format": "scry-screen-map/1", "application": "bricks", "mode": "verified",
 "screens": [{"name": "play", "kind": "pixel", "size": [320, 200], "anchor": "main_loop",
              "match": [{"crop": [0, 0, 52, 8], "signature": "<16 hex>"}],
              "controls": [{"name": "court", "rect": [200, 80, 80, 40]}]}]}
```

A program that keeps a mouse pointer of its own and clamps it drifts from the mouse driver's. With `pointer` given, `send_mouse` reads the program's pointer back and corrects until it is where it was asked to be. A `save` keeps the pointer, and a `load` replaces it.

In the replay test `perform_export` writes, `load` and `add` are replayed as steps and `screen_map_find` becomes a check of what it matched. A `save` is left out, since a replay would find its file there.

</details>

### Related tools

- [`screen_map_find`](#screen_map_find)
- [`send_mouse`](input.md#send_mouse)
- [`run_to`](run.md#run_to)
- [`screen_signature`](screen.md#screen_signature)
- [`screen_view`](screen.md#screen_view)
- [`promote`](project.md#promote)

<details><summary>The contract your client receives</summary>

```text
The screen map: an application's screens, each known by the signatures of its stable regions, and their controls, in a session layer and a file layer.

`add`: the screen shown now as `screen` in the session layer, one read signing each `match` crop ([x, y, width, height], 1..16), `controls` ([{"name", "rect"}]) in the screen's own units; needs the machine stopped. Reply: `screen`, `kind`, `size`, `cells`, `match`, `controls`, `replaced`, `shadows_file`, `anchor` (when given), `kept` (a complete map is kept for `promote`).

`pointer`: the program's own pointer as an object, `{"x": ref, "y": ref, "bytes": 2}` (a symbol or
`SEG:OFF` for each axis; `bytes` 1, 2 or 4), as a map file declares it; kept by `save`, replaced by a `load`; a misshapen object is `bad_argument`. Reply: `pointer`.

`add`'s `cells` `index` (a pixel screen; default
`rgb`) signs the palette indices drawn, not the colours shown, so one map knows a program
shown through two palettes; a screen with no palette refuses it (`no_channel`).

`add`'s `anchor` (a symbol or an address, as `run_to`'s `ref`) is the place after which the screen is whole,
what `run_to(screen=)` runs to: a consolidated map refuses an `add` without one (`bad_argument`),
since it enters its screens by theirs.

`load`: `path` (`<application>-screen-map.json`, absolute or `~`-led) as the file layer, held by the
server; nothing is written to disk. `scale` (1..8) and `margin` [x, y] (machine pixels on
each side) say how the program's picture sits on this machine's screen; maps and `add`'s
crops are in the program's units. Reply: `path`, `application`, `mode`, `screens`, `controls`, `pointer`
(a map that declares the program's pointer).

`save`: both layers as one map to `dest`, refused there without `overwrite`, made the file
layer, in the loaded map's `mode` (`verified` when none was loaded). Reply: `path`,
`application`, `mode`, `screens`, `controls`, `promoted`.

Refused: an argument the method does not take; a misshapen name, crop, control, view or file; an `add` without an `anchor` to a consolidated map, and a save of one holding a screen with none (`bad_argument`); neither a screen nor a `pointer` to save (`needs_call`); the modes `screen_view` refuses.

Reference: REFERENCE.md, Screen maps.
```

</details>
<!-- scry-reference:end screen_map_write -->
