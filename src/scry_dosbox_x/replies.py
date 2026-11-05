"""THE REPLY MODELS, one per tool: the fields each tool's reply names beside the envelope
every reply carries, published as its `outputSchema` (each field its value or `unavailable`,
the always-present ones required) and held to every reply the battery builds
(`scry_core.reply_schema`). Named from the replies the battery and the live runs built, so a
branch none of them reached is unnamed until one does: a field a reply grows is named here in
the same change. The file tools' models are the core's (`scry_core.media_replies`)."""

from __future__ import annotations

from typing import Annotated, Any, Required

from scry_core import media_replies, tool_replies
from scry_core import sequence_account as account
from scry_core.instruction import StopInstruction
from scry_core.reply_contract import OmitEmpty, When
from scry_core.reply_schema import RunEnvelope
from typing_extensions import TypedDict


class DosboxInstruction(StopInstruction):
    """The stop's instruction, with what the decoder adds on this platform."""

    bytes_from: str
    code_bits: int
    flow: str


class DosboxEnvelope(RunEnvelope, total=False):
    """What this server's shared paths add to any reply: the stop a call met or
    applied, the refusal's context."""

    applied_on_stop: dict[str, Any]
    symbols_placed: dict[str, Any]


class WindowRefused(DosboxEnvelope, tool_replies.WindowRefusedFields, total=False):
    """What a `window_not_visible` refusal says of the window it looked for."""


class BreakpointAtReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: Required[bool]
    by: str
    entry: Annotated[str, When("once armed")]
    marked: Annotated[bool, OmitEmpty]
    ref: str
    state: Required[str]
    stored: Required[bool]
    why: Annotated[str, When("`unarmable`")]


class BreakpointInterruptReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: Required[bool]
    clipped: bool
    entry: Annotated[str, When("once armed")]
    ref: Required[str]
    output: Annotated[str, When("with `detail=True`")]
    output_chars: int
    state: Annotated[str, When("while the guest runs")]
    stored: Required[bool]


class RegpointAddReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: Required[bool]
    by: str
    condition: str
    entry: Annotated[str, When("once armed")]
    ref: Required[str]
    state: Required[str]
    stored: Required[bool]
    while_running: Required[bool]


class BuildCheckReply(DosboxEnvelope, total=False):
    binary: str
    binary_origin: Required[str]
    debugger: Required[bool]
    debugger_commands: Annotated[list[Any], OmitEmpty]
    debugger_commands_missing: Annotated[list[Any], OmitEmpty]
    heavy_debug: Required[bool]
    tools: list[Any]
    version: Required[str | dict[str, Any]]


class CallStackReply(DosboxEnvelope, total=False):
    calls: Required[list[Any]]
    code_bits: Required[int]
    ended_why: Required[str]
    heuristic: Required[bool]
    truncated: Required[bool]


class CaptureFrameReply(DosboxEnvelope, total=False):
    bytes: Required[int]
    capture_path: str
    frame: int
    path: Required[str]
    sha256: Required[str]


class CapturesReply(DosboxEnvelope, media_replies.CapturesFields, total=False):
    pass


class CloseReply(DosboxEnvelope, total=False):
    bound_s: float
    bundle: str
    captures: str
    closed: Required[bool]
    conf: str
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: str
    elapsed_s: float
    ended_by: Required[str]
    errorlog_tail: Annotated[str | dict[str, Any], When("not a clean")]
    guest_files: Annotated[list[Any], When("each file")]
    pid: Required[int | dict[str, Any]]
    state_dir: str
    stdout_tail: Annotated[str, When("not a clean")]
    output_bytes_dropped: Annotated[int, OmitEmpty]
    watched: Annotated[bool, OmitEmpty]
    # The base leaves `exit_code` optional; this reply always carries it.
    exit_code: Required[int | dict[str, Any]]  # type: ignore[misc]


class CommentListReply(DosboxEnvelope, total=False):
    comments: Required[list[Any]]
    comments_total: Required[int]
    declarations: Required[dict[str, Any]]
    truncated: Required[bool]


class DebugReply(DosboxEnvelope, total=False):
    clipped: Required[bool]
    command: str
    output: Required[str]
    output_chars: Required[int]


class DisassembleReply(DosboxEnvelope, total=False):
    code_bits: Required[int]
    code_bits_from: Required[str]
    flow: Required[list[Any]]
    flow_source: Required[str]
    length: int
    lines: Required[list[Any]]
    ref: str
    resolved: Annotated[list[Any], When("with symbols loaded")]
    seg_off: Required[str]


