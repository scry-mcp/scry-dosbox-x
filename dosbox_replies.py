"""THE REPLY MODELS, one per tool: the fields each tool's reply names beside the envelope
every reply carries, published as its `outputSchema` (names only) and held to every reply
the battery builds (`scry_core.reply_schema`). Named from the replies the battery and the
live runs built, so a branch none of them reached is unnamed until one does: a field a
reply grows is named here in the same change. The file tools' models are the core's
(`scry_core.media_replies`)."""

from __future__ import annotations

from typing import Annotated, Any

from scry_core import media_replies
from scry_core import sequence_account as account
from scry_core.reply_contract import OmitEmpty
from scry_core.reply_schema import ReplyEnvelope
from typing_extensions import TypedDict


class DosboxEnvelope(ReplyEnvelope, total=False):
    """What this server's shared paths add to any reply: the stop a call met or
    applied, the refusal's context."""

    answers_while_running: list[Any]
    applied_on_stop: dict[str, Any]
    exit_code: int | dict[str, Any]
    last_stop: dict[str, Any]
    stopped_on_its_own: dict[str, Any]


class BreakpointAtReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: bool
    by: str
    entry: str
    marked: Annotated[bool, OmitEmpty]
    note: str
    ref: str
    state: str
    stored: bool
    why: str


class BreakpointInterruptReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: bool
    clipped: bool
    entry: str
    note: str
    ref: str
    output: str
    output_chars: int
    state: str
    stored: bool


class RegpointAddReply(DosboxEnvelope, total=False):
    already_stored: Annotated[bool, OmitEmpty]
    armed: bool
    by: str
    condition: str
    entry: str
    note: str
    ref: str
    state: str
    stored: bool
    while_running: bool


class BuildCheckReply(DosboxEnvelope, total=False):
    binary: str
    binary_origin: str
    debugger: bool
    debugger_commands: Annotated[list[Any], OmitEmpty]
    heavy_debug: bool
    tools: list[Any]
    version: str | dict[str, Any]


class CallStackReply(DosboxEnvelope, total=False):
    calls: list[Any]
    code_bits: int
    ended_why: str
    heuristic: bool
    truncated: bool


class CaptureFrameReply(DosboxEnvelope, total=False):
    bytes: int
    capture_path: str
    frame: int
    path: str
    sha256: str


class CapturesReply(DosboxEnvelope, total=False):
    captures: list[Any]


class CloseReply(DosboxEnvelope, total=False):
    bound_s: float
    captures: str
    closed: bool
    conf: str
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: str
    elapsed_s: float
    ended_by: str
    errorlog_tail: str | dict[str, Any]
    guest_files: list[Any]
    note: str
    pid: int
    state_dir: str
    stdout_tail: str
    output_bytes_dropped: Annotated[int, OmitEmpty]
    watched: Annotated[bool, OmitEmpty]


class CommentListReply(DosboxEnvelope, total=False):
    comments: list[Any]
    comments_total: int
    declarations: dict[str, Any]
    truncated: bool


class DebugReply(DosboxEnvelope, total=False):
    clipped: bool
    command: str
    note: str
    output: str
    output_chars: int


class DisassembleReply(DosboxEnvelope, total=False):
    code_bits: int
    code_bits_from: str
    flow: list[Any]
    flow_source: str
    length: int
    lines: list[Any]
    ref: str
    resolved: list[Any]
    seg_off: str


class DriveReply(DosboxEnvelope, total=False):
    act: dict[str, Any]
    looked: dict[str, Any]
    operations: list[Any]
    verify: dict[str, Any]


class FindReply(DosboxEnvelope, total=False):
    hits: list[Any]
    hits_total: int
    length: int
    ref: str
    seg_off: str
    span: dict[str, Any]
    truncated: bool


class InterruptVectorsReply(DosboxEnvelope, total=False):
    counts: dict[str, Any]
    coverage_note: str
    cpu_mode: str | dict[str, Any]
    sources: dict[str, Any]
    vectors: list[Any]


class LogReply(DosboxEnvelope, total=False):
    calls: list[Any]
    channel: str
    labels: dict[str, Any]
    lines: list[Any]
    lines_total: int
    note: str
    pattern: str
    truncated: bool


