"""他ユーザーのプロフィールを表示する閲覧用ダイアログ（フォロー切替のみ
操作可能。編集は自分のプロフィール画面(ProfileView)のみ）。"""

from __future__ import annotations

import asyncio
from typing import Optional

import qasync
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from yaylib.models.realm_user import RealmUser

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.image_loader import load_cropped_image, load_square_icon

_AVATAR_SIZE = 96
_COVER_WIDTH = 420
_COVER_HEIGHT = 140

_GENDER_LABELS = {0: "男性", 1: "女性", -1: "回答しない"}


def _format_gender(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return _GENDER_LABELS.get(value, "不明")


class UserProfileDialog(QDialog):
    def __init__(
        self, user_id: int, client_manager: ClientManager, parent=None
    ) -> None:
        super().__init__(parent)
        self._user_id = user_id
        self._client_manager = client_manager
        self._user: Optional[RealmUser] = None

        self.setWindowTitle("プロフィール")
        self.resize(460, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(_COVER_WIDTH, _COVER_HEIGHT)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)

        self._nickname_label = QLabel("")
        self._nickname_label.setTextFormat(Qt.TextFormat.RichText)
        self._meta_label = QLabel("")
        self._demographics_label = QLabel("")
        self._bio_label = QLabel("")
        self._bio_label.setWordWrap(True)

        self._follow_button = QPushButton("")
        self._follow_button.setProperty("primary", True)
        self._follow_button.setVisible(False)
        self._follow_button.clicked.connect(self._on_follow_clicked)

        self._status_label = QLabel("読み込み中...")

        header_col = QVBoxLayout()
        header_col.addWidget(self._nickname_label)
        header_col.addWidget(self._meta_label)
        header_col.addWidget(self._demographics_label)

        header_row = QHBoxLayout()
        header_row.addWidget(self._avatar_label)
        header_row.addLayout(header_col, 1)
        header_row.addWidget(self._follow_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._cover_label)
        layout.addLayout(header_row)
        layout.addWidget(self._bio_label)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

        asyncio.ensure_future(self._load())

    async def _load(self) -> None:
        client = self._client_manager.require_client()
        try:
            # get_user(自分専用に近い)は本人以外だとgender/prefecture/
            # followings_countがことごとくnullになるため、他ユーザーの
            # プロフィール表示にはget_user_infoを使う（同じ項目でも
            # ちゃんと値が返ってくる）。
            response = await client.get_user_info(id=self._user_id)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            return

        user = response.user
        self._user = user
        if user is None:
            self._status_label.setText("プロフィールを取得できませんでした。")
            return

        self.setWindowTitle(user.nickname or "プロフィール")
        self._nickname_label.setText(f"<b style='font-size:16px'>{user.nickname or ''}</b>")
        meta_parts = [f"フォロワー {user.followers_count or 0}"]
        if user.followings_count is not None:
            meta_parts.append(f"フォロー中 {user.followings_count}")
        self._meta_label.setText("　".join(meta_parts))

        # 生年月日(年齢)はどの経路で取得しても常にnullで返ってくるため
        # 表示しようがない。性別・都道府県は取れた分だけ出す。
        demographics_parts = []
        gender_label = _format_gender(user.gender)
        if gender_label is not None:
            demographics_parts.append(gender_label)
        if user.prefecture:
            demographics_parts.append(user.prefecture)
        self._demographics_label.setText("　".join(demographics_parts))

        self._bio_label.setText(user.biography or "")
        if user.profile_icon:
            load_square_icon(user.profile_icon, _AVATAR_SIZE, self._avatar_label)
        if user.cover_image:
            load_cropped_image(user.cover_image, _COVER_WIDTH, _COVER_HEIGHT, self._cover_label)
        self._status_label.setText("")

        if user.id is not None and user.id != client.user_id:
            self._follow_button.setVisible(True)
            self._update_follow_button_text()

    def _update_follow_button_text(self) -> None:
        if self._user is None:
            return
        self._follow_button.setText("フォロー中" if self._user.following else "フォローする")

    @qasync.asyncSlot()
    async def _on_follow_clicked(self) -> None:
        if self._user is None or self._user.id is None:
            return
        client = self._client_manager.require_client()
        self._follow_button.setEnabled(False)
        try:
            if self._user.following:
                await client.unfollow_user(id=self._user.id)
                self._user.following = False
            else:
                await client.follow_user(id=self._user.id)
                self._user.following = True
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._update_follow_button_text()
            self._follow_button.setEnabled(True)
