"""Configuration management for RxOverlay."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "version": 1,
    "enabled_on_startup": True,
    "overlay": {
        "position": {"x": 100, "y": 100},
        "always_on_top": True,
        "opacity": 0.9,
        "theme": "light",
        "auto_hide_after_action_ms": 0,
    },
    "hotkeys": {
        "toggle_enabled": {"mods": ["CTRL", "ALT"], "scancode": 42},  # Left Shift
        "exit": {"mods": ["CTRL", "ALT"], "scancode": 41},  # Grave/Tilde
        "send_r": {"mods": [], "scancode": 19},  # R key
        "send_x": {"mods": [], "scancode": 45},  # X key
    },
    "injection": {
        "method": "sendinput",
        "use_keyup": True,
        "inter_key_delay_ms": 10,
        "fallback_hide_overlay_before_send": True,
    },
    "logging": {
        "level": "INFO",
        "file": "rxoverlay.log",
    },
}


def get_config_dir() -> Path:
    """Get the configuration directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".config"
    return base / "RxOverlay"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def get_state_path() -> Path:
    """Get the state file path."""
    return get_config_dir() / "state.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from file, creating defaults if needed."""
    config_path = get_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # Version migration
            if config.get("version", 0) < DEFAULT_CONFIG["version"]:
                logger.info(f"Migrating config from version {config.get('version', 0)} to {DEFAULT_CONFIG['version']}")
                config = migrate_config(config)
            
            # Fill in missing defaults
            config = merge_defaults(config, DEFAULT_CONFIG)
            logger.debug(f"Loaded config from {config_path}")
            return config
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load config from {config_path}: {e}. Using defaults.")
    
    # Create default config
    config = DEFAULT_CONFIG.copy()
    save_config(config)
    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.debug(f"Saved config to {config_path}")
    except IOError as e:
        logger.error(f"Failed to save config to {config_path}: {e}")


def load_state() -> Dict[str, Any]:
    """Load runtime state from file."""
    state_path = get_state_path()

    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Fill any missing keys for forwards/backwards compatibility.
            if "enabled" not in state:
                state["enabled"] = True
            if "minimized" not in state:
                state["minimized"] = False
            return state
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state from {state_path}: {e}")

    return {"enabled": True, "minimized": False}


def save_state(state: Dict[str, Any]) -> None:
    """Save runtime state to file."""
    state_path = get_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state to {state_path}")
    except IOError as e:
        logger.error(f"Failed to save state to {state_path}: {e}")


def merge_defaults(config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge defaults into config."""
    result = defaults.copy()
    
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_defaults(value, result[key])
        else:
            result[key] = value
    
    return result


def migrate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate configuration to latest version."""
    # For now, just merge with latest defaults
    return merge_defaults(config, DEFAULT_CONFIG)