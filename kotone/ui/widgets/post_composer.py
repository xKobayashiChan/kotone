"""投稿作成フォーム（テキスト・画像最大9枚・動画1本、画像/動画は排他）。"""

from __future__ import annotations

import asyncio
from typing import Optional

import qasync
import yaylib
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from yaylib import Upload
from yaylib.models.call_type import CallType
from yaylib.models.joinable_by import JoinableBy
from yaylib.models.post import Post

from kotone.core.client_manager import ClientManager
from kotone.ui.call.call_dialog import CallDialog
from kotone.ui.widgets.media_picker import MediaPicker

_ATTACHMENT_KWARGS = [
    "attachment_filename",
    "attachment_2_filename",
    "attachment_3_filename",
    "attachment_4_filename",
    "attachment_5_filename",
    "attachment_6_filename",
    "attachment_7_filename",
    "attachment_8_filename",
    "attachment_9_filename",
]


class PostComposer(QWidget):
    post_created = Signal(object)  # Post

    def __init__(self, client_manager: ClientManager) -> None:
        super().__init__()
        self._client_manager = client_manager

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("いまどうしてる？")
        self._text_edit.setFixedHeight(80)

        self._media_picker = MediaPicker()

        self._status_label = QLabel("")
        # TODO: VC(音声通話)機能は未完成のため無効化中。実装を完了させたら有効化する。
        self._call_button = QPushButton("\U0001F4DE 通話を始める")
        self._call_button.clicked.connect(self._on_call_clicked)
        self._call_button.setEnabled(False)
        self._call_button.setToolTip("通話機能は開発中のため利用できません")
        self._submit_button = QPushButton("投稿する")
        self._submit_button.setProperty("primary", True)
        self._submit_button.clicked.connect(self._on_submit_clicked)

        button_row = QHBoxLayout()
        button_row.addWidget(self._call_button)
        button_row.addStretch(1)
        button_row.addWidget(self._submit_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._text_edit)
        layout.addWidget(self._media_picker)
        layout.addLayout(button_row)
        layout.addWidget(self._status_label)

    @qasync.asyncSlot()
    async def _on_submit_clicked(self) -> None:
        text = self._text_edit.toPlainText().strip()
        if not text and self._media_picker.is_empty():
            self._status_label.setText("本文か画像/動画のどちらかを入力してください。")
            return

        self._set_busy(True)
        self._status_label.setText("投稿中...")
        try:
            post = await self._submit(text)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"投稿に失敗しました: {err}")
            self._set_busy(False)
            return

        self._text_edit.clear()
        self._media_picker.clear()
        self._status_label.setText("投稿しました。")
        self._set_busy(False)
        self.post_created.emit(post)

    async def _submit(self, text: str) -> Post:
        client = self._client_manager.require_client()

        attachment_kwargs: dict = {}
        video_file_name: Optional[str] = None
        post_type = yaylib.PostType.TEXT

        image_paths = self._media_picker.image_paths
        if image_paths:
            uploads = []
            for path in image_paths:
                data = await asyncio.to_thread(path.read_bytes)
                uploads.append(Upload(filename=path.name, body=data))
            filenames = await client.upload_post_images(uploads)
            for kwarg, filename in zip(_ATTACHMENT_KWARGS, filenames):
                attachment_kwargs[kwarg] = filename
            post_type = yaylib.PostType.IMAGE

        video_path = self._media_picker.video_path
        if video_path is not None:
            data = await asyncio.to_thread(video_path.read_bytes)
            video_file_name = await client.upload_video(data)
            post_type = yaylib.PostType.VIDEO

        return await client.create_post(
            x_jwt=client.generate_x_jwt(),
            post_type=post_type,
            text=text,
            video_file_name=video_file_name,
            **attachment_kwargs,
        )

    @qasync.asyncSlot()
    async def _on_call_clicked(self) -> None:
        client = self._client_manager.require_client()
        self._call_button.setEnabled(False)
        self._status_label.setText("通話を開始しています...")
        try:
            response = await client.create_conference_call_post(
                call_type=CallType.VOICE.value,
                joinable_by=JoinableBy.ANYONE.value,
                text=self._text_edit.toPlainText().strip() or None,
            )
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"通話の開始に失敗しました: {err}")
            return
        finally:
            self._call_button.setEnabled(True)

        self._status_label.setText("")
        self._text_edit.clear()
        if response.post is not None:
            self.post_created.emit(response.post)
        if response.conference_call is not None:
            dialog = CallDialog(response.conference_call, "通話", self._client_manager, parent=self)
            dialog.show()

    def _set_busy(self, busy: bool) -> None:
        self._submit_button.setEnabled(not busy)
        self._text_edit.setEnabled(not busy)
