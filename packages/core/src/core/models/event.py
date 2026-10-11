"""事件模型"""

from abc import ABC, abstractmethod
from typing import Protocol


class Event(ABC):
    """事件接口。"""

    @abstractmethod
    def event(self) -> object:
        """获取事件类型。"""
        ...


class EventPublisher(Protocol):
    """事件发布端口。

    基础设施只需要发布事件，不应该依赖完整的事件管理器生命周期接口。
    """

    def publish_event(self, event: Event) -> None:
        """发布事件。"""
        ...


class EventManager(ABC):
    """事件管理器接口。"""

    @abstractmethod
    def publish_event(self, event: Event) -> None:
        """注册事件。"""
        ...

    @abstractmethod
    def stop_publish_event(self, event: Event) -> None:
        """注销事件。"""
        ...
   