# The Write tools

These tools change the machine instead of reading it: bytes in memory, a register, and `debug`, which sends any command to the debugger's command line. All three need the machine stopped.

Every write marks the session. From then on the `session` block of every reply carries `altered`: this session has written to the machine, so a later measurement is of a changed program.

<!-- scry-reference:begin set_register -->
## `set_register`

Force a register to a value you choose, and see what the cpu holds afterwards.

```text
set_register(name, value)
```

### Try it

On Bricks, the game this repository builds, stopped at `brick_hit` as the ball knocks out its first brick. AL holds the brick's row there.

Ask:

> Set AX to 0, so the game takes this brick for one of the top row.

Call:

```text
set_register(name="ax", value=0)
```

Reply, 5 of 7 fields:

```json
{
  "summary": "set_register ax = 0, verified True",
  "register": "ax",
  "value": "0x0000",
  "readback": "0x0000",
  "verified": true
}
```

AX now holds 0. `readback` is what the register held after the write, four digits for a 16-bit name, and `verified` says it equals what was asked.

<details><summary>The whole reply</summary>

```json
{
  "summary": "set_register ax = 0, verified True",
  "status": "ok",
  "value": "0x0000",
  "register": "ax",
  "regs": {
    "EAX": "0x00000000",
    "EBX": "0x00000707",
    "ECX": "0x005b0020",
    "EDX": "0x00000000",
    "ESI": "0x00000039",
    "EDI": "0x000064e4",
    "EBP": "0x0000091c",
    "ESP": "0x0000fffa",
    "EIP": "0x000002a5",
    "CS": "0x08df",
    "DS": "0x08df",
    "ES": "0xa000",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x08df"
  },
  "readback": "0x0000",
  "verified": true
}
```

</details>

### Arguments

- `name` (string, required): The register, as the debugger's `SR` command takes it: a 32-bit one (`eax`), a segment (`ds`), or a 16-bit low half (`ax`, `ip`).
- `value` (integer or string, required): The value to set: an integer or a `0x` string, not negative and no wider than the register.

### What comes back

- `register`: The register written, in lower case.
- `value`: What was asked, as `0x` text at the register's width.
- `readback`: What the register holds after the write, in the same spelling. A 16-bit name is read as the low half of its 32-bit register, so four digits.
- `verified`: `true` when `readback` equals `value`.
- `regs`: Every register as it reads after the write.

<details><summary>All 5 reply fields</summary>

- `readback` (string)
- `register` (string)
- `regs` (object)
- `value` (string)
- `verified` (boolean)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- A name the debugger does not set; the message lists the ones it does (`bad_argument`).
- A negative value, or one wider than the register, before anything is sent (`bad_argument`).
- Registers that do not come back after the write, so it cannot be read back (`readback_refused`).

### Why it works this way

The value is read back because a register can refuse part of it. `verified: false` is not always a failure: a register that masks the value is doing its job.

The write marks the session: the `session` block of every later reply carries `altered`, which says this session has written to the machine.

### Related tools

