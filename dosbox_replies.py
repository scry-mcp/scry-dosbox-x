"""THE REPLY MODELS, one per tool: the fields each tool's reply names beside the envelope
every reply carries, published as its `outputSchema` (names only) and held to every reply
the battery builds (`scry_core.reply_schema`). Named from the replies the battery and the
live runs built, so a branch none of them reached is unnamed until one does: a field a
reply grows is named here in the same change. The file tools' models are the core's
(`scry_core.media_replies`)."""

from __future__ import annotations

from typing import Any

from scry_core import media_replies
from scry_core.reply_schema import ReplyEnvelope


class DosboxEnvelope(ReplyEnvelope, total=False):
    """What this server's shared paths add to any reply: the stop a call met or
    applied, the refusal's context."""

    answers_while_running: list[Any]
    applied_on_stop: dict[str, Any]
    exit_code: int | dict[str, Any]
    last_stop: dict[str, Any]
    stopped_on_its_own: dict[str, Any]


class BreakpointAtReply(DosboxEnvelope, total=False):
    already_stored: bool
    armed: bool
    by: str
    entry: str
    marked: bool
    note: str
    ref: str
    state: str
    stored: bool
    why: str


class BreakpointClearReply(DosboxEnvelope, total=False):
    declarations_cleared: int
    disarmed: list[Any]
    note: str
    pending_disarm: list[Any]


class BreakpointInterruptReply(DosboxEnvelope, total=False):
    already_stored: bool
    armed: bool
    clipped: bool
    entry: str
    note: str
    ref: str
    screen_chars: int
    screen_delta: str
    state: str
    stored: bool


class BreakpointListReply(DosboxEnvelope, total=False):
    breakpoints: list[Any]
    debugger_read: bool
    foreign: list[Any]


class BuildCheckReply(DosboxEnvelope, total=False):
    binary: str
    binary_origin: str
    debugger: bool
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
    closed: bool
    ended_by: str
    note: str


class CommentAddReply(DosboxEnvelope, total=False):
    comment: dict[str, Any]
    declarations: dict[str, Any]
    held_in_memory: bool
    note: str
    replaced_comments: list[Any]


class CommentDeleteReply(DosboxEnvelope, total=False):
    declarations: dict[str, Any]
    deleted: dict[str, Any]
    note: str


class CommentListReply(DosboxEnvelope, total=False):
    comments: list[Any]
    comments_total: int
    declarations: dict[str, Any]
    truncated: bool


class CommentLoadReply(DosboxEnvelope, total=False):
    added: int
    comments_total: int
    declarations: dict[str, Any]
    note: str
    parsed: int
    path: str
    replaced_comments: list[Any]
    replaced_total: int
    truncated: bool
    unchanged: int


class CommentSaveReply(DosboxEnvelope, total=False):
    comments_total: int
    dropped_comments: list[Any]
    dropped_total: int
    note: str
    path: str
    truncated: bool


class DebugReply(DosboxEnvelope, total=False):
    clipped: bool
    command: str
    screen_chars: int
    screen_delta: str


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
    errors: list[Any]
    failed: dict[str, Any]
    failed_at: int
    looked: dict[str, Any]
    ran: list[Any]
    steps_completed: int
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
    channel: str
    labels: dict[str, Any]
    lines: list[Any]
    lines_total: int
    pattern: str
    truncated: bool


class LogWaitReply(DosboxEnvelope, total=False):
    already: bool
    arrived_during: int
    channel: str
    line: str
    lines_before: int
    lines_examined: int
    lines_total: int
    note: str
    pattern: str
    since_mark: int
    verdict: str
    waited_s: float


class MachineMapReply(DosboxEnvelope, total=False):
    bios_mem: list[Any]
    callbacks: list[Any]
    counts: dict[str, Any]
    coverage_note: str
    cpu: dict[str, Any]
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


class MapAddReply(DosboxEnvelope, total=False):
    controls: int
    kind: str
    match: list[Any]
    replaced: bool
    screen: str
    shadows_file: bool
    size: list[Any]


class MapFindReply(DosboxEnvelope, total=False):
    controls: list[Any]
    kind: str
    layer: str
    matched: bool
    screen: str
    screens_mapped: int
    screens_tried: int
    size: list[Any]


class MapLoadReply(DosboxEnvelope, total=False):
    application: str
    controls: int
    path: str
    screens: int


