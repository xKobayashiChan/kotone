"""アバターやサムネイル画像をQNetworkAccessManagerで非同期取得するための
ごく薄いヘルパー。Qt自身のイベントループでノンブロッキングに動くため、
asyncio/qasync側の管理は不要。"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QLabel

_manager: Optional[QNetworkAccessManager] = None
_cache: Dict[str, QPixmap] = {}


def _get_manager() -> QNetworkAccessManager:
    global _manager
    if _manager is None:
        _manager = QNetworkAccessManager()
    return _manager


def load_pixmap(url: str, callback: Callable[[QPixmap], None]) -> None:
    """urlの画像を取得してcallback(pixmap)を呼ぶ。URL単位でメモリキャッシュ
    し、同一セッション内での再取得を避ける。取得失敗時はcallbackを呼ばない。"""
    if not url:
        return
    cached = _cache.get(url)
    if cached is not None:
        callback(cached)
        return

    manager = _get_manager()
    reply = manager.get(QNetworkRequest(QUrl(url)))

    def _on_finished() -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return
        data = reply.readAll()
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            _cache[url] = pixmap
            callback(pixmap)

    reply.finished.connect(_on_finished)


def fit_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
    """アスペクト比を保ったままwidth x heightにフィットさせ、はみ出た分は
    中央基準でトリミングする。setScaledContents(True)だけだと元画像の縦横
    比がラベルと違う場合に歪んで潰れてしまうため、アイコンやカバー画像の
    表示ではこちらを使う。"""
    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    return scaled.copy(x, y, width, height)


def fit_square_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    return fit_pixmap(pixmap, size, size)


def load_square_icon(url: str, size: int, label: QLabel) -> None:
    """load_pixmap + fit_square_pixmap + label.setPixmapをまとめた
    ヘルパー。アバター/アイコンをsize x sizeの正方形ラベルに歪みなく表示
    する（labelのサイズもここで確定させる）。"""
    label.setFixedSize(size, size)

    def _apply(pixmap: QPixmap) -> None:
        label.setPixmap(fit_square_pixmap(pixmap, size))

    load_pixmap(url, _apply)


def load_cropped_image(url: str, width: int, height: int, label: QLabel) -> None:
    """load_pixmap + fit_pixmap + label.setPixmapをまとめたヘルパー。
    カバー画像など正方形以外の比率のラベルに歪みなく表示する。"""
    label.setFixedSize(width, height)

    def _apply(pixmap: QPixmap) -> None:
        label.setPixmap(fit_pixmap(pixmap, width, height))

    load_pixmap(url, _apply)
