"""QWebEngineView側(call.html + Agora RTC Web SDK)とネイティブUI(CallDialog)
をつなぐQWebChannelブリッジ。JS側からは`bridge.on_xxx(...)`として呼ばれ、
このクラスは対応するQt Signalに変換して再発行するだけの薄い層。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class CallBridge(QObject):
    ready = Signal()
    joined = Signal(str)
    user_joined = Signal(str)
    user_left = Signal(str)
    connection_state_changed = Signal(str, str)
    error = Signal(str)

    @Slot()
    def on_ready(self) -> None:
        self.ready.emit()

    @Slot(str)
    def on_joined(self, uid: str) -> None:
        self.joined.emit(uid)

    @Slot(str)
    def on_user_joined(self, uid: str) -> None:
        self.user_joined.emit(uid)

    @Slot(str)
    def on_user_left(self, uid: str) -> None:
        self.user_left.emit(uid)

    @Slot(str, str)
    def on_connection_state_change(self, state: str, reason: str) -> None:
        self.connection_state_changed.emit(state, reason)

    @Slot(str)
    def on_error(self, message: str) -> None:
        self.error.emit(message)
