# The Write tools

<!-- scry-reference:begin set_register -->
## `set_register`

*Force a register*

```text
set_register(name, value)
```

Write one register, READ IT BACK off the pane, and mark the session `altered` for
good: every later reading is of a forced state, and the flag on every reply is how a reader
three questions later knows. `name` is a register the debugger's `SR` takes (`eax`, `ax`,
`ip`, ...); `value` is an integer or a `0x` hex string within the register's width, refused
before anything is sent when negative or wider. Needs the machine stopped.

Reply: `register` (the name as `SR` takes it), `regs` (the pane after the write), `value`
(what was sent) and `readback` (the register asked for as the pane shows it now), both `0x`
at the register's own width (eight digits for a 32-bit name, four for a segment register,
and four for a 16-bit name, read as the low half of its 32-bit register, `ax` in `EAX`),
`verified` (readback equals what was sent; false is not always a failure: a register the
debugger masks is doing its job). INVALID when no pane, or a pane without that register,
came back to read.

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

<!-- scry-reference:begin write -->
## `write`

*Write memory*

```text
write(ref, data_hex)
```

Write bytes at a SYMBOL or a `SEG:OFF` and READ THEM BACK. MODIFIES the machine:
every later reply says so in `altered`.

`data_hex` is whole hex bytes, two digits each, up to 128 (the data view's reach for the
readback; a region is not a write). The bytes go through the debugger's `SM` and the
range is read back off the data view. Needs the machine stopped; an absent or ambiguous
symbol is refused.

Reply: `ref`, `seg_off`, `bytes_written` (sent), `readback` (hex read back from
the same range), `verified` (readback equals what was sent). `verified: false` is not
always a failure: a memory-mapped register answers what it answers; for RAM the read-back
differs from what was sent (the write did not land, or the view did not repaint). A
real-mode address in the ROM range is REFUSED with nothing sent: measured on this build,
`SM` into ROM ends the emulator instead of writing.

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
