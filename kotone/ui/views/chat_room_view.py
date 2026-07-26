"""1つのチャットルームのメッセージ履歴・送信・リアルタイム受信。

新着メッセージはmessages_channel(room_id)のイベントストリームで受信する。
自分が送ったテキストメッセージは楽観的にその場で表示し、画像メッセージは
（アップロード直後のレスポンスに公開URLが含まれないため）イベント
ストリーム経由で届く完全な内容を待って表示する。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Optional, Set

import qasync
import yaylib
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from yaylib import Upload
from yaylib.event_stream import messages_channel
from yaylib.models.realm_chat_room import RealmChatRoom
from yaylib.models.realm_message import RealmMessage

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.chat_room_row import room_display_name
from kotone.ui.widgets.clickable_label import ClickableLabel
from kotone.ui.widgets.image_loader import load_pixmap
from kotone.ui.widgets.user_profile_opener import open_user_profile

_MESSAGE_PAGE_SIZE = 50
_MEDIA_MAX_WIDTH = 320


class ChatRoomView(QWidget):
    back_requested = Signal()

    def __init__(self, room: RealmChatRoom, client_manager: ClientManager) -> None:
        super().__init__()
        self._room = room
        self._client_manager = client_manager
        self._client = client_manager.require_client()
        self._own_user_id = self._client.user_id

        self._members_by_id: Dict[int, object] = {}
        for member in room.members or []:
            if member.id is not None:
                self._members_by_id[member.id] = member
        if room.owner is not None and room.owner.id is not None:
            self._members_by_id.setdefault(room.owner.id, room.owner)

        self._seen_message_ids: Set[int] = set()
        self._oldest_message_id: Optional[int] = None
        self._pending_image: Optional[Path] = None
        self._stream = None
        self._sub = None

        back_button = QPushButton("← 一覧に戻る")
        back_button.clicked.connect(self.back_requested.emit)
        title = room_display_name(room, self._own_user_id)
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setTextFormat(Qt.TextFormat.RichText)

        header_row = QHBoxLayout()
        header_row.addWidget(back_button)
        header_row.addWidget(title_label, 1)

        self._load_more_button = QPushButton("さらに読み込む")
        self._load_more_button.setVisible(False)
        self._load_more_button.clicked.connect(self._on_load_more_clicked)

        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.addWidget(self._load_more_button)
        self._messages_layout.addStretch(1)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._messages_container)
        # 中身が増えてもウィンドウを際限なく大きくしないための指定。
        self._scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored
        )

        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("メッセージを入力")
        self._input_edit.returnPressed.connect(self._on_send_clicked)
        attach_button = QPushButton("画像を添付")
        attach_button.clicked.connect(self._on_attach_clicked)
        send_button = QPushButton("送信")
        send_button.setProperty("primary", True)
        send_button.clicked.connect(self._on_send_clicked)

        self._attach_label = QLabel("")

        input_row = QHBoxLayout()
        input_row.addWidget(attach_button)
        input_row.addWidget(self._input_edit, 1)
        input_row.addWidget(send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(header_row)
        layout.addWidget(self._scroll_area, 1)
        layout.addWidget(self._attach_label)
        layout.addLayout(input_row)

        asyncio.ensure_future(self._load_initial())
        asyncio.ensure_future(self._start_listening())

    async def _load_initial(self) -> None:
        try:
            response = await self._client.get_chat_messages(
                id=self._room.id, number=_MESSAGE_PAGE_SIZE
            )
        except Exception as err:  # noqa: BLE001
            self._add_system_label(f"メッセージの取得に失敗しました: {err}")
            return

        raw_messages = response.messages or []
        messages = list(reversed(raw_messages))  # 古い→新しい順に並べ直す
        for msg in messages:
            self._append_message(msg, at_top=False)
        if messages:
            self._oldest_message_id = messages[0].id
        self._load_more_button.setVisible(len(raw_messages) >= _MESSAGE_PAGE_SIZE)
        self._scroll_to_bottom()

    @qasync.asyncSlot()
    async def _on_load_more_clicked(self) -> None:
        if self._oldest_message_id is None:
            return
        try:
            response = await self._client.get_chat_messages(
                id=self._room.id,
                number=_MESSAGE_PAGE_SIZE,
                from_message_id=self._oldest_message_id,
            )
        except Exception:  # noqa: BLE001
            return

        raw_messages = response.messages or []
        messages = list(reversed(raw_messages))
        for msg in messages:
            self._append_message(msg, at_top=True)
        if messages:
            self._oldest_message_id = messages[0].id
        self._load_more_button.setVisible(len(raw_messages) >= _MESSAGE_PAGE_SIZE)

    async def _start_listening(self) -> None:
        try:
            self._stream = await self._client.open_event_stream()
            self._sub = await self._stream.subscribe(messages_channel(self._room.id))
        except Exception:  # noqa: BLE001
            return
        self._sub.on_new_message(self._on_new_message_event)

    def _on_new_message_event(self, event) -> None:
        try:
            msg = RealmMessage.from_dict(event.raw)
        except Exception:  # noqa: BLE001
            return
        if msg is None:
            return
        self._append_message(msg, at_top=False)
        self._scroll_to_bottom()

    async def shutdown(self) -> None:
        if self._sub is not None:
            await self._sub.unsubscribe()
        if self._stream is not None:
            await self._stream.close()

    def _append_message(self, msg: RealmMessage, at_top: bool) -> None:
        if msg.id is not None:
            if msg.id in self._seen_message_ids:
                return
            self._seen_message_ids.add(msg.id)
        widget = self._build_message_widget(msg)
        if at_top:
            self._messages_layout.insertWidget(1, widget)  # index0は「さらに読み込む」
        else:
            stretch_index = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(stretch_index, widget)

    def _build_message_widget(self, msg: RealmMessage) -> QWidget:
        sender = self._members_by_id.get(msg.user_id)
        if msg.user_id == self._own_user_id:
            nickname = "自分"
        elif sender is not None and sender.nickname:
            nickname = sender.nickname
        else:
            nickname = "?"

        container = QWidget()
        col = QVBoxLayout(container)
        header = ClickableLabel(f"<b>{nickname}</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        if msg.user_id != self._own_user_id and msg.user_id is not None:
            header.clicked.connect(
                lambda uid=msg.user_id: open_user_profile(self._client_manager, uid)
            )
        col.addWidget(header)

        if msg.text:
            text_label = QLabel(msg.text)
            text_label.setWordWrap(True)
            col.addWidget(text_label)

        if msg.attachment:
            image_label = QLabel()
            image_label.setMaximumWidth(_MEDIA_MAX_WIDTH)
            load_pixmap(
                msg.attachment, lambda pm, lbl=image_label: self._set_scaled_pixmap(lbl, pm)
            )
            col.addWidget(image_label)

        return container

    def _set_scaled_pixmap(self, label: QLabel, pixmap) -> None:
        scaled = pixmap.scaledToWidth(
            _MEDIA_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation
        )
        label.setPixmap(scaled)

    def _add_system_label(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        stretch_index = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(stretch_index, label)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_attach_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "画像を選択", "", "画像ファイル (*.png *.jpg *.jpeg *.gif)"
        )
        if path:
            self._pending_image = Path(path)
            self._attach_label.setText(f"添付: {self._pending_image.name}")

    @qasync.asyncSlot()
    async def _on_send_clicked(self) -> None:
        text = self._input_edit.text().strip()
        if not text and self._pending_image is None:
            return

        attachment_file_name: Optional[str] = None
        message_type = yaylib.MessageType.TEXT
        if self._pending_image is not None:
            data = await asyncio.to_thread(self._pending_image.read_bytes)
            upload = Upload(filename=self._pending_image.name, body=data)
            try:
                filenames = await self._client.upload_chat_message_images(
                    self._room.id, [upload]
                )
            except Exception as err:  # noqa: BLE001
                self._add_system_label(f"画像の送信に失敗しました: {err}")
                return
            attachment_file_name = filenames[0]
            message_type = yaylib.MessageType.IMAGE

        try:
            response = await self._client.send_chat_message(
                id=self._room.id,
                message_type=message_type,
                text=text,
                attachment_file_name=attachment_file_name,
            )
        except Exception as err:  # noqa: BLE001
            self._add_system_label(f"送信に失敗しました: {err}")
            return

        self._input_edit.clear()
        self._pending_image = None
        self._attach_label.setText("")

        if message_type == yaylib.MessageType.TEXT and response.id is not None:
            # 画像添付時はアップロード直後のレスポンスに公開URLが無いため、
            # イベントストリーム経由で届く完全な内容の表示を待つ。
            echo = RealmMessage(
                id=response.id,
                text=text,
                user_id=self._own_user_id,
                message_type=yaylib.MessageType.TEXT,
                room_id=self._room.id,
            )
            self._append_message(echo, at_top=False)
            self._scroll_to_bottom()
