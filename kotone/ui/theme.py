"""アプリ全体の配色・余白・角丸を統一するテーマ。QApplicationに一括で
スタイルシートを適用する方式で、ライト/ダークをいつでも切り替えられる
ようにする。

アクセントカラー（差し色）はライト/ダークの配色そのものとは独立に、
設定画面からユーザーが自由に変更できる（kotone.ui.views.settings_dialog
参照）。accent_textはアクセントカラーの明度から自動計算するため、
黄色のような明るい色を選んでも文字が読めなくなることはない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from PySide6.QtWidgets import QApplication

THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK

# (表示名, 16進カラーコード)。設定画面のプリセットスウォッチと同じ並びを使う。
ACCENT_PRESETS: Tuple[Tuple[str, str], ...] = (
    ("イエロー", "#ffcc33"),
    ("レッド", "#ff3d78"),
    ("オレンジ", "#ff9f0a"),
    ("グリーン", "#34c759"),
    ("ブルー", "#0a84ff"),
    ("パープル", "#af52de"),
)
DEFAULT_ACCENT = ACCENT_PRESETS[0][1]


@dataclass(frozen=True)
class _Palette:
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str


_DARK = _Palette(
    bg="#121214",
    surface="#1c1c1f",
    surface_alt="#28282c",
    border="#38383e",
    text="#eaeaec",
    text_muted="#9a9aa1",
)

_LIGHT = _Palette(
    bg="#f5f5f7",
    surface="#ffffff",
    surface_alt="#ececef",
    border="#dcdce1",
    text="#1c1c1e",
    text_muted="#6e6e76",
)

_PALETTES: Dict[str, _Palette] = {THEME_DARK: _DARK, THEME_LIGHT: _LIGHT}


def _accent_text_color(accent_hex: str) -> str:
    """アクセントカラーの上に置く文字色を、背景の明度から自動選択する。
    黄色などの明るい色に白文字だと読めなくなるため。"""
    value = accent_hex.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1c1c1e" if luma > 0.6 else "#ffffff"


def _build_stylesheet(p: _Palette, accent: str) -> str:
    accent_text = _accent_text_color(accent)
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
        selection-background-color: {accent};
    }}

    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {accent};
    }}

    QPushButton {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px 14px;
        color: {p.text};
    }}

    QPushButton:hover {{
        border: 1px solid {accent};
    }}

    QPushButton:pressed {{
        background-color: {p.border};
    }}

    QPushButton:disabled {{
        color: {p.text_muted};
    }}

    QPushButton[primary="true"] {{
        background-color: {accent};
        border: 1px solid {accent};
        color: {accent_text};
        font-weight: 600;
    }}

    QPushButton[primary="true"]:hover {{
        background-color: {accent};
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
        background-color: {accent};
        color: {accent_text};
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
        border-bottom: 2px solid {accent};
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
        background: {accent};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}

    QSlider::sub-page:horizontal {{
        background: {accent};
        border-radius: 2px;
    }}
    """


def apply_theme(app: QApplication, theme: str, accent: str = DEFAULT_ACCENT) -> None:
    palette = _PALETTES.get(theme, _DARK)
    app.setStyleSheet(_build_stylesheet(palette, accent))


def toggle_theme(theme: str) -> str:
    return THEME_LIGHT if theme == THEME_DARK else THEME_DARK