class DriveReply(DosboxEnvelope, total=False):
    act: dict[str, Any]
    looked: dict[str, Any]
    operations: list[Any]
    verify: Required[dict[str, Any]]


class FindReply(DosboxEnvelope, total=False):
    hits: Required[list[Any]]
    hits_total: Required[int]
    length: int
    ref: str
    seg_off: Required[str]
    span: Required[dict[str, Any]]
    truncated: Required[bool]


class InterruptVectorsReply(DosboxEnvelope, total=False):
    counts: Required[dict[str, Any]]
    coverage_note: Required[str]
    cpu_mode: Required[str | dict[str, Any]]
    sources: Required[dict[str, Any]]
    vectors: Required[list[Any]]


class LogReply(DosboxEnvelope, total=False):
    calls: Annotated[list[Any], When("the DOS channel")]
    calls_dropped: Annotated[int, When("on `dos`, past the calls held")]
    channel: str
    labels: dict[str, Any]
    lines: Annotated[list[Any], When("not on `dos`")]
    lines_total: Required[int]
    pattern: str
    truncated: Required[bool]


class LogWaitReply(DosboxEnvelope, tool_replies.LogWaitFields, total=False):
    call: Annotated[dict[str, Any], When("on `dos`")]
    calls_dropped: Annotated[int, When("on `dos`, past the calls held")]


class MachineMapReply(DosboxEnvelope, total=False):
    bios_mem: list[Any]
    callbacks: list[Any]
    control: dict[str, Any]
    counts: Required[dict[str, Any]]
    coverage_note: Required[str]
    cpu_mode: Required[str | dict[str, Any]]
    devs: list[Any]
    ems: list[Any]
    ems_pages: list[Any]
    emu_mem: dict[str, Any]
    gdt: list[Any]
    kern: list[Any]
    ldt: list[Any]
    machine: str
    mcbs: list[Any]
    paging: list[Any]
    path: Annotated[str, When("with `dest`")]
    sources: Required[dict[str, Any]]
    truncated: Required[bool]
    vga: dict[str, Any]
    xms: list[Any]


class MapFindReply(DosboxEnvelope, total=False):
    controls: Annotated[list[Any], When("when matched")]
    kind: Required[str]
    layer: Annotated[str, When("when matched")]
    matched: Required[bool]
    screen: Annotated[str, When("when matched")]
    screens_mapped: Annotated[int, When("when not")]
    screens_tried: Annotated[int, When("if the view fits")]
    screens_unjudged: Annotated[int, When("if the view fits")]
    size: Required[list[Any]]
    view_fits: Annotated[bool, When("else")]


class MemdumpReply(DosboxEnvelope, total=False):
    bytes: Required[int]
    length: int
    path: Required[str]
    ref: str
    seg_off: Required[str]


class PaletteReply(DosboxEnvelope, total=False):
    bits: Required[int]
    colors: Required[list[Any]]
    count: int
    entries: Required[int]
    first: int
    image: Required[dict[str, Any]]
    pel_mask: Required[str]
    rgb: Required[list[Any]]


class PerformReply(DosboxEnvelope, account.SequenceFields, account.SequenceRun, total=False):
    """The sequence's fields (`scry_core.sequence_account.SequenceFields`), and `operations` on
    a refusal for a step naming no operation."""
    failed: Annotated[dict[str, Any], When("`step_failed`")]
    verdict: Annotated[str, When("once the list waited")]
    frame_reached: Annotated[int | dict[str, Any], When("with `until_frame`")]
    operations: list[Any]
    until_frame: int


class PerformExportReply(DosboxEnvelope, media_replies.PerformExportFields, total=False):
    pass


class ReadMemoryReply(DosboxEnvelope, total=False):
    hex: Required[str]
    length: int
    ref: str
    rows: list[Any]
    seg_off: Required[str]


class RegistersReply(DosboxEnvelope, total=False):
    regs: Required[dict[str, Any]]
    superseded: Annotated[bool, When("with `from_last_stop`")]


class ResumeReply(DosboxEnvelope, total=False):
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    clipped: bool
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: DosboxInstruction
    pc: str
    regs: dict[str, Any]
    output: Required[str]
    output_chars: int
    stop_seq: int
    verdict: Annotated[str, When("with a bound")]
    waited_s: Annotated[float, When("with a bound")]
    watches: list[Any]


