// keypost -- post keystrokes and mouse events to a RUNNING guest's emulator window.
//
// WHY THIS EXISTS, and it is the whole of the driver's ACT half. Measured 2026-09-02: the
// only route that reaches a DOS program already running under DOSBox-X on macOS is a host
// key event delivered to the emulator's window WHILE IT IS FRONTMOST. AUTOTYPE is host-timed
// and cannot bracket the DPMI entry walk; the debugger console has no key command; the
// integration device's injection registers are driven by GUEST code, not the host. A pipe/
// socket control channel is upstream issue #4601, still open. So until that lands, this is
// the route, and this program is it: it brings the emulator frontmost, posts the events, and
// hands focus back. The Python side keeps a route-independent contract, so the day #4601
// arrives this program is swapped out under a tool that does not change.
//
// IT IS SEPARATE FROM THE PACKAGE'S PYTHON on purpose: synthetic input on macOS is CGEvent +
// Accessibility trust, which is native. The Python side compiles this once into a per-user
// cache and invokes it.
//
// OUTPUT is one `key=value` line per fact, so the caller parses fields rather than prose:
//   keypost=<n>           the contract version this binary speaks (first line, always)
//   trusted=<bool>        AXIsProcessTrusted -- false means nothing can be posted
//   activated=<bool>      the emulator app was brought frontmost, READ BACK from the window
//                         server and AX (never the activation request's own result)
//   attempts=<n>          how many activate-and-read-back rounds it took
//   ax_frontmost=<bool>   what the app's own AX frontmost flag read after the last round
//   top_window_pid=<pid>  who owns the topmost on-screen window, per the window server
//   window=<x>,<y>,<w>,<h>  the emulator's front window per the window server, or `none`
//   pointer=<x>,<y>       where a `move` put the host pointer
//   posted=<n>            how many events were posted
//   previous_pid=<pid>    the app that was in front when this call started (absent when
//                         that was the emulator itself, or nothing)
//   restored=<bool|skipped|kept|lost>  the previous app was put back (AX read-back); there
//                         was nothing to put back; `--keep-focus` left the emulator in front
//                         and it READ BACK as still there; or it was asked to keep and the
//                         read-back says the focus went elsewhere
//   error=<text>          a refusal, on stderr, with a non-zero exit
//
// EXIT: 0 posted; 2 usage (a bad number, too many key names, a nudge past the cap); 3 not
//       Accessibility-trusted; 4 the pid is not a running app; 5 an unknown key or modifier
//       name; 6 the emulator never read as frontmost; 7 the click would land outside the
//       emulator's window, or it has none. On 2, 5, 6 and 7 NOTHING is posted: every argument
//       is checked before the focus is touched, and a refusal that comes after the activation
//       gives the focus back first.

import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

func die(_ code: Int32, _ msg: String) -> Never {
    FileHandle.standardError.write(("error=" + msg + "\n").data(using: .utf8)!)
    exit(code)
}

// The mapper-style key names DOSBox-X's AUTOTYPE uses, mapped to macOS virtual keycodes.
// A SUBSET chosen for what a debugging session sends -- letters, digits, the editing and
// navigation keys, and the function row -- not the whole mapper. An unknown name is a
// refusal (exit 5), never a silent no-op, because a key that did not go is the failure this
// route is most likely to hide.
let KEYCODES: [String: CGKeyCode] = [
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "o": 31, "u": 32,
    "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28, "9": 25, "0": 29,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 117,
    "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121, "insert": 114,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "minus": 27, "equals": 24, "leftbracket": 33, "rightbracket": 30, "semicolon": 41,
    "quote": 39, "grave": 50, "backslash": 42, "comma": 43, "period": 47, "slash": 44,
    "capslock": 57,
]
// THE TWO ROUTES SHARE THIS VOCABULARY: `SCAN_SET1` on the Python side names the same keys
// for the serial route, and a test holds the two name sets equal, so a caller says the same
// thing whichever route answers.

let MODIFIERS: [String: CGEventFlags] = [
    "shift": .maskShift, "ctrl": .maskControl, "control": .maskControl,
    "alt": .maskAlternate, "option": .maskAlternate, "cmd": .maskCommand, "command": .maskCommand,
]

