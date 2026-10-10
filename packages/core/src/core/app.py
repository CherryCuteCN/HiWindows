"""应用运行时。"""

from .event import EventManagerImpl, EventType
from .models.app import App, AppType
from .models.event import Event, EventManager


class AppEvent(Event):
    """应用生命周期事件。"""

    def __init__(self, event_type: EventType, app_type: AppType) -> None:
        self._event_type = event_type
        self.app_type = app_type

    def event(self) -> EventType:
        """获取事件类型。"""
        return self._event_type


class AppImpl(App):
    """通过事件管理器驱动应用生命周期。"""

    def __init__(self, event_manager: EventManager | None = None) -> None:
        self._event_manager = event_manager or EventManagerImpl()

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
        self._event_manager.publish_event(AppEvent(event_type, app_type))


__all__ = ["AppEvent", "AppImpl"]