class LogWaitReply(DosboxEnvelope, total=False):
    already: bool
    arrived_during: int
    call: dict[str, Any]
    channel: str
    line: str
    lines_before: int
    lines_examined: int
    lines_total: int
    note: str
    pattern: str
    verdict: str
    waited_s: float


class MachineMapReply(DosboxEnvelope, total=False):
    bios_mem: list[Any]
    callbacks: list[Any]
    control: dict[str, Any]
    counts: dict[str, Any]
    coverage_note: str
    cpu_mode: str | dict[str, Any]
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
    path: str
    sources: dict[str, Any]
    truncated: bool
    vga: dict[str, Any]
    xms: list[Any]


class MapFindReply(DosboxEnvelope, total=False):
    controls: list[Any]
    kind: str
    layer: str
    matched: bool
    screen: str
    screens_mapped: int
    screens_tried: int
    screens_unjudged: int
    size: list[Any]


class MemdumpReply(DosboxEnvelope, total=False):
    bytes: int
    length: int
    path: str
    ref: str
    seg_off: str


class PaletteReply(DosboxEnvelope, total=False):
    bits: int
    colors: list[Any]
    count: int
    entries: int
    first: int
    image: dict[str, Any]
    pel_mask: str
    rgb: list[Any]


class PerformReply(DosboxEnvelope, account.SequenceFields, total=False):
    """The sequence's fields (`scry_core.sequence_account.SequenceFields`), and `operations` on
    a refusal for a step naming no operation."""
    frame_reached: int | dict[str, Any]
    operations: list[Any]
    until_frame: int


class PerformExportReply(DosboxEnvelope, total=False):
    checks: int
    cut: dict[str, Any]
    dropped: list[Any]
    dropped_total: int
    path: str
    replay: str
    steps: int


class ReadMemoryReply(DosboxEnvelope, total=False):
    hex: str
    length: int
    ref: str
    rows: list[Any]
    seg_off: str


class RegistersReply(DosboxEnvelope, total=False):
    regs: dict[str, Any]
    superseded: bool


class ResumeReply(DosboxEnvelope, total=False):
    cause: str
    clipped: bool
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str
    regs: dict[str, Any]
    output: str
    output_chars: int
    stop_seq: int
    verdict: str
    waited_s: float
    watches: list[Any]


class RunForReply(DosboxEnvelope, total=False):
    cause: str
    cpu_mode: str | dict[str, Any]
    cycles: dict[str, Any]
    e9: dict[str, Any]
    emulated_after_s: float | dict[str, Any]
    emulated_before_s: float
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    frame_after: int | dict[str, Any]
    frame_before: int | dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str | dict[str, Any]
    polls: int
    regs: dict[str, Any]
    retrace_pending: bool
    stop_seq: int
    verdict: str
    watches: list[Any]


class RecordReply(RunForReply, total=False):
    avi_frames: int
    began: bool
    bytes: int
    ended: bool
    frames: int
    kind: str
    path: str | dict[str, Any]


class AudioRecordReply(RunForReply, total=False):
    began: bool
    bytes: int
    channels: int
    emulated_s: float | dict[str, Any]
    ended: bool
    frames: int
    kind: str
    midi_bytes: int
    opl_ms: int
    opl_pairs: int
    path: str | dict[str, Any]
    sample_max: int
    sample_min: int
    sample_rate_hz: int
    samples: int


class RunToReply(DosboxEnvelope, total=False):
    cause: str
    control_hits: int
    controls: list[Any]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str
    ref: str
    regs: dict[str, Any]
    stop_seq: int
    target: str
    target_disarmed: bool
    verdict: str
    watches: list[Any]


class ScreenSignatureReply(DosboxEnvelope, total=False):
    crop: list[Any]
    height: int
    kind: str
    signature: str
    vga_mode: str
    width: int


class ScreenViewReply(DosboxEnvelope, total=False):
    crop: list[Any]
    cursor: list[Any] | dict[str, Any]
    display_start: str
    height: int
    image: dict[str, Any]
    kind: str
    text: list[Any]
    vga_mode: str
    width: int


class ScreenWaitReply(DosboxEnvelope, total=False):
    already: bool
    cause: str
    cpu_mode: str
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    line: str
    note: str
    pc: str
    point: list[Any]
    polls: int
    regs: dict[str, Any]
    retrace_pending: bool
    stop_seq: int
    text: list[Any]
    verdict: str
    waited_s: float
    watches: list[Any]


