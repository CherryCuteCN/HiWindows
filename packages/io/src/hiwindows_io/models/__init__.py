"""导出 I/O 抽象模型。"""

from .backend import IOBackend
from .events import IOEvent, IOEventType
from .filesystem import (
    FileSystem,
    FileSystemProgress,
    FileSystemProgressCallback,
    PathLike,
)
from .process import ProcessResult, ProcessRunner
from .registry import (
    Registry,
    RegistryHive,
    RegistryValue,
    RegistryValueType,
)
from .shell import ShortcutInfo, ShortcutResolver

__all__ = [
    "FileSystem",
    "FileSystemProgress",
    "FileSystemProgressCallback",
    "IOBackend",
    "IOEvent",
    "IOEventType",
    "PathLike",
    "ProcessResult",
    "ProcessRunner",
    "Registry",
    "RegistryHive",
    "RegistryValue",
    "RegistryValueType",
    "ShortcutInfo",
    "ShortcutResolver",
]
