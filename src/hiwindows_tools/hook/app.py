from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import webview

from core import AppImpl, AppType, EventManagerImpl
from hiwindows_io import PathFileSystem

from .api import Api


def _frontend_url() -> str:
    configured_url = os.getenv("HIWINDOWS_FRONTEND_URL")
    if configured_url:
        return configured_url

    file_system = PathFileSystem()
    dist_index = (
        Path(__file__).resolve().parents[3] / "frontend" / "dist" / "index.html"
    )
    if file_system.exists(dist_index):
        return f"file://{quote(str(dist_index))}"

    return "http://localhost:5173"


def create_window() -> None:
    app = AppImpl(EventManagerImpl())
    app.run(AppType.UI)
    try:
        webview.create_window("HiWindows", _frontend_url(), js_api=Api())
        webview.start()
    except Exception:
        app.error(AppType.UI)
        raise
    finally:
        app.stop(AppType.UI)


def main() -> None:
    create_window()
