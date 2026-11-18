# The Hardware tools

The ports, the interrupt controllers and the A20 line hold the state a DOS program keeps behind the cpu instead of in memory. A sound driver, a keyboard handler or a timer lives there. Each tool needs the machine stopped.

Each call writes to the machine, except `pic(method="read")` and `a20(method="read")`. A write marks the session: the `session` block of every later reply carries `altered`, so a later measurement is known to be of a changed program.

<!-- scry-reference:begin port -->
## `port`

Read or write one I/O port, and be told when no device answers there.

```text
port(method, port=null, bits=8, value=null)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen.

Ask:

> Read VGA port 3C8h, the index of the next palette entry to be written.

Call:

```text
port(method="read", port="0x3C8")
```

Reply, 4 of 5 fields:

```json
{
  "summary": "port read: 8-bit read of 0x03C8: 0x28",
  "port": "0x03C8",
  "bits": 8,
  "value": "0x28"
}
```

Port `0x3C8` reads `0x28`, an 8-bit value: the next palette entry to be written is 40.

<details><summary>The whole reply</summary>

```json
{
  "summary": "port read: 8-bit read of 0x03C8: 0x28",
  "status": "ok",
  "port": "0x03C8",
  "bits": 8,
  "value": "0x28"
}
```

</details>

### The two methods

| method | what it does |
|---|---|
| `read` | Reads the port and returns its `value`. Takes `port` and `bits`. |
| `write` | Sends `value` to the port. Takes `port`, `value` and `bits`. |

### Arguments

- `method` (one of `"read"`, `"write"`, required): `read` or `write`, as above.
- `port` (integer or string, optional): The port: an integer or `0x` hex, 0 to `0xFFFF`.
- `bits` (one of `8`, `16`, `32`, default `8`): The size of the access: 8, 16 or 32 bits. Left out, 8.
- `value` (integer or string, optional): What a `write` sends: an integer or `0x` hex, no wider than `bits`.

### What comes back

- `value`: What the read returned, or what the write sent, as `0x` text at the width of `bits`.
- `port`: The port, as four hex digits.
- `readback`: On a `write`: always unavailable, `available: false` with its `why`, because a port holds no value to read back.

<details><summary>All 4 reply fields</summary>

- `bits` (integer)
- `port` (string)
- `readback` (object)
- `value` (string)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- A port past `0xFFFF`, a value wider than `bits`, or an argument the method does not take (`bad_argument`).
- A port no device answers at that size and direction (`no_channel`).
- A DOSBox-X whose debugger has no `PORTINFO` command (`no_channel`).
- A debugger answer in a shape the tool does not know (`unexpected_answer`).

### Why it works this way

The debugger's `PORTINFO` is asked before every access, because a port with no device reads all ones and takes a write in silence: nothing in the value says so.

It reports each width apart, and an access the emulator splits byte by byte reaches a device only if every byte does. So a 16-bit read of `0x3DA` is refused where an 8-bit one answers.

A read marks the session `altered` too: reading a port is a bus cycle the device sees.

### Related tools

- [`pic`](#pic)
- [`a20`](#a20)
- [`read_memory`](read.md#read_memory)
- [`build_check`](session.md#build_check)

<details><summary>The contract your client receives</summary>

```text
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
```

</details>
<!-- scry-reference:end port -->

<!-- scry-reference:begin pic -->
## `pic`

Read the 8259 interrupt controllers, or mask, unmask, acknowledge, raise or lower one interrupt line.

```text
pic(method, irq=null)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen.

Ask:

> Which interrupt lines are masked right now?

Call:

```text
pic(method="read")
```

Reply, 2 of 4 fields:

```json
{
  "summary": "pic read: 2 controllers, masked 3, 5, 6, 7, 10, 11, requested none",
  "status": "ok"
}
```

Two controllers, with lines 3, 5, 6, 7, 10 and 11 masked and none requested. The whole reply below has a row for each controller and each line.

<details><summary>The whole reply</summary>

```json
{
  "summary": "pic read: 2 controllers, masked 3, 5, 6, 7, 10, 11, requested none",
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
      "active_irq": {"available": false, "why": "no line is in service"},
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
      "active_irq": {"available": false, "why": "no line is in service"},
      "isr": "0x00",
      "isrr": "0xFF",
      "isr_ignore": "0x00"
    }
  ],
  "irqs": [
    {"irq": 0, "vector": "0x08", "requested": false, "masked": false, "in_service": false},
    {"irq": 1, "vector": "0x09", "requested": false, "masked": false, "in_service": false},
    {
      "irq": 2,
      "vector": "0x0A",
      "requested": false,
      "masked": false,
      "in_service": false,
      "cascade": true
    },
    {"irq": 3, "vector": "0x0B", "requested": false, "masked": true, "in_service": false},
    {"irq": 4, "vector": "0x0C", "requested": false, "masked": false, "in_service": false},
    {"irq": 5, "vector": "0x0D", "requested": false, "masked": true, "in_service": false},
    "... 10 more"
  ]
}
```

</details>

### The six methods

| method | what it does |
|---|---|
| `read` | Lists the controllers and every line. It writes nothing. |
| `mask` | Masks line `irq`. |
| `unmask` | Unmasks line `irq`. |
| `acknowledge` | Clears the in-service bit of line `irq`. |
| `raise` | Raises the request of line `irq`. |
| `lower` | Lowers the request of line `irq`. |

### Arguments

- `method` (one of `"read"`, `"mask"`, `"unmask"`, `"acknowledge"`, `"raise"`, `"lower"`, required): `read`, or one of the five actions above.
- `irq` (integer (>= 0, <= 15), optional): The interrupt line an action works on, 0 to 15; 8 to 15 are on the slave controller. `read` takes none.

