"""Windows 进程执行端口与模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """一次命令执行结果。"""

    return_code: int


@runtime_checkable
class ProcessRunner(Protocol):
    """外部进程执行端口。"""

    def run(self, command: str, *, working_dir: str | None = None) -> ProcessResult:
        """执行命令并等待其结束。"""
        ...