class MapSaveReply(DosboxEnvelope, total=False):
    application: str
    controls: int
    path: str
    promoted: list[Any]
    screens: int


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


class PerformReply(DosboxEnvelope, total=False):
    errors: list[Any]
    failed: dict[str, Any]
    failed_at: int | dict[str, Any]
    field: str
    got: Any
    held: int
    note: str
    ran: list[Any]
    ran_path: str
    recorded: Any
    replies_path: str
    steps_completed: int
    steps_total: int
    still_running: bool
    stopped: dict[str, Any]
    stops: dict[str, Any]
    truncated: bool
    verdict: str


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
    attribution: dict[str, Any]
    clipped: bool
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str
    regs: dict[str, Any]
    screen_chars: int
    screen_delta: str
    stop_seq: int
    verdict: str
    waited_s: float
    watches: list[Any]


class RunForReply(DosboxEnvelope, total=False):
    attribution: dict[str, Any]
    cpu_mode: str | dict[str, Any]
    cycles: dict[str, Any]
    e9: dict[str, Any]
    emulated_after_s: float | dict[str, Any]
    emulated_before_s: float
    enrichment: dict[str, Any]
    frame_after: dict[str, Any]
    frame_before: dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str | dict[str, Any]
    polls: int
    regs: dict[str, Any]
    retrace_pending: bool
    stop_seq: int
    verdict: str
    waited_s: float
    watches: list[Any]


class RunToReply(DosboxEnvelope, total=False):
    attribution: dict[str, Any]
    control_hits: int
    controls: list[Any]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    instruction: dict[str, Any]
    note: str
    pc: str
    ref: str
    regs: dict[str, Any]
    stop_seq: int
    target: str
    target_disarmed: bool
    verdict: str
    waited_s: float
    watches: list[Any]


class ScanClearReply(DosboxEnvelope, total=False):
    cleared: bool
    line_recovered: bool
    note: str


class ScanFilterReply(DosboxEnvelope, total=False):
    closed: bool
    hits: list[Any]
    hits_total: int
    iterations: int | dict[str, Any]
    line_recovered: bool
    note: str
    operator: str
    rows: int
    survivors: int
    truncated: bool
    value: int | dict[str, Any]


class ScanStartReply(DosboxEnvelope, total=False):
    addr: str
    cell_bytes: int
    hits_total: int
    length: int
    line_recovered: bool
    note: str
    ref: str
    seg_off: str


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
    attribution: dict[str, Any]
    cpu_mode: str
    e9: dict[str, Any]
    enrichment: dict[str, Any]
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


class SendKeysReply(DosboxEnvelope, total=False):
    bytes: int
    delivered: bool
    keys: list[Any]
    modifiers: list[Any]
    posted: int
    route: str
    ticks: int
    verify: dict[str, Any]


class SendMouseReply(DosboxEnvelope, total=False):
    action: str
    arrived: bool
    asked: dict[str, Any]
    button: str
    delivered: bool
    identified_at_stop: int | dict[str, Any]
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
    value: int
    verified: bool


class SnapshotReply(DosboxEnvelope, total=False):
    bytes: int
    path: str
    route: str
    sha256: str
    waited_s: float


class StartReply(DosboxEnvelope, total=False):
    argv: list[Any]
    background: bool
    binary: str
    binary_origin: str
    errors: list[Any]
    failed: dict[str, Any]
    failed_at: int | dict[str, Any]
    held: int
    input_port: int | dict[str, Any]
    note: str
    presence: bool | dict[str, Any]
    ran: list[Any]
    ran_path: str
    ready_after_s: float
    rearm_refused: str
    replies_path: str
    shared: bool
    start: dict[str, Any]
    steps_completed: int
    steps_total: int
    still_running: bool
    stopped: dict[str, Any]
    stops: dict[str, Any]
    stub: str
    truncated: bool
    verdict: str
    version: str | dict[str, Any]


class StateListReply(DosboxEnvelope, total=False):
    state_dir: str
    states: list[Any]
    working_slot: dict[str, Any]


class StateLoadReply(DosboxEnvelope, total=False):
    machine: str
    memory_mb: int
    name: str
    path: str
    paused: bool
    program: str
    saved_at: str
    version: str
    waited_s: float


class StateSaveReply(DosboxEnvelope, total=False):
    bytes: int
    machine: str
    memory_mb: int
    name: str
    path: str
    paused: bool
    program: str
    saved_at: str
    version: str
    waited_s: float


