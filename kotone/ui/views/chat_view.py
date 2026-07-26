"""チャット画面。ルーム一覧⇔個別ルームをQStackedWidgetで切り替える。"""

from __future__ import annotations

import asyncio

from PySide6.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from yaylib.models.realm_chat_room import RealmChatRoom

from kotone.core.client_manager import ClientManager
from kotone.ui.views.chat_list_view import ChatListView
from kotone.ui.views.chat_room_view import ChatRoomView


class ChatView(QWidget):
    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager

        self._list_view = ChatListView(client_manager)
        self._list_view.room_selected.connect(self._on_room_selected)

        self._stack = QStackedWidget()
        # ルーム一覧⇔個別ルームの切り替えで、片方の内容が増えても
        # ウィンドウが際限なく大きくならないようにする。
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self._stack.addWidget(self._list_view)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stack)

    def _on_room_selected(self, room: RealmChatRoom) -> None:
        room_view = ChatRoomView(room, self._client_manager)
        room_view.back_requested.connect(lambda: self._on_back_requested(room_view))
        self._stack.addWidget(room_view)
        self._stack.setCurrentWidget(room_view)

    def _on_back_requested(self, room_view: ChatRoomView) -> None:
        self._stack.setCurrentWidget(self._list_view)
        self._stack.removeWidget(room_view)
        asyncio.ensure_future(self._cleanup_room_view(room_view))

    async def _cleanup_room_view(self, room_view: ChatRoomView) -> None:
        await room_view.shutdown()
        room_view.deleteLater()
