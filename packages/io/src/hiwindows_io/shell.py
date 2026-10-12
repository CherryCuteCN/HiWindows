"""Windows Shell 快捷方式后端。"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from .exceptions import BackendUnavailableError
from .models.filesystem import PathLike
from .models.shell import ShortcutInfo, ShortcutResolver


def _load_wscript_shell() -> Any:
    """延迟加载 COM Shell，保证非 Windows 平台可以导入本包。"""
    try:
        client = import_module("win32com.client")
        return client.Dispatch("WScript.Shell")
    except ImportError as error:
        raise BackendUnavailableError(
            "WindowsShortcutResolver 需要在 Windows 环境安装 pywin32。"
        ) from error


class WindowsShortcutResolver:
    """通过 Windows Script Host 解析 ``.lnk`` 快捷方式。"""

    def __init__(self) -> None:
        self._shell = _load_wscript_shell()

    def resolve(self, path: PathLike) -> ShortcutInfo:
        shortcut_path = Path(path).expanduser()
        if shortcut_path.suffix.lower() != ".lnk":
            raise ValueError(f"不是 Windows 快捷方式: {shortcut_path}")
        if not shortcut_path.is_file():
            raise FileNotFoundError(shortcut_path)

        shortcut = self._shell.CreateShortcut(str(shortcut_path))
        target = str(shortcut.TargetPath).strip()
        if not target:
            raise ValueError(f"快捷方式没有目标程序: {shortcut_path}")
        working_directory = str(shortcut.WorkingDirectory).strip()
        return ShortcutInfo(
            path=shortcut_path,
            target_path=Path(target).expanduser(),
            working_directory=Path(working_directory).expanduser()
            if working_directory
            else None,
            arguments=str(shortcut.Arguments or ""),
            description=str(shortcut.Description or ""),
            icon_location=str(shortcut.IconLocation or ""),
        )


WindowsShellShortcutResolver = WindowsShortcutResolver

__all__ = [
    "ShortcutResolver",
    "WindowsShortcutResolver",
    "WindowsShellShortcutResolver",
]
