from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import webview

from .api import Api


def _frontend_url() -> str:
    configured_url = os.getenv("HIWINDOWS_FRONTEND_URL")
    if configured_url:
        return configured_url

    dist_index = (
        Path(__file__).resolve().parents[4] / "frontend" / "dist" / "index.html"
    )
    if dist_index.exists():
        return f"file://{quote(str(dist_index))}"

    return "http://localhost:5173"


def create_window() -> None:
    webview.create_window("HiWindows", _frontend_url(), js_api=Api())
    webview.start()


def main() -> None:
    create_window()
