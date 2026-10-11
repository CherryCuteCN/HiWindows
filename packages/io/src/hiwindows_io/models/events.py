"""I/O 操作事件。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.models.event import Event


class IOEventType(StrEnum):
    """I/O 操作事件类型。"""

    FILESYSTEM_OPERATION = "io.filesystem.operation"
    REGISTRY_OPERATION = "io.registry.operation"


@dataclass(frozen=True, slots=True)
class IOEvent(Event):
    """一次 I/O 操作的结果事件。"""

    event_type: IOEventType
    operation: str
    target: str
    succeeded: bool
    error_type: str | None = None

    def event(self) -> IOEventType:
        """获取事件类型。"""
        return self.event_type
