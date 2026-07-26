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