class RunForReply(DosboxEnvelope, total=False):
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    cpu_mode: str | dict[str, Any]
    cycles: Required[int | dict[str, Any]]
    e9: dict[str, Any]
    emulated_after_s: Required[float | dict[str, Any]]
    emulated_before_s: Required[float]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    frame_after: Required[int | dict[str, Any]]
    frame_before: Required[int | dict[str, Any]]
    instruction: DosboxInstruction
    pc: str | dict[str, Any]
    polls: Required[int]
    regs: dict[str, Any]
    retrace_pending: Annotated[bool, When("a retrace stop is left armed")]
    stop_seq: int
    verdict: Required[str]
    watches: list[Any]


class RecordReply(RunForReply, total=False):
    avi_frames: Required[int]
    began: Required[bool]
    bytes: Required[int]
    ended: Required[bool]
    frames: int
    kind: Required[str]
    path: Required[str | dict[str, Any]]


class AudioRecordReply(RunForReply, total=False):
    began: Required[bool]
    bytes: Annotated[int, When("a file was written")]
    channels: Annotated[int, When("a WAV's")]
    emulated_s: Annotated[float | dict[str, Any], When("a WAV's")]
    ended: Required[bool]
    files: Annotated[list[dict[str, Any]], When("the OPL writer rolled over to a new file")]
    frames: int
    kind: str
    midi_bytes: Annotated[int, When("a MIDI file's")]
    opl_ms: Annotated[int, When("a DRO's")]
    opl_pairs: Annotated[int, When("a DRO's")]
    path: Annotated[str | dict[str, Any], When("could not be turned off")]
    sample_max: Annotated[int, When("a WAV's")]
    sample_min: Annotated[int, When("a WAV's")]
    sample_rate_hz: Annotated[int, When("a WAV's")]
    samples: Annotated[int, When("a WAV's")]


class RunToReply(DosboxEnvelope, total=False):
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    control_hits: Annotated[int, When("a run to a ref or an anchor")]
    controls: Annotated[list[Any], When("a run to a ref or an anchor")]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: DosboxInstruction
    pc: str
    ref: str
    regs: dict[str, Any]
    screen: dict[str, Any]
    frames: Annotated[int, When("a screen with no anchor")]
    stop_seq: int
    target: str
    target_disarmed: Annotated[bool, When("a run to a ref or an anchor")]
    verdict: Required[str]
    watches: list[Any]


class ScreenSignatureReply(DosboxEnvelope, total=False):
    crop: list[Any]
    height: Required[int]
    kind: Required[str]
    signature: Required[str]
    vga_mode: Required[str]
    width: Required[int]


class ScreenViewReply(DosboxEnvelope, total=False):
    bbox: list[Any] | dict[str, Any]
    color: str
    crop: list[Any]
    cursor: Annotated[list[Any] | dict[str, Any], When("in text")]
    display_start: Required[str]
    entries: Annotated[int, When("indexed")]
    height: Required[int]
    histogram: Annotated[list[Any], When("mode histogram")]
    image: Annotated[dict[str, Any], When("not for mode histogram")]
    isolate_color: str
    kind: Required[str]
    mode: str
    pen: int
    pens: list[Any]
    pens_used: int
    pixels: int
    point_in_crop: list[Any]
    screen_indexed: Annotated[bool, When("in graphics")]
    text: Annotated[list[Any], When("in text")]
    unused: list[Any]
    vga_mode: Required[str]
    width: Required[int]
    x: int
    y: int


class ScreenWaitReply(DosboxEnvelope, total=False):
    already: bool
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    cpu_mode: str
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    entries: int
    frame: Annotated[int | dict[str, Any], When("unless the predicate was already true")]
    instruction: DosboxInstruction
    line: str
    palette: str
    pc: str
    point: list[Any]
    polls: int
    predicate: str
    regs: dict[str, Any]
    retrace_pending: bool
    sampled_every: int
    screen: dict[str, Any]
    stop_seq: int
    text: list[Any]
    verdict: Required[str]
    waited_s: float
    watches: list[Any]


FROM_A_STOPPED_MACHINE = When("from a stopped machine")
A_REGPOINT_STOPPED_IT = When("a registerpoint stopped it")


