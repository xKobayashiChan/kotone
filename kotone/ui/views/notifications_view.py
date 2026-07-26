"""通知/アクティビティ画面。get_user_activitiesで取得し、種別（いいね・
返信・フォロー等）ごとに分かりやすい文言で一覧表示する。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

import qasync
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.activity import Activity

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.clickable_label import ClickableLabel
from kotone.ui.widgets.image_loader import load_square_icon
from kotone.ui.widgets.user_profile_opener import open_user_profile

_AVATAR_SIZE = 40
_TEXT_PREVIEW_LEN = 24


def _format_timestamp(value: Optional[int]) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def _preview(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ")
    return text if len(text) <= _TEXT_PREVIEW_LEN else text[:_TEXT_PREVIEW_LEN] + "…"


def describe_activity(activity: Activity) -> str:
    nickname = activity.user.nickname if activity.user and activity.user.nickname else "誰か"
    kind = activity.type
    if kind == "like":
        post_text = _preview(activity.to_post.text if activity.to_post else None)
        return f"{nickname}さんが投稿にいいねしました「{post_text}」"
    if kind == "reply":
        post_text = _preview(activity.from_post.text if activity.from_post else None)
        return f"{nickname}さんが返信しました「{post_text}」"
    if kind == "follow":
        count = activity.followers_count or 1
        if count > 1:
            return f"{nickname}さん他{count - 1}人にフォローされました"
        return f"{nickname}さんにフォローされました"
    if kind == "follow_accepted":
        return f"{nickname}さんがフォローリクエストを承認しました"
    if kind == "id_check_success":
        return "本人確認が完了しました"
    if kind == "id_check_checking":
        return "本人確認を確認中です"
    return f"{nickname}さんから通知が届きました ({kind})"


class NotificationsView(QWidget):
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
        self._load_more_button.setVisible(False)
        self._load_more_button.clicked.connect(self._on_load_more_clicked)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.addWidget(self._load_more_button)
        self._rows_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._rows_container)
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
            response = await client.get_user_activities()
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            self._loading = False
            return

        self._clear_rows()
        activities = response.activities or []
        self._append_rows(activities)
        self._last_timestamp = response.last_timestamp
        self._load_more_button.setVisible(bool(self._last_timestamp))
        self._status_label.setText(f"{len(activities)}件")
        self._loading = False

    @qasync.asyncSlot()
    async def _on_load_more_clicked(self) -> None:
        if self._loading or self._last_timestamp is None:
            return
        self._loading = True
        client = self._client_manager.require_client()
        try:
            response = await client.get_user_activities(from_timestamp=self._last_timestamp)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"追加読み込みに失敗しました: {err}")
            self._loading = False
            return

        activities = response.activities or []
        self._append_rows(activities)
        self._last_timestamp = response.last_timestamp
        self._load_more_button.setVisible(bool(self._last_timestamp))
        self._loading = False

    def _append_rows(self, activities: List[Activity]) -> None:
        stretch_index = self._rows_layout.count() - 1
        for activity in activities:
            row = self._build_row(activity)
            self._rows_layout.insertWidget(stretch_index, row)
            stretch_index += 1

    def _build_row(self, activity: Activity) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(frame)

        avatar_label = ClickableLabel()
        avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        icon_url = None
        if activity.user is not None:
            icon_url = activity.user.profile_icon_thumbnail or activity.user.profile_icon
        if icon_url:
            load_square_icon(icon_url, _AVATAR_SIZE, avatar_label)
        if activity.user is not None and activity.user.id is not None:
            avatar_label.clicked.connect(
                lambda uid=activity.user.id: open_user_profile(self._client_manager, uid)
            )

        text_label = ClickableLabel(
            f"{describe_activity(activity)}　{_format_timestamp(activity.created_at)}"
        )
        text_label.setWordWrap(True)
        if activity.user is not None and activity.user.id is not None:
            text_label.clicked.connect(
                lambda uid=activity.user.id: open_user_profile(self._client_manager, uid)
            )

        layout.addWidget(avatar_label)
        layout.addWidget(text_label, 1)
        return frame

    def _clear_rows(self) -> None:
        while self._rows_layout.count() > 2:
            item = self._rows_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
