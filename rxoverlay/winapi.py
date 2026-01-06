"""Windows API wrappers for keyboard hooks and input injection (Windows only).

This module is intentionally small and explicit:
- Correct ctypes bindings (argtypes/restype)
- Robust WH_KEYBOARD_LL hook on a dedicated thread with a real message loop
- SendInput Unicode text injection

No external dependencies.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# --- DLLs ---

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
except Exception:  # pragma: no cover - Windows-only best-effort
    dwmapi = None

# --- Constants ---

WH_KEYBOARD_LL = 13

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

LLKHF_LOWER_IL_INJECTED = 0x00000002
LLKHF_INJECTED = 0x00000010

VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4  # Alt
VK_RMENU = 0xA5
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LWIN = 0x5B
VK_RWIN = 0x5C

# Window styles / messages (for non-activating overlay behavior)
GWL_EXSTYLE = -20
GWLP_WNDPROC = -4

WS_EX_NOACTIVATE = 0x08000000

WM_MOUSEACTIVATE = 0x0021
MA_NOACTIVATE = 3

WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

# DWM window attributes (Windows 11+ best-effort)
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2
DWMSBT_TRANSIENTWINDOW = 3
DWMSBT_TABBEDWINDOW = 4

# Pointer-sized Win32 types missing from ctypes.wintypes
ULONG_PTR = ctypes.c_size_t
LRESULT = wintypes.LPARAM
HHOOK = wintypes.HANDLE
LONG_PTR = ctypes.c_ssize_t

HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUTUNION),
    ]


# --- Function prototypes (argtypes/restype) ---

kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.GetCurrentThreadId.argtypes = ()
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = HHOOK

user32.UnhookWindowsHookEx.argtypes = (HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

# NOTE: no A/W suffix exists for CallNextHookEx.
user32.CallNextHookEx.argtypes = (HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT

user32.GetForegroundWindow.argtypes = ()
user32.GetForegroundWindow.restype = wintypes.HWND

user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
user32.DispatchMessageW.restype = LRESULT

user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostThreadMessageW.restype = wintypes.BOOL

user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.AttachThreadInput.restype = wintypes.BOOL

user32.CallWindowProcW.argtypes = (LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.CallWindowProcW.restype = LRESULT

user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.SendMessageW.restype = LRESULT

user32.ReleaseCapture.argtypes = ()
user32.ReleaseCapture.restype = wintypes.BOOL

user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = (
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
)
user32.SetWindowPos.restype = wintypes.BOOL

user32.BringWindowToTop.argtypes = (wintypes.HWND,)
user32.BringWindowToTop.restype = wintypes.BOOL

user32.SetActiveWindow.argtypes = (wintypes.HWND,)
user32.SetActiveWindow.restype = wintypes.HWND

# These are present on all supported Windows; on 32-bit they alias Get/SetWindowLongW.
user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongPtrW.restype = LONG_PTR

user32.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, LONG_PTR)
user32.SetWindowLongPtrW.restype = LONG_PTR

if dwmapi is not None:
    dwmapi.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD)
    dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long  # HRESULT


def get_foreground_window() -> int:
    """Return the current foreground HWND as an int.

    WinAPI returns NULL (ctypes maps this to None) when there is no foreground
    window (e.g. during desktop transitions). Treat that as 0.
    """

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0

    # Depending on ctypes/wintypes, hwnd may be an int or a c_void_p-like object.
    value = getattr(hwnd, "value", None)
    if value is None:
        try:
            return int(hwnd)
        except TypeError:
            return 0

    return int(value) if value else 0


def is_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    return bool(user32.IsWindow(wintypes.HWND(hwnd)))


def set_foreground_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    return bool(user32.SetForegroundWindow(wintypes.HWND(hwnd)))


def is_window_visible(hwnd: int) -> bool:
    if not hwnd:
        return False
    return bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))


def _get_window_thread_id(hwnd: int) -> int:
    if not hwnd:
        return 0
    pid = wintypes.DWORD(0)
    return int(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid)))


# Keep references to subclass WndProcs so they aren't GC'd.
_subclassed_wndprocs: dict[int, tuple[int, object]] = {}

def _dwm_set_window_attribute(hwnd: int, attribute: int, value: int) -> bool:
    if dwmapi is None or not is_window(hwnd):
        return False

    c_value = ctypes.c_int(int(value))
    hr = int(
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(int(attribute)),
            ctypes.byref(c_value),
            wintypes.DWORD(ctypes.sizeof(c_value)),
        )
    )
    return hr == 0


def enable_overlay_chrome(hwnd: int, *, dark: bool) -> None:
    """Best-effort DWM polish: rounded corners + acrylic-like backdrop.

    These attributes are Windows 11+ and should safely no-op on older systems.
    """

    # Rounded corners + native shadow (when the OS supports it).
    _dwm_set_window_attribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)

    # Ask for a glassy transient backdrop (acrylic-like).
    _dwm_set_window_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_TRANSIENTWINDOW)

    # Dark-mode hint for DWM effects (best-effort; depends on OS).
    _dwm_set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)


def enable_noactivate_window(hwnd: int) -> bool:
    """Best-effort: make a HWND non-activating on mouse click.

    This fixes the root cause of "overlay steals focus": if the overlay never becomes
    foreground, `SendInput` naturally lands in the already-focused target app.
    """

    if not is_window(hwnd):
        return False

    ex_style = int(user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    if not (ex_style & WS_EX_NOACTIVATE):
        user32.SetWindowLongPtrW(
            wintypes.HWND(hwnd),
            GWL_EXSTYLE,
            LONG_PTR(ex_style | WS_EX_NOACTIVATE),
        )
        user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(0),
            0,
            0,
            0,
            0,
            SWP_FRAMECHANGED | SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
        )

    if hwnd in _subclassed_wndprocs:
        return True

    orig_proc = int(user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWLP_WNDPROC))

    @WNDPROC
    def _wndproc(h_wnd, u_msg, w_param, l_param):
        if int(u_msg) == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        return user32.CallWindowProcW(LONG_PTR(orig_proc), h_wnd, u_msg, w_param, l_param)

    wndproc_ptr = ctypes.cast(_wndproc, ctypes.c_void_p).value
    if wndproc_ptr is None:
        return False

    user32.SetWindowLongPtrW(
        wintypes.HWND(hwnd),
        GWLP_WNDPROC,
        LONG_PTR(int(wndproc_ptr)),
    )
    _subclassed_wndprocs[int(hwnd)] = (orig_proc, _wndproc)
    return True


def show_window_noactivate(hwnd: int, *, topmost: bool = True) -> bool:
    """Show a window without activating it."""

    if not is_window(hwnd):
        return False

    user32.ShowWindow(wintypes.HWND(hwnd), SW_SHOWNOACTIVATE)

    insert_after = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    return bool(
        user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(insert_after),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
    )


def begin_system_move(hwnd: int) -> bool:
    """Start a native (smooth) window move from a click-and-drag gesture."""

    if not is_window(hwnd):
        return False

    # Ensure mouse capture isn't held by a child widget.
    user32.ReleaseCapture()

    # This enters the system move loop until mouse button is released.
    user32.SendMessageW(wintypes.HWND(hwnd), WM_NCLBUTTONDOWN, wintypes.WPARAM(HTCAPTION), wintypes.LPARAM(0))
    return True


def focus_window(hwnd: int) -> bool:
    """Best-effort attempt to make `hwnd` the foreground window.

    Use sparingly (fallback only): Windows can refuse focus changes depending on
    timing and foreground-lock rules.
    """

    if not is_window(hwnd):
        return False

    if get_foreground_window() == int(hwnd):
        return True

    if set_foreground_window(int(hwnd)) and get_foreground_window() == int(hwnd):
        return True

    fg = get_foreground_window()
    this_tid = int(kernel32.GetCurrentThreadId())
    fg_tid = _get_window_thread_id(fg)
    target_tid = _get_window_thread_id(int(hwnd))

    attached: list[int] = []
    try:
        for tid in {fg_tid, target_tid}:
            if tid and tid != this_tid:
                if user32.AttachThreadInput(wintypes.DWORD(this_tid), wintypes.DWORD(tid), True):
                    attached.append(tid)

        if set_foreground_window(int(hwnd)):
            user32.BringWindowToTop(wintypes.HWND(hwnd))
            user32.SetActiveWindow(wintypes.HWND(hwnd))
    finally:
        for tid in attached:
            user32.AttachThreadInput(wintypes.DWORD(this_tid), wintypes.DWORD(tid), False)

    return get_foreground_window() == int(hwnd)


def _utf16_code_units(text: str) -> List[int]:
    data = text.encode("utf-16-le")
    units: List[int] = []
    for i in range(0, len(data), 2):
        units.append(data[i] | (data[i + 1] << 8))
    return units


def send_unicode_text(text: str) -> None:
    """Type text into the currently focused application (Unicode, layout-independent)."""

    if not text:
        return

    units = _utf16_code_units(text)
    inputs: List[INPUT] = []

    for code_unit in units:
        inputs.append(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE, 0, 0)))
        inputs.append(
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
        )

    arr = (INPUT * len(inputs))(*inputs)
    sent = int(user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT)))
    if sent != len(arr):
        err = ctypes.get_last_error()
        logger.error("SendInput sent %s/%s events (err=%s)", sent, len(arr), err)


def send_unicode_char(char: str) -> None:
    if len(char) != 1:
        raise ValueError("send_unicode_char expects a single character")
    send_unicode_text(char)


KeyboardCallback = Callable[[int, int, int, bool, dict[str, bool]], bool]
# Args: vk_code, scan_code, flags, is_keydown, modifiers -> consume?


class KeyboardHook:
    """Low-level keyboard hook for global hotkey detection.

    Installed on a dedicated thread with a proper Win32 message loop.
    """

    def __init__(self) -> None:
        self._hook_handle: Optional[int] = None
        self._hook_proc: Optional[object] = None
        self._callbacks: List[KeyboardCallback] = []

        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._ready = threading.Event()
        self._shutdown = threading.Event()
        self._thread_error: Optional[BaseException] = None

        self.modifier_state: dict[str, bool] = {"ctrl": False, "alt": False, "shift": False, "win": False}

    def add_callback(self, callback: KeyboardCallback) -> None:
        self._callbacks.append(callback)

    def _update_modifier_state(self, vk_code: int, is_keydown: bool) -> None:
        if vk_code in (0x11, VK_LCONTROL, VK_RCONTROL):
            self.modifier_state["ctrl"] = is_keydown
        elif vk_code in (0x12, VK_LMENU, VK_RMENU):
            self.modifier_state["alt"] = is_keydown
        elif vk_code in (0x10, VK_LSHIFT, VK_RSHIFT):
            self.modifier_state["shift"] = is_keydown
        elif vk_code in (VK_LWIN, VK_RWIN):
            self.modifier_state["win"] = is_keydown

    def _low_level_keyboard_proc(self, n_code: int, w_param: wintypes.WPARAM, l_param: wintypes.LPARAM) -> int:
        if n_code < 0:
            return int(user32.CallNextHookEx(wintypes.HANDLE(self._hook_handle or 0), n_code, w_param, l_param))

        msg = int(w_param)
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk_code = int(kb.vkCode)
            scan_code = int(kb.scanCode)
            flags = int(kb.flags)
            is_keydown = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)

            # Avoid recursion: ignore our own injected keystrokes for hotkey matching.
            if flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED):
                return int(user32.CallNextHookEx(wintypes.HANDLE(self._hook_handle or 0), n_code, w_param, l_param))

            self._update_modifier_state(vk_code, is_keydown)
            modifiers_snapshot = self.modifier_state.copy()

            for cb in self._callbacks:
                try:
                    if cb(vk_code, scan_code, flags, is_keydown, modifiers_snapshot):
                        return 1  # consume
                except Exception:
                    logger.exception("Error in keyboard callback")

        return int(user32.CallNextHookEx(wintypes.HANDLE(self._hook_handle or 0), n_code, w_param, l_param))

    def _thread_main(self) -> None:
        self._thread_id = int(kernel32.GetCurrentThreadId())

        try:
            self._hook_proc = HOOKPROC(self._low_level_keyboard_proc)

            hmod = kernel32.GetModuleHandleW(None)
            hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, hmod, 0)
            if not hook:
                err = ctypes.get_last_error()
                raise OSError(f"SetWindowsHookExW failed (err={err})")

            self._hook_handle = int(hook)
            logger.info("Keyboard hook installed")
        except BaseException as e:
            self._thread_error = e
        finally:
            self._ready.set()

        if self._thread_error:
            return

        msg = wintypes.MSG()
        while not self._shutdown.is_set():
            r = int(user32.GetMessageW(ctypes.byref(msg), 0, 0, 0))
            if r == 0:
                break
            if r == -1:
                err = ctypes.get_last_error()
                logger.error("GetMessageW failed (err=%s)", err)
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook_handle:
            user32.UnhookWindowsHookEx(wintypes.HANDLE(self._hook_handle))
            self._hook_handle = None
        self._hook_proc = None
        logger.info("Keyboard hook thread exiting")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._ready.clear()
        self._thread_error = None

        self._thread = threading.Thread(target=self._thread_main, name="rxoverlay-keyhook", daemon=False)
        self._thread.start()

        if not self._ready.wait(timeout=2.0):
            raise TimeoutError("Keyboard hook thread did not initialize")

        if self._thread_error:
            raise self._thread_error

    def stop(self) -> None:
        if not self._thread_id:
            return

        self._shutdown.set()
        user32.PostThreadMessageW(wintypes.DWORD(self._thread_id), WM_QUIT, 0, 0)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._thread = None
        self._thread_id = None
        self._hook_handle = None
        self._hook_proc = None
        self._ready.clear()
        logger.info("Keyboard hook stopped")