class ParkedPost(TypedDict, total=False):
    """What an input sent to a parked machine adds: the retraces it ran and the stop it left."""
    cause: Annotated[str, FROM_A_STOPPED_MACHINE]
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    cpu_mode: Annotated[str | dict[str, Any], FROM_A_STOPPED_MACHINE]
    e9: Annotated[dict[str, Any], FROM_A_STOPPED_MACHINE]
    frame: Annotated[int | dict[str, Any], FROM_A_STOPPED_MACHINE]
    instruction: Annotated[DosboxInstruction, FROM_A_STOPPED_MACHINE]
    pc: Annotated[str | dict[str, Any], FROM_A_STOPPED_MACHINE]
    polls: Annotated[int, FROM_A_STOPPED_MACHINE]
    regs: Annotated[dict[str, Any], FROM_A_STOPPED_MACHINE]
    stop_seq: Annotated[int, FROM_A_STOPPED_MACHINE]
    watches: Annotated[list[Any], FROM_A_STOPPED_MACHINE]


class SendKeysReply(DosboxEnvelope, ParkedPost, total=False):
    bytes: Required[int]
    delivered: bool
    frames: Required[int]
    keys: list[Any]
    modifiers: list[Any]
    posted: Required[int]
    route: Required[str]
    verify: Required[dict[str, Any]]
    polls: Annotated[int, When("stopped machine")]


class SendMouseReply(DosboxEnvelope, ParkedPost, total=False):
    action: str
    arrived: Annotated[bool, When("the program's pointer read")]
    asked: Annotated[dict[str, Any], When("else")]
    button: str
    delivered: bool
    driver_arrived: Annotated[bool, When("else")]
    identified_at_stop: int | dict[str, Any]
    motion: Annotated[bool | dict[str, Any], When("a move")]
    pointer: Required[dict[str, Any]]
    route: Required[str]
    screen: str
    target: str
    units: str
    verify: Required[dict[str, Any]]
    x: int
    y: int
    polls: Annotated[int, When("stopped machine")]


class SeriesCaptureReply(DosboxEnvelope, total=False):
    capture_path: str
    count: Required[int]
    crop: list[Any]
    distinct: Required[int]
    first: int
    frame_source: str
    frames_asked: int
    kept_after_close: Required[bool]
    last: int
    manifest: Required[str]


class SetRegisterReply(DosboxEnvelope, total=False):
    readback: Required[str]
    register: Required[str]
    regs: Required[dict[str, Any]]
    value: str
    verified: Required[bool]


class SnapshotReply(DosboxEnvelope, total=False):
    bytes: Required[int]
    path: Required[str]
    route: Required[str]
    sha256: Required[str]


class StartReply(WindowRefused, account.SequenceFields, total=False):
    failed_at: int | dict[str, Any]
    held: int
    ran: list[Any]
    steps_completed: int
    argv: list[Any]
    background: bool
    binary: str
    binary_origin: str
    bound_s: float
    bundle: str
    captures: str
    conf: str
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: str
    debugger_commands: Annotated[list[Any], OmitEmpty]
    declarations: Annotated[dict[str, Any], When("under `start`")]
    dos_calls: str
    elapsed_s: float
    guest_files: list[Any]
    input_port: int | dict[str, Any]
    log_categories: dict[str, Any]
    operations: list[Any]
    pid: Annotated[int, When("under `start`")]
    presence: bool | dict[str, Any]
    ready_after_s: float
    rearm_refused: str
    shared: Annotated[bool, OmitEmpty]
    start: Annotated[dict[str, Any], When("with `plan`")]
    state_dir: str
    stub: Annotated[str, When("under `start`")]
    output_bytes_dropped: Annotated[int, OmitEmpty]
    symbols: dict[str, Any]
    version: str | dict[str, Any]
    watched: Annotated[bool, OmitEmpty]
    window: Annotated[dict[str, Any], When("with `shared`")]


class StateListReply(DosboxEnvelope, total=False):
    state_dir: Required[str]
    states: Required[list[Any]]
    working_slot: Required[dict[str, Any]]


class WindowReply(WindowRefused, tool_replies.WindowSizeField, total=False):
    window: Required[dict[str, Any]]


