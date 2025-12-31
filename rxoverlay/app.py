"""Main application orchestrator for RxOverlay."""

from __future__ import annotations

import logging
import queue
import time
from typing import Optional

from .config import load_config, load_state, save_config, save_state
from .hotkeys import HotkeyManager
from .logging_setup import setup_logging
from .ui import OverlayWindow
from .winapi import focus_window, get_foreground_window, is_window_visible, send_unicode_text

logger = logging.getLogger(__name__)


class RxOverlayApp:
    """Main application class that orchestrates all components."""

    def __init__(self):
        self.config = load_config()
        self.state = load_state()

        log_config = self.config.get("logging", {})
        setup_logging(log_config.get("level", "INFO"), log_config.get("file", "rxoverlay.log"))

        self.overlay: Optional[OverlayWindow] = None
        self.hotkey_manager: Optional[HotkeyManager] = None

        self.enabled = bool(self.state.get("enabled", True))
        self.minimized = bool(self.state.get("minimized", False))

        self._last_target_hwnd: Optional[int] = None
        self._action_queue: "queue.Queue[str]" = queue.Queue()

        logger.info("RxOverlay initialized")

    def _enqueue_action(self, action: str) -> None:
        # Called from the keyboard hook thread.
        self._action_queue.put(action)

    def _process_actions(self) -> None:
        if not self.overlay:
            return

        try:
            while True:
                action = self._action_queue.get_nowait()

                if action == "toggle":
                    if self.minimized:
                        self._restore_overlay()
                    else:
                        self._toggle_enabled()

                elif action == "exit":
                    self.shutdown()
                    return

                elif action == "send_r":
                    self._inject_character("r")

                elif action == "send_x":
                    self._inject_character("x")

                else:
                    logger.warning("Unknown action: %s", action)
        except queue.Empty:
            pass
        finally:
            # Poll again.
            self.overlay.after(25, self._process_actions)

    def _poll_foreground(self) -> None:
        if not self.overlay:
            return

        try:
            hwnd = get_foreground_window()
            if hwnd and not self.overlay.is_own_hwnd(hwnd) and is_window_visible(hwnd):
                self._last_target_hwnd = hwnd
        except Exception:
            logger.exception("Foreground polling failed")
        finally:
            self.overlay.after(100, self._poll_foreground)

    def _pick_target_hwnd(self) -> Optional[int]:
        try:
            current = get_foreground_window()
        except Exception:
            logger.exception("Failed to query foreground window")
            current = 0

        if self.overlay and self.overlay.is_own_hwnd(current):
            return self._last_target_hwnd
        return current if current else self._last_target_hwnd

    def _inject_character(self, char: str) -> None:
        if not self.enabled:
            return

        target = self._pick_target_hwnd()
        if not target:
            logger.warning("No visible target window - please focus another app first")
            return

        # Always hide the overlay before injection to ensure the target window gets focus.
        # This is more aggressive than the previous fallback-only approach, but more reliable.
        was_visible = False
        if self.overlay:
            try:
                was_visible = bool(self.overlay.winfo_viewable())
                if was_visible:
                    self.overlay.hide()
                    time.sleep(0.02)
            except Exception:
                pass

        # Attempt to return focus to the target window.
        focused = focus_window(target)
        if not focused:
            logger.debug("Failed to restore focus to target (%s); aborting injection", target)
            # Restore overlay visibility before aborting.
            if was_visible and self.overlay:
                try:
                    self.overlay.show()
                except Exception:
                    pass
            return

        send_unicode_text(char)
        logger.debug("Injected '%s'", char)

        # Restore overlay visibility after successful injection.
        if was_visible and self.overlay:
            try:
                self.overlay.show()
            except Exception:
                pass

    def _toggle_enabled(self) -> None:
        self.enabled = not self.enabled
        self.state["enabled"] = self.enabled

        if self.overlay:
            self.overlay.set_enabled(self.enabled)

        if not self.enabled:
            self.minimized = False
            self.state["minimized"] = False
            if self.overlay:
                self.overlay.hide()
        else:
            if self.overlay:
                if self.minimized:
                    self.overlay.minimize()
                else:
                    self.overlay.show()

        save_state(self.state)
        logger.info("RxOverlay %s", "enabled" if self.enabled else "disabled")

    def _minimize_overlay(self) -> None:
        if not self.enabled or not self.overlay:
            return
        self.minimized = True
        self.state["minimized"] = True
        save_state(self.state)
        self.overlay.minimize()
        logger.info("Overlay minimized")

    def _restore_overlay(self) -> None:
        if not self.overlay:
            return
        self.minimized = False
        self.state["minimized"] = False
        save_state(self.state)
        self.overlay.restore()
        logger.info("Overlay restored")

    def _on_position_change(self, position: dict) -> None:
        self.config["overlay"]["position"] = position
        save_config(self.config)
        logger.debug("Saved position: %s", position)

    def run(self) -> None:
        logger.info("Starting RxOverlay...")

        self.overlay = OverlayWindow(self.config)
        self.overlay.set_callbacks(
            on_r=lambda: self._inject_character("r"),
            on_x=lambda: self._inject_character("x"),
            on_toggle=self._toggle_enabled,
            on_minimize=self._minimize_overlay,
            on_restore=self._restore_overlay,
            on_position_change=self._on_position_change,
        )

        self.overlay.set_enabled(self.enabled)

        self.hotkey_manager = HotkeyManager(self.config)
        self.hotkey_manager.set_callbacks(
            on_toggle_enabled=lambda: self._enqueue_action("toggle"),
            on_exit=lambda: self._enqueue_action("exit"),
            on_send_r=lambda: self._enqueue_action("send_r"),
            on_send_x=lambda: self._enqueue_action("send_x"),
        )
        self.hotkey_manager.start()

        # Schedule periodic tasks in the Tk thread.
        self.overlay.after(25, self._process_actions)
        self.overlay.after(100, self._poll_foreground)

        if self.enabled and self.config.get("enabled_on_startup", True):
            if self.minimized:
                self.overlay.minimize()
            else:
                self.overlay.show()

        logger.info("RxOverlay running")
        try:
            self.overlay.mainloop()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        logger.info("Shutting down RxOverlay...")

        if self.hotkey_manager:
            try:
                self.hotkey_manager.stop()
            except Exception:
                logger.exception("Failed to stop hotkey manager")

        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass

        logger.info("RxOverlay shutdown complete")


def main() -> None:
    RxOverlayApp().run()


if __name__ == "__main__":
    main()
