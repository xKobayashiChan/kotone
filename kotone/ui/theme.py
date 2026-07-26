"""アプリ全体の配色・余白・角丸を統一するテーマ。QApplicationに一括で
スタイルシートを適用する方式で、ライト/ダークをいつでも切り替えられる
ようにする。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from PySide6.QtWidgets import QApplication

THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK


@dataclass(frozen=True)
class _Palette:
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_text: str


_DARK = _Palette(
    bg="#121214",
    surface="#1c1c1f",
    surface_alt="#28282c",
    border="#38383e",
    text="#eaeaec",
    text_muted="#9a9aa1",
    accent="#ff3d78",
    accent_text="#ffffff",
)

_LIGHT = _Palette(
    bg="#f5f5f7",
    surface="#ffffff",
    surface_alt="#ececef",
    border="#dcdce1",
    text="#1c1c1e",
    text_muted="#6e6e76",
    accent="#ff3d78",
    accent_text="#ffffff",
)

_PALETTES: Dict[str, _Palette] = {THEME_DARK: _DARK, THEME_LIGHT: _LIGHT}


def _build_stylesheet(p: _Palette) -> str:
    return f"""
    QWidget {{
        background-color: {p.bg};
        color: {p.text};
        font-size: 13px;
    }}

    QFrame {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: 10px;
    }}

    QFrame#PostCard {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {p.border};
        border-radius: 0;
    }}

    /* QLabelはQFrameのサブクラスなので、上のQFrame向けの枠線スタイルが
       そのままラベル全部に付いてしまう。Qtのスタイルシートは同じ詳細度
       なら後に書いた方が勝つため、このQLabelルールは必ずQFrameより後に
       書いて明示的に打ち消す。 */
    QLabel {{
        background: transparent;
        border: none;
        border-radius: 0;
    }}

    QLineEdit, QTextEdit {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px 8px;
        color: {p.text};
        selection-background-color: {p.accent};
    }}

    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {p.accent};
    }}

    QPushButton {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px 14px;
        color: {p.text};
    }}

    QPushButton:hover {{
        border: 1px solid {p.accent};
    }}

    QPushButton:pressed {{
        background-color: {p.border};
    }}

    QPushButton:disabled {{
        color: {p.text_muted};
    }}

    QPushButton[primary="true"] {{
        background-color: {p.accent};
        border: 1px solid {p.accent};
        color: {p.accent_text};
        font-weight: 600;
    }}

    QPushButton[primary="true"]:hover {{
        background-color: {p.accent};
        border: 1px solid {p.text};
    }}

    QListWidget {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 4px;
        outline: 0;
    }}

    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 6px;
        color: {p.text};
    }}

    QListWidget::item:selected {{
        background-color: {p.accent};
        color: {p.accent_text};
    }}

    QListWidget::item:hover:!selected {{
        background-color: {p.surface_alt};
    }}

    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: 10px;
        top: -1px;
    }}

    QTabBar::tab {{
        background: transparent;
        color: {p.text_muted};
        padding: 8px 16px;
        border: none;
    }}

    QTabBar::tab:selected {{
        color: {p.text};
        font-weight: 600;
        border-bottom: 2px solid {p.accent};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {p.border};
        border-radius: 5px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p.text_muted};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {p.border};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {p.accent};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}

    QSlider::sub-page:horizontal {{
        background: {p.accent};
        border-radius: 2px;
    }}
    """


def apply_theme(app: QApplication, theme: str) -> None:
    palette = _PALETTES.get(theme, _DARK)
    app.setStyleSheet(_build_stylesheet(palette))


def toggle_theme(theme: str) -> str:
    return THEME_LIGHT if theme == THEME_DARK else THEME_DARK
