"""グループ詳細画面。ヘッダー・参加/退会ボタン・グループタイムラインを
表示する（説明文はSEO目的の長文が多く画面を圧迫するため表示しない）。"""

from __future__ import annotations

from typing import Optional

import qasync
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.call_type import CallType
from yaylib.models.group import Group
from yaylib.models.joinable_by import JoinableBy
from yaylib.models.posts_response import PostsResponse
from yaylib.models.realm_conference_call import RealmConferenceCall

from kotone.core.client_manager import ClientManager
from kotone.ui.call.call_dialog import CallDialog, is_agora_call
from kotone.ui.widgets.image_loader import load_square_icon
from kotone.ui.widgets.post_feed_list import PAGE_SIZE, PostFeedList

_ICON_SIZE = 56


class GroupDetailView(QWidget):
    back_requested = Signal()
    membership_changed = Signal()

    def __init__(self, group: Group, client_manager: ClientManager) -> None:
        super().__init__()
        self._group = group
        self._client_manager = client_manager

        back_button = QPushButton("← 一覧に戻る")
        back_button.clicked.connect(self.back_requested.emit)

        icon_label = QLabel()
        icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        icon_url = group.group_icon or group.cover_image
        if icon_url:
            load_square_icon(icon_url, _ICON_SIZE, icon_label)

        title_label = QLabel(f"<b>{group.topic or '(無題)'}</b>")
        meta_label = QLabel(
            f"メンバー {group.groups_users_count or 0}人　投稿 {group.posts_count or 0}件"
        )

        self._join_button = QPushButton()
        self._update_join_button_text()
        self._join_button.clicked.connect(self._on_join_leave_clicked)

        self._vc_button = QPushButton("VC")
        self._vc_button.clicked.connect(self._on_vc_clicked)

        header_text_col = QVBoxLayout()
        header_text_col.addWidget(title_label)
        header_text_col.addWidget(meta_label)

        header_row = QHBoxLayout()
        header_row.addWidget(icon_label)
        header_row.addLayout(header_text_col, 1)
        header_row.addWidget(self._vc_button)
        header_row.addWidget(self._join_button)

        async def _fetch_timeline(from_post_id: Optional[int]) -> PostsResponse:
            client = client_manager.require_client()
            return await client.get_group_timeline(
                group_id=self._group.id, number=PAGE_SIZE, from_post_id=from_post_id
            )

        self._feed = PostFeedList(client_manager, _fetch_timeline)
        self._feed.setVisible(False)

        self._view_posts_button = QPushButton("投稿を見る")
        self._view_posts_button.clicked.connect(self._on_view_posts_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(back_button)
        layout.addLayout(header_row)
        layout.addWidget(self._view_posts_button)
        layout.addWidget(self._feed, 1)

    def _on_view_posts_clicked(self) -> None:
        showing = not self._feed.isVisible()
        self._feed.setVisible(showing)
        self._view_posts_button.setText("投稿を閉じる" if showing else "投稿を見る")

    def _update_join_button_text(self) -> None:
        self._join_button.setText("退会する" if self._group.is_joined else "参加する")

    async def _find_active_conference_call(self, client) -> Optional[RealmConferenceCall]:
        timeline = await client.get_group_timeline(group_id=self._group.id, number=PAGE_SIZE)
        for post in timeline.posts or []:
            if post.conference_call is not None and post.conference_call.active:
                response = await client.get_conference_call(call_id=post.conference_call.id)
                return response.conference_call
        return None

    @qasync.asyncSlot()
    async def _on_vc_clicked(self) -> None:
        client = self._client_manager.require_client()
        self._vc_button.setEnabled(False)
        try:
            conference_call = await self._find_active_conference_call(client)
            if conference_call is None:
                # create_conference_call_postはx_jwtではなくsigned_info+
                # timestampでの署名を要求する(付けないと400 Invalid signed
                # info)。サーバー側がこのハッシュを検証するには、ハッシュに
                # 使ったapi_key/uuid(device_uuid)自体もリクエストに含めて
                # おく必要がある(どちらか片方でも欠けると同じエラーになる)。
                signed = await client.generate_signed_info()
                response = await client.create_conference_call_post(
                    group_id=self._group.id,
                    # "voice"はサーバーに拒否される(400 call_type does not
                    # have a valid value)。実際に稼働中の通話をAPIで確認した
                    # ところcall_type="vdo"だったため、音声のみの通話でも
                    # こちらを使う。
                    call_type=CallType.VDO.value,
                    joinable_by=JoinableBy.ANYONE.value,
                    timestamp=signed.timestamp,
                    signed_info=signed.value,
                    api_key=client.api_key,
                    uuid=client.device_uuid,
                )
                conference_call = response.conference_call
            if conference_call is not None:
                if not is_agora_call(conference_call):
                    QMessageBox.warning(
                        self,
                        "通話",
                        "この通話はAgora以外の方式(未対応)のため、このアプリからは参加できません。",
                    )
                else:
                    dialog = CallDialog(
                        conference_call,
                        self._group.topic or "(無題)",
                        self._client_manager,
                        parent=self,
                    )
                    dialog.show()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._vc_button.setEnabled(True)

    @qasync.asyncSlot()
    async def _on_join_leave_clicked(self) -> None:
        client = self._client_manager.require_client()
        self._join_button.setEnabled(False)
        try:
            if self._group.is_joined:
                await client.leave_group(id=self._group.id)
                self._group.is_joined = False
            else:
                await client.join_group(id=self._group.id)
                self._group.is_joined = True
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._update_join_button_text()
            self._join_button.setEnabled(True)
            self.membership_changed.emit()
