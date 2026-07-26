"""グループ画面。「参加中」「探す」をタブで切り替え、グループを選ぶと
GroupDetailViewに遷移する。"""

from __future__ import annotations

import asyncio
from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.group import Group
from yaylib.models.groups_response import GroupsResponse

from kotone.core.client_manager import ClientManager
from kotone.ui.views.group_detail_view import GroupDetailView
from kotone.ui.widgets.group_list_panel import GroupListPanel


class GroupsView(QWidget):
    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager

        async def _fetch_my_groups(from_timestamp: Optional[int]) -> GroupsResponse:
            client = client_manager.require_client()
            return await client.list_my_groups(from_timestamp=from_timestamp)

        self._my_groups_panel = GroupListPanel(_fetch_my_groups)
        self._my_groups_panel.group_selected.connect(self._on_group_selected)

        self._keyword_edit = QLineEdit()
        self._keyword_edit.setPlaceholderText("キーワードで検索")
        self._keyword_edit.returnPressed.connect(self._on_search_clicked)
        search_button = QPushButton("検索")
        search_button.clicked.connect(self._on_search_clicked)

        search_row = QHBoxLayout()
        search_row.addWidget(self._keyword_edit, 1)
        search_row.addWidget(search_button)

        self._search_panel = GroupListPanel(self._make_search_fetcher(""))
        self._search_panel.group_selected.connect(self._on_group_selected)

        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addLayout(search_row)
        search_layout.addWidget(self._search_panel, 1)

        tabs = QTabWidget()
        # QTabWidget/QStackedWidgetは全ページ中の最大サイズを要求して
        # しまうため、一覧が増えてもウィンドウが際限なく大きくならない
        # ようにする。
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        tabs.addTab(self._my_groups_panel, "参加中")
        tabs.addTab(search_tab, "探す")

        self._list_page = QWidget()
        list_layout = QVBoxLayout(self._list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(tabs)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self._stack.addWidget(self._list_page)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stack)

        asyncio.ensure_future(self._my_groups_panel.refresh())

    def _make_search_fetcher(self, keyword: str):
        async def _fetch(from_timestamp: Optional[int]) -> GroupsResponse:
            client = self._client_manager.require_client()
            return await client.list_groups(
                keyword=keyword or None, from_timestamp=from_timestamp
            )

        return _fetch

    def _on_search_clicked(self) -> None:
        keyword = self._keyword_edit.text().strip()
        self._search_panel.set_fetch_page(self._make_search_fetcher(keyword))
        asyncio.ensure_future(self._search_panel.refresh())

    def _on_group_selected(self, group: Group) -> None:
        detail_view = GroupDetailView(group, self._client_manager)
        detail_view.back_requested.connect(lambda: self._on_back_requested(detail_view))
        detail_view.membership_changed.connect(self._on_membership_changed)
        self._stack.addWidget(detail_view)
        self._stack.setCurrentWidget(detail_view)

    def _on_back_requested(self, detail_view: GroupDetailView) -> None:
        self._stack.setCurrentWidget(self._list_page)
        self._stack.removeWidget(detail_view)
        detail_view.deleteLater()

    def _on_membership_changed(self) -> None:
        asyncio.ensure_future(self._my_groups_panel.refresh())
