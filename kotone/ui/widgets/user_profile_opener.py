"""クリックで他ユーザーのプロフィールダイアログを開くための共通ヘルパー。"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from kotone.core.client_manager import ClientManager
from kotone.ui.views.user_profile_dialog import UserProfileDialog


def open_user_profile(client_manager: ClientManager, user_id: int) -> None:
    parent = QApplication.activeWindow()
    dialog = UserProfileDialog(user_id, client_manager, parent=parent)
    dialog.show()
