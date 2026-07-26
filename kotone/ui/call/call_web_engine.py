"""Agora RTC Web SDKを埋め込んだ非表示QWebEngineView。実際の音声の
送受信(マイクキャプチャ/再生/エコーキャンセル)はここでロードされる
call.html + Agora Web SDKが担う。ネイティブUI側はjoin/leave/set_muted
の呼び出しとCallBridgeのイベントだけを扱えばよい。"""

from __future__ import annotations

import json

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePermission, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from kotone.core.resources import resource_dir
from kotone.ui.call.call_bridge import CallBridge

_CALL_HTML_PATH = resource_dir() / "call.html"


class CallWebEngine(QWebEngineView):
    """通話中は表示せず、音声エンジンとしてのみ使うQWebEngineView。"""

    def __init__(self, bridge: CallBridge, parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge

        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", bridge)
        self.page().setWebChannel(self._channel)
        self.page().permissionRequested.connect(self._on_permission_requested)

        # call.htmlはfile://で読み込むため、デフォルトのままだとAgora Web
        # SDK(https://...)へのfetch/<script src>が「ローカルコンテンツから
        # リモートURLへのアクセス」としてブロックされる。
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self.setVisible(False)
        self.load(QUrl.fromLocalFile(str(_CALL_HTML_PATH)))

    def _on_permission_requested(self, permission: QWebEnginePermission) -> None:
        if permission.permissionType() == QWebEnginePermission.PermissionType.MediaAudioCapture:
            permission.grant()
        else:
            permission.deny()

    def join(self, app_id: str, channel: str, token: str, uid: str) -> None:
        args = ", ".join(json.dumps(a) for a in (app_id, channel, token, uid))
        self.page().runJavaScript(f"window.callApi.join({args});")

    def leave(self) -> None:
        self.page().runJavaScript("window.callApi.leave();")

    def set_muted(self, muted: bool) -> None:
        self.page().runJavaScript(f"window.callApi.setMuted({json.dumps(bool(muted))});")
