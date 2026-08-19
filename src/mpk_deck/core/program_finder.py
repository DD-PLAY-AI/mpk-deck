import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstalledProgram:
    name: str
    path: str


def list_installed_programs(
    *,
    search_dirs: list[Path] | None = None,
    resolver: Callable[[Path], str | None] | None = None,
) -> list[InstalledProgram]:
    """Scan Start Menu shortcut folders and resolve each .lnk to its target exe.

    Later search_dirs never override a name already found in an earlier one.
    """
    dirs = search_dirs if search_dirs is not None else _default_search_dirs()
    resolve = resolver or _resolve_shortcut_target

    programs: dict[str, str] = {}
    for directory in dirs:
        if not directory.exists():
            continue
        for lnk_path in directory.rglob("*.lnk"):
            name = lnk_path.stem
            if name in programs:
                continue
            target = resolve(lnk_path)
            if not target:
                continue
            programs[name] = target

    return sorted(
        (InstalledProgram(name=name, path=path) for name, path in programs.items()),
        key=lambda program: program.name.lower(),
    )


def _default_search_dirs() -> list[Path]:
    dirs = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        dirs.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return dirs


def _resolve_shortcut_target(lnk_path: Path) -> str | None:
    """Resolve a .lnk shortcut's target path using the Windows Shell COM API."""
    import win32com.client

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        target = shortcut.Targetpath
    except Exception:
        logger.warning("failed to resolve shortcut %s", lnk_path, exc_info=True)
        return None
    return target or None