class StatusReply(DosboxEnvelope, total=False):
    bound_s: Annotated[float, When("with a session")]
    bundle: str
    captures: Annotated[str, When("with a session")]
    conf: Annotated[str, When("with a session")]
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: Annotated[str, When("with a session")]
    cpu_mode: Annotated[str | dict[str, Any], When("with a session")]
    declarations: Annotated[dict[str, Any], When("with a session")]
    elapsed_s: Annotated[float, When("with a session")]
    pc: Annotated[str | dict[str, Any], When("with a session")]
    pending: Required[dict[str, Any]]
    pid: Annotated[int, When("with a session")]
    presence: Annotated[bool | dict[str, Any], When("with a session")]
    state_dir: Annotated[str, When("with a session")]
    symbols_held: Annotated[dict[str, Any], When("a `start` table waits for its program")]
    output_bytes_dropped: Annotated[int, OmitEmpty]
    watched: Annotated[bool, OmitEmpty]
    # Every status says where the guest was last seen. A TypedDict cannot make a key required
    # that its base leaves optional, and the base serves tools that do not carry it.
    last_stop: Required[dict[str, Any]]  # type: ignore[misc]


class StepReply(DosboxEnvelope, total=False):
    after: Required[str]
    asked: Required[int]
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    before: Required[str]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: DosboxInstruction
    instructions_completed: Required[int]
    mode: str
    moved: Required[bool]
    pc: str
    regs: dict[str, Any]
    stalled: Required[int]
    stop_seq: int
    watches: list[Any]


class StopReply(DosboxEnvelope, total=False):
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: DosboxInstruction
    interrupted: Required[bool]
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    via: str
    watches: list[Any]


class SymbolsFindReply(DosboxEnvelope, total=False):
    addr: str
    delta: Annotated[int, When("by address")]
    idle: bool
    kind: str
    name: str
    offset: int
    query: Required[str]
    section: int
    symbols: Annotated[list[Any], When("by name")]
    symbols_total: Annotated[int, When("by name")]
    truncated: Annotated[bool, When("by name")]


class SymbolsLoadReply(DosboxEnvelope, total=False):
    base: int
    base_from: str
    bytes: int
    declarations: Required[dict[str, Any]]
    descriptor: int
    disambiguated: int
    excluded_pattern: int
    excluded_sections: int
    excluded_unplaceable: int
    kept: Required[int]
    limit: int
    loaded: Required[int]
    overlay_idle: int
    parsed: Required[int]
    pending: Required[bool]
    #: The table against the executable beside it (`against`, `agree`), or unavailable why.
    checked: Required[dict[str, Any]]
    renamed: Required[int]
    symbols_typed: int
    table_mode: Required[str]
    table_total: Required[int]
    truncated_names: int
    unencodable: list[Any]
    unencodable_total: int
    unreadable: int


class TraceReply(DosboxEnvelope, total=False):
    cause: str
    regpoint_hit: Annotated[dict[str, Any], A_REGPOINT_STOPPED_IT]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: DosboxInstruction
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    trace: Required[dict[str, Any]]
    verdict: Required[str]
    watches: list[Any]


class WatchAddReply(DosboxEnvelope, total=False):
    addr: Annotated[str, When("a count or capture's", "a freeze's")]
    already_stored: Annotated[bool, OmitEmpty]
    armed: Required[bool]
    by: str
    caveat: Annotated[str, When("protected mode")]
    command: str
    entries: Annotated[list[Any], When("a freeze's")]
    entry: Annotated[str, When("once armed")]
    fmt: str
    frozen_hex: Annotated[str, When("a freeze's")]
    length: int
    mode: str
    pointer: Annotated[dict[str, Any], When("a pointer")]
    ref: str
    state: Required[str]
    stored: Required[bool]
    tally_id: Annotated[str, When("a count or capture's")]
    trigger: str
    trigger_addr: Annotated[str, When("a count or capture's")]
    trigger_type: str
    why: str


class PortReply(DosboxEnvelope, total=False):
    bits: int
    port: str
    readback: Annotated[dict[str, Any], When("`write`")]
    value: str


class PicReply(DosboxEnvelope, total=False):
    controllers: Annotated[list[Any], When("`read`")]
    irq: int
    irqs: Annotated[list[Any], When("`read`")]
    line: Annotated[dict[str, Any],
                    When("`mask`", "`unmask`", "`acknowledge`", "`raise`", "`lower`")]
    method: str


class A20Reply(DosboxEnvelope, total=False):
    enabled: Required[bool]


class GuestFileReply(DosboxEnvelope, total=False):
    before: Required[dict[str, Any]]
    bytes: Required[int]
    path: str
    same_bytes: Annotated[bool, OmitEmpty]
    sha256: Required[str]
    state: Required[str]


