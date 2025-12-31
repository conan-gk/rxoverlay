"""Tkinter overlay UI for RxOverlay."""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, Optional

from rxoverlay.winapi import begin_system_move, enable_noactivate_window, show_window_noactivate

logger = logging.getLogger(__name__)


class OverlayWindow(tk.Tk):
    """Minimal overlay window with r/x buttons."""

    def __init__(self, config: dict):
        super().__init__()

        self.config = config
        self.enabled = True

        self.on_r_callback: Optional[Callable[[], None]] = None
        self.on_x_callback: Optional[Callable[[], None]] = None
        self.on_toggle_callback: Optional[Callable[[], None]] = None
        self.on_minimize_callback: Optional[Callable[[], None]] = None
        self.on_position_change: Optional[Callable[[dict], None]] = None
        self._restore_win: Optional[tk.Toplevel] = None

        # Drag state
        self._drag_start_x: Optional[int] = None
        self._drag_start_y: Optional[int] = None
        self._drag_window_x: Optional[int] = None
        self._drag_window_y: Optional[int] = None

        self._pending_drag_pos: Optional[tuple[int, int]] = None
        self._drag_move_scheduled = False

        self._setup_window()
        self._setup_ui()
        self._restore_position()

    def _setup_window(self) -> None:
        self.overrideredirect(True)

        if self.config.get("overlay", {}).get("always_on_top", True):
            self.wm_attributes("-topmost", True)

        opacity = float(self.config.get("overlay", {}).get("opacity", 0.9))
        self.wm_attributes("-alpha", opacity)

        self.geometry("140x70+100+100")
        self.withdraw()

        # Best-effort: keep the overlay non-activating so clicks don't steal focus.
        try:
            self.update_idletasks()
            enable_noactivate_window(int(self.winfo_id()))
        except Exception:
            logger.exception("Failed to set overlay NOACTIVATE")

    def _setup_ui(self) -> None:
        theme = self.config.get("overlay", {}).get("theme", "light")

        style = ttk.Style()
        style.theme_use("clam")

        if theme == "dark":
            style.configure(
                "Overlay.TButton",
                font=("Segoe UI", 9),
                padding=4,
                relief="flat",
                background="#2d3748",
                foreground="#ffffff",
                borderwidth=1,
            )
            style.map("Overlay.TButton", background=[("active", "#4a5568")])
            self.configure(bg="#2d3748")
        else:
            style.configure(
                "Overlay.TButton",
                font=("Segoe UI", 9),
                padding=4,
                relief="flat",
                background="#f8f9fa",
                foreground="#333333",
                borderwidth=1,
            )
            style.map("Overlay.TButton", background=[("active", "#e9ecef")])
            self.configure(bg="#f8f9fa")

        # Borderless/minimal variant for the minimize button (inherits Overlay.TButton).
        style.configure("Min.Overlay.TButton", borderwidth=0, relief="flat")

        # Layout: small top drag-handle + controls row.
        container = ttk.Frame(self, padding=(4, 3, 4, 4))
        container.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar: drag handle (left) + minimize button (right).
        top_bar = ttk.Frame(container, padding=(0, 0, 0, 2))
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        # Dedicated drag handle (drag bindings ONLY here).
        drag_handle = ttk.Frame(top_bar, padding=(8, 2))
        drag_handle.grid(row=0, column=0, sticky="ew")

        # Minimize button: small + top-right.
        self.btn_min = ttk.Button(
            top_bar,
            text="–",
            width=2,
            style="Min.Overlay.TButton",
            command=self._on_minimize_click,
            takefocus=0,
        )
        self.btn_min.grid(row=0, column=1, sticky="e", padx=(6, 0))

        controls = ttk.Frame(container)
        controls.grid(row=1, column=0, sticky="ew")

        self.btn_r = ttk.Button(
            controls,
            text="r",
            width=3,
            style="Overlay.TButton",
            command=self._on_r_click,
            takefocus=0,
        )
        self.btn_r.pack(side="left", padx=(0, 2))

        self.btn_x = ttk.Button(
            controls,
            text="x",
            width=3,
            style="Overlay.TButton",
            command=self._on_x_click,
            takefocus=0,
        )
        self.btn_x.pack(side="left", padx=2)

        self.btn_toggle = ttk.Button(
            controls,
            text="◷",
            width=3,
            style="Overlay.TButton",
            command=self._on_toggle_click,
            takefocus=0,
        )
        self.btn_toggle.pack(side="left", padx=(2, 0))

        # Dragging: bind only on non-button surfaces.
        drag_handle.bind("<ButtonPress-1>", self._on_drag_start, add="+")
        drag_handle.bind("<B1-Motion>", self._on_drag_motion, add="+")
        drag_handle.bind("<ButtonRelease-1>", self._on_drag_end, add="+")

        # Dragging: bind across our own widgets so mouse move events remain
        # reliable even when the window is non-activating.
        for widget in (self, container, top_bar, drag_handle, controls):
            widget.bind("<ButtonPress-1>", self._on_drag_start, add="+")
            widget.bind("<B1-Motion>", self._on_drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", self._on_drag_end, add="+")

    def _on_r_click(self) -> None:
        if self.enabled and self.on_r_callback:
            try:
                self.on_r_callback()
                self._maybe_auto_hide()
            except Exception:
                logger.exception("Error in R callback")

    def _on_x_click(self) -> None:
        if self.enabled and self.on_x_callback:
            try:
                self.on_x_callback()
                self._maybe_auto_hide()
            except Exception:
                logger.exception("Error in X callback")

    def _on_toggle_click(self) -> None:
        if self.on_toggle_callback:
            try:
                self.on_toggle_callback()
            except Exception:
                logger.exception("Error in toggle callback")

    def _on_minimize_click(self) -> None:
        if self.on_minimize_callback:
            try:
                self.on_minimize_callback()
            except Exception:
                logger.exception("Error in minimize callback")

    def _on_drag_start(self, event) -> None:
        # Do not start a drag gesture on button clicks.
        if event.widget in (self.btn_r, self.btn_x, self.btn_toggle, self.btn_min):
            return

        # Tk-driven dragging
        self._drag_start_x = int(event.x_root)
        self._drag_start_y = int(event.y_root)
        self._drag_window_x = self.winfo_x()
        self._drag_window_y = self.winfo_y()



    def _apply_pending_drag_move(self) -> None:
        self._drag_move_scheduled = False
        if self._pending_drag_pos is None:
            return

        x, y = self._pending_drag_pos
        self._pending_drag_pos = None
        self.geometry(f"+{x}+{y}")

    def _on_drag_motion(self, event) -> None:
        if (
            self._drag_start_x is None
            or self._drag_start_y is None
            or self._drag_window_x is None
            or self._drag_window_y is None
        ):
            return

        new_x = self._drag_window_x + (int(event.x_root) - self._drag_start_x)
        new_y = self._drag_window_y + (int(event.y_root) - self._drag_start_y)

        self._pending_drag_pos = (new_x, new_y)
        if not self._drag_move_scheduled:
            self._drag_move_scheduled = True
            self.after(16, self._apply_pending_drag_move)

    def _on_drag_end(self, event) -> None:
        self._apply_pending_drag_move()
        self._save_position()

        self._drag_start_x = None
        self._drag_start_y = None
        self._drag_window_x = None
        self._drag_window_y = None
        self._pending_drag_pos = None
        self._drag_move_scheduled = False

        # Release mouse grab.
        try:
            self.grab_release()
        except Exception:
            pass

    def _maybe_auto_hide(self) -> None:
        auto_hide_ms = int(self.config.get("overlay", {}).get("auto_hide_after_action_ms", 0))
        if auto_hide_ms > 0:
            self.after(auto_hide_ms, self.hide)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.btn_toggle.configure(text="◶" if enabled else "◷")

        state = "normal" if enabled else "disabled"
        self.btn_r.configure(state=state)
        self.btn_x.configure(state=state)
        self.btn_min.configure(state=state)

    def show(self) -> None:
        self.deiconify()
        try:
            show_window_noactivate(int(self.winfo_id()), topmost=bool(self.config.get("overlay", {}).get("always_on_top", True)))
        except Exception:
            pass
        logger.debug("Overlay shown")

    def hide(self) -> None:
        self.withdraw()
        logger.debug("Overlay hidden")

    def minimize(self) -> None:
        """Hide the main overlay and show a tiny restore widget."""
        if self._restore_win is None or not self._restore_win.winfo_exists():
            self._restore_win = tk.Toplevel(self)
            self._restore_win.overrideredirect(True)
            self._restore_win.wm_attributes("-topmost", True)
            try:
                self._restore_win.wm_attributes("-alpha", 0.85)
            except Exception:
                pass

            # Place near the overlay's current position.
            x = self.winfo_x()
            y = self.winfo_y()
            self._restore_win.geometry(f"50x24+{x}+{y}")

            btn = ttk.Button(self._restore_win, text="↑", width=3, command=self._on_restore_click, takefocus=0)
            btn.pack(fill="both", expand=True)

            # Best-effort: keep the restore widget non-activating.
            try:
                self._restore_win.update_idletasks()
                enable_noactivate_window(int(self._restore_win.winfo_id()))
            except Exception:
                logger.exception("Failed to set restore widget NOACTIVATE")

            self._restore_win.bind("<Button-1>", lambda e: self._on_restore_click())

        self.hide()
        self._restore_win.deiconify()
        try:
            show_window_noactivate(int(self._restore_win.winfo_id()), topmost=True)
        except Exception:
            pass

    def _on_restore_click(self) -> None:
        if self.on_restore_callback:
            try:
                self.on_restore_callback()
                return
            except Exception:
                logger.exception("Error in restore callback")

        self.restore()

    def restore(self) -> None:
        """Restore the main overlay and remove the restore widget."""
        try:
            if self._restore_win is not None and self._restore_win.winfo_exists():
                self._restore_win.destroy()
        except Exception:
            logger.exception("Failed to destroy restore widget")
        finally:
            self._restore_win = None

        self.show()

    def get_position(self) -> dict:
        return {"x": self.winfo_x(), "y": self.winfo_y()}

    def set_position(self, x: int, y: int) -> None:
        self.geometry(f"+{x}+{y}")

    def _restore_position(self) -> None:
        position = self.config.get("overlay", {}).get("position", {"x": 100, "y": 100})
        self.set_position(int(position["x"]), int(position["y"]))

    def _save_position(self) -> None:
        if not self.on_position_change:
            return

        position = self.get_position()
        if hasattr(self, "_save_timer_id") and self._save_timer_id:
            self.after_cancel(self._save_timer_id)
        self._save_timer_id = self.after(500, lambda cb=self.on_position_change: cb(position))

    def is_own_hwnd(self, hwnd: int) -> bool:
        try:
            if hwnd == int(self.winfo_id()):
                return True
        except Exception:
            pass

        try:
            if self._restore_win is not None and self._restore_win.winfo_exists():
                if hwnd == int(self._restore_win.winfo_id()):
                    return True
        except Exception:
            pass

        return False

    def set_callbacks(
        self,
        *,
        on_r: Callable[[], None],
        on_x: Callable[[], None],
        on_toggle: Callable[[], None],
        on_minimize: Callable[[], None],
        on_restore: Callable[[], None],
        on_position_change: Callable[[dict], None],
    ) -> None:
        self.on_r_callback = on_r
        self.on_x_callback = on_x
        self.on_toggle_callback = on_toggle
        self.on_minimize_callback = on_minimize
        self.on_restore_callback = on_restore
        self.on_position_change = on_position_change
