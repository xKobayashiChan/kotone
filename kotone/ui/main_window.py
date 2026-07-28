"""ログイン後のメインウィンドウ。サイドバー + 中央のスタック表示という
シェルのみをM1時点で用意する。各セクションの実際のビュー（タイムライン等）
は後続のマイルストーンで `set_page` により差し込む。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from kotone.core.client_manager import ClientManager, LoginResult

_role_key = Qt.ItemDataRole.UserRole

# サイドバーの項目キー。表示順はこの並びに従う。
NAV_ITEMS = (
    ("timeline", "タイムライン"),
    ("chat", "チャット"),
    ("groups", "サークル"),
    ("notifications", "通知"),
    ("footprints", "足跡"),
    ("profile", "プロフィール"),
)


def _placeholder(text: str) -> QWidget:
    label = QLabel(text)
    label.setContentsMargins(16, 16, 16, 16)
    return label


class MainWindow(QMainWindow):
    logout_requested = Signal()
    theme_toggle_requested = Signal()
    settings_requested = Signal()

    def __init__(self, client_manager: ClientManager, login_result: LoginResult) -> None:
        super().__init__()
        self._client_manager = client_manager
        self._login_result = login_result

        self.setWindowTitle("Kotone")
        self.resize(960, 640)

        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(160)
        for key, label in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(_role_key, key)
            self._nav_list.addItem(item)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)

        self._stack = QStackedWidget()
        # QStackedWidgetは既定では「現在表示中のページ」だけでなく
        # 「全ページ中で一番大きいもの」に合わせてサイズを要求してしまう。
        # ここを無視させないと、他のタブ(チャット等)に投稿やメッセージが
        # 増えるたびにウィンドウ全体が際限なく大きくなろうとする。
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self._pages: dict[str, QWidget] = {}
        for key, label in NAV_ITEMS:
            page = _placeholder(f"{label}（準備中）")
            self._pages[key] = page
            self._stack.addWidget(page)

        account_label = QLabel(f"ログイン中: {login_result.email} (user_id={login_result.user_id})")
        theme_button = QPushButton("🌓 テーマ切替")
        theme_button.clicked.connect(self.theme_toggle_requested.emit)
        settings_button = QPushButton("⚙ 設定")
        settings_button.clicked.connect(self.settings_requested.emit)
        logout_button = QPushButton("ログアウト")
        logout_button.clicked.connect(self.logout_requested.emit)

        sidebar = QVBoxLayout()
        sidebar.addWidget(self._nav_list, 1)
        sidebar.addWidget(account_label)
        sidebar.addWidget(theme_button)
        sidebar.addWidget(settings_button)
        sidebar.addWidget(logout_button)

        sidebar_container = QWidget()
        sidebar_container.setLayout(sidebar)
        sidebar_container.setFixedWidth(200)

        central = QWidget()
        root = QHBoxLayout(central)
        root.addWidget(sidebar_container)
        root.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self._nav_list.setCurrentRow(0)

    def set_page(self, key: str, widget: QWidget) -> None:
        """後続マイルストーンで、指定セクションの中身を実際のビューに
        差し替えるためのフック。"""
        old = self._pages[key]
        index = self._stack.indexOf(old)
        # removeWidgetで現在表示中のページが消えると、QStackedWidgetは
        # 別のページを勝手にカレントにしてしまう。差し替え後も同じページ
        # を表示し続けるため、元々カレントだった場合は明示的に戻す。
        was_current = self._stack.currentWidget() is old
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(index, widget)
        self._pages[key] = widget
        if was_current:
            self._stack.setCurrentWidget(widget)

    def _on_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        key = self._nav_list.item(row).data(_role_key)
        self._stack.setCurrentWidget(self._pages[key])
