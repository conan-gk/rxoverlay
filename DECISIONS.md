# Decisions

## Architecture

- **Hook thread → queue → Tk thread scheduling for all cross-thread calls**
  - Why: Tkinter is not thread-safe; calling Tk APIs from the keyboard hook thread would cause crashes or undefined behavior.
  - Not chosen: Direct Tkinter calls from hook thread, thread-unsafe shared state, or more complex locking mechanisms.

- **Two separate config files (`config.json` + `state.json`)**
  - Why: Separates user-configurable settings (theme, hotkeys) from volatile runtime state (enabled/minimized). Simpler merging and less risk of user edits being overwritten.
  - Not chosen: Single combined file, Windows registry, or `~/.config/RxOverlay/*.toml` structure.

## Technology Choices

- **Run via `python -m rxoverlay` (module execution) instead of pip-installable package**
  - Why: Minimal distribution model; no packaging metadata or installation overhead required.
  - Not chosen: `pyproject.toml` + entry points, `setup.py`, wheel building, or Windows executable bundling.

- **Tkinter for UI (stdlib-only)**
  - Why: Zero external dependencies; Python ships with Tkinter on Windows.
  - Not chosen: PyQt/PySide, wxPython, Dear PyGui, or other third-party GUI frameworks.

- **`KEYEVENTF_UNICODE` (SendInput) for text injection**
  - Why: Layout-independent text injection. Sends actual Unicode code units rather than VK codes that map differently across keyboard layouts.
  - Not chosen: Virtual key code (VK) sequences, clipboard-based injection, or accessibility APIs.

- **`WH_KEYBOARD_LL` low-level hook with dedicated message loop thread**
  - Why: Reliable global hotkey interception before other apps consume events. Dedicated thread with real message loop prevents blocking.
  - Not chosen: Higher-level hooks (`WH_KEYBOARD`), `RegisterHotKey`, or polling approaches.

- **Scan codes (hardware-level) for hotkey matching**
  - Why: Layout-independent hotkey detection. Physical key position is consistent regardless of keyboard layout.
  - Not chosen: Virtual key codes (VK), character-based matching, or platform-dependent key names.

- **`WS_EX_NOACTIVATE` + `WM_MOUSEACTIVATE -> MA_NOACTIVATE` for overlay window**
  - Why: Prevent overlay from stealing focus when clicked. If overlay never becomes foreground, injected text lands in the already-focused target app naturally.
  - Not chosen: Allowing overlay to become foreground and attempting focus restoration after each click.

## Non-Goals

- **Test suite or CI pipeline**
  - Evidence: No `tests/` directory, no pytest/jest/vitest configuration, no `.github/workflows/`.
- **Packaging as wheel or executable**
  - Evidence: No `pyproject.toml`, no `setup.py`, no build scripts.
- **Cross-platform support**
  - Evidence: All WinAPI calls guarded by `sys.platform == "win32"`; non-Windows config fallback is a minimal path change only.
- **Third-party dependencies**
  - Evidence: Imports are from stdlib only (`tkinter`, `ctypes`, `json`, `logging`, `threading`, `pathlib`).
