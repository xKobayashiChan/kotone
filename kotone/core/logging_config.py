"""ログ設定。%APPDATA%\\Kotone\\logs\\kotone.log にローテーション付きで
出力する。console=Falseでビルドしたexeはコンソールを持たず、未処理の
例外が発生してもどこにも表示されず消えてしまうため、
sys.excepthookでログに残す。"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def _log_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Kotone", "logs")


def setup_logging() -> None:
    log_dir = _log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "kotone.log")

    level_name = os.environ.get("KOTONE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)

    # ソースから起動している場合(コンソールがある場合)はターミナルにも出す。
    if not getattr(sys, "frozen", False):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    sys.excepthook = _log_uncaught_exception


def _log_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("kotone.uncaught").critical(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
    )