- [`registers`](read.md#registers)
- [`write`](#write)
- [`step`](run.md#step)

<details><summary>The contract your client receives</summary>

```text
Write one register and read it back; marks the session `altered`. Needs the machine
stopped.

`name` is a register the debugger's `SR` takes (`eax`, `ax`, `ip`); a negative or too wide
`value` is refused unsent.

Reply: `register`, `regs`, `value`, `readback` (both `0x` at the register's width),
`verified`. INVALID when the registers did not come back.
```

</details>
<!-- scry-reference:end set_register -->

<!-- scry-reference:begin write -->
## `write`

Write bytes into memory at an address or a symbol, and see what the memory holds afterwards.

```text
write(ref, data_hex)
```

### Try it

On Bricks, the game this repository builds, at any stop, with its symbols loaded: `quit` is the flag the game checks to leave.

Ask:

> Set the game's quit flag, so it exits by itself.

Call:

```text
write(ref="quit", data_hex="01")
```

Reply, 5 of 8 fields:

```json
{
  "summary": "write quit: 1 byte, verified True",
  "seg_off": "08DF:000005CD",
  "bytes_written": 1,
  "readback": "01",
  "verified": true
}
```

The byte at `08DF:000005CD` now holds 1. `readback` is what the memory holds after the write, and `verified` says it is what was sent.

<details><summary>The whole reply</summary>

```json
{
  "summary": "write quit: 1 byte, verified True",
  "status": "ok",
  "ref": "quit",
  "seg_off": "08DF:000005CD",
  "bytes_written": 1,
  "readback": "01",
  "verified": true,
  "names": [
    {"field": "given.ref", "number": "0x000093bd", "kind": "symbol", "name": "quit"}
  ]
}
```

</details>

### Arguments

- `ref` (string, required): Where the bytes go: a `SEG:OFF` address or a symbol.
- `data_hex` (string, required): The bytes to write, as hex digits, two per byte: 1 to 128 bytes, what one read takes back for the readback.

### What comes back

- `readback`: The bytes at the address after the write, as hex.
- `verified`: `true` when `readback` is what was sent.
- `bytes_written`: How many bytes were sent, whether or not they landed.
- `seg_off`: The address `ref` resolved to, as segment and offset.

<details><summary>All 5 reply fields</summary>

- `bytes_written` (integer)
- `readback` (string)
- `ref` (string)
- `seg_off` (string)
- `verified` (boolean)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- `data_hex` that is not whole hex bytes, is empty, or holds more than 128 (`bad_argument`).
- A real-mode address in ROM, before anything is sent (`bad_argument`).
- Bytes that run past what an offset can reach in the cpu's mode (`bad_argument`).
- A symbol the loaded table lacks (`unknown_ref`), or one it holds twice (`ambiguous_ref`).

### Why it works this way

`verified: false` on RAM means the write went nowhere; on a hardware register it can be the register answering something else, which is its job.

ROM is refused because `SM`, the debugger's memory-write command, ends the emulator there instead of writing.

The write marks the session: the `session` block of every later reply carries `altered`, which says this session has written to the machine.

### Related tools

- [`read_memory`](read.md#read_memory)
- [`set_register`](#set_register)
- [`symbols_load`](symbols.md#symbols_load)
- [`memdump`](read.md#memdump)

<details><summary>The contract your client receives</summary>

```text
Write bytes at a symbol or `SEG:OFF` and read them back. Modifies the machine; needs it
stopped.

`data_hex` is whole hex bytes, up to 128. An absent or ambiguous symbol, and a
real-mode ROM address, are refused unsent.

Reply: `ref`, `seg_off`, `bytes_written`, `readback`, `verified`.
```

</details>
<!-- scry-reference:end write -->

<!-- scry-reference:begin debug -->
## `debug`

Send one command to the debugger and read what it printed, for what no other tool does.

```text
debug(command)
```

### Try it

On Bricks, the game this repository builds, at any stop.

Ask:

> Show me the FPU registers.

Call:

```text
debug(command="FPU")
```

Reply, 4 of 5 fields:

```json
{
  "summary": "debug 'FPU': 460 chars",
  "command": "FPU",
  "output": "status: B=0 C3-C0=0000 ES=0 SF=0 PE=0 UE=0 OE=0 ZE=0 DE=0 IE ... (261 characters)",
  "clipped": false
}
```

`output` holds what the debugger's `FPU` command printed, shown here cut short: the whole reply below has it all. No other tool reads the FPU's registers.

<details><summary>The whole reply</summary>

```json
{
  "summary": "debug 'FPU': 460 chars",
  "status": "ok",
  "command": "FPU",
  "output": "status: B=0 C3-C0=0000 ES=0 SF=0 PE=0 UE=0 OE=0 ZE=0 DE=0 IE=0 TOP=0\n st(0): empty use80=0 val=0 (0x0000000000000000)\n st(1): empty use80=0 val=0 (0x0000000000000000)\n st(2): empty use80=0 val=0 (0x0000000000000000)\n st(3): empty use80=0 va ... (460 characters)",
  "clipped": false
}
```

</details>

### Arguments

- `command` (string, required): One debugger command, as you would type it at the debugger's command line.

### What comes back

- `output`: What the debugger printed. Past 4000 characters it is cut: `clipped` is `true` and `output_path` names a file with all `output_chars` of it.
- `note`: Set when the debugger did not take the command: it does not know it, or refused it for the reason `output` shows.

<details><summary>All 5 reply fields</summary>

- `clipped` (boolean)
- `command` (string)
- `output` (string)
- `output_chars` (integer)
- `output_path` (string)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- A command that lets the program run: `RUN`, `VRT`, `RUNWATCH`, `INT`, `STEPIN`, `LOG` and its family. The message names the tool to use (`bad_argument`).
- A control character, such as a line break (`bad_argument`).
- `DOSTRACE` with a file or `OFF`, which would move or end the trace the `dos` log reads (`bad_argument`).

### Why it works this way

A command that lets the program run is refused before it is sent. It would leave the debugger without the session knowing, and `status` and `last_stop` would go on naming the stop before it. A line break would carry a second command past that check.

A command that writes to the machine, such as `SM` or `LOADSTATE`, marks the session: every later reply carries `altered` in its `session` block.

### Related tools

- [`registers`](read.md#registers)
- [`read_memory`](read.md#read_memory)
- [`memdump`](read.md#memdump)
- [`log`](machine.md#log)
- [`resume`](run.md#resume)
- [`step`](run.md#step)

<details><summary>The contract your client receives</summary>

```text
One raw `command` to the debugger; the last resort. For a value use `registers`,
`read_memory` or `memdump`; for the log `log`.

Reply: `command`, `output`, `clipped`, `note` (when the debugger did not take the command);
past 4000 characters the text goes to a file (`output_chars`, `output_path`).

Refused `bad_argument`: a command that lets the guest run (`RUN`, `VRT`, `RUNWATCH`, `INT`,
`STEPIN`, the `LOG` family) and a control character.
```

</details>
<!-- scry-reference:end debug -->
