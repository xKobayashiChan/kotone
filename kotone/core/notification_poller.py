"""アクティビティ（いいね・返信・フォロー等）とチャット未読を定期的に
ポーリングし、新着があればデスクトップ通知(システムトレイのバルーン)と
音で知らせる。

yaylibのイベントストリームにはアクティビティ用のリアルタイムpushが無く
（チャンネルはChatRoomChannel/MessagesChannel(部屋単位)/GroupUpdates/
GroupPostsのみ）、開いていないチャットルームの新着も同様にpushされない
ため、素朴な定期ポーリングで代替する。
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from kotone.core.client_manager import ClientManager
from kotone.ui.views.notifications_view import describe_activity

POLL_INTERVAL_SECONDS = 60
_SUMMARIZE_THRESHOLD = 3
_TOAST_DURATION_MS = 5000


class NotificationPoller:
    def __init__(self, client_manager: ClientManager, tray_icon: QSystemTrayIcon) -> None:
        self._client_manager = client_manager
        self._tray_icon = tray_icon
        self._task: Optional[asyncio.Task] = None
        self._initialized = False
        self._seen_activity_ts: Optional[int] = None
        self._known_room_unread: Dict[int, int] = {}

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_once(self) -> None:
        client = self._client_manager.require_client()
        await self._poll_activities(client)
        await self._poll_chat_unread(client)
        self._initialized = True

    async def _poll_activities(self, client) -> None:
        try:
            response = await client.get_user_activities()
        except Exception:  # noqa: BLE001
            return
        activities = response.activities or []
        newest_ts = activities[0].created_at if activities else None

        if self._initialized and self._seen_activity_ts is not None:
            new_ones = [
                a for a in activities if (a.created_at or 0) > self._seen_activity_ts
            ]
            if len(new_ones) > _SUMMARIZE_THRESHOLD:
                self._notify(f"{len(new_ones)}件の新着通知があります")
            else:
                for activity in reversed(new_ones):  # 古い順に通知する
                    self._notify(describe_activity(activity))

        if newest_ts is not None:
            self._seen_activity_ts = max(self._seen_activity_ts or 0, newest_ts)

    async def _poll_chat_unread(self, client) -> None:
        try:
            response = await client.get_main_chat_rooms()
        except Exception:  # noqa: BLE001
            return
        for room in response.chat_rooms or []:
            if room.id is None:
                continue
            current = room.unread_count or 0
            previous = self._known_room_unread.get(room.id)
            if self._initialized and previous is not None and current > previous:
                name = room.name or "チャット"
                self._notify(f"{name}に新着メッセージがあります")
            self._known_room_unread[room.id] = current

    def _notify(self, message: str) -> None:
        self._tray_icon.showMessage(
            "Kotone",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            _TOAST_DURATION_MS,
        )
        QApplication.beep()
