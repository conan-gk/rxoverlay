"""Global hotkey handling for RxOverlay.

This module must be thread-safe:
- KeyboardHook callbacks run on a dedicated hook thread.
- Do NOT call Tkinter from the hook thread.

The app should provide callbacks that are safe from any thread
(e.g., enqueue into a Queue and handle in Tk via `after`).
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from rxoverlay.winapi import KeyboardHook

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Matches scan-code-based hotkeys and triggers callbacks."""

    def __init__(self, config: dict):
        self._config = config
        self._hook = KeyboardHook()
        self._running = False

        self._on_toggle_enabled: Optional[Callable[[], None]] = None
        self._on_exit: Optional[Callable[[], None]] = None
        self._on_send_r: Optional[Callable[[], None]] = None
        self._on_send_x: Optional[Callable[[], None]] = None

        # Track pressed scancodes to avoid repeat firing while held.
        self._pressed_scancodes: set[int] = set()

    def set_callbacks(
        self,
        *,
        on_toggle_enabled: Callable[[], None],
        on_exit: Callable[[], None],
        on_send_r: Callable[[], None],
        on_send_x: Callable[[], None],
    ) -> None:
        self._on_toggle_enabled = on_toggle_enabled
        self._on_exit = on_exit
        self._on_send_r = on_send_r
        self._on_send_x = on_send_x

    @staticmethod
    def _current_mods(modifiers: dict[str, bool]) -> set[str]:
        mods: set[str] = set()
        if modifiers.get("ctrl"):
            mods.add("CTRL")
        if modifiers.get("alt"):
            mods.add("ALT")
        if modifiers.get("shift"):
            mods.add("SHIFT")
        if modifiers.get("win"):
            mods.add("WIN")
        return mods

    def _matches_hotkey(self, scan_code: int, modifiers: dict[str, bool], hotkey_config: dict) -> bool:
        """Match a single triggering scan code + exact modifier set."""
        if not hotkey_config:
            return False

        target_scan = hotkey_config.get("scancode")
        if target_scan is None:
            return False

        if int(target_scan) != int(scan_code):
            return False

        required_mods = set(hotkey_config.get("mods", []))
        return required_mods == self._current_mods(modifiers)

    def _handle_key_event(
        self,
        vk_code: int,
        scan_code: int,
        flags: int,
        is_keydown: bool,
        modifiers: dict[str, bool],
    ) -> bool:
        """KeyboardHook callback. Return True to consume the event."""
        # We only trigger actions on key-down.
        if not is_keydown:
            self._pressed_scancodes.discard(int(scan_code))
            return False

        # Debounce repeats while key is held.
        if int(scan_code) in self._pressed_scancodes:
            return False
        self._pressed_scancodes.add(int(scan_code))

        hotkeys = self._config.get("hotkeys", {})

        # Toggle enabled
        if self._matches_hotkey(scan_code, modifiers, hotkeys.get("toggle_enabled", {})):
            logger.debug("Hotkey: toggle_enabled")
            if self._on_toggle_enabled:
                self._on_toggle_enabled()
            return True

        # Exit
        if self._matches_hotkey(scan_code, modifiers, hotkeys.get("exit", {})):
            logger.debug("Hotkey: exit")
            if self._on_exit:
                self._on_exit()
            return True

        # Send r / x
        if self._matches_hotkey(scan_code, modifiers, hotkeys.get("send_r", {})):
            logger.debug("Hotkey: send_r")
            if self._on_send_r:
                self._on_send_r()
            return True

        if self._matches_hotkey(scan_code, modifiers, hotkeys.get("send_x", {})):
            logger.debug("Hotkey: send_x")
            if self._on_send_x:
                self._on_send_x()
            return True

        return False

    def start(self) -> None:
        if self._running:
            return

        self._hook.add_callback(self._handle_key_event)
        self._hook.start()
        self._running = True
        logger.info("Hotkey manager started")

    def stop(self) -> None:
        if not self._running:
            return

        self._hook.stop()
        self._running = False
        self._pressed_scancodes.clear()
        logger.info("Hotkey manager stopped")