### What comes back

- `controllers`: On `read`: one row per `controller`, `master` then `slave`, with its `vector_base`, its `active_irq` and the registers `isr` and `isrr`.
- `irqs`: On `read`: one row per line, with `irq`, `vector`, and whether it is `requested`, `masked` and `in_service`. `cascade` marks the line that links the two controllers.
- `line`: After an action: the row of that line as it reads now, with the keys of an `irqs` row.
- `method`: After an action: the action taken, with `irq` the line.

<details><summary>All 5 reply fields</summary>

- `controllers` (array)
- `irq` (integer)
- `irqs` (array)
- `line` (object)
- `method` (string)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- An `irq` outside 0 to 15, or on a slave controller this machine does not have (`bad_argument`).
- An argument the method does not take (`bad_argument`).
- A DOSBox-X whose debugger has no `PIC` command (`no_channel`).
- A `mask` or `unmask` the listing does not show afterwards (`readback_refused`).
- A listing in a shape the tool does not know (`unexpected_answer`).

### Why it works this way

The debugger takes any line number and acts on none past 15, so `irq` is checked before anything is sent.

Only a mask is read back. A raised line on an unmasked input may already have been taken by the cpu when the listing is read, so `line` says what the line holds afterwards.

A controller's `active_irq` is its own line in service, 0 to 7. With none it is unavailable: the emulator writes 8 there, which would read as a ninth line.

<details><summary>More on why</summary>

Every action marks the session `altered`, which says this session has written to the machine. A `read` does not.

The `controllers` rows also carry `icw_index`, `icw_words`, `special`, `auto_eoi`, `rotate_eoi`, `single`, `request_issr` and `isr_ignore`: the rest of the 8259's state, named as the debugger's `PIC` listing prints it.

</details>

### Related tools

- [`interrupt_vectors`](machine.md#interrupt_vectors)
- [`breakpoint_interrupt`](breakpoints.md#breakpoint_interrupt)
- [`port`](#port)
- [`build_check`](session.md#build_check)

<details><summary>The contract your client receives</summary>

```text
The 8259 interrupt controllers, which decide which hardware interrupt reaches the CPU.
Needs the machine stopped.

`read`: Reply: `controllers` (each `controller`, `vector_base`, `active_irq` (unavailable
with none in service), `isr`, `isrr`, `auto_eoi`, ...), `irqs` (each `irq`, `vector`,
`requested`, `masked`, `in_service`, `cascade`).

`mask`, `unmask`, `acknowledge` (clear its in-service bit), `raise`, `lower` (its request line):
`irq` 0 to 15. Marks the session `altered`. The timer is IRQ 0: `raise` it to run its
handler on demand. Reply: `method`, `irq`, `line` (its row after).

Refused (`bad_argument`): an `irq` out of range or on a slave this machine lacks, an
argument the method does not take. `no_channel`: a build with no `PIC` command.
`readback_refused`: a mask or unmask the listing does not show after. `not_stopped`: a
running guest. `unexpected_answer`: a listing of another shape.

Reference: REFERENCE.md, The machine's hardware.
```

</details>
<!-- scry-reference:end pic -->

<!-- scry-reference:begin a20 -->
## `a20`

Read or set the A20 line, which decides whether addresses past 1 MB wrap around to 0.

```text
a20(method)
```

### Try it

On Bricks, the game this repository builds, stopped on its play screen.

Ask:

> Is the A20 line on?

Call:

```text
a20(method="read")
```

Reply, 2 of 3 fields:

```json
{
  "summary": "a20 read: the A20 gate is on",
  "enabled": true
}
```

`enabled` is true: the A20 line is on, so addresses past 1 MB do not wrap to 0.

<details><summary>The whole reply</summary>

```json
{
  "summary": "a20 read: the A20 gate is on",
  "status": "ok",
  "enabled": true
}
```

</details>

### The three methods

| method | what it does |
|---|---|
| `read` | Says whether the line is on. It writes nothing. |
| `on` | Turns the line on and reads it back. That is a write: the session is marked `altered`. |
| `off` | Turns the line off, the same way. |

### Arguments

- `method` (one of `"read"`, `"on"`, `"off"`, required): `read`, `on` or `off`, as above.

### What comes back

- `enabled`: `true` when the A20 line is on.

<details><summary>All 1 reply fields</summary>

- `enabled` (boolean)

</details>

### What it refuses

- A machine that is running (`not_stopped`).
- A DOSBox-X whose debugger has no `A20` command (`no_channel`).
- A line that does not read back as set (`readback_refused`).
- An answer in a shape the tool does not know (`unexpected_answer`).

### Why it works this way

A DOS kernel loaded into the high memory area turns the line on for itself at each INT 21h. So a line set off may be undone at the program's next DOS call.

### Related tools

- [`read_memory`](read.md#read_memory)
- [`machine_map`](machine.md#machine_map)
- [`port`](#port)
- [`build_check`](session.md#build_check)

<details><summary>The contract your client receives</summary>

```text
The A20 gate, which decides whether memory past 1 MB wraps to 0. Needs the machine
stopped.

`method`: one of `read`, `on`, `off`. The last two mark the session `altered` and read the
gate back.
Reply: `enabled`.

Refused: a build with no `A20` command (`no_channel`); a gate that does not read back as set
(`readback_refused`); a running guest
(`not_stopped`); an answer of another shape (`unexpected_answer`).

Reference: REFERENCE.md, The machine's hardware.
```

</details>
<!-- scry-reference:end a20 -->
