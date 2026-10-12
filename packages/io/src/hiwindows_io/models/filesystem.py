"""文件系统端口。"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

type PathLike = str | os.PathLike[str]
type FileSystemProgressCallback = Callable[["FileSystemProgress"], None]


@dataclass(frozen=True, slots=True)
class FileSystemProgress:
    """文件系统批量操作的进度。"""

    operation: str
    current_path: Path
    completed_items: int
    total_items: int


@runtime_checkable
class FileSystem(Protocol):
    """文件系统操作端口。

    这是调用方依赖的最小契约，具体实现不需要继承它。
    """

    def exists(self, path: PathLike) -> bool:
        """判断路径是否存在。"""
        ...

    def is_file(self, path: PathLike) -> bool:
        """判断路径是否为文件。"""
        ...

    def is_dir(self, path: PathLike) -> bool:
        """判断路径是否为目录。"""
        ...

    def read_bytes(self, path: PathLike) -> bytes:
        """读取文件的原始字节。"""
        ...

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        """以覆盖方式写入原始字节。"""
        ...

    def remove_file(self, path: PathLike) -> None:
        """删除文件。"""
        ...

    def remove_dir(self, path: PathLike) -> None:
        """删除空目录。"""
        ...

    def remove_tree(
        self,
        path: PathLike,
        *,
        on_progress: FileSystemProgressCallback | None = None,
    ) -> None:
        """递归删除目录，并在删除每个项目后报告进度。"""
        ...

    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        """创建目录。"""
        ...

    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        """列出目录下的直接子项。"""
        ...

    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        """复制文件。"""
        ...

    def move_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        """移动文件。"""
        ...

    def read_text(
        self,
        path: PathLike,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> str:
        """按指定编码读取文本文件。"""
        ...

    def write_text(
        self,
        path: PathLike,
        data: str,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> None:
        """按指定编码覆盖写入文本文件。"""
        ...
