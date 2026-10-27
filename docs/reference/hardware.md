# The Hardware tools

The ports, the interrupt controllers and the A20 gate: the state a DOS program keeps behind the
CPU rather than in memory, where a sound driver, a keyboard handler or a timer lives. Each tool
needs the machine stopped, and each writes the machine but `pic(method="read")` and
`a20(method="read")`.

<!-- scry-reference:begin port -->
## `port`

*Read or write an I/O port*

```text
port(method, port=null, bits=8, value=null)
```

One access of an I/O port, the one kind a memory write cannot make. Marks the session
`altered`, a read too: reading a port can change its device (3DAh resets the attribute
flip-flop, 60h takes the key). Needs the machine stopped and a build whose debugger has
`PORTINFO`. `port` and `value` are integers or `0x` hex, as the reply spells them.

`read`: `port`, `bits` (8, 16 or 32). Reply: `port`, `bits`, `value`.

`write`: `port`, `value`, `bits`. Reply: `port`, `bits`, `value`, `readback` (unavailable:
a port holds no value to read back).

Refused (`bad_argument`): a port past 0xFFFF, a value wider than `bits`, an argument the
method does not take. `no_channel`: a port no device answers at that size and side (the
emulator would answer all ones, or swallow the write, in silence), or no `PORTINFO`.
`not_stopped`: a running guest. `unexpected_answer`: the debugger answered another shape.

Reference: REFERENCE.md, The machine's hardware.

| argument | type | default |
|---|---|---|
| `method` | one of `"read"`, `"write"` | required |
| `port` | integer or string or null | `null` |
| `bits` | one of `8`, `16`, `32` | `8` |
| `value` | integer or string or null | `null` |

| reply field | type |
|---|---|
| `bits` | integer |
| `port` | string |
| `readback` | object |
| `value` | string |

Example, from a live run:

```json
{
  "method": "read",
  "port": 986
}
```

```json
{
  "summary": "port read: 8-bit read of 0x03DA: 0x04",
  "status": "ok",
  "port": "0x03DA",
  "bits": 8,
  "value": "0x04"
}
```
<!-- scry-reference:end port -->

**`PORTINFO` is asked before every access**, because the answer it replaces cannot be read off
the value: a port with no device reads all ones and takes a write in silence. It reports each
width apart, and an access the emulator would split byte by byte reaches a device only if every
byte does, so a 16-bit read of 3DAh is refused where an 8-bit one answers.

<!-- scry-reference:begin pic -->
## `pic`

*Read or drive the interrupt controllers*

```text
pic(method, irq=null)
```

The 8259 interrupt controllers, which decide which hardware interrupt reaches the CPU.
Needs the machine stopped.

`read`: Reply: `controllers` (each `controller`, `vector_base`, `isr`, `isrr`,
`auto_eoi`, ...), `irqs` (each `irq`, `vector`, `requested`, `masked`, `in_service`,
`cascade`).

`mask`, `unmask`, `ack` (clear its in-service bit), `raise`, `lower` (its request line):
`irq` 0 to 15. Marks the session `altered`. The timer is IRQ 0: `raise` it to run its
handler on demand. Reply: `method`, `irq`, `line` (its row after).

Refused (`bad_argument`): an `irq` out of range or on a slave this machine lacks, an
argument the method does not take. `readback_refused`: a mask or unmask the listing does
not show after. `not_stopped`: a running guest. `unexpected_answer`: a listing of another
shape.

Reference: REFERENCE.md, The machine's hardware.

| argument | type | default |
|---|---|---|
| `method` | one of `"read"`, `"mask"`, `"unmask"`, `"ack"`, `"raise"`, `"lower"` | required |
| `irq` | integer (>= 0, <= 15) or null | `null` |

| reply field | type |
|---|---|
| `controllers` | array |
| `irq` | integer |
| `irqs` | array |
| `line` | object |
| `method` | string |

Example, from a live run:

```json
{
  "method": "read"
}
```

```json
{
  "summary": "pic read: 2 controllers, masked 3, 4, 5, 6, 7, 10, 11, requested none",
  "status": "ok",
  "controllers": [
    {
      "controller": "master",
      "icw_index": 0,
      "icw_words": 0,
      "special": false,
      "auto_eoi": false,
      "rotate_eoi": false,
      "single": false,
      "request_issr": false,
      "vector_base": "0x08",
      "active_irq": 8,
      "isr": "0x00",
      "isrr": "0xFF",
      "isr_ignore": "0x00"
    },
    {
      "controller": "slave",
      "icw_index": 0,
      "icw_words": 0,
      "special": false,
      "auto_eoi": false,
      "rotate_eoi": false,
      "single": false,
      "request_issr": false,
      "vector_base": "0x70",
      "active_irq": 8,
      "isr": "0x00",
      "isrr": "0xFF",
      "isr_ignore": "0x00"
    }
  ],
  "irqs": [
    {
      "irq": 0,
      "vector": "0x08",
      "requested": false,
      "masked": false,
      "in_service": false
    },
    {
      "irq": 1,
      "vector": "0x09",
      "requested": false,
      "masked": false,
      "in_service": false
    },
    {
      "irq": 2,
      "vector": "0x0A",
      "requested": false,
      "masked": false,
      "in_service": false,
      "cascade": true
    },
    {
      "irq": 3,
      "vector": "0x0B",
      "requested": false,
      "masked": true,
      "in_service": false
    },
    {
      "irq": 4,
      "vector": "0x0C",
      "requested": false,
      "masked": true,
      "in_service": false
    },
    {
      "irq": 5,
      "vector": "0x0D",
      "requested": false,
      "masked": true,
      "in_service": false
    },
    "... 10 more"
  ]
}
```
<!-- scry-reference:end pic -->

**The debugger takes any line number and acts on none past 15**, so `irq` is held to 0..15
before anything is sent, and a slave line on a machine with one controller is refused as such.
Only a mask is a state the listing has to show after; a raised line on an unmasked input may
already have been taken by the CPU when the listing is read.

<!-- scry-reference:begin a20 -->
## `a20`

*Read or set the A20 gate*

```text
a20(method)
```

The A20 gate, which decides whether memory past 1 MB wraps to 0. Needs the machine
stopped.

`read`, `on`, `off`; the last two mark the session `altered` and read the gate back.
Reply: `enabled`.

Refused: a gate that does not read back as set (`readback_refused`); a running guest
(`not_stopped`); an answer of another shape (`unexpected_answer`).

Reference: REFERENCE.md, The machine's hardware.

| argument | type | default |
|---|---|---|
| `method` | one of `"read"`, `"on"`, `"off"` | required |

| reply field | type |
|---|---|
| `enabled` | boolean |

Example, from a live run:

```json
{
  "method": "read"
}
```

```json
{
  "summary": "a20 read: the A20 gate is on",
  "status": "ok",
  "enabled": true
}
```
<!-- scry-reference:end a20 -->

A DOS kernel loaded into the HMA turns the gate on for itself at each INT 21h, so a gate set
off is a state the guest may undo at its next DOS call.
