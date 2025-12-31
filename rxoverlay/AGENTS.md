# RXOVERLAY PACKAGE (rxoverlay/)

**Generated:** 2025-12-31 (Europe/London)

## OVERVIEW

Core implementation package: Tkinter overlay UI + WinAPI keyboard hook + SendInput text injection.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| App lifecycle / orchestration | `rxoverlay/app.py` | Tk thread owns UI + periodic work; actions come in via queue |
| Global hotkeys + matching | `rxoverlay/hotkeys.py` | Scan-code + exact modifiers; consumes matched events |
| Hook thread + WinAPI wrappers | `rxoverlay/winapi.py` | `KeyboardHook` thread with message loop; `SendInput` injection |
| Overlay UI widgets/behavior | `rxoverlay/ui.py` | Drag, minimize/restore widget, theme/opacity, NOACTIVATE best-effort |
| Config + state persistence | `rxoverlay/config.py` | Defaults + merge; config/state paths; simple migration |
| Logging setup | `rxoverlay/logging_setup.py` | Root logger config + optional file handler |

## MODULE NOTES

- `rxoverlay/app.py`: Central controller (`RxOverlayApp`). Bridges hook-thread callbacks into Tk via `queue.Queue` + `after` polling (`_process_actions`). Tracks last foreground target HWND; injects text via `send_unicode_text()`.
- `rxoverlay/hotkeys.py`: `HotkeyManager` wraps `KeyboardHook`. Debounces held keys with `_pressed_scancodes`. Exact-modifier matching (set equality) is intentional.
- `rxoverlay/winapi.py`:
  - `KeyboardHook`: dedicated thread, `WH_KEYBOARD_LL`, real message loop (`GetMessageW`).
  - Injection: `send_unicode_text()` uses `KEYEVENTF_UNICODE` (layout-independent).
  - Recursion guard: ignores injected key events (`LLKHF_INJECTED`, `LLKHF_LOWER_IL_INJECTED`) for hotkey matching.
  - Overlay focus rules: `enable_noactivate_window()` + `WM_MOUSEACTIVATE -> MA_NOACTIVATE`; `show_window_noactivate()`.
- `rxoverlay/ui.py`: Tk `OverlayWindow`. Best-effort non-activating overlay; provides callbacks back to `RxOverlayApp`.
- `rxoverlay/config.py`: Two files in config dir: `config.json` (settings) and `state.json` (enabled/minimized). Missing keys backfilled on load.

## SHARP EDGES (DIRECTORY-SPECIFIC)

- **Tk thread-safety**: `rxoverlay/ui.py` uses `threading.Timer(..., self.hide)` for auto-hide. Tk widgets are not thread-safe; any Tk calls should be scheduled via `after()`.
- **Position persistence callback thread**: `rxoverlay/ui.py` debounces `_save_position()` via `threading.Timer`, which runs outside Tk. Current callback writes config (I/O) so it’s OK, but keep it non-Tk.
- **Focus restore is best-effort**: `rxoverlay/app.py` attempts `focus_window()` only when overlay is foreground; injection should not proceed if focus cannot be restored.

## CONVENTIONS (DIRECTORY-SPECIFIC)

- Use scan codes for hotkeys (layout-independent) and match **exact modifier set**.
- Keep all WinAPI ctypes signatures explicit (`argtypes`/`restype`); changes here are high-risk.
- For cross-thread signaling from hook thread, pass only primitives / immutable data (e.g., action strings) into the queue.