// argv: keypost [--keep-focus] [--return-to <pid>] <pid> keys <mods> <name> [name ...]
//       keypost [--keep-focus] <pid> click <left|right>
//       keypost [--keep-focus] [--return-to <pid>] <pid> move <x> <y> | move center
//       keypost [--keep-focus] <pid> nudge <dx> <dy>
// <mods> is a '+'-joined list or "-" for none (e.g. ctrl+shift, or -).
// `--keep-focus`, anywhere in argv, leaves the emulator FRONTMOST afterwards instead of
// handing the focus back. It exists for the mouse: DOSBox-X captures the pointer on a click
// and RELEASES it the moment the window loses focus, so a click followed by the usual
// hand-back never keeps a capture, and every later click is swallowed as a fresh capture
// attempt -- MEASURED, a run whose clicks were all handed back delivered none of them, and a
// run where the emulator happened to stay in front delivered every one.
//
// `--return-to <pid>` names the app to hand the focus back to when the emulator is ALREADY
// in front at start (a previous `--keep-focus` call left it there): without it that call
// would find nothing to return to and say `skipped`, and the app the user was in before the
// first keep would never get the focus back. The caller remembers that pid from the
// `previous_pid=` fact of the call that kept.
var args = CommandLine.arguments
let keepFocus = args.contains("--keep-focus")
args.removeAll { $0 == "--keep-focus" }
var returnTo: pid_t? = nil
if let i = args.firstIndex(of: "--return-to") {
    guard i + 1 < args.count, let p = pid_t(args[i + 1]) else { die(2, "--return-to needs a pid") }
    returnTo = p
    args.removeSubrange(i...(i + 1))
}
guard args.count >= 3, let pid = pid_t(args[1]) else {
    die(2, "usage: keypost [--keep-focus] [--return-to <pid>] <pid> keys <mods> <name>... "
           + "| click <left|right> | move <x> <y> | move center | nudge <dx> <dy>")
}
let mode = args[2]

// THE CONTRACT VERSION COMES FIRST. The Python side compiles this file into a cache keyed by
// mtime, and an edit that lands while a build is running (or a cache copied with its mtimes)
// serves an OLD binary to NEW Python: the facts it prints would then be read under the new
// contract's meaning. So every reply names the contract it speaks, and Python rebuilds when
// it is not the one it expects. Bump it whenever a fact's meaning or the exit codes change.
print("keypost=3")

// TRUST FIRST: without it CGEvent posts are silently dropped, which is the false green this
// route is most exposed to (a key that reports sent and never arrives).
let trusted = AXIsProcessTrusted()
print("trusted=\(trusted)")
if !trusted { die(3, "not Accessibility-trusted; grant the host process access in System Settings") }

guard NSRunningApplication(processIdentifier: pid) != nil else {
    die(4, "no running application with pid \(pid)")
}
let previous = NSWorkspace.shared.frontmostApplication      // to hand focus back

// ACTIVATE VIA THE ACCESSIBILITY API, then let the window server settle. Measured
// 2026-09-02: a key posted to the emulator lands only while its window is frontmost, AND
// NSRunningApplication.activate (even ignoringOtherApps) reports success from a CLI while the
// guest receives NOTHING -- the WindowServer does not honour a cooperative activation from a
// non-GUI process. Setting kAXFrontmost and raising the main window through AX DOES deliver,
// and it uses the SAME Accessibility grant CGEvent already needs, so there is no Automation
// prompt an autonomous session could not answer. Both were measured landing the cue key.
//
// THE WINDOW IS LOOKED UP FRESH EVERY TIME, and the result is READ BACK rather than believed.
// An app that changes video mode (ReChip going from text to VESA on a song load) can recreate
// its SDL window, so a handle kept from earlier raises a window that no longer exists; and the
// `AXUIElementSetAttributeValue` result says the REQUEST was accepted, not that the app is now
// in front. So: ask for the app's windows now, raise the focused one (or the first), set
// frontmost, settle, then read `kAXFrontmost` back AND ask the window server whose window is
// on top. Retried a few times because the window server takes its time; refused (exit 6) if
// the app never reads as frontmost, since a key posted then is exactly the silent drop this
// route is most exposed to.
func raiseAWindow(of ax: AXUIElement) {
    var focused: CFTypeRef?
    if AXUIElementCopyAttributeValue(ax, kAXFocusedWindowAttribute as CFString, &focused) == .success,
       let w = focused {
        // swiftlint:disable:next force_cast
        _ = AXUIElementPerformAction(w as! AXUIElement, kAXRaiseAction as CFString)
        return
    }
    var windows: CFTypeRef?
    if AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &windows) == .success,
       let list = windows as? [AXUIElement], let first = list.first {
        _ = AXUIElementPerformAction(first, kAXRaiseAction as CFString)
    }
}

