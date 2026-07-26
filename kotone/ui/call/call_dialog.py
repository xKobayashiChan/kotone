"""VC(音声通話)ダイアログ。参加者一覧・ミュート/退出ボタンを表示する
ネイティブUIと、非表示のCallWebEngine(Agora RTC Web SDK)を組み合わせる。
実際の音声送受信はCallWebEngine側が担い、ここではその結果(参加者の
出入り・エラー)をSignal経由で受け取って表示を更新するだけ。"""

from __future__ import annotations

import asyncio
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from yaylib.models.realm_conference_call import RealmConferenceCall
from yaylib.models.realm_user import RealmUser

from kotone.core.agora_config import get_agora_app_id
from kotone.core.client_manager import ClientManager
from kotone.ui.call.call_bridge import CallBridge
from kotone.ui.call.call_web_engine import CallWebEngine
from kotone.ui.widgets.image_loader import load_square_icon

_AVATAR_SIZE = 40


class _ParticipantRow(QWidget):
    def __init__(self, user: RealmUser) -> None:
        super().__init__()
        icon_label = QLabel()
        icon_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        if user.profile_icon:
            load_square_icon(user.profile_icon, _AVATAR_SIZE, icon_label)
        name_label = QLabel(user.nickname or "(名無し)")

        row = QHBoxLayout(self)
        row.addWidget(icon_label)
        row.addWidget(name_label, 1)


class CallDialog(QDialog):
    def __init__(
        self,
        conference_call: RealmConferenceCall,
        group_name: str,
        client_manager: ClientManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client_manager = client_manager
        self._call_id = conference_call.id
        self._agora_channel = conference_call.agora_channel or ""
        self._agora_token = conference_call.agora_token or ""
        self._muted = False
        self._left = False

        self.setWindowTitle(f"VC - {group_name}")
        self.resize(360, 480)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        title_label = QLabel(f"<b>{group_name}</b>")
        self._timer_label = QLabel("00:00")

        self._participants_layout = QVBoxLayout()
        self._participants_layout.addStretch(1)
        participants_container = QWidget()
        participants_container.setLayout(self._participants_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(participants_container)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        self._mute_button = QPushButton("ミュート")
        self._mute_button.clicked.connect(self._on_mute_clicked)
        self._leave_button = QPushButton("退出")
        self._leave_button.setProperty("primary", True)
        self._leave_button.clicked.connect(self.close)

        controls_row = QHBoxLayout()
        controls_row.addWidget(self._mute_button)
        controls_row.addWidget(self._leave_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addWidget(self._timer_label)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._status_label)
        layout.addLayout(controls_row)

        self._bridge = CallBridge()
        self._bridge.ready.connect(self._on_bridge_ready)
        self._bridge.user_joined.connect(self._on_roster_changed)
        self._bridge.user_left.connect(self._on_roster_changed)
        self._bridge.error.connect(self._on_bridge_error)

        self._web_engine = CallWebEngine(self._bridge, parent=self)

        self._elapsed_seconds = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._on_tick)
        self._elapsed_timer.start()

        self._set_participants(conference_call.conference_call_users or [])

    def _set_participants(self, users: List[RealmUser]) -> None:
        while self._participants_layout.count() > 1:
            item = self._participants_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for user in users:
            self._participants_layout.insertWidget(
                self._participants_layout.count() - 1, _ParticipantRow(user)
            )

    def _on_tick(self) -> None:
        self._elapsed_seconds += 1
        minutes, seconds = divmod(self._elapsed_seconds, 60)
        self._timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_bridge_ready(self) -> None:
        client = self._client_manager.require_client()
        self._web_engine.join(
            get_agora_app_id(),
            self._agora_channel,
            self._agora_token,
            str(client.user_id),
        )

    def _on_roster_changed(self, _uid: str) -> None:
        asyncio.ensure_future(self._refresh_roster())

    async def _refresh_roster(self) -> None:
        client = self._client_manager.require_client()
        try:
            call = await client.get_conference_call(call_id=self._call_id)
        except Exception:  # noqa: BLE001
            return
        self._set_participants(call.conference_call_users or [])

    def _on_mute_clicked(self) -> None:
        self._muted = not self._muted
        self._web_engine.set_muted(self._muted)
        self._mute_button.setText("ミュート解除" if self._muted else "ミュート")

    def _on_bridge_error(self, message: str) -> None:
        self._status_label.setText(message)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qtの命名規則に合わせる)
        self._elapsed_timer.stop()
        self._web_engine.leave()
        if not self._left:
            self._left = True
            asyncio.ensure_future(self._leave_call())
        super().closeEvent(event)

    async def _leave_call(self) -> None:
        client = self._client_manager.require_client()
        try:
            await client.leave_conference_call(conference_id=self._call_id)
        except Exception:  # noqa: BLE001
            pass
