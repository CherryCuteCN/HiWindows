"""应用生命周期运行时。"""

from dataclasses import dataclass

from .event import EventManagerImpl, EventType
from .models.app import App, AppType
from .models.event import EventPublisher


@dataclass(frozen=True, slots=True)
class AppEvent:
    """应用生命周期事件。"""

    event_type: EventType
    app_type: AppType


class AppImpl(App):
    """通过事件管理器驱动应用生命周期。"""

    def __init__(self, event_publisher: EventPublisher | None = None) -> None:
        self._event_publisher = event_publisher or EventManagerImpl()

    def run(self, app_type: AppType) -> None:
        """运行应用并发布启动事件。"""
        self._publish(EventType.APP_START, app_type)

    def stop(self, app_type: AppType) -> None:
        """停止应用并发布停止事件。"""
        self._publish(EventType.APP_STOP, app_type)

    def error(self, app_type: AppType) -> None:
        """发布应用异常事件。"""
        self._publish(EventType.APP_ERROR, app_type)

    def _publish(self, event_type: EventType, app_type: AppType) -> None:
        self._event_publisher.publish(AppEvent(event_type, app_type))


__all__ = ["AppEvent", "AppImpl"]
