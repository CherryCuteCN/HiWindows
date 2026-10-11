"""文件系统抽象接口。"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

type PathLike = str | os.PathLike[str]


class FileSystem(ABC):
    """文件系统操作契约。"""

    @abstractmethod
    def exists(self, path: PathLike) -> bool:
        """判断路径是否存在。"""
        ...

    @abstractmethod
    def read_bytes(self, path: PathLike) -> bytes:
        """读取文件的原始字节。"""
        ...

    @abstractmethod
    def write_bytes(self, path: PathLike, data: bytes) -> None:
        """以覆盖方式写入原始字节。"""
        ...

    @abstractmethod
    def remove_file(self, path: PathLike) -> None:
        """删除文件。"""
        ...

    @abstractmethod
    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        """创建目录。"""
        ...

    @abstractmethod
    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        """列出目录下的直接子项。"""
        ...

    @abstractmethod
    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        """复制文件。"""
        ...

    @abstractmethod
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
        return self.read_bytes(path).decode(encoding, errors)

    def write_text(
        self,
        path: PathLike,
        data: str,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> None:
        """按指定编码覆盖写入文本文件。"""
        self.write_bytes(path, data.encode(encoding, errors))