// THE WINDOW SERVER IS ASKED, NOT THE WORKSPACE. `NSWorkspace.frontmostApplication` is
// kept current by the process's run loop, and a command-line helper has none, so it kept
// answering with whatever was frontmost when the helper STARTED: activation then read as
// failed four times in a row while the window was in front (and, the other way, as an
// instant success when a previous refusal had left the emulator frontmost). The on-screen
// window list is the window server's own answer and needs no run loop: the topmost
// layer-0 window's owner is the app with the focus. AX's own frontmost flag is read as well
// and both are reported, so a disagreement is visible instead of averaged away.
//
// WHICH WINDOW COUNTS AS "ON TOP". The on-screen list is front-to-back. Ordinary app windows
// sit at layer 0; a fullscreen or always-on-top SDL window sits ABOVE that (the shielding or
// floating level), and a `layer == 0` filter would skip the emulator's own window while it is
// in front and refuse forever. So the first window that is EITHER at layer 0 OR the target's
// decides: if it is the target's, the target is on top. Menu-bar extras, the dock and the
// desktop are above/below that band and are excluded by the query or by the walk.
func topWindowOwner(above target: pid_t) -> pid_t? {
    guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }
    for entry in list {
        guard let owner = entry[kCGWindowOwnerPID as String] as? Int else { continue }
        let layer = entry[kCGWindowLayer as String] as? Int ?? -1
        if layer == 0 || pid_t(owner) == target { return pid_t(owner) }
    }
    return nil
}

func axFrontmost(_ ax: AXUIElement) -> Bool {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(ax, kAXFrontmostAttribute as CFString, &value) == .success
        && (value as? Bool) == true
}

let ACTIVATE_ATTEMPTS = 4
let SETTLE_S = 0.35
let AX_CALL_TIMEOUT_S: Float = 2.0   // an app not servicing AX must not hang the helper

