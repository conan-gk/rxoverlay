# RxOverlay

A minimal desktop tool to compensate for broken "r" and "x" keys.
> **Note**: This was just a personal tool I custom made when the "r" and "x" keys on my keyboard stopped working.

## Features

- Always-on-top overlay with virtual "r" and "x" buttons
- Configurable physical keybinds to emit "r" or "x"
- Toggle on/off functionality
- Minimal, unobtrusive UI
- Runs locally, no cloud or accounts required
- Windows-only (uses WinAPI for reliable keyboard injection)

## Installation

1. Clone or download this repository
2. Install Python 3.8+ if not already installed
3. Run the application:

```bash
python -m rxoverlay
```

## Running Tests

Use the test runner to verify the implementation:

```bash
cd C:\test_space\rxoverlay
python test_runner.py
```

**Expected output**:
- All tests pass ✓
- No import errors
- WinAPI calls return sensible values
- OverlayWindow creates successfully

If the test runner passes, try running the main app:
```bash
cd C:\test_space\rxoverlay
python -m rxoverlay
```

## Manual Test Checklist (Windows)

Use Notepad for baseline test (fastest signal).

### 1) Input injection (critical)

1. Open Notepad and click into the text area.
2. With Notepad still focused, click overlay `r` button 20 times.
   - Expected: 20 `r` characters appear in Notepad.
   - Expected: Notepad stays focused (caret remains in Notepad); overlay should not steal focus.
3. Repeat with the overlay `x` button.
4. Repeat in another app with a normal text input (browser address bar, chat app input, etc.).

If it fails only for elevated apps, run RxOverlay as Administrator (UIPI/integrity limitation).

### 2) Dragging polish

1. Drag the overlay by its top bar (drag handle area) for ~10 seconds.
2. Drag quickly and slowly.
   - Expected: no flashing, resizing, or visual deformation.
   - Expected: buttons remain clickable and don't accidentally drag.

### 3) Minimize + restore

1. Click the top-right minimize button.
   - Expected: overlay hides and a small restore widget (↑) appears.
2. Click the restore widget.
   - Expected: overlay reappears and stays topmost if configured.
3. While minimized, press the toggle hotkey.
   - Expected: it restores (instead of only toggling enabled state).



## Troubleshooting

### Tool doesn't start

1. Ensure you have Python 3.8+ installed
2. Run from Command Prompt as Administrator if you encounter permission errors
3. Check that no other similar tools are running (keyboard hook conflicts)

### Hotkeys not working

1. Try different hotkey combinations to avoid conflicts
2. Ensure the tool is enabled (overlay buttons should be clickable)
3. Check the log file at `%LOCALAPPDATA%\RxOverlay\rxoverlay.log`

### Characters not appearing in target application

1. Some applications (especially games) may use different input methods
2. Try running as Administrator
3. Ensure the target application is focused before clicking buttons or using hotkeys

### Overly aggressive security software

Some antivirus or endpoint security software may block low-level keyboard hooks. If the tool doesn't work:

1. Add an exception for the tool in your security software
2. Run as Administrator
3. Check Windows Security event logs for blocked operations

## Limitations

- **Windows only**: Uses Windows-specific APIs for reliable keyboard injection
- **Administrator privileges may be required**: For some applications, especially games or elevated apps
- **Games with anti-cheat**: May block keyboard injection
- **Remote Desktop**: May have reduced functionality in RDP sessions

## Development

### Project Structure

```
rxoverlay/
├── __init__.py         # Package init
├── __main__.py        # Entry point
├── app.py             # Main application orchestrator
├── config.py          # Configuration management
├── hotkeys.py         # Global hotkey handling
├── logging_setup.py   # Logging configuration
├── ui.py              # Tkinter overlay UI
└── winapi.py          # Windows API wrappers
```

### Dependencies

- **stdlib only**: Uses only Python standard library modules
- **ctypes**: Windows API access
- **tkinter**: UI framework (built-in)
- **json**: Configuration file format
- **threading**: Background operations
- **pathlib**: Cross-platform path handling

No external dependencies required!

## License

MIT License - feel free to use, modify, and distribute.

## Support

If you encounter issues:

1. Check the log file at `%LOCALAPPDATA%\RxOverlay\rxoverlay.log`
2. Try running with `--debug` flag for detailed logging
3. Ensure no conflicting keyboard tools are running
4. Consider if the target application has special input handling requirements