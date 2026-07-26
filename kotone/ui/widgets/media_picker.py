"""投稿に添付する画像(最大9枚)・動画(1本)を選ぶウィジェット。

Yay!の投稿は post_type が単一（image / video / text 等）のため、画像と
動画は排他選択とする（どちらか一方のみ添付可能）。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from yaylib import MAX_IMAGES_PER_UPLOAD

_IMAGE_FILTER = "画像ファイル (*.png *.jpg *.jpeg *.gif *.webp)"
_VIDEO_FILTER = "動画ファイル (*.mp4 *.mov *.m4v)"
_THUMB_SIZE = 72


class MediaPicker(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._image_paths: List[Path] = []
        self._video_path: Optional[Path] = None

        add_image_button = QPushButton("画像を追加")
        add_image_button.clicked.connect(self._pick_images)
        add_video_button = QPushButton("動画を追加")
        add_video_button.clicked.connect(self._pick_video)

        button_row = QHBoxLayout()
        button_row.addWidget(add_image_button)
        button_row.addWidget(add_video_button)
        button_row.addStretch(1)

        self._preview_row = QHBoxLayout()
        self._preview_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(button_row)
        layout.addLayout(self._preview_row)

    @property
    def image_paths(self) -> List[Path]:
        return list(self._image_paths)

    @property
    def video_path(self) -> Optional[Path]:
        return self._video_path

    def is_empty(self) -> bool:
        return not self._image_paths and self._video_path is None

    def clear(self) -> None:
        self._image_paths.clear()
        self._video_path = None
        self._rebuild_preview()

    def _pick_images(self) -> None:
        if self._video_path is not None:
            return
        remaining = MAX_IMAGES_PER_UPLOAD - len(self._image_paths)
        if remaining <= 0:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "画像を選択", "", _IMAGE_FILTER)
        for p in paths[:remaining]:
            self._image_paths.append(Path(p))
        self._rebuild_preview()
        self.changed.emit()

    def _pick_video(self) -> None:
        if self._image_paths:
            return
        path, _ = QFileDialog.getOpenFileName(self, "動画を選択", "", _VIDEO_FILTER)
        if path:
            self._video_path = Path(path)
            self._rebuild_preview()
            self.changed.emit()

    def _remove_image(self, path: Path) -> None:
        if path in self._image_paths:
            self._image_paths.remove(path)
            self._rebuild_preview()
            self.changed.emit()

    def _remove_video(self) -> None:
        self._video_path = None
        self._rebuild_preview()
        self.changed.emit()

    def _rebuild_preview(self) -> None:
        while self._preview_row.count() > 1:
            item = self._preview_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for path in self._image_paths:
            self._preview_row.insertWidget(
                self._preview_row.count() - 1, self._build_image_chip(path)
            )
        if self._video_path is not None:
            self._preview_row.insertWidget(
                self._preview_row.count() - 1, self._build_video_chip(self._video_path)
            )

    def _build_image_chip(self, path: Path) -> QWidget:
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        thumb = QLabel()
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            thumb.setPixmap(
                pixmap.scaled(
                    _THUMB_SIZE,
                    _THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        remove_button = QPushButton("削除")
        remove_button.clicked.connect(lambda: self._remove_image(path))
        col.addWidget(thumb)
        col.addWidget(remove_button)
        return container

    def _build_video_chip(self, path: Path) -> QWidget:
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        name_label = QLabel(path.name)
        remove_button = QPushButton("削除")
        remove_button.clicked.connect(self._remove_video)
        col.addWidget(name_label)
        col.addWidget(remove_button)
        return container
