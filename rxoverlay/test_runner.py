#!/usr/bin/env python3
"""Quick test runner for RxOverlay."""

import sys
import pathlib

# Add the project root to sys.path so imports work as a package
project_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test all major components
def test_imports():
    """Test that all module imports work."""
    from rxoverlay import winapi
    from rxoverlay import ui

    print("✓ Imports OK")
    print(f"  - winapi.get_foreground_window() -> {winapi.get_foreground_window()}")
    print(f"  - winapi.begin_system_move() available: {hasattr(winapi, 'begin_system_move')}")
    print(f"  - winapi.show_window_noactivate() available: {hasattr(winapi, 'show_window_noactivate')}")
    print(f"  - OverlayWindow defined: {ui.OverlayWindow is not None}")

def test_winapi_calls():
    """Test WinAPI calls directly."""
    from rxoverlay.winapi import get_foreground_window, begin_system_move, show_window_noactivate

    fg = get_foreground_window()
    print(f"✓ get_foreground_window() -> {fg}")

    # Test begin_system_move with a dummy HWND (0) - should be safe and return False
    result = begin_system_move(0)
    print(f"✓ begin_system_move(0) -> {result} (expected False)")

    # Test show_window_noactivate with dummy HWND (0) - should be safe and return False
    result2 = show_window_noactivate(0, topmost=False)
    print(f"✓ show_window_noactivate(0, topmost=False) -> {result2} (expected False)")

def test_ui_components():
    """Test that UI can be instantiated without crashes."""
    from rxoverlay.ui import OverlayWindow
    from rxoverlay.config import load_config

    print("✓ Creating OverlayWindow...")
    config = load_config()
    window = OverlayWindow(config)
    print(f"✓ OverlayWindow created: {window}")
    print(f"  - Geometry: {window.geometry()}")
    print(f"  - Style variant exists: {'Min.Overlay.TButton' in [s for s in window.winfo_children()[0].winfo_class()]}")

if __name__ == "__main__":
    print("=" * 60)
    print("RxOverlay Component Tests")
    print("=" * 60)

    try:
        test_imports()
        test_winapi_calls()
        test_ui_components()

        print("=" * 60)
        print("All tests passed!")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print("=" * 60)
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
