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
