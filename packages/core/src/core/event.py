"""事件类型与同步事件总线实现。"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from threading import RLock

from .models.event import Event, EventHandler, Subscription


class EventType(Enum):
    """应用生命周期事件类型。"""

    APP_START = "app_start"
    APP_STOP = "app_stop"
    APP_ERROR = "app_error"
    APP_LOG = "app_log"
    APP_CONFIG = "app_config"
    APP_DATA = "app_data"


class EventManagerImpl:
    """进程内同步事件总线。

    事件处理器按注册顺序执行。处理器抛出的异常会继续向发布者传播，
    这样启动和停止流程不会在错误发生后继续伪装成成功。
    """

    def __init__(self) -> None:
        self._handlers: dict[object, dict[int, EventHandler]] = defaultdict(dict)
        self._subscriptions: dict[int, tuple[object, EventHandler]] = {}
        self._next_identifier = 0
        self._lock = RLock()

    def subscribe(self, event_type: object, handler: EventHandler) -> Subscription:
        """订阅指定类型的事件并返回取消订阅句柄。"""
        with self._lock:
            self._next_identifier += 1
            subscription = Subscription(self._next_identifier, event_type)
            self._handlers[event_type][subscription.identifier] = handler
            self._subscriptions[subscription.identifier] = (event_type, handler)
            return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        """取消订阅；重复取消同一个句柄不会报错。"""
        with self._lock:
            registered = self._subscriptions.pop(subscription.identifier, None)
            if registered is None:
                return

            event_type, _ = registered
            handlers = self._handlers[event_type]
            handlers.pop(subscription.identifier, None)
            if not handlers:
                del self._handlers[event_type]

    def publish(self, event: Event[object]) -> None:
        """同步发布事件。"""
        with self._lock:
            handlers = tuple(self._handlers.get(event.event_type, {}).values())

        for handler in handlers:
            handler(event)
