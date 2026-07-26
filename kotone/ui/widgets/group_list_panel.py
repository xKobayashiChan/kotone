"""グループ一覧＋ページネーションを提供する再利用可能な部品。

「参加中グループ」「グループ検索」など、list_groups系のAPIを外から関数
として差し込むことで、同じ表示・ページネーションの配線を共有する。
"""

from __future__ import annotations

from typing import Awaitable, Callable, List, Optional

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

from yaylib.models.group import Group
from yaylib.models.groups_response import GroupsResponse

from kotone.ui.widgets.group_row import GroupRow

# from_timestamp (Noneなら先頭ページ) を受け取り、GroupsResponseを返す関数。
FetchPage = Callable[[Optional[int]], Awaitable[GroupsResponse]]


class GroupListPanel(QWidget):
    group_selected = Signal(object)  # Group

    def __init__(self, fetch_page: FetchPage) -> None:
        super().__init__()
        self._fetch_page = fetch_page
        self._loading = False
        self._last_timestamp: Optional[int] = None

        self._status_label = QLabel("")

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._status_label)
        layout.addWidget(scroll_area, 1)

    def set_fetch_page(self, fetch_page: FetchPage) -> None:
        self._fetch_page = fetch_page

    async def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._status_label.setText("読み込み中...")
        try:
            response = await self._fetch_page(None)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            self._loading = False
            return

        self._clear_rows()
        groups = response.groups or []
        self._append_groups(groups)
        self._last_timestamp = groups[-1].updated_at if groups else None
        self._load_more_button.setVisible(bool(groups))
        self._status_label.setText(f"{len(groups)}件")
        self._loading = False

    @qasync.asyncSlot()
    async def _on_load_more_clicked(self) -> None:
        if self._loading or self._last_timestamp is None:
            return
        self._loading = True
        try:
            response = await self._fetch_page(self._last_timestamp)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"追加読み込みに失敗しました: {err}")
            self._loading = False
            return

        groups = response.groups or []
        self._append_groups(groups)
        if groups:
            self._last_timestamp = groups[-1].updated_at
        self._load_more_button.setVisible(bool(groups))
        self._loading = False

    def _append_groups(self, groups: List[Group]) -> None:
        stretch_index = self._rows_layout.count() - 1
        for group in groups:
            row = GroupRow(group)
            row.opened.connect(self.group_selected.emit)
            self._rows_layout.insertWidget(stretch_index, row)
            stretch_index += 1

    def _clear_rows(self) -> None:
        while self._rows_layout.count() > 2:
            item = self._rows_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
