"""1つのチャットルームのメッセージ履歴・送信・リアルタイム受信。

新着メッセージはmessages_channel(room_id)のイベントストリームで受信する。
自分が送ったテキストメッセージは楽観的にその場で表示し、画像メッセージは
（アップロード直後のレスポンスに公開URLが含まれないため）イベント
ストリーム経由で届く完全な内容を待って表示する。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import qasync
import yaylib
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
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
from kotone.ui.widgets.image_loader import load_pixmap, load_square_icon
from kotone.ui.widgets.user_profile_opener import open_user_profile

_MESSAGE_PAGE_SIZE = 50
_MEDIA_MAX_WIDTH = 320
_AVATAR_SIZE = 32
_BUBBLE_MAX_WIDTH = 420
_TIME_LABEL_COLOR = "#8a8a8f"
_WEEKDAY_JP_LABELS = ("月", "火", "水", "木", "金", "土", "日")


def _message_date(msg: RealmMessage) -> Optional[date]:
    if not msg.created_at:
        return None
    try:
        return datetime.fromtimestamp(msg.created_at).date()
    except (OverflowError, OSError, ValueError):
        return None


def _format_date_separator(value: date) -> str:
    return f"{value.month}/{value.day} - {_WEEKDAY_JP_LABELS[value.weekday()]}曜日"


def _format_message_time(msg: RealmMessage) -> str:
    if not msg.created_at:
        return ""
    try:
        return datetime.fromtimestamp(msg.created_at).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


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

        # 日付区切りの管理用。_bottom_date/_top_dateは現在表示中の一番下/
        # 一番上のメッセージの日付、_top_separator_widgetは一番上に表示中の
        # 区切りウィジェット（「さらに読み込む」で過去メッセージを継ぎ足す
        # 際、境界が変わったら差し替える）。
        self._bottom_date: Optional[date] = None
        self._top_date: Optional[date] = None
        self._top_separator_widget: Optional[QWidget] = None

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
            self._append_message(msg)
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
        self._prepend_older_messages(messages)
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
        self._append_message(msg)
        self._scroll_to_bottom()

    async def shutdown(self) -> None:
        if self._sub is not None:
            await self._sub.unsubscribe()
        if self._stream is not None:
            await self._stream.close()

    def _append_message(self, msg: RealmMessage) -> None:
        """新しいメッセージを一番下に追加する（初回読み込み・新着イベント・
        自メッセージの楽観的表示で使う）。日付が変わっていれば区切りも
        ここで挿入する。"""
        if msg.id is not None:
            if msg.id in self._seen_message_ids:
                return
            self._seen_message_ids.add(msg.id)

        msg_date = _message_date(msg)
        is_first_ever = self._top_date is None
        stretch_index = self._messages_layout.count() - 1
        if msg_date is not None and msg_date != self._bottom_date:
            separator = self._build_date_separator(msg_date)
            self._messages_layout.insertWidget(stretch_index, separator)
            stretch_index += 1
            self._bottom_date = msg_date
            if is_first_ever:
                self._top_date = msg_date
                self._top_separator_widget = separator

        widget = self._build_message_widget(msg)
        self._messages_layout.insertWidget(stretch_index, widget)

    def _prepend_older_messages(self, messages: List[RealmMessage]) -> None:
        """「さらに読み込む」で取得した過去メッセージ群を一番上にまとめて
        追加する。1件ずつ同じ位置(index1)に挿し込むと逆順になってしまう
        ため、増加していくインデックスを使ってまとめて挿入する。"""
        fresh: List[RealmMessage] = []
        for msg in messages:
            if msg.id is not None:
                if msg.id in self._seen_message_ids:
                    continue
                self._seen_message_ids.add(msg.id)
            fresh.append(msg)
        if not fresh:
            return

        # 追加分の末尾（一番新しい過去メッセージ）が既存の一番上のメッセージ
        # と同じ日付なら、既存側にあった区切りはもう境界ではなくなるため
        # 消す（新しい境界はこのあと追加分の先頭に付け直す）。
        last_new_date = _message_date(fresh[-1])
        if (
            self._top_separator_widget is not None
            and last_new_date is not None
            and last_new_date == self._top_date
        ):
            self._messages_layout.removeWidget(self._top_separator_widget)
            self._top_separator_widget.deleteLater()
            self._top_separator_widget = None

        insert_index = 1  # index0は「さらに読み込む」ボタン
        prev_date: Optional[date] = None
        new_top_separator: Optional[QWidget] = None
        for msg in fresh:
            msg_date = _message_date(msg)
            if msg_date is not None and msg_date != prev_date:
                separator = self._build_date_separator(msg_date)
                self._messages_layout.insertWidget(insert_index, separator)
                insert_index += 1
                prev_date = msg_date
                if new_top_separator is None:
                    new_top_separator = separator
            widget = self._build_message_widget(msg)
            self._messages_layout.insertWidget(insert_index, widget)
            insert_index += 1

        if new_top_separator is not None:
            self._top_separator_widget = new_top_separator
        first_date = _message_date(fresh[0])
        if first_date is not None:
            self._top_date = first_date

    def _build_date_separator(self, value: date) -> QWidget:
        label = QLabel(_format_date_separator(value))

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 4, 12, 4)
        frame_layout.addWidget(label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 8, 0, 8)
        row_layout.addStretch(1)
        row_layout.addWidget(frame)
        row_layout.addStretch(1)
        return row

    def _build_message_widget(self, msg: RealmMessage) -> QWidget:
        sender = self._members_by_id.get(msg.user_id)
        is_own = msg.user_id == self._own_user_id
        if is_own:
            nickname = "自分"
        elif sender is not None and sender.nickname:
            nickname = sender.nickname
        else:
            nickname = "?"

        bubble = QWidget()
        bubble.setMaximumWidth(_BUBBLE_MAX_WIDTH)
        col = QVBoxLayout(bubble)
        col.setContentsMargins(0, 0, 0, 0)
        header = ClickableLabel(f"<b>{nickname}</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        if not is_own and msg.user_id is not None:
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

        time_label = QLabel(_format_message_time(msg))
        time_label.setStyleSheet(f"color: {_TIME_LABEL_COLOR}; font-size: 11px;")

        # 相手のメッセージはアイコン付きで左寄せ、自分のメッセージは右寄せに
        # 表示し、誰の発言か一目で分かるようにする。時刻はバブルの内側
        # （画面中央寄りの辺）に添える。
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if is_own:
            row_layout.addStretch(1)
            row_layout.addWidget(time_label, 0, Qt.AlignmentFlag.AlignBottom)
            row_layout.addWidget(bubble)
        else:
            avatar_label = ClickableLabel()
            avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
            icon_url = None
            if sender is not None:
                icon_url = sender.profile_icon_thumbnail or sender.profile_icon
            if icon_url:
                load_square_icon(icon_url, _AVATAR_SIZE, avatar_label)
            if msg.user_id is not None:
                avatar_label.clicked.connect(
                    lambda uid=msg.user_id: open_user_profile(self._client_manager, uid)
                )
            row_layout.addWidget(avatar_label, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(bubble)
            row_layout.addWidget(time_label, 0, Qt.AlignmentFlag.AlignBottom)
            row_layout.addStretch(1)

        return row

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
                created_at=int(datetime.now().timestamp()),
            )
            self._append_message(echo)
            self._scroll_to_bottom()
