"""Tkinter overlay UI for RxOverlay."""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, Optional

from rxoverlay.winapi import begin_system_move, enable_noactivate_window, enable_overlay_chrome, show_window_noactivate

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

        # Initial position; final size is computed from content to avoid clipping.
        self.geometry("10x10+100+100")
        self.withdraw()

        # Best-effort: keep the overlay non-activating so clicks don't steal focus.
        try:
            self.update_idletasks()
            hwnd = int(self.winfo_id())
            enable_noactivate_window(hwnd)
            enable_overlay_chrome(hwnd, dark=self.config.get("overlay", {}).get("theme", "light") == "dark")
        except Exception:
            logger.exception("Failed to set overlay NOACTIVATE")

    def _size_to_content(self) -> None:
        self.update_idletasks()
        req_w = int(self.winfo_reqwidth())
        req_h = int(self.winfo_reqheight())
        self.geometry(f"{req_w}x{req_h}+{self.winfo_x()}+{self.winfo_y()}")

    def _setup_ui(self) -> None:
        theme = self.config.get("overlay", {}).get("theme", "light")
        dark = theme == "dark"

        style = ttk.Style()
        style.theme_use("clam")

        if dark:
            surface_bg = "#1c1c1e"
            stroke = "#2c2c2e"
            button_bg = "#2c2c2e"
            button_bg_hover = "#3a3a3c"
            button_bg_pressed = "#242426"
            fg = "#ffffff"
            fg_disabled = "#8e8e93"
            style.configure(
                "Overlay.TButton",
                font=("Segoe UI Variable Text", 10),
                padding=(0, 3),
                relief="flat",
                background=button_bg,
                foreground=fg,
                borderwidth=0,
            )
            style.map(
                "Overlay.TButton",
                background=[
                    ("pressed", button_bg_pressed),
                    ("active", button_bg_hover),
                    ("disabled", surface_bg),
                ],
                foreground=[("disabled", fg_disabled)],
            )
            style.configure(
                "Overlay.Min.TButton",
                font=("Segoe UI Variable Text", 10),
                padding=(1, 0),
                relief="flat",
                background=surface_bg,
                foreground=fg,
                borderwidth=0,
            )
            style.map(
                "Overlay.Min.TButton",
                background=[
                    ("pressed", button_bg_pressed),
                    ("active", button_bg_hover),
                    ("disabled", surface_bg),
                ]
            )
            self.configure(bg=stroke)
        else:
            surface_bg = "#f2f2f7"
            stroke = "#d1d1d6"
            button_bg = "#ffffff"
            button_bg_hover = "#f5f5f7"
            button_bg_pressed = "#e5e5ea"
            fg = "#1c1c1e"
            fg_disabled = "#8e8e93"
            style.configure(
                "Overlay.TButton",
                font=("Segoe UI Variable Text", 10),
                padding=(0, 3),
                relief="flat",
                background=button_bg,
                foreground=fg,
                borderwidth=0,
            )
            style.map(
                "Overlay.TButton",
                background=[
                    ("pressed", button_bg_pressed),
                    ("active", button_bg_hover),
                    ("disabled", surface_bg),
                ],
                foreground=[("disabled", fg_disabled)],
            )
            style.configure(
                "Overlay.Min.TButton",
                font=("Segoe UI Variable Text", 10),
                padding=(1, 0),
                relief="flat",
                background=surface_bg,
                foreground=fg,
                borderwidth=0,
            )
            style.map(
                "Overlay.Min.TButton",
                background=[
                    ("pressed", button_bg_pressed),
                    ("active", button_bg_hover),
                    ("disabled", surface_bg),
                ]
            )
            self.configure(bg=stroke)

        style.configure("Overlay.Surface.TFrame", background=surface_bg)
        style.configure("Overlay.Stroke.TFrame", background=stroke)

        # Compact layout: r/x row with a tiny minimize on the right.
        outer = ttk.Frame(self, style="Overlay.Stroke.TFrame", padding=1)
        outer.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        container = ttk.Frame(outer, style="Overlay.Surface.TFrame", padding=(2, 2))
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        controls = ttk.Frame(container, style="Overlay.Surface.TFrame")
        controls.grid(row=0, column=0, sticky="sw")
        controls.grid_columnconfigure(0, weight=0)
        controls.grid_columnconfigure(1, weight=0)

        min_frame = ttk.Frame(container, style="Overlay.Surface.TFrame")
        min_frame.grid(row=0, column=0, sticky="ne")

        self.btn_r = ttk.Button(
            controls,
            text="r",
            style="Overlay.TButton",
            command=self._on_r_click,
            takefocus=0,
        )
        self.btn_r.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_x = ttk.Button(
            controls,
            text="x",
            style="Overlay.TButton",
            command=self._on_x_click,
            takefocus=0,
        )
        self.btn_x.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.btn_min = ttk.Button(
            min_frame,
            text="˅",
            style="Overlay.Min.TButton",
            command=self._on_minimize_click,
            takefocus=0,
            width=1,
        )
        self.btn_min.pack()

        # Dragging: bind across our own widgets so mouse move events remain
        # reliable even when the window is non-activating.
        for widget in (self, outer, container, controls, min_frame):
            widget.bind("<ButtonPress-1>", self._on_drag_start, add="+")
            widget.bind("<B1-Motion>", self._on_drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", self._on_drag_end, add="+")

        self._size_to_content()

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
        if event.widget in (self.btn_r, self.btn_x, self.btn_min):
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

            btn = ttk.Button(self._restore_win, text="˄", width=3, command=self._on_restore_click, takefocus=0)
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
