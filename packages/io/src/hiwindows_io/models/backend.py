"""I/O 后端的共享运行能力。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from core.models.event import EventPublisher

from .events import IOEvent, IOEventType


class IOBackend:
    """为具体 I/O 实现提供操作结果报告能力。

    这是共享实现，不是需要被业务依赖的抽象接口。
    """

    def __init__(self, event_publisher: EventPublisher | None = None) -> None:
        self._event_publisher = event_publisher

    def _publish_operation(
        self,
        event_type: IOEventType,
        operation: str,
        target: str,
        *,
        succeeded: bool,
        error: BaseException | None = None,
    ) -> None:
        """发布一次 I/O 操作结果。"""
        if self._event_publisher is None:
            return
        self._event_publisher.publish(
            IOEvent(
                event_type=event_type,
                operation=operation,
                target=target,
                succeeded=succeeded,
                error_type=type(error).__name__ if error else None,
            )
        )

    @contextmanager
    def _operation(
        self,
        event_type: IOEventType,
        operation: str,
        target: str,
    ) -> Iterator[None]:
        """执行并报告一次 I/O 操作。"""
        try:
            yield
        except Exception as error:
            self._publish_operation(
                event_type,
                operation,
                target,
                succeeded=False,
                error=error,
            )
            raise
        else:
            self._publish_operation(
                event_type,
                operation,
                target,
                succeeded=True,
            )
