"""メール/パスワードでのログイン画面。

パスワードはメモリ上でのみ扱い、どこにも永続化しない。ログイン成功後は
yaylib側がトークンをセッションファイルにキャッシュするため、次回以降は
そのメールアドレスに対して自動復元を試みられる。
"""

from __future__ import annotations

import qasync
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kotone.core.client_manager import ClientManager, LoginResult


class LoginWindow(QWidget):
    login_succeeded = Signal(object)  # LoginResult

    def __init__(self, client_manager: ClientManager, initial_email: str = "") -> None:
        super().__init__()
        self._client_manager = client_manager
        self.setWindowTitle("Kotone - ログイン")
        self.resize(360, 200)

        self._email_edit = QLineEdit(initial_email)
        self._email_edit.setPlaceholderText("メールアドレス")
        self._password_edit = QLineEdit()
        self._password_edit.setPlaceholderText("パスワード")
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.returnPressed.connect(self._login_clicked)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        self._login_button = QPushButton("ログイン")
        self._login_button.setProperty("primary", True)
        self._login_button.clicked.connect(self._login_clicked)

        form = QFormLayout()
        form.addRow("メールアドレス", self._email_edit)
        form.addRow("パスワード", self._password_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._login_button)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

    @qasync.asyncSlot()
    async def _login_clicked(self) -> None:
        email = self._email_edit.text().strip()
        password = self._password_edit.text()
        if not email or not password:
            self._status_label.setText("メールアドレスとパスワードを入力してください。")
            return

        self._set_busy(True)
        self._status_label.setText("ログイン中...")
        try:
            result = await self._client_manager.login(email, password)
        except Exception as err:  # noqa: BLE001
            self._status_label.setText(f"ログインに失敗しました: {err}")
            self._set_busy(False)
            return

        self._password_edit.clear()
        self._set_busy(False)
        self.login_succeeded.emit(result)

    def _set_busy(self, busy: bool) -> None:
        self._login_button.setEnabled(not busy)
        self._email_edit.setEnabled(not busy)
        self._password_edit.setEnabled(not busy)
