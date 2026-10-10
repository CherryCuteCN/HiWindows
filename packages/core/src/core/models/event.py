"""事件模型"""

from abc import ABC, abstractmethod


class Event(ABC):
    """事件接口。"""

    @abstractmethod
    def event(self) -> object:
        """获取事件类型。"""
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
   