"""アプリケーションのエントリポイント。

yaylibは全面的にasync/awaitで書かれているため、PySide6のイベントループに
asyncioを重ねるqasyncを使う。QApplication/QEventLoopの生成とasyncio側の
既定イベントループ設定はここでのみ行う。

起動フロー:
  1. 前回ログイン時のメールアドレスが保存されていれば、キャッシュ済み
     セッションの復元を試みる（パスワード不要）。
  2. 復元できればメインウィンドウへ、できなければログイン画面を表示する。
"""

from __future__ import annotations

import asyncio
import sys

import qasync
import PySide6.QtWebEngineWidgets  # noqa: F401  (副作用インポート。下記コメント参照)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

# QtWebEngine(VC機能で使用)は、QApplication生成前にAA_ShareOpenGLContexts
# を設定し、かつQtWebEngineWidgetsを一度importしておく必要がある
# （Qt公式ドキュメントの初期化要件）。
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

from kotone.core.client_manager import ClientManager, LoginResult
from kotone.core.logging_config import setup_logging
from kotone.core.notification_poller import NotificationPoller
from kotone.core.resources import resource_dir
from kotone.core.settings import AppSettings
from kotone.ui.login_window import LoginWindow
from kotone.ui.main_window import MainWindow
from kotone.ui.theme import DEFAULT_THEME, apply_theme, toggle_theme
from kotone.ui.views.chat_view import ChatView
from kotone.ui.views.footprints_view import FootprintsView
from kotone.ui.views.groups_view import GroupsView
from kotone.ui.views.notifications_view import NotificationsView
from kotone.ui.views.profile_view import ProfileView
from kotone.ui.views.timeline_view import TimelineView

_ICON_PATH = resource_dir() / "kotone.ico"


class _AppController:
    """ログイン画面とメインウィンドウの表示切り替えを担う。"""

    def __init__(self) -> None:
        self._settings = AppSettings()
        self._client_manager = ClientManager()
        self._login_window: LoginWindow | None = None
        self._main_window: MainWindow | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._notification_poller: NotificationPoller | None = None
        self._theme = self._settings.theme() or DEFAULT_THEME
        apply_theme(QApplication.instance(), self._theme)

    def _on_theme_toggle_requested(self) -> None:
        self._theme = toggle_theme(self._theme)
        self._settings.set_theme(self._theme)
        apply_theme(QApplication.instance(), self._theme)

    async def start(self) -> None:
        last_email = self._settings.last_email()
        result = await self._client_manager.try_restore_session(last_email)
        if result is not None:
            self._show_main_window(result)
        else:
            self._show_login_window(last_email)

    def _show_login_window(self, initial_email: str) -> None:
        window = LoginWindow(self._client_manager, initial_email)
        window.login_succeeded.connect(self._on_login_succeeded)
        self._login_window = window
        window.show()

    def _on_login_succeeded(self, result: LoginResult) -> None:
        self._settings.set_last_email(result.email)
        if self._login_window is not None:
            self._login_window.close()
            self._login_window = None
        self._show_main_window(result)

    def _show_main_window(self, result: LoginResult) -> None:
        window = MainWindow(self._client_manager, result)
        window.logout_requested.connect(
            lambda: asyncio.ensure_future(self._on_logout_requested(result.email))
        )
        window.theme_toggle_requested.connect(self._on_theme_toggle_requested)
        window.set_page("timeline", TimelineView(self._client_manager))
        window.set_page("chat", ChatView(self._client_manager))
        window.set_page("groups", GroupsView(self._client_manager))
        window.set_page("notifications", NotificationsView(self._client_manager))
        window.set_page("footprints", FootprintsView(self._client_manager))
        window.set_page("profile", ProfileView(self._client_manager))
        self._main_window = window
        window.show()

        self._start_notification_poller()

    def _start_notification_poller(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray_icon = QSystemTrayIcon(QIcon(str(_ICON_PATH)))
            tray_icon.setToolTip("Kotone")
            tray_icon.show()
            self._tray_icon = tray_icon
            self._notification_poller = NotificationPoller(self._client_manager, tray_icon)
            self._notification_poller.start()

    async def _stop_notification_poller(self) -> None:
        if self._notification_poller is not None:
            await self._notification_poller.stop()
            self._notification_poller = None
        if self._tray_icon is not None:
            self._tray_icon.hide()
            self._tray_icon = None

    async def _on_logout_requested(self, email: str) -> None:
        await self._stop_notification_poller()
        await self._client_manager.logout(email)
        if self._main_window is not None:
            self._main_window.close()
            self._main_window = None
        self._show_login_window(email)


def run() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(_ICON_PATH)))
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    controller = _AppController()

    with loop:
        loop.create_task(controller.start())
        loop.run_forever()


if __name__ == "__main__":
    run()
