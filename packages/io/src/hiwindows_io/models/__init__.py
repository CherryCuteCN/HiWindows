"""导出 I/O 抽象模型。"""

from .backend import IOBackend
from .events import IOEvent, IOEventType
from .filesystem import FileSystem, PathLike
from .registry import (
    Registry,
    RegistryHive,
    RegistryValue,
    RegistryValueType,
)

__all__ = [
    "FileSystem",
    "IOBackend",
    "IOEvent",
    "IOEventType",
    "PathLike",
    "Registry",
    "RegistryHive",
    "RegistryValue",
    "RegistryValueType",
]