class ParkedPost(TypedDict, total=False):
    """What an input sent to a parked machine adds: the retraces it ran and the stop it left."""
    cause: str
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    pc: str | dict[str, Any]
    polls: int
    regs: dict[str, Any]
    stop_seq: int
    watches: list[Any]


class SendKeysReply(DosboxEnvelope, ParkedPost, total=False):
    bytes: int
    delivered: bool
    frames: int
    keys: list[Any]
    modifiers: list[Any]
    posted: int
    route: str
    verify: dict[str, Any]


class SendMouseReply(DosboxEnvelope, ParkedPost, total=False):
    action: str
    arrived: bool
    asked: dict[str, Any]
    button: str
    delivered: bool
    identified_at_stop: int | dict[str, Any]
    motion: bool | dict[str, Any]
    pointer: dict[str, Any]
    route: str
    screen: str
    target: str
    units: str
    verify: dict[str, Any]
    x: int
    y: int


class SeriesCaptureReply(DosboxEnvelope, total=False):
    capture_path: str
    count: int
    crop: list[Any]
    distinct: int
    first: int
    frame_source: str
    frames_asked: int
    kept_after_close: bool
    last: int
    manifest: str


class SetRegisterReply(DosboxEnvelope, total=False):
    readback: str
    register: str
    regs: dict[str, Any]
    value: str
    verified: bool


class SnapshotReply(DosboxEnvelope, total=False):
    bytes: int
    path: str
    route: str
    sha256: str


class StartReply(DosboxEnvelope, account.SequenceFields, total=False):
    argv: list[Any]
    background: bool
    binary: str
    binary_origin: str
    bound_s: float
    captures: str
    conf: str
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: str
    debugger_commands: Annotated[list[Any], OmitEmpty]
    declarations: dict[str, Any]
    dos_calls: str
    elapsed_s: float
    guest_files: list[Any]
    input_port: int | dict[str, Any]
    log_categories: dict[str, Any]
    operations: list[Any]
    pid: int
    presence: bool | dict[str, Any]
    ready_after_s: float
    rearm_refused: str
    shared: Annotated[bool, OmitEmpty]
    start: dict[str, Any]
    state_dir: str
    stub: str
    output_bytes_dropped: Annotated[int, OmitEmpty]
    version: str | dict[str, Any]
    watched: Annotated[bool, OmitEmpty]


class StateListReply(DosboxEnvelope, total=False):
    state_dir: str
    states: list[Any]
    working_slot: dict[str, Any]


class StatusReply(DosboxEnvelope, total=False):
    bound_s: float
    captures: str
    conf: str
    conf_changed_on_disk: Annotated[bool | dict[str, Any], OmitEmpty]
    conf_digest: str
    cpu_mode: str | dict[str, Any]
    declarations: dict[str, Any]
    elapsed_s: float
    pc: str | dict[str, Any]
    pending: dict[str, Any]
    pid: int
    presence: bool | dict[str, Any]
    state_dir: str
    output_bytes_dropped: Annotated[int, OmitEmpty]
    watched: Annotated[bool, OmitEmpty]


class StepReply(DosboxEnvelope, total=False):
    after: str
    asked: int
    cause: str
    before: str
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    instructions_completed: int
    mode: str
    moved: bool
    note: str
    pc: str
    regs: dict[str, Any]
    stalled: int
    stop_seq: int
    watches: list[Any]


class StopReply(DosboxEnvelope, total=False):
    cause: str
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    interrupted: bool
    note: str
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    via: str
    watches: list[Any]


class SymbolsFindReply(DosboxEnvelope, total=False):
    addr: str
    delta: int
    idle: bool
    kind: str
    name: str
    offset: int
    query: str
    section: int
    symbols: list[Any]
    symbols_total: int
    truncated: bool


class SymbolsLoadReply(DosboxEnvelope, total=False):
    base: int
    base_from: str
    bytes: int
    declarations: dict[str, Any]
    descriptor: int
    disambiguated: int
    excluded_pattern: int
    excluded_sections: int
    excluded_unplaceable: int
    kept: int
    limit: int
    loaded: int
    overlay_idle: int
    parsed: int
    pending: bool
    #: The table against the executable beside it (`against`, `agree`), or unavailable why.
    checked: dict[str, Any]
    renamed: int
    symbols_typed: int
    table_mode: str
    table_total: int
    truncated_names: int
    unencodable: list[Any]
    unencodable_total: int
    unreadable: int


