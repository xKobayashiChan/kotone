"""投稿一覧＋ページネーション付きスクロールを提供する再利用可能な部品。

「フォロー中」「オープン」など、get_xxx_timeline系のAPIを外から関数として
差し込むことで、同じ表示・ページネーション・いいね等の配線を共有する。
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional, Set

import qasync
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.post import Post
from yaylib.models.posts_response import PostsResponse

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.post_card import PostCard

PAGE_SIZE = 30
_LOAD_MORE_THRESHOLD = 0.9

# from_post_id (Noneなら先頭ページ) を受け取り、PostsResponseを返す関数。
FetchPage = Callable[[Optional[int]], Awaitable[PostsResponse]]


class PostFeedList(QWidget):
    def __init__(self, client_manager: ClientManager, fetch_page: FetchPage) -> None:
        super().__init__()
        self._client_manager = client_manager
        self._fetch_page = fetch_page
        self._loading = False
        self._has_more = True
        self._last_post_id: Optional[int] = None
        self._seen_post_ids: Set[int] = set()

        self._status_label = QLabel("")
        refresh_button = QPushButton("更新")
        refresh_button.clicked.connect(self._on_refresh_clicked)

        top_row = QHBoxLayout()
        top_row.addWidget(refresh_button)
        top_row.addWidget(self._status_label, 1)

        self._posts_container = QWidget()
        self._posts_layout = QVBoxLayout(self._posts_container)
        self._posts_layout.addStretch(1)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._posts_container)
        self._scroll_area.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        # 中身がどれだけ増えてもこのスクロールエリアの"欲しいサイズ"を
        # 親レイアウト（延いてはウィンドウ全体）へ伝播させない。これが
        # 無いと投稿が増えるたびにウィンドウが際限なく大きくなろうとする。
        self._scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored
        )

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self._scroll_area, 1)

        asyncio.ensure_future(self.refresh())

    @qasync.asyncSlot()
    async def _on_refresh_clicked(self) -> None:
        await self.refresh()

    async def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._status_label.setText("読み込み中...")
        try:
            response = await self._fetch_page(None)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"タイムラインの取得に失敗しました: {err}")
            self._loading = False
            return

        self._clear_posts()
        self._seen_post_ids.clear()
        self._last_post_id = None
        posts = response.posts or []
        self._append_posts(posts)
        self._has_more = len(posts) >= PAGE_SIZE
        self._status_label.setText(f"{len(posts)}件表示中")
        self._loading = False

    async def _load_more(self) -> None:
        if self._loading or not self._has_more or self._last_post_id is None:
            return
        self._loading = True
        self._status_label.setText("さらに読み込み中...")
        try:
            response = await self._fetch_page(self._last_post_id)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"追加読み込みに失敗しました: {err}")
            self._loading = False
            return

        posts = response.posts or []
        self._append_posts(posts)
        self._has_more = len(posts) >= PAGE_SIZE
        self._status_label.setText("")
        self._loading = False

    def prepend_post(self, post: Post) -> None:
        """自分が投稿した直後に、サーバーへ再取得しなくても先頭に反映する
        ためのフック（フォロー中タブから呼ばれる想定）。"""
        if post.id is not None:
            self._seen_post_ids.add(post.id)
        card = self._build_card(post)
        self._posts_layout.insertWidget(0, card)

    def _append_posts(self, posts: List[Post]) -> None:
        # レイアウト末尾のstretchの直前に挿入していく。
        stretch_index = self._posts_layout.count() - 1
        for post in posts:
            if post.id is None or post.id in self._seen_post_ids:
                continue
            self._seen_post_ids.add(post.id)
            self._last_post_id = post.id
            card = self._build_card(post)
            self._posts_layout.insertWidget(stretch_index, card)
            stretch_index += 1

    def _build_card(self, post: Post) -> PostCard:
        card = PostCard(post, self._client_manager)
        card.deleted.connect(lambda post_id, c=card: self._on_card_deleted(post_id, c))
        return card

    def _on_card_deleted(self, post_id: int, card: PostCard) -> None:
        self._seen_post_ids.discard(post_id)
        self._posts_layout.removeWidget(card)
        card.deleteLater()

    def _clear_posts(self) -> None:
        while self._posts_layout.count() > 1:
            item = self._posts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_scrolled(self, value: int) -> None:
        bar = self._scroll_area.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        if value / bar.maximum() >= _LOAD_MORE_THRESHOLD:
            asyncio.ensure_future(self._load_more())
