"""タイムライン画面。「フォロー中」（get_following_timeline）と「オープン」
（get_timeline、おすすめ寄りの全体フィードで自分の投稿は含まれない）を
タブで切り替えて表示する。投稿フォームは共通で、投稿すると「フォロー中」
タブの先頭に反映する（「オープン」は本来のレコメンド挙動に任せる）。
"""

from __future__ import annotations

from typing import Optional

import yaylib
from PySide6.QtWidgets import QSizePolicy, QTabWidget, QVBoxLayout, QWidget
from yaylib.models.posts_response import PostsResponse

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.post_composer import PostComposer
from kotone.ui.widgets.post_feed_list import PAGE_SIZE, PostFeedList


class TimelineView(QWidget):
    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()

        composer = PostComposer(client_manager)

        async def _fetch_following(from_post_id: Optional[int]) -> PostsResponse:
            client = client_manager.require_client()
            return await client.get_following_timeline(
                number=PAGE_SIZE, from_post_id=from_post_id
            )

        async def _fetch_open(from_post_id: Optional[int]) -> PostsResponse:
            client = client_manager.require_client()
            return await client.get_timeline(
                noreply_mode=yaylib.NoreplyMode.EMPTY,
                number=PAGE_SIZE,
                from_post_id=from_post_id,
            )

        following_feed = PostFeedList(client_manager, _fetch_following)
        open_feed = PostFeedList(client_manager, _fetch_open)
        composer.post_created.connect(following_feed.prepend_post)

        tabs = QTabWidget()
        # QTabWidgetもQStackedWidgetと同様に全タブの最大サイズを要求して
        # しまうため、内容が増えてもウィンドウが際限なく大きくならない
        # ようにする。
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        tabs.addTab(following_feed, "フォロー中")
        tabs.addTab(open_feed, "オープン")

        layout = QVBoxLayout(self)
        layout.addWidget(composer)
        layout.addWidget(tabs, 1)
