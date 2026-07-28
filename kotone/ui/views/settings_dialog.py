"""設定ダイアログ。通知の種類ごとのON/OFFと、アクセントカラー（テーマの
差し色）の変更をまとめて行う。設定変更はAppSettingsに即座に反映される
（通知トグルはNotificationPollerが次回ポーリング時に読む。アクセント
カラーはaccent_changedシグナルで呼び出し側に伝え、その場でテーマに
反映する）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from kotone.core.settings import NOTIFICATION_TYPES, AppSettings
from kotone.ui.theme import ACCENT_PRESETS, DEFAULT_ACCENT

_SWATCH_SIZE = 24


def _swatch_style(hex_color: str) -> str:
    return (
        f"background-color: {hex_color}; border: 1px solid #00000040; border-radius: 4px;"
    )


class SettingsDialog(QDialog):
    accent_changed = Signal(str)

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._accent = settings.accent_color() or DEFAULT_ACCENT

        self.setWindowTitle("設定")
        self.resize(360, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        notify_group = QGroupBox("通知設定")
        notify_layout = QVBoxLayout(notify_group)
        for key, label in NOTIFICATION_TYPES:
            checkbox = QCheckBox(label)
            checkbox.setChecked(settings.notify_enabled(key))
            checkbox.toggled.connect(
                lambda checked, key=key: self._settings.set_notify_enabled(key, checked)
            )
            notify_layout.addWidget(checkbox)

        color_group = QGroupBox("色設定")
        color_layout = QVBoxLayout(color_group)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
        self._update_preview()

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("現在の色:"))
        preview_row.addWidget(self._preview_label)
        preview_row.addStretch(1)
        color_layout.addLayout(preview_row)

        presets_row = QHBoxLayout()
        for name, hex_color in ACCENT_PRESETS:
            button = QPushButton()
            button.setToolTip(name)
            button.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
            button.setStyleSheet(_swatch_style(hex_color))
            button.clicked.connect(lambda _checked=False, c=hex_color: self._set_accent(c))
            presets_row.addWidget(button)
        presets_row.addStretch(1)
        color_layout.addLayout(presets_row)

        custom_button = QPushButton("カラーピッカーで選ぶ...")
        custom_button.clicked.connect(self._on_pick_custom_color)
        color_layout.addWidget(custom_button)

        close_button = QPushButton("閉じる")
        close_button.setProperty("primary", True)
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(notify_group)
        layout.addWidget(color_group)
        layout.addStretch(1)
        layout.addWidget(close_button)

    def _on_pick_custom_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._accent), self, "アクセントカラーを選択")
        if color.isValid():
            self._set_accent(color.name())

    def _set_accent(self, hex_color: str) -> None:
        self._accent = hex_color
        self._settings.set_accent_color(hex_color)
        self._update_preview()
        self.accent_changed.emit(hex_color)

    def _update_preview(self) -> None:
        self._preview_label.setStyleSheet(_swatch_style(self._accent))
