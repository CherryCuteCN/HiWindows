"""Windows Shell 操作端口与模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .filesystem import PathLike


@dataclass(frozen=True, slots=True)
class ShortcutInfo:
    """Windows 快捷方式解析结果。"""

    path: Path
    target_path: Path
    working_directory: Path | None = None
    arguments: str = ""
    description: str = ""
    icon_location: str = ""


@runtime_checkable
class ShortcutResolver(Protocol):
    """快捷方式解析端口。"""

    def resolve(self, path: PathLike) -> ShortcutInfo:
        """解析快捷方式并返回其目标。"""
        ...