// Returns (frontmost as READ BACK, attempts spent, what AX said, who owns the top window).
func axActivate(_ target: pid_t) -> (Bool, Int, Bool, pid_t?) {
    let ax = AXUIElementCreateApplication(target)
    AXUIElementSetMessagingTimeout(ax, AX_CALL_TIMEOUT_S)
    var axSays = false
    var top: pid_t? = nil
    for attempt in 1...ACTIVATE_ATTEMPTS {
        raiseAWindow(of: ax)
        _ = AXUIElementSetAttributeValue(ax, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
        Thread.sleep(forTimeInterval: SETTLE_S)
        axSays = axFrontmost(ax)
        top = topWindowOwner(above: target)
        if axSays && top == target { return (true, attempt, axSays, top) }
    }
    return (false, ACTIVATE_ATTEMPTS, axSays, top)
}

// HANDING FOCUS BACK is a courtesy, not the thing being verified, so it is ONE round and AX's
// own answer: the previous app may own no window at all (Finder after a click on the desktop),
// and the window-server test would then spend every round to report a restore that worked
// as a failure.
func axRestore(_ target: pid_t) -> Bool {
    let ax = AXUIElementCreateApplication(target)
    AXUIElementSetMessagingTimeout(ax, AX_CALL_TIMEOUT_S)
    raiseAWindow(of: ax)
    _ = AXUIElementSetAttributeValue(ax, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
    Thread.sleep(forTimeInterval: SETTLE_S)
    return axFrontmost(ax)
}

// EVERY NAME IS RESOLVED BEFORE ANYTHING IS POSTED, so "unknown key name" really means nothing
// went: resolving inside the posting loop sent the names before the bad one and then reported
// nothing posted, with the emulator left frontmost. And the count is CAPPED, because the
// helper's runtime grows with it and the caller kills it at a fixed bound: a text longer than
// this goes in several calls.
//
// THE SAME HOLDS FOR THE MOUSE: every argument is parsed here, before the focus is touched,
// because a refusal that fires after the activation leaves the emulator in front with nothing
// handed back. The nudge is CAPPED for the reason the key count is: one delta event per
// point, so its runtime grows with the distance and the caller kills it at a fixed bound.
let MAX_KEYS_PER_CALL = 64
let MAX_NUDGE_PX = 2000
var keyCodes: [CGKeyCode] = []
var keyFlags: CGEventFlags = []
var clickRight = false
var movePoint: CGPoint? = nil       // nil with mode == "move" means "the window's centre"
var nudgeDx = 0, nudgeDy = 0
switch mode {
case "keys":
    guard args.count >= 5 else { die(2, "keys needs <mods> and at least one name") }
    if args[3] != "-" {
        for m in args[3].split(separator: "+") {
            guard let f = MODIFIERS[String(m).lowercased()] else { die(5, "unknown modifier \(m)") }
            keyFlags.insert(f)
        }
    }
    for name in args[4...] {
        guard let code = KEYCODES[name.lowercased()] else { die(5, "unknown key name \(name)") }
        keyCodes.append(code)
    }
    if keyCodes.count > MAX_KEYS_PER_CALL {
        die(2, "at most \(MAX_KEYS_PER_CALL) key names per call (got \(keyCodes.count)); send "
               + "a longer text in several calls")
    }
case "click":
    guard args.count == 4, ["left", "right"].contains(args[3]) else {
        die(2, "click needs left or right")
    }
    clickRight = args[3] == "right"
case "move":
    if args.count == 4, args[3] == "center" {
        movePoint = nil
    } else {
        guard args.count == 5, let x = Int(args[3]), let y = Int(args[4]) else {
            die(2, "move needs <x> <y> in whole screen points, or the word center")
        }
        movePoint = CGPoint(x: x, y: y)
    }
case "nudge":
    guard args.count == 5, let dx = Int(args[3]), let dy = Int(args[4]) else {
        die(2, "nudge needs <dx> <dy> in whole points")
    }
    guard dx >= -MAX_NUDGE_PX, dx <= MAX_NUDGE_PX, dy >= -MAX_NUDGE_PX, dy <= MAX_NUDGE_PX else {
        die(2, "a nudge is at most \(MAX_NUDGE_PX) points on either axis per call (got \(dx),\(dy)); "
               + "it is one event per point, so a longer one goes in several calls")
    }
    nudgeDx = dx; nudgeDy = dy
default:
    die(2, "mode is keys | click | move | nudge; got \(mode)")
}

// THE TARGET'S FRONT WINDOW, from the window server: reported on every call (`window=`), it
// gives `move center` its point and the click its bounds check. The first on-screen window
// the target owns is the one in front, since the list is front-to-back.
func frontWindowBounds(of target: pid_t) -> CGRect? {
    guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }
    for entry in list where (entry[kCGWindowOwnerPID as String] as? Int).map({ pid_t($0) }) == target {
        if let b = entry[kCGWindowBounds as String] as? [String: CGFloat],
           let x = b["X"], let y = b["Y"], let w = b["Width"], let h = b["Height"], w > 1, h > 1 {
            return CGRect(x: x, y: y, width: w, height: h)
        }
    }
    return nil
}

let (activated, attempts, axSaysFront, topOwner) = axActivate(pid)
print("activated=\(activated)")   // READ BACK: AX frontmost AND the window server's top window
print("attempts=\(attempts)")
print("ax_frontmost=\(axSaysFront)")
print("top_window_pid=\(topOwner.map { String($0) } ?? "none")")
if !activated {
    // THE BORROW IS RETURNED EVEN ON A REFUSAL: a failed activation can still have moved the
    // focus half-way, and leaving it there is what made the NEXT call read as an instant success.
    if let previous = previous, previous.processIdentifier != pid {
        _ = axRestore(previous.processIdentifier)
    }
    die(6, "the emulator never read as frontmost after \(attempts) attempts (AX frontmost "
           + "\(axSaysFront), top window owned by pid \(topOwner.map { String($0) } ?? "none")); "
           + "nothing was posted, because a key sent to a window without the focus is dropped "
           + "in silence")
}

let src = CGEventSource(stateID: .hidSystemState)
var posted = 0

func postKey(_ code: CGKeyCode, _ flags: CGEventFlags) {
    if let down = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true),
       let up = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false) {
        down.flags = flags
        up.flags = flags
        down.postToPid(pid)
        usleep(40_000)
        up.postToPid(pid)
        usleep(40_000)
        posted += 1
    }
}

