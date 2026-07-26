"""足跡（自分のプロフィールを見に来た人の履歴）画面。get_footprintsで
取得し一覧表示する。行ごとに削除（自分の足跡一覧から消す）もできる。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

import qasync
from PySide6.QtCore import Qt
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

from yaylib.models.footprint_dto import FootprintDTO

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.clickable_label import ClickableLabel
from kotone.ui.widgets.image_loader import load_square_icon
from kotone.ui.widgets.user_profile_opener import open_user_profile

_AVATAR_SIZE = 40


def _format_timestamp(value: Optional[int]) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


class FootprintsView(QWidget):
    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager
        self._loading = False
        self._next_page_value: Optional[str] = None

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
            response = await client.get_footprints()
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            self._loading = False
            return

        self._clear_rows()
        footprints = response.footprints or []
        self._append_rows(footprints)
        self._next_page_value = response.next_page_value
        self._load_more_button.setVisible(bool(self._next_page_value))
        self._status_label.setText(f"{len(footprints)}件")
        self._loading = False

    @qasync.asyncSlot()
    async def _on_load_more_clicked(self) -> None:
        if self._loading or not self._next_page_value:
            return
        self._loading = True
        client = self._client_manager.require_client()
        try:
            response = await client.get_footprints(var_from=self._next_page_value)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"追加読み込みに失敗しました: {err}")
            self._loading = False
            return

        footprints = response.footprints or []
        self._append_rows(footprints)
        self._next_page_value = response.next_page_value
        self._load_more_button.setVisible(bool(self._next_page_value))
        self._loading = False

    def _append_rows(self, footprints: List[FootprintDTO]) -> None:
        stretch_index = self._rows_layout.count() - 1
        for fp in footprints:
            row = self._build_row(fp)
            self._rows_layout.insertWidget(stretch_index, row)
            stretch_index += 1

    def _build_row(self, fp: FootprintDTO) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)

        avatar_label = ClickableLabel()
        avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        icon_url = None
        if fp.user is not None:
            icon_url = fp.user.profile_icon_thumbnail or fp.user.profile_icon
        if icon_url:
            load_square_icon(icon_url, _AVATAR_SIZE, avatar_label)

        nickname = fp.user.nickname if fp.user is not None and fp.user.nickname else "(不明なユーザー)"
        text_label = ClickableLabel(f"<b>{nickname}</b>　{_format_timestamp(fp.visited_at)}")
        text_label.setTextFormat(Qt.TextFormat.RichText)

        if fp.user is not None and fp.user.id is not None:
            avatar_label.clicked.connect(
                lambda uid=fp.user.id: open_user_profile(self._client_manager, uid)
            )
            text_label.clicked.connect(
                lambda uid=fp.user.id: open_user_profile(self._client_manager, uid)
            )

        layout.addWidget(avatar_label)
        layout.addWidget(text_label, 1)

        delete_button = QPushButton("削除")
        delete_button.clicked.connect(lambda: self._on_delete_clicked(fp, frame))
        layout.addWidget(delete_button)

        return frame

    @qasync.asyncSlot()
    async def _on_delete_clicked(self, fp: FootprintDTO, row: QWidget) -> None:
        if fp.id is None or fp.user is None or fp.user.id is None:
            return
        client = self._client_manager.require_client()
        try:
            await client.delete_footprint(user_id=fp.user.id, footprint_id=fp.id)
        except Exception:  # noqa: BLE001
            return
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    def _clear_rows(self) -> None:
        while self._rows_layout.count() > 2:
            item = self._rows_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
