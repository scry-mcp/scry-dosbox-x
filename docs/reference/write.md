# The Write tools

<!-- scry-reference:begin set_register -->
## `set_register`

*Force a register*

```text
set_register(name, value)
```

Write one register and read it back off the pane; marks the session `altered`. Needs the
machine stopped.

`name` is a register the debugger's `SR` takes (`eax`, `ax`, `ip`); a negative or too wide
`value` is refused unsent.

Reply: `register`, `regs`, `value`, `readback` (both `0x` at the register's width),
`verified`. INVALID when no pane came back.

| argument | type | default |
|---|---|---|
| `name` | string | required |
| `value` | integer or string | required |

| reply field | type |
|---|---|
| `readback` | string |
| `register` | string |
| `regs` | object |
| `value` | string |
| `verified` | boolean |

Example, from a live run:

```json
{
  "name": "eax",
  "value": 0
}
```

```json
{
  "summary": "set_register eax = 0, verified True",
  "status": "ok",
  "value": "0x00000000",
  "register": "eax",
  "regs": {
    "EAX": "0x00000000",
    "ESI": "0x00000100",
    "DS": "0x0814",
    "ES": "0x0814",
    "FS": "0x0000",
    "GS": "0x0000",
    "SS": "0x0814",
    "EBX": "0x00000124",
    "EDI": "0x0000fffe",
    "CS": "0xf000",
    "EIP": "0x0000fea5",
    "ECX": "0x0000a97e",
    "EBP": "0x0000091c",
    "EDX": "0x00000814",
    "ESP": "0x0000fff8"
  },
  "readback": "0x00000000",
  "verified": true
}
```
<!-- scry-reference:end set_register -->

**Why the session stays `altered`.** Every later reading is of a forced state, and the flag on each reply is how a reader several questions later knows.

**Why a 16-bit name reads four digits.** It is read as the low half of its 32-bit register (`ax` in `EAX`).

**Why `verified: false` is not always a failure.** A register the debugger masks is doing its job.

<!-- scry-reference:begin write -->
## `write`

*Write memory*

```text
write(ref, data_hex)
```

Write bytes at a symbol or `SEG:OFF` and read them back. Modifies the machine; needs it
stopped.

`data_hex` is whole hex bytes, up to 128. An absent or ambiguous symbol, and a
real-mode ROM address, are refused unsent.

Reply: `ref`, `seg_off`, `bytes_written`, `readback`, `verified`.

| argument | type | default |
|---|---|---|
| `ref` | string | required |
| `data_hex` | string | required |

| reply field | type |
|---|---|
| `bytes_written` | integer |
| `readback` | string |
| `ref` | string |
| `seg_off` | string |
| `verified` | boolean |
| `written` | integer |

Example, from a live run:

```json
{
  "ref": "8000:0100",
  "data_hex": "A55A"
}
```

```json
{
  "summary": "write 8000:0100: 2 bytes, verified True",
  "status": "ok",
  "ref": "8000:0100",
  "seg_off": "8000:00000100",
  "bytes_written": 2,
  "readback": "a55a",
  "verified": true
}
```
<!-- scry-reference:end write -->

**Why ROM is refused.** The debugger's `SM` into ROM ends the emulator instead of writing.

**Why `verified: false` is not always a failure.** A memory-mapped register answers what it answers; for RAM the write did not land or the view did not repaint.

**Why the width is bounded.** `the read ceiling` is the data view's reach for the readback; a region is not a write.