class TraceReply(DosboxEnvelope, total=False):
    cause: str
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    frame: int | dict[str, Any]
    instruction: dict[str, Any]
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    trace: dict[str, Any]
    verdict: str
    watches: list[Any]


class WatchAddReply(DosboxEnvelope, total=False):
    addr: str
    already_stored: Annotated[bool, OmitEmpty]
    armed: bool
    by: str
    caveat: str
    command: str
    entries: list[Any]
    entry: str
    fmt: str
    frozen_hex: str
    length: int
    mode: str
    note: str
    pointer: dict[str, Any]
    ref: str
    state: str
    stored: bool
    tally_id: str
    trigger: str
    trigger_addr: str
    trigger_type: str
    why: str


class PortReply(DosboxEnvelope, total=False):
    bits: int
    port: str
    readback: dict[str, Any]
    value: str


class PicReply(DosboxEnvelope, total=False):
    controllers: list[Any]
    irq: int
    irqs: list[Any]
    line: dict[str, Any]
    method: str


class A20Reply(DosboxEnvelope, total=False):
    enabled: bool


class GuestFileReply(DosboxEnvelope, total=False):
    before: dict[str, Any]
    bytes: int
    path: str
    same_bytes: Annotated[bool, OmitEmpty]
    sha256: str
    state: str


class WriteReply(DosboxEnvelope, total=False):
    bytes_written: int
    readback: str
    ref: str
    seg_off: str
    verified: bool
    written: int


class CommentWriteReply(DosboxEnvelope, total=False):
    added: int
    comment: dict[str, Any]
    comments_total: int
    declarations: dict[str, Any]
    deleted: dict[str, Any]
    dropped_comments: list[Any]
    dropped_total: int
    note: str
    parsed: int
    path: str
    replaced_comments: list[Any]
    replaced_total: int
    truncated: bool
    unchanged: int


class DeclarationClearReply(DosboxEnvelope, total=False):
    declarations_cleared: int
    disarmed: list[Any]
    note: str
    pending_disarm: Annotated[list[Any], OmitEmpty]


class DeclarationListReply(DosboxEnvelope, total=False):
    breakpoints: list[Any]
    debugger_read: bool
    foreign: Annotated[dict[str, Any], OmitEmpty]
    regpoints: list[Any]
    watches: list[Any]


class MapWriteReply(DosboxEnvelope, total=False):
    application: str
    cells: str
    controls: int
    kind: str
    match: list[Any]
    path: str
    promoted: list[Any]
    replaced: bool
    screen: str
    screens: int
    shadows_file: bool
    size: list[Any]


class ScanReply(DosboxEnvelope, total=False):
    addr: str
    cell_bytes: int
    cleared: bool
    closed: bool
    hits: list[Any]
    hits_total: int
    iterations: int | dict[str, Any]
    length: int
    note: str
    operator: str
    ref: str
    rows: int
    seg_off: str
    survivors: int
    truncated: bool
    value: str | dict[str, Any]


class StateWriteReply(DosboxEnvelope, total=False):
    bytes: int
    machine: str
    mark: dict[str, Any]
    memory_mb: int
    name: str
    path: str
    paused: bool
    program: str
    saved_at: str
    version: str


#: Each tool's reply model, by the tool's name.
MODELS: dict[str, type] = {
    "comment_write": CommentWriteReply,
    "port": PortReply,
    "pic": PicReply,
    "a20": A20Reply,
    "guest_file": GuestFileReply,
    "declaration_clear": DeclarationClearReply,
    "declaration_list": DeclarationListReply,
    "map_write": MapWriteReply,
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
    "comment_list": CommentListReply,
    "debug": DebugReply,
    "disassemble": DisassembleReply,
    "drive": DriveReply,
    "find": FindReply,
    "interrupt_vectors": InterruptVectorsReply,
    "log": LogReply,
    "log_wait": LogWaitReply,
    "machine_map": MachineMapReply,
    "map_find": MapFindReply,
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
