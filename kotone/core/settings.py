"""機密情報を含まない、非機密の永続設定（最後に使ったメールアドレス等）。

パスワードやトークンはここでは扱わない。トークンはyaylibの
FileSessionStoreが別途 %APPDATA%\\Kotone\\session.json に管理する。
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "kotone"
_APP = "kotone"
_KEY_LAST_EMAIL = "auth/last_email"
_KEY_THEME = "ui/theme"
_KEY_ACCENT_COLOR = "ui/accent_color"
_NOTIFY_KEY_PREFIX = "notifications/"

# 通知設定画面・通知ポーリングの両方が参照する、選択可能な通知種別の一覧。
# "footprint"は足跡（NotificationPollerが独自にポーリングする）、それ以外は
# get_user_activitiesが返すActivity.typeに対応する（詳細はnotification_poller.py）。
NOTIFICATION_TYPES = (
    ("footprint", "足跡"),
    ("like", "いいね"),
    ("reply", "返信"),
    ("follow", "フォロー"),
    ("follow_accepted", "フォロー承認"),
    ("id_check", "本人確認"),
)


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings(_ORG, _APP)

    def last_email(self) -> str:
        return self._settings.value(_KEY_LAST_EMAIL, "", type=str)

    def set_last_email(self, email: str) -> None:
        self._settings.setValue(_KEY_LAST_EMAIL, email)

    def theme(self) -> str:
        return self._settings.value(_KEY_THEME, "", type=str)

    def set_theme(self, theme: str) -> None:
        self._settings.setValue(_KEY_THEME, theme)

    def accent_color(self) -> str:
        """空文字列は「未設定」を意味し、呼び出し側でデフォルト色に
        フォールバックする（kotone.ui.theme.DEFAULT_ACCENT）。"""
        return self._settings.value(_KEY_ACCENT_COLOR, "", type=str)

    def set_accent_color(self, color: str) -> None:
        self._settings.setValue(_KEY_ACCENT_COLOR, color)

    def notify_enabled(self, key: str) -> bool:
        return self._settings.value(f"{_NOTIFY_KEY_PREFIX}{key}", True, type=bool)

    def set_notify_enabled(self, key: str, enabled: bool) -> None:
        self._settings.setValue(f"{_NOTIFY_KEY_PREFIX}{key}", enabled)
