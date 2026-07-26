"""自分のプロフィール表示・編集（アイコン・カバー画像・ニックネーム・
自己紹介）。

TODO(#2): アイコン/カバー画像は保存直後は反映されるが、しばらくすると
Yay!側で「未設定」に戻ることがある（サーバー側の非同期モデレーション
処理が原因と推測されるが未解決。クライアント側の実装に既知の問題は
見つかっていない）。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import qasync
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from yaylib import Upload
from yaylib.models.realm_user import RealmUser

from kotone.core.client_manager import ClientManager
from kotone.ui.widgets.image_loader import fit_pixmap, load_cropped_image, load_square_icon

_AVATAR_SIZE = 96
_COVER_WIDTH = 420
_COVER_HEIGHT = 150
_IMAGE_FILTER = "画像ファイル (*.png *.jpg *.jpeg *.gif)"


class ProfileView(QWidget):
    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager
        self._user: Optional[RealmUser] = None
        self._pending_avatar: Optional[Path] = None
        self._pending_cover: Optional[Path] = None

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(_COVER_WIDTH, _COVER_HEIGHT)
        change_cover_button = QPushButton("カバー画像を変更")
        change_cover_button.clicked.connect(self._on_pick_cover)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        change_avatar_button = QPushButton("アイコンを変更")
        change_avatar_button.clicked.connect(self._on_pick_avatar)

        avatar_col = QVBoxLayout()
        avatar_col.addWidget(self._avatar_label)
        avatar_col.addWidget(change_avatar_button)
        avatar_col.addStretch(1)

        self._nickname_edit = QLineEdit()
        self._bio_edit = QTextEdit()
        self._bio_edit.setFixedHeight(100)

        form_col = QVBoxLayout()
        form_col.addWidget(QLabel("ニックネーム"))
        form_col.addWidget(self._nickname_edit)
        form_col.addWidget(QLabel("自己紹介"))
        form_col.addWidget(self._bio_edit)

        top_row = QHBoxLayout()
        top_row.addLayout(avatar_col)
        top_row.addLayout(form_col, 1)

        self._status_label = QLabel("")
        save_button = QPushButton("保存する")
        save_button.setProperty("primary", True)
        save_button.clicked.connect(self._on_save_clicked)
        refresh_button = QPushButton("再読み込み")
        refresh_button.clicked.connect(self._on_refresh_clicked)

        button_row = QHBoxLayout()
        button_row.addWidget(save_button)
        button_row.addWidget(refresh_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._cover_label)
        layout.addWidget(change_cover_button)
        layout.addLayout(top_row)
        layout.addLayout(button_row)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

        asyncio.ensure_future(self._load())

    @qasync.asyncSlot()
    async def _on_refresh_clicked(self) -> None:
        await self._load()

    async def _load(self) -> None:
        client = self._client_manager.require_client()
        self._status_label.setText("読み込み中...")
        try:
            response = await client.get_user(id=client.user_id)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"取得に失敗しました: {err}")
            return

        user = response.user
        self._user = user
        if user is None:
            self._status_label.setText("プロフィールを取得できませんでした。")
            return

        self._pending_avatar = None
        self._pending_cover = None
        self._nickname_edit.setText(user.nickname or "")
        self._bio_edit.setPlainText(user.biography or "")
        if user.profile_icon:
            load_square_icon(user.profile_icon, _AVATAR_SIZE, self._avatar_label)
        if user.cover_image:
            load_cropped_image(user.cover_image, _COVER_WIDTH, _COVER_HEIGHT, self._cover_label)
        self._status_label.setText("")

    def _on_pick_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "アイコン画像を選択", "", _IMAGE_FILTER)
        if path:
            self._pending_avatar = Path(path)
            self._avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._avatar_label.setPixmap(fit_pixmap(pixmap, _AVATAR_SIZE, _AVATAR_SIZE))

    def _on_pick_cover(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "カバー画像を選択", "", _IMAGE_FILTER)
        if path:
            self._pending_cover = Path(path)
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._cover_label.setPixmap(fit_pixmap(pixmap, _COVER_WIDTH, _COVER_HEIGHT))

    @qasync.asyncSlot()
    async def _on_save_clicked(self) -> None:
        client = self._client_manager.require_client()
        self._status_label.setText("保存中...")
        try:
            avatar_filename = None
            if self._pending_avatar is not None:
                data = await asyncio.to_thread(self._pending_avatar.read_bytes)
                upload = Upload(filename=self._pending_avatar.name, body=data)
                avatar_filename = await client.upload_avatar_image(upload)

            cover_filename = None
            if self._pending_cover is not None:
                data = await asyncio.to_thread(self._pending_cover.read_bytes)
                upload = Upload(filename=self._pending_cover.name, body=data)
                cover_filename = await client.upload_cover_image(upload)

            signed = await client.generate_signed_info()
            kwargs = {
                # signed_infoはapi_key+uuid+timestampのハッシュなので、
                # サーバー側が検証できるようこの3つも併せて送る必要がある
                # (省略すると "Invalid signed info" (-380) で拒否される)。
                "api_key": client.api_key,
                "uuid": client.device_uuid,
                "signed_info": signed.value,
                "timestamp": signed.timestamp,
                "nickname": self._nickname_edit.text().strip(),
                "biography": self._bio_edit.toPlainText(),
            }
            if avatar_filename:
                kwargs["profile_icon_filename"] = avatar_filename
            if cover_filename:
                kwargs["cover_image_filename"] = cover_filename

            await client.edit_user(**kwargs)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"保存に失敗しました: {err}")
            return

        self._status_label.setText("保存しました。")
        await self._load()
