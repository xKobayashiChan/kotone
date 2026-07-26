"""グループ一覧の1行を表す部品。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from yaylib.models.group import Group

from kotone.ui.widgets.image_loader import load_square_icon

_ICON_SIZE = 40


class GroupRow(QFrame):
    opened = Signal(object)  # Group

    def __init__(self, group: Group) -> None:
        super().__init__()
        self._group = group
        self.setFrameShape(QFrame.Shape.StyledPanel)

        icon_label = QLabel()
        icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        # group_iconを設定していないサークルも多いため、その場合は
        # cover_image(カバー画像)を代わりに表示する。
        icon_url = group.group_icon or group.cover_image
        if icon_url:
            load_square_icon(icon_url, _ICON_SIZE, icon_label)

        joined_mark = " ✓参加中" if group.is_joined else ""
        text_label = QLabel(
            f"<b>{group.topic or '(無題)'}</b>{joined_mark}<br>"
            f"メンバー {group.groups_users_count or 0}人"
        )
        text_label.setTextFormat(Qt.TextFormat.RichText)

        layout = QHBoxLayout(self)
        layout.addWidget(icon_label)
        layout.addWidget(text_label, 1)

        open_button = QPushButton("開く")
        open_button.clicked.connect(lambda: self.opened.emit(self._group))
        layout.addWidget(open_button)
