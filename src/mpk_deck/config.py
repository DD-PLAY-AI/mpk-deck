from pathlib import Path

from PySide6.QtCore import QSettings

DEFAULT_ACTIONS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "actions.yaml"

ORG_NAME = "DD-PLAY-AI"
APP_NAME = "mpk-deck"

ACCENT_HEX = "#3a6df0"
ACCENT_RGB = "58,109,240"


def _get_settings(ini_path: str | None = None) -> QSettings:
    if ini_path:
        return QSettings(ini_path, QSettings.Format.IniFormat)
    return QSettings(ORG_NAME, APP_NAME)


def load_last_mode(default: str = "mini", *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/mode", default)


def save_last_mode(mode: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/mode", mode)
    settings.sync()


def load_last_theme(default: str = "dark", *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/theme", default)


def save_last_theme(theme: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/theme", theme)
    settings.sync()


def load_last_always_on_top(default: bool = False, *, ini_path: str | None = None) -> bool:
    settings = _get_settings(ini_path)
    return settings.value("ui/always_on_top", default, type=bool)


def save_last_always_on_top(always_on_top: bool, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/always_on_top", always_on_top)
    settings.sync()


def load_last_accent(default: str = ACCENT_HEX, *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/accent", default)


def save_last_accent(accent_hex: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/accent", accent_hex)
    settings.sync()


def load_last_knob_style(default: str = "A", *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/knob_style", default)


def save_last_knob_style(style: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/knob_style", style)
    settings.sync()
