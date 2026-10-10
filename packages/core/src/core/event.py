"""事件管理"""

from enum import Enum

from .models.event import Event, EventManager


class EventType(Enum):
    """事件类型。"""
    APP_START = "app_start"
    APP_STOP = "app_stop"
    APP_ERROR = "app_error"
    APP_LOG = "app_log"
    APP_CONFIG = "app_config"
    APP_DATA = "app_data"

class EventManagerImpl(EventManager):
    def publish_event(self, event: Event) -> None:
        pass

    def stop_publish_event(self, event: Event) -> None:
        pass