let window = frontWindowBounds(of: pid)
if let w = window {
    print("window=\(Int(w.origin.x)),\(Int(w.origin.y)),\(Int(w.width)),\(Int(w.height))")
} else {
    print("window=none")
}

// A REFUSAL AFTER THE ACTIVATION HANDS THE FOCUS BACK FIRST, whatever the policy: nothing was
// posted, so leaving the emulator in front would only be the half-moved state the next call
// misreads.
func refuseAfterActivation(_ code: Int32, _ msg: String) -> Never {
    if let previous = previous, previous.processIdentifier != pid {
        _ = axRestore(previous.processIdentifier)
    } else if let back = returnTo {
        _ = axRestore(back)
    }
    die(code, msg)
}

switch mode {
case "keys":
    for code in keyCodes { postKey(code, keyFlags) }
case "click":
    // THE CLICK LANDS AT THE HOST POINTER'S CURRENT SPOT, and through the HID tap it is
    // routed to the window UNDER that spot exactly as a hand's click is -- so a pointer
    // outside the emulator's window would click another app, activate it, and drop any
    // capture. The spot is checked against the target's window bounds first; `move` (or
    // `move center`) is how a caller puts the pointer where the click should go.
    let loc = CGEvent(source: src)?.location ?? .zero
    guard let w = window else {
        refuseAfterActivation(7, "the emulator owns no on-screen window to click in")
    }
    guard w.contains(loc) else {
        refuseAfterActivation(7, "the host pointer is at \(Int(loc.x)),\(Int(loc.y)), outside the "
                                 + "emulator's window \(Int(w.origin.x)),\(Int(w.origin.y)) "
                                 + "\(Int(w.width))x\(Int(w.height)); nothing was posted. Place it "
                                 + "first (move center, or move <x> <y>)")
    }
    let downType: CGEventType = clickRight ? .rightMouseDown : .leftMouseDown
    let upType: CGEventType = clickRight ? .rightMouseUp : .leftMouseUp
    let button: CGMouseButton = clickRight ? .right : .left
    // THROUGH THE HID TAP, not to the pid: a mouse event carries a POSITION, and the window
    // server routes a tap-posted click to the window under it exactly as a hand's click is
    // routed; a click posted to the pid arrives without that routing. MEASURED: clicks posted
    // to the pid over a frontmost emulator window produced no button edge in the guest.
    if let down = CGEvent(mouseEventSource: src, mouseType: downType, mouseCursorPosition: loc,
                          mouseButton: button),
       let up = CGEvent(mouseEventSource: src, mouseType: upType, mouseCursorPosition: loc,
                        mouseButton: button) {
        down.post(tap: .cghidEventTap); usleep(40_000)
        up.post(tap: .cghidEventTap); usleep(40_000)
        posted += 1
    }
case "move":
    // THE HOST POINTER IS WARPED, NOT JUST TOLD ABOUT. A `mouseMoved` posted to the pid
    // carries a position but leaves the real pointer where it was, and the click that
    // follows lands at the REAL pointer -- MEASURED: three moves into the window, three
    // clicks, and the guest logged nothing, because every click fell outside it. So the
    // pointer itself is moved (a visible act on the host, announced by the tool), then the
    // motion is posted through the HID tap so the app sees the same event a hand would
    // produce. The mouse is NOT re-associated with the cursor afterwards: a captured SDL
    // window owns that association (it is how relative mode works), and taking it back
    // behind its back would let the physical mouse move a pointer the emulator believes is
    // locked. `center` is the middle of the target's front window, read from the window
    // server rather than guessed from a conf and a title-bar height.
    var point: CGPoint
    if let p = movePoint {
        point = p
    } else {
        guard let w = window else {
            refuseAfterActivation(7, "move center: the emulator owns no on-screen window")
        }
        point = CGPoint(x: w.midX, y: w.midY)
    }
    CGWarpMouseCursorPosition(point)
    if let mv = CGEvent(mouseEventSource: src, mouseType: .mouseMoved,
                        mouseCursorPosition: point, mouseButton: .left) {
        mv.post(tap: .cghidEventTap); usleep(40_000); posted += 1
    }
    print("pointer=\(Int(point.x)),\(Int(point.y))")
case "nudge":
    // RELATIVE MOTION, for a guest that integrates deltas. A captured (relative-mode) SDL
    // window reads the event's DELTA fields, not its position: a warp or a positioned move
    // carries a delta of zero and moves nothing in the guest. So each step here is a
    // mouseMoved with its delta fields set, posted through the HID tap.
    //
    // THE POINTER IS NOT WARPED HERE, deliberately. A captured SDL window keeps re-centring
    // the hidden pointer itself, and warping it in step with the deltas made the two fight:
    // MEASURED, a nudge of +100 on X moved the guest by -71 on X and -87 on Y. The deltas
    // alone are what relative mode reads, one small event per point so the guest's driver
    // integrates them the way it integrates a hand's motion. The per-step split below
    // telescopes to exactly (dx, dy) whatever the rounding.
    let dx = nudgeDx, dy = nudgeDy
    let at = CGEvent(source: src)?.location ?? .zero
    let steps = max(abs(dx), abs(dy), 1)
    for i in 1...steps {
        let sx = (dx * i) / steps - (dx * (i - 1)) / steps
        let sy = (dy * i) / steps - (dy * (i - 1)) / steps
        if let mv = CGEvent(mouseEventSource: src, mouseType: .mouseMoved,
                            mouseCursorPosition: at, mouseButton: .left) {
            mv.setIntegerValueField(.mouseEventDeltaX, value: Int64(sx))
            mv.setIntegerValueField(.mouseEventDeltaY, value: Int64(sy))
            mv.post(tap: .cghidEventTap)
            usleep(4_000)
        }
    }
    posted += 1
default:
    die(2, "mode is keys | click | move | nudge; got \(mode)")   // unreachable: parsed above
}

print("posted=\(posted)")

// HAND FOCUS BACK. A debugging session runs while the person is doing something else, so the
// activation above is a borrow, not a seizure. FOUR answers, every one READ BACK or a
// statement about what there was to do: `true`/`false` are AX's read-back of the restore;
// `kept`/`lost` are the read-back of a `--keep-focus` call (a click routed to another app's
// window would move the focus there, and a literal "kept" would then be a lie); `skipped`
// means there was nothing to give the focus back to. `previous_pid=` names the app that was
// in front when this call started, so a caller that keeps the focus can hand it back later
// with `--return-to`, when this call's own `previous` would already be the emulator.
if let previous = previous, previous.processIdentifier != pid {
    print("previous_pid=\(previous.processIdentifier)")
}
if keepFocus {
    Thread.sleep(forTimeInterval: SETTLE_S)
    print("restored=\(axFrontmost(AXUIElementCreateApplication(pid)) ? "kept" : "lost")")
} else if let previous = previous, previous.processIdentifier != pid {
    print("restored=\(axRestore(previous.processIdentifier))")
} else if let back = returnTo, back != pid {
    print("restored=\(axRestore(back))")
} else {
    print("restored=skipped")
}
