"""注册表端口与数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Protocol, runtime_checkable


class RegistryHive(StrEnum):
    """注册表根键。"""

    CLASSES_ROOT = "HKEY_CLASSES_ROOT"
    CURRENT_USER = "HKEY_CURRENT_USER"
    LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"
    USERS = "HKEY_USERS"
    CURRENT_CONFIG = "HKEY_CURRENT_CONFIG"


class RegistryValueType(IntEnum):
    """注册表值类型。数值与 Windows Registry API 保持一致。"""

    NONE = 0
    STRING = 1
    EXPAND_STRING = 2
    BINARY = 3
    DWORD = 4
    DWORD_BIG_ENDIAN = 5
    LINK = 6
    MULTI_STRING = 7
    QWORD = 11


@dataclass(frozen=True, slots=True)
class RegistryValue:
    """注册表中的一个值。"""

    name: str
    data: object
    value_type: RegistryValueType | int


@runtime_checkable
class Registry(Protocol):
    """注册表操作端口。

    具体实现通过结构化类型满足这个端口，不需要继承它。
    """

    def key_exists(self, hive: RegistryHive, key_path: str) -> bool:
        """判断注册表键是否存在。"""
        ...

    def create_key(self, hive: RegistryHive, key_path: str) -> None:
        """创建注册表键及其父键。"""
        ...

    def delete_key(
        self,
        hive: RegistryHive,
        key_path: str,
        *,
        recursive: bool = False,
    ) -> None:
        """删除注册表键。"""
        ...

    def read_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str = "",
        *,
        default: object | None = None,
    ) -> object | None:
        """读取值；键或值不存在时返回 ``default``。"""
        ...

    def write_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str,
        value: object,
        *,
        value_type: RegistryValueType | int | None = None,
    ) -> None:
        """写入值；键不存在时自动创建。"""
        ...

    def delete_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str = "",
    ) -> None:
        """删除值。"""
        ...

    def list_subkeys(self, hive: RegistryHive, key_path: str) -> tuple[str, ...]:
        """列出键的直接子键。"""
        ...

    def list_values(
        self,
        hive: RegistryHive,
        key_path: str,
    ) -> tuple[RegistryValue, ...]:
        """列出键的直接值。"""
        ...