class WriteReply(DosboxEnvelope, total=False):
    bytes_written: Required[int]
    readback: Required[str]
    ref: str
    seg_off: Required[str]
    verified: Required[bool]
    written: int


class CommentWriteReply(DosboxEnvelope, tool_replies.CommentWriteFields, total=False):
    pass


class DeclarationClearReply(DosboxEnvelope, total=False):
    declarations_cleared: Required[int]
    disarmed: Required[list[Any]]
    pending_disarm: Annotated[list[Any], OmitEmpty]


class DeclarationListReply(DosboxEnvelope, total=False):
    breakpoints: Annotated[list[Any], When("each kind asked")]
    debugger_read: Required[bool]
    foreign: Annotated[dict[str, Any], OmitEmpty]
    regpoints: Annotated[list[Any], When("each kind asked")]
    watches: Annotated[list[Any], When("each kind asked")]


class MapWriteReply(DosboxEnvelope, tool_replies.MapWriteFields, total=False):
    pass


class ScanReply(DosboxEnvelope, total=False):
    addr: Annotated[str, When("`start`")]
    cell_bytes: int
    cleared: Annotated[bool, When("`clear`")]
    closed: Annotated[bool, When("`filter`")]
    hits: Annotated[list[Any], When("`filter`")]
    hits_total: Annotated[int, When("`start`", "`filter`")]
    iterations: Annotated[int | dict[str, Any], When("`filter`")]
    length: int
    operator: str
    ref: str
    rows: int
    seg_off: Annotated[str, When("`start`")]
    survivors: int
    truncated: Annotated[bool, When("`filter`")]
    value: str | dict[str, Any]


class StateWriteReply(DosboxEnvelope, total=False):
    bytes: Annotated[int, When("`save`")]
    machine: Required[str]
    mark: Annotated[dict[str, Any], When("`load`")]
    memory_mb: Required[int]
    name: str
    path: Required[str]
    paused: Required[bool]
    program: Required[str]
    saved_at: Required[str]
    taps: Annotated[dict[str, Any], When("a declared tap was tapped again or could not be")]
    version: Required[str]


#: Each tool's reply model, by the tool's name.
MODELS: dict[str, type] = {
    "comment_write": CommentWriteReply,
    "port": PortReply,
    "pic": PicReply,
    "a20": A20Reply,
    "guest_file": GuestFileReply,
    "declaration_clear": DeclarationClearReply,
    "declaration_list": DeclarationListReply,
    "screen_map_write": MapWriteReply,
    "scan": ScanReply,
    "state_write": StateWriteReply,
    "breakpoint_at": BreakpointAtReply,
    "breakpoint_interrupt": BreakpointInterruptReply,
    "regpoint_add": RegpointAddReply,
    "build_check": BuildCheckReply,
    "call_stack": CallStackReply,
    "capture_frame": CaptureFrameReply,
    "captures": CapturesReply,
    "close": CloseReply,
    "window": WindowReply,
    "comment_list": CommentListReply,
    "debug": DebugReply,
    "disassemble": DisassembleReply,
    "drive": DriveReply,
    "find": FindReply,
    "interrupt_vectors": InterruptVectorsReply,
    "log": LogReply,
    "log_wait": LogWaitReply,
    "machine_map": MachineMapReply,
    "screen_map_find": MapFindReply,
    "memdump": MemdumpReply,
    "palette": PaletteReply,
    "perform": PerformReply,
    "perform_export": PerformExportReply,
    "read_memory": ReadMemoryReply,
    "registers": RegistersReply,
    "resume": ResumeReply,
    "run_for": RunForReply,
    "record": RecordReply,
    "audio_record": AudioRecordReply,
    "run_to": RunToReply,
    "screen_signature": ScreenSignatureReply,
    "screen_view": ScreenViewReply,
    "screen_wait": ScreenWaitReply,
    "send_keys": SendKeysReply,
    "send_mouse": SendMouseReply,
    "series_capture": SeriesCaptureReply,
    "set_register": SetRegisterReply,
    "snapshot": SnapshotReply,
    "start": StartReply,
    "state_list": StateListReply,
    "status": StatusReply,
    "step": StepReply,
    "stop": StopReply,
    "symbols_find": SymbolsFindReply,
    "symbols_load": SymbolsLoadReply,
    "trace": TraceReply,
    "watch_add": WatchAddReply,
    "write": WriteReply,
    "image_compare": media_replies.MODELS["image_compare"],
    "audio_compare": media_replies.MODELS["audio_compare"],
}
