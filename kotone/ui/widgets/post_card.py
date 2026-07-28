"""タイムライン上の1投稿を表示するカード。

いいね・削除（自分の投稿のみ）・コメント表示/投稿を扱う。コメントは
Yay!内部では「in_reply_toを持つ投稿」として扱われるため、一覧取得は
get_conversation、投稿はcreate_post(in_reply_to=...)で行う。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

import qasync
import yaylib
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.call_type import CallType
from yaylib.models.post import Post
from yaylib.models.realm_conference_call import RealmConferenceCall

from kotone.core.client_manager import ClientManager
from kotone.ui.call.call_dialog import CallDialog, is_agora_call
from kotone.ui.widgets.clickable_label import ClickableLabel
from kotone.ui.widgets.image_loader import load_pixmap, load_square_icon
from kotone.ui.widgets.user_profile_opener import open_user_profile

logger = logging.getLogger(__name__)

_AVATAR_SIZE = 40
_MEDIA_MAX_WIDTH = 420


def _format_timestamp(value: Optional[int]) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def _format_ms(value: int) -> str:
    total_seconds = max(0, value) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class PostCard(QFrame):
    deleted = Signal(int)  # post_id

    def __init__(self, post: Post, client_manager: ClientManager) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # 個々のカードを箱で囲まず、区切り線だけのフラットな見た目にする
        # ためのオブジェクト名（theme.pyでこの名前だけ別スタイルを当てる）。
        self.setObjectName("PostCard")
        self._post = post
        self._client_manager = client_manager
        # プレイヤー/動画ウィジェットはGC/イベントループから回収されない
        # よう、生きている間はカードに参照を保持しておく。
        self._player: Optional[QMediaPlayer] = None
        self._video_widget: Optional[QVideoWidget] = None

        self._liked = bool(post.liked)
        self._likes_count = post.likes_count or 0
        self._comments_count = post.in_reply_to_post_count or 0
        self._comments_loaded = False

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_header(post))

        text_label = QLabel(post.text or "")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        media_widget = self._build_media_widget(post)
        if media_widget is not None:
            layout.addWidget(media_widget)

        call_widget = self._build_conference_call_widget(post)
        if call_widget is not None:
            layout.addWidget(call_widget)

        layout.addLayout(self._build_actions_row(post))

        self._comments_area = QWidget()
        self._comments_layout = QVBoxLayout(self._comments_area)
        self._comments_area.setVisible(False)
        layout.addWidget(self._comments_area)

    def _build_header(self, post: Post) -> QHBoxLayout:
        avatar_label = ClickableLabel()
        avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)

        user = post.user
        if user is not None and user.profile_icon:
            load_square_icon(user.profile_icon, _AVATAR_SIZE, avatar_label)

        nickname = user.nickname if user is not None and user.nickname else "(不明なユーザー)"
        header_label = ClickableLabel(f"<b>{nickname}</b>　{_format_timestamp(post.created_at)}")
        header_label.setTextFormat(Qt.TextFormat.RichText)

        if user is not None and user.id is not None:
            avatar_label.clicked.connect(
                lambda uid=user.id: open_user_profile(self._client_manager, uid)
            )
            header_label.clicked.connect(
                lambda uid=user.id: open_user_profile(self._client_manager, uid)
            )

        row = QHBoxLayout()
        row.addWidget(avatar_label)
        row.addWidget(header_label, 1)
        return row

    def _build_media_widget(self, post: Post) -> Optional[QWidget]:
        if post.videos:
            return self._build_video_widget(post.videos[0])
        if post.attachment:
            image_label = QLabel()
            image_label.setMaximumWidth(_MEDIA_MAX_WIDTH)
            load_pixmap(post.attachment, lambda pm: self._set_scaled_pixmap(image_label, pm))
            return image_label
        return None

    def _build_conference_call_widget(self, post: Post) -> Optional[QWidget]:
        call = post.conference_call
        if call is None:
            return None

        frame = QFrame()
        frame.setObjectName("ConferenceCallCard")
        row = QHBoxLayout(frame)

        icon = "\U0001F3A5" if call.call_type == CallType.VDO else "\U0001F4DE"
        row.addWidget(QLabel(icon))

        count = call.conference_call_users_count or len(call.conference_call_users or [])
        status_text = f"{count}人が参加中" if call.active else "通話は終了しました"
        text_col = QVBoxLayout()
        text_col.addWidget(QLabel(f"<b>{post.text or '通話'}</b>"))
        text_col.addWidget(QLabel(status_text))
        row.addLayout(text_col, 1)

        join_button = QPushButton("参加する")
        join_button.setProperty("primary", True)
        join_button.clicked.connect(lambda: self._on_join_call_clicked(call))
        row.addWidget(join_button)

        return frame

    @qasync.asyncSlot()
    async def _on_join_call_clicked(self, call: RealmConferenceCall) -> None:
        if call.id is None:
            return
        client = self._client_manager.require_client()
        try:
            response = await client.get_conference_call(call_id=call.id)
        except Exception:  # noqa: BLE001
            logger.exception("get_conference_call failed for call_id=%s", call.id)
            return
        logger.debug("get_conference_call response: %r", response.model_dump())
        if response.conference_call is None:
            return
        if not is_agora_call(response.conference_call):
            QMessageBox.warning(
                self,
                "通話",
                "この通話はAgora以外の方式(未対応)のため、このアプリからは参加できません。",
            )
            return
        group_name = self._post.group.topic if self._post.group else "通話"
        dialog = CallDialog(response.conference_call, group_name, self._client_manager, parent=self)
        dialog.show()

    def _set_scaled_pixmap(self, label: QLabel, pixmap: QPixmap) -> None:
        scaled = pixmap.scaledToWidth(
            _MEDIA_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation
        )
        label.setPixmap(scaled)

    def _build_video_widget(self, video) -> QPushButton:
        button = QPushButton("▶ 動画を再生")
        button.clicked.connect(lambda: self._play_video(button, video))
        return button

    def _play_video(self, button: QPushButton, video) -> None:
        layout = self.layout()
        index = layout.indexOf(button)
        layout.removeWidget(button)
        button.deleteLater()

        video_widget = QVideoWidget()
        video_widget.setMinimumSize(_MEDIA_MAX_WIDTH, int(_MEDIA_MAX_WIDTH * 9 / 16))
        player = QMediaPlayer(self)
        audio_output = QAudioOutput(self)
        player.setAudioOutput(audio_output)
        player.setVideoOutput(video_widget)
        self._player = player
        self._video_widget = video_widget

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(video_widget)
        col.addLayout(self._build_video_controls(player))

        layout.insertWidget(index, container)
        player.setSource(QUrl(video.video_url))
        player.play()

    def _build_video_controls(self, player: QMediaPlayer) -> QHBoxLayout:
        play_pause_button = QPushButton("⏸")
        position_slider = QSlider(Qt.Orientation.Horizontal)
        position_slider.setRange(0, 0)
        time_label = QLabel("00:00 / 00:00")

        seeking = False

        def _toggle_play_pause() -> None:
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.pause()
            else:
                player.play()

        def _on_playback_state_changed(state: QMediaPlayer.PlaybackState) -> None:
            is_playing = state == QMediaPlayer.PlaybackState.PlayingState
            play_pause_button.setText("⏸" if is_playing else "▶")

        def _on_duration_changed(duration: int) -> None:
            position_slider.setRange(0, duration)
            time_label.setText(f"{_format_ms(player.position())} / {_format_ms(duration)}")

        def _on_position_changed(position: int) -> None:
            if not seeking:
                position_slider.setValue(position)
            time_label.setText(f"{_format_ms(position)} / {_format_ms(player.duration())}")

        def _on_slider_pressed() -> None:
            nonlocal seeking
            seeking = True

        def _on_slider_released() -> None:
            nonlocal seeking
            seeking = False
            player.setPosition(position_slider.value())

        play_pause_button.clicked.connect(_toggle_play_pause)
        player.playbackStateChanged.connect(_on_playback_state_changed)
        player.durationChanged.connect(_on_duration_changed)
        player.positionChanged.connect(_on_position_changed)
        position_slider.sliderPressed.connect(_on_slider_pressed)
        position_slider.sliderReleased.connect(_on_slider_released)

        row = QHBoxLayout()
        row.addWidget(play_pause_button)
        row.addWidget(position_slider, 1)
        row.addWidget(time_label)
        return row

    # ---- いいね・削除・コメント ----

    def _build_actions_row(self, post: Post) -> QHBoxLayout:
        row = QHBoxLayout()

        self._like_button = QPushButton()
        self._update_like_button_text()
        self._like_button.clicked.connect(self._on_like_clicked)
        row.addWidget(self._like_button)

        self._comment_button = QPushButton()
        self._update_comment_button_text()
        self._comment_button.clicked.connect(self._on_comment_button_clicked)
        row.addWidget(self._comment_button)

        row.addWidget(QLabel(f"\U0001F501 {post.reposts_count or 0}"))

        client = self._client_manager.require_client()
        if post.user is not None and post.user.id == client.user_id:
            delete_button = QPushButton("削除")
            delete_button.clicked.connect(self._on_delete_clicked)
            row.addWidget(delete_button)

        row.addStretch(1)
        return row

    def _update_like_button_text(self) -> None:
        heart = "♥" if self._liked else "♡"
        self._like_button.setText(f"{heart} {self._likes_count}")

    def _update_comment_button_text(self) -> None:
        self._comment_button.setText(f"\U0001F4AC {self._comments_count}")

    @qasync.asyncSlot()
    async def _on_like_clicked(self) -> None:
        if self._post.id is None:
            return
        client = self._client_manager.require_client()
        self._like_button.setEnabled(False)
        try:
            if self._liked:
                await client.unlike_post(id=self._post.id)
                self._liked = False
                self._likes_count = max(0, self._likes_count - 1)
            else:
                await client.like_posts(post_ids=[self._post.id])
                self._liked = True
                self._likes_count += 1
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._update_like_button_text()
            self._like_button.setEnabled(True)

    @qasync.asyncSlot()
    async def _on_delete_clicked(self) -> None:
        if self._post.id is None:
            return
        client = self._client_manager.require_client()
        self.setEnabled(False)
        try:
            await client.delete_posts(posts_ids=[self._post.id])
        except Exception:  # noqa: BLE001
            self.setEnabled(True)
            return
        self.deleted.emit(self._post.id)

    @qasync.asyncSlot()
    async def _on_comment_button_clicked(self) -> None:
        if self._comments_area.isVisible():
            self._comments_area.setVisible(False)
            return
        self._comments_area.setVisible(True)
        if not self._comments_loaded:
            await self._load_comments()

    async def _load_comments(self) -> None:
        self._comments_loaded = True
        client = self._client_manager.require_client()
        root_id = self._post.conversation_id or self._post.id
        try:
            response = await client.get_conversation(id=root_id, number=30)
        except Exception as err:  # noqa: BLE001
            error_label = QLabel(f"コメントの取得に失敗しました: {err}")
            error_label.setWordWrap(True)
            self._comments_layout.addWidget(error_label)
            return

        replies = [p for p in (response.posts or []) if p.id != self._post.id]
        for reply in replies:
            self._comments_layout.addWidget(self._build_comment_label(reply))

        self._comments_layout.addLayout(self._build_comment_input_row())

    def _build_comment_label(self, reply: Post) -> QLabel:
        nickname = reply.user.nickname if reply.user is not None and reply.user.nickname else "?"
        label = ClickableLabel(f"<b>{nickname}</b>: {reply.text or ''}")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        if reply.user is not None and reply.user.id is not None:
            label.clicked.connect(
                lambda uid=reply.user.id: open_user_profile(self._client_manager, uid)
            )
        return label

    def _build_comment_input_row(self) -> QHBoxLayout:
        comment_edit = QLineEdit()
        comment_edit.setPlaceholderText("コメントを入力")
        send_button = QPushButton("送信")

        # qasync.asyncSlot()はシグナルの引数個数から実際の関数シグネチャに
        # 合わせて末尾の引数を取り除きながら呼び出そうとするが、_sendの
        # ように引数を1つも取らない関数だとその調整ロジックが0個の状態を
        # 試さずに諦めてしまい、クリック(bool付き)・Enter(引数無し)の
        # どちらから呼んでも失敗する。そのためここではasyncSlot()を使わず、
        # 素のasyncio.ensure_futureで直接スケジュールする。
        async def _send() -> None:
            text = comment_edit.text().strip()
            if not text or self._post.id is None:
                return
            client = self._client_manager.require_client()
            send_button.setEnabled(False)
            try:
                reply_post = await client.create_post(
                    x_jwt=client.generate_x_jwt(),
                    post_type=yaylib.PostType.TEXT,
                    text=text,
                    in_reply_to=self._post.id,
                )
            except Exception:  # noqa: BLE001
                send_button.setEnabled(True)
                return

            # 入力行(row)はこのレイアウトの最後の要素として追加されている
            # ので、その直前に差し込めば入力欄の上に新規コメントが並ぶ。
            insert_index = self._comments_layout.count() - 1
            self._comments_layout.insertWidget(insert_index, self._build_comment_label(reply_post))
            comment_edit.clear()
            send_button.setEnabled(True)
            self._comments_count += 1
            self._update_comment_button_text()

        def _on_send_triggered(*_args) -> None:
            asyncio.ensure_future(_send())

        comment_edit.returnPressed.connect(_on_send_triggered)
        send_button.clicked.connect(_on_send_triggered)

        row = QHBoxLayout()
        row.addWidget(comment_edit, 1)
        row.addWidget(send_button)
        return row
