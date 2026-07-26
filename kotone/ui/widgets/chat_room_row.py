"""チャットルーム一覧の1行を表す部品。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from yaylib.models.realm_chat_room import RealmChatRoom

from kotone.ui.widgets.image_loader import load_square_icon

_AVATAR_SIZE = 40


def room_display_name(room: RealmChatRoom, own_user_id: int) -> str:
    if room.name:
        return room.name
    if room.members:
        other = next(
            (m for m in room.members if m.id != own_user_id and m.nickname), None
        )
        if other is not None:
            return other.nickname
    return "チャット"


class ChatRoomRow(QFrame):
    opened = Signal(object)  # RealmChatRoom

    def __init__(self, room: RealmChatRoom, own_user_id: int) -> None:
        super().__init__()
        self._room = room
        self.setFrameShape(QFrame.Shape.StyledPanel)

        avatar_label = QLabel()
        avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        icon_url = None
        if room.members:
            other = next((m for m in room.members if m.profile_icon), None)
            if other is not None:
                icon_url = other.profile_icon
        if icon_url:
            load_square_icon(icon_url, _AVATAR_SIZE, avatar_label)

        name = room_display_name(room, own_user_id)
        preview = room.last_message.text if room.last_message and room.last_message.text else ""
        text_label = QLabel(f"<b>{name}</b><br>{preview}")
        text_label.setTextFormat(Qt.TextFormat.RichText)

        layout = QHBoxLayout(self)
        layout.addWidget(avatar_label)
        layout.addWidget(text_label, 1)
        if room.unread_count:
            layout.addWidget(QLabel(f"未読 {room.unread_count}"))

        open_button = QPushButton("開く")
        open_button.clicked.connect(lambda: self.opened.emit(self._room))
        layout.addWidget(open_button)
