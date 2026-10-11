"""事件端口与订阅模型。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

EventTypeT = TypeVar("EventTypeT", covariant=True)


@runtime_checkable
class Event(Protocol[EventTypeT]):
    """事件必须提供一个可路由的事件类型。"""

    @property
    def event_type(self) -> EventTypeT:
        """获取事件类型。"""
        ...


EventHandler = Callable[[Event[object]], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """事件订阅句柄。"""

    identifier: int
    event_type: object


class EventPublisher(Protocol):
    """事件发布端口。

    基础设施只依赖发布能力，不依赖事件总线的订阅管理。
    """

    def publish(self, event: Event[object]) -> None:
        """发布事件。"""
        ...


class EventManager(EventPublisher, Protocol):
    """事件总线端口。"""

    def subscribe(self, event_type: object, handler: EventHandler) -> Subscription:
        """订阅指定类型的事件。"""
        ...

    def unsubscribe(self, subscription: Subscription) -> None:
        """取消订阅。"""
        ...
   