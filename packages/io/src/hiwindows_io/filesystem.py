"""文件系统抽象与 Windows 后端实现。"""

from __future__ import annotations

import shutil
from importlib import import_module
from pathlib import Path
from typing import Any

from core.models.event import EventPublisher

from .exceptions import BackendUnavailableError
from .models.events import IOEventType
from .models.filesystem import FileSystem, PathLike


class PathFileSystem(FileSystem):
    """基于 Python 标准库的文件系统实现。

    该实现用于跨平台测试和不需要 Windows 特有语义的场景。
    """

    def exists(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "exists", str(path)):
            return Path(path).exists()

    def read_bytes(self, path: PathLike) -> bytes:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "read_bytes",
            str(path),
        ):
            return Path(path).read_bytes()

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "write_bytes",
            str(path),
        ):
            Path(path).write_bytes(data)

    def remove_file(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_file",
            str(path),
        ):
            Path(path).unlink()

    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "make_dir",
            str(path),
        ):
            Path(path).mkdir(parents=parents, exist_ok=True)

    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "list_dir",
            str(path),
        ):
            return tuple(sorted(Path(path).iterdir()))

    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "copy_file",
            f"{source} -> {destination}",
        ):
            if not overwrite and Path(destination).exists():
                raise FileExistsError(destination)
            shutil.copy2(source, destination)

    def move_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "move_file",
            f"{source} -> {destination}",
        ):
            if not overwrite and Path(destination).exists():
                raise FileExistsError(destination)
            if overwrite:
                Path(destination).unlink(missing_ok=True)
            shutil.move(source, destination)


def _load_pywin32_file_module() -> Any:
    """延迟加载 pywin32，保证非 Windows 平台可以导入本包。"""
    try:
        return import_module("win32file")
    except ImportError as error:
        raise BackendUnavailableError(
            "PyWin32FileSystem 需要在 Windows 环境安装 pywin32。"
        ) from error


class PyWin32FileSystem(FileSystem):
    """使用 ``pywin32.win32file`` 的 Windows 文件系统实现。"""

    def __init__(
        self,
        *,
        chunk_size: int = 1024 * 1024,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        super().__init__(event_publisher)
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0。")
        self._win32file = _load_pywin32_file_module()
        self._chunk_size = chunk_size

    def exists(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "exists", str(path)):
            try:
                self._win32file.GetFileAttributes(str(path))
            except Exception:
                return False
            return True

    def read_bytes(self, path: PathLike) -> bytes:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "read_bytes",
            str(path),
        ):
            handle = self._win32file.CreateFile(
                str(path),
                self._win32file.GENERIC_READ,
                self._win32file.FILE_SHARE_READ
                | self._win32file.FILE_SHARE_WRITE
                | self._win32file.FILE_SHARE_DELETE,
                None,
                self._win32file.OPEN_EXISTING,
                self._win32file.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            try:
                content = bytearray()
                while True:
                    _, chunk = self._win32file.ReadFile(handle, self._chunk_size)
                    if not chunk:
                        return bytes(content)
                    content.extend(chunk)
            finally:
                self._win32file.CloseHandle(handle)

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "write_bytes",
            str(path),
        ):
            handle = self._win32file.CreateFile(
                str(path),
                self._win32file.GENERIC_WRITE,
                self._win32file.FILE_SHARE_READ
                | self._win32file.FILE_SHARE_WRITE
                | self._win32file.FILE_SHARE_DELETE,
                None,
                self._win32file.CREATE_ALWAYS,
                self._win32file.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            try:
                offset = 0
                while offset < len(data):
                    _, written = self._win32file.WriteFile(
                        handle,
                        data[offset : offset + self._chunk_size],
                    )
                    if written <= 0:
                        raise OSError("Windows 文件写入未取得进展。")
                    offset += written
            finally:
                self._win32file.CloseHandle(handle)

    def remove_file(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_file",
            str(path),
        ):
            self._win32file.DeleteFile(str(path))

    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "make_dir",
            str(path),
        ):
            path_object = Path(path)
            if parents:
                path_object.mkdir(parents=True, exist_ok=True)
                return
            try:
                self._win32file.CreateDirectory(str(path_object), None)
            except Exception:
                if not path_object.is_dir():
                    raise

    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "list_dir",
            str(path),
        ):
            return tuple(sorted(Path(path).iterdir()))

    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "copy_file",
            f"{source} -> {destination}",
        ):
            self._win32file.CopyFile(
                str(source),
                str(destination),
                int(not overwrite),
            )

    def move_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "move_file",
            f"{source} -> {destination}",
        ):
            flags = 0
            if overwrite:
                flags |= self._win32file.MOVEFILE_REPLACE_EXISTING
            self._win32file.MoveFileEx(
                str(source),
                str(destination),
                flags,
            )


WindowsFileSystem = PyWin32FileSystem

__all__ = [
    "PathFileSystem",
    "PyWin32FileSystem",
    "WindowsFileSystem",
]
