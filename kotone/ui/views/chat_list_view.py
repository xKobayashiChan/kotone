"""チャットルーム一覧画面。get_main_chat_roomsで取得し、行クリックで
room_selectedを発火する（実際のルーム表示はChatViewが担当）。"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import qasync
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.realm_chat_room import RealmChatRoom

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.chat_room_row import ChatRoomRow


class ChatListView(QWidget):
    room_selected = Signal(object)  # RealmChatRoom

    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager
        self._loading = False
        self._last_timestamp: Optional[int] = None

        self._status_label = QLabel("")
        refresh_button = QPushButton("更新")
        refresh_button.clicked.connect(self._on_refresh_clicked)

        top_row = QHBoxLayout()
        top_row.addWidget(refresh_button)
        top_row.addWidget(self._status_label, 1)

        self._load_more_button = QPushButton("さらに読み込む")
        self._load_more_button.clicked.connect(self._on_load_more_clicked)
        self._load_more_button.setVisible(False)

        self._rooms_container = QWidget()
        self._rooms_layout = QVBoxLayout(self._rooms_container)
        self._rooms_layout.addWidget(self._load_more_button)
        self._rooms_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._rooms_container)
        # 中身が増えてもウィンドウを際限なく大きくしないための指定。
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(scroll_area, 1)

        asyncio.ensure_future(self.refresh())

    @qasync.asyncSlot()
    async def _on_refresh_clicked(self) -> None:
        await self.refresh()

    async def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._status_label.setText("読み込み中...")
        client = self._client_manager.require_client()
        try:
            response = await client.get_main_chat_rooms()
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            self._loading = False
            return

        self._clear_rooms()
        rooms = response.chat_rooms or []
        self._append_rooms(rooms)
        self._last_timestamp = rooms[-1].updated_at if rooms else None
        self._load_more_button.setVisible(bool(rooms))
        self._status_label.setText(f"{len(rooms)}件")
        self._loading = False

    @qasync.asyncSlot()
    async def _on_load_more_clicked(self) -> None:
        if self._loading or self._last_timestamp is None:
            return
        self._loading = True
        self._status_label.setText("さらに読み込み中...")
        client = self._client_manager.require_client()
        try:
            response = await client.get_main_chat_rooms(from_timestamp=self._last_timestamp)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"追加読み込みに失敗しました: {err}")
            self._loading = False
            return

        rooms = response.chat_rooms or []
        self._append_rooms(rooms)
        if rooms:
            self._last_timestamp = rooms[-1].updated_at
        self._load_more_button.setVisible(bool(rooms))
        self._status_label.setText("")
        self._loading = False

    def _append_rooms(self, rooms: List[RealmChatRoom]) -> None:
        own_user_id = self._client_manager.require_client().user_id
        stretch_index = self._rooms_layout.count() - 1
        for room in rooms:
            row = ChatRoomRow(room, own_user_id)
            row.opened.connect(self.room_selected.emit)
            self._rooms_layout.insertWidget(stretch_index, row)
            stretch_index += 1

    def _clear_rooms(self) -> None:
        # index 0 は「さらに読み込む」ボタン、末尾はstretchなので、
        # その間の行だけを取り除く。
        while self._rooms_layout.count() > 2:
            item = self._rooms_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
