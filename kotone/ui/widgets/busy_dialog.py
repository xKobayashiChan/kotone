"""テーマ/アクセントカラーの適用など、体感時間のかかる同期処理の間だけ
表示する軽量なローディング表示。

Qtはシングルスレッドで動いており、ここで行う処理（QApplicationへの
スタイルシート再適用）を別スレッド化するのは全ウィジェットへのアクセスが
絡むため危険。そこで「先にダイアログを描画してから重い処理を呼ぶ」形に
し、processEvents()で一度だけ強制的に描画させることで、進捗バー自体は
見えるようにしている（処理中は他の操作を受け付けない点は変わらない）。
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QVBoxLayout


class BusyDialog(QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True)
        self.setFixedSize(240, 80)

        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 完了時点までの進捗を計算する手段が無いため、不定進捗(マーキー)表示にする。
        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(progress)

    def run(self, task: Callable[[], None]) -> None:
        """ダイアログを表示してから同期処理taskを実行し、終わったら閉じる。"""
        self.show()
        QApplication.processEvents()
        try:
            task()
        finally:
            self.close()