class StatusReply(DosboxEnvelope, total=False):
    alive: bool
    cpu_mode: str | dict[str, Any]
    declarations: dict[str, Any]
    pc: str
    pending: dict[str, Any]
    presence: bool | dict[str, Any]
    running: bool


class StepReply(DosboxEnvelope, total=False):
    after: str
    asked: int
    attribution: dict[str, Any]
    before: str
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    enrichment: dict[str, Any]
    instruction: dict[str, Any]
    instructions_completed: int
    mode: str
    moved: bool
    pc: str
    regs: dict[str, Any]
    stalled: int
    stop_seq: int
    watches: list[Any]


class StopReply(DosboxEnvelope, total=False):
    attribution: dict[str, Any]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    instruction: dict[str, Any]
    interrupted: bool
    note: str
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    via: str
    waited_s: float
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
    held_in_memory: bool
    kept: int
    limit: int
    loaded: int
    overlay_idle: int
    parsed: int
    pending: bool
    renamed: int
    symbols_typed: int
    table_mode: str
    table_total: int
    truncated_names: int
    unencodable: list[Any]
    unencodable_total: int
    unreadable: int


class TraceReply(DosboxEnvelope, total=False):
    attribution: dict[str, Any]
    cpu_mode: str | dict[str, Any]
    e9: dict[str, Any]
    instruction: dict[str, Any]
    pc: str
    regs: dict[str, Any]
    stop_seq: int
    trace: dict[str, Any]
    verdict: str
    waited_s: float
    watches: list[Any]


class WatchAddReply(DosboxEnvelope, total=False):
    already_stored: bool
    armed: bool
    by: str
    caveat: str
    command: str
    entry: str
    fmt: str
    length: int
    mode: str
    note: str
    pointer: dict[str, Any]
    ref: str
    state: str
    stored: bool
    why: str


class WatchClearReply(DosboxEnvelope, total=False):
    declarations_cleared: int
    disarmed: list[Any]
    note: str
    pending_disarm: list[Any]


class WatchListReply(DosboxEnvelope, total=False):
    debugger_read: bool
    foreign: list[Any]
    watches: list[Any]


class WriteReply(DosboxEnvelope, total=False):
    bytes_written: int
    readback: str
    ref: str
    seg_off: str
    verified: bool
    written: int


#: Each tool's reply model, by the tool's name.
MODELS: dict[str, type] = {
    "breakpoint_at": BreakpointAtReply,
    "breakpoint_clear": BreakpointClearReply,
    "breakpoint_interrupt": BreakpointInterruptReply,
    "breakpoint_list": BreakpointListReply,
    "build_check": BuildCheckReply,
    "call_stack": CallStackReply,
    "capture_frame": CaptureFrameReply,
    "captures": CapturesReply,
    "close": CloseReply,
    "comment_add": CommentAddReply,
    "comment_delete": CommentDeleteReply,
    "comment_list": CommentListReply,
    "comment_load": CommentLoadReply,
    "comment_save": CommentSaveReply,
    "debug": DebugReply,
    "disassemble": DisassembleReply,
    "drive": DriveReply,
    "find": FindReply,
    "interrupt_vectors": InterruptVectorsReply,
    "log": LogReply,
    "log_wait": LogWaitReply,
    "machine_map": MachineMapReply,
    "map_add": MapAddReply,
    "map_find": MapFindReply,
    "map_load": MapLoadReply,
    "map_save": MapSaveReply,
    "memdump": MemdumpReply,
    "palette": PaletteReply,
    "perform": PerformReply,
    "perform_export": PerformExportReply,
    "read_memory": ReadMemoryReply,
    "registers": RegistersReply,
    "resume": ResumeReply,
    "run_for": RunForReply,
    "run_to": RunToReply,
    "scan_clear": ScanClearReply,
    "scan_filter": ScanFilterReply,
    "scan_start": ScanStartReply,
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
    "state_load": StateLoadReply,
    "state_save": StateSaveReply,
    "status": StatusReply,
    "step": StepReply,
    "stop": StopReply,
    "symbols_find": SymbolsFindReply,
    "symbols_load": SymbolsLoadReply,
    "trace": TraceReply,
    "watch_add": WatchAddReply,
    "watch_clear": WatchClearReply,
    "watch_list": WatchListReply,
    "write": WriteReply,
    **{name: media_replies.MODELS[name]
       for name in ("golden_check", "image_diff", "region_track", "series_diff")},
}
