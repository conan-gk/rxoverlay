# PROJECT KNOWLEDGE BASE

**Generated:** 2025-12-31 03:13 (Europe/London)

## OVERVIEW

RxOverlay: Windows-only Python overlay app. Fix broken `r`/`x` keys via Tkinter UI + WinAPI (`SendInput`, low-level keyboard hook).

## STRUCTURE

```
./
├── README.md            # run + manual test checklist (Windows)
├── rxoverlay/           # package
│   ├── __main__.py      # entrypoint for `python -m rxoverlay`
│   ├── app.py           # orchestrator (UI + hotkeys + injection)
│   ├── ui.py            # Tkinter overlay UI
│   ├── winapi.py        # ctypes Win32 wrappers + keyboard hook + SendInput
│   ├── hotkeys.py       # hotkey matching (thread-safe callbacks)
│   ├── config.py        # config/state load/save + defaults
│   └── logging_setup.py # logging setup
└── rxoverlay.log        # generated runtime log (artifact)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Run app | `rxoverlay/__main__.py` | `python -m rxoverlay` calls `rxoverlay.app:main` |
| App lifecycle/orchestration | `rxoverlay/app.py` | Tk thread schedules action processing + foreground polling |
| UI behavior | `rxoverlay/ui.py` | Tkinter overlay; no-activate window best-effort |
| Global hotkeys | `rxoverlay/hotkeys.py` | hook-thread safe; enqueue into app queue |
| WinAPI hook/injection | `rxoverlay/winapi.py` | `KeyboardHook` + `send_unicode_text()` |
| Config/state | `rxoverlay/config.py` | writes to `%LOCALAPPDATA%\RxOverlay\config.json` + `state.json` |
| Logging | `rxoverlay/logging_setup.py` | console + optional file handler |

## CONVENTIONS (DEVIATIONS ONLY)

- **Run-in-place**: no `pyproject.toml` / `setup.py` / `requirements.txt`; intended: `python -m rxoverlay`.
- **Stdlib-only**: Tkinter + ctypes; no external deps.
- **Config location**: `%LOCALAPPDATA%\RxOverlay\config.json` (Windows), `~/.config/RxOverlay` (non-Windows fallback).

## ANTI-PATTERNS (THIS PROJECT)

- **Tk from hook thread**: forbidden. `rxoverlay/hotkeys.py` says: do NOT call Tkinter from the keyboard hook thread; use queue + `after`.
- **Overlay focus stealing**: avoid making overlay foreground; `rxoverlay/winapi.py` implements `WS_EX_NOACTIVATE` + `WM_MOUSEACTIVATE -> MA_NOACTIVATE` best-effort.

## Decisions

- DECISIONS.md records intentional, non-obvious tradeoffs
- Treat decisions as authoritative constraints
- Do not modify or invalidate decisions unless explicitly instructed
- If a task conflicts with a recorded decision, surface the conflict before proceeding

## COMMANDS

```bash
python -m rxoverlay
python -m rxoverlay --debug
python -m rxoverlay --config path/to/config.json
```

## NOTES

- Generated artifacts currently in tree: `rxoverlay/__pycache__/` and `rxoverlay.log` (nonstandard for source repos).
- Tests/CI: none detected.
- LSP: not installed in this environment; rely on text/AST search.
