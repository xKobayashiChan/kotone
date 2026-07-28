"""yaylib.Clientのライフサイクル管理。

セッション（アクセス/リフレッシュトークン）はyaylib組み込みの
FileSessionStoreにより %APPDATA%\\Kotone\\session.json へ自動永続化
される（パーミッション0o600）。パスワードはここでも保存しない —
起動時はまずキャッシュ済みセッションの復元を試み、失効していれば
ログイン画面でメール/パスワードの再入力を求める。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import yaylib
from yaylib.session import NoSessionError
from yaylib.session_file import new_session_store

logger = logging.getLogger(__name__)

# yaylib自体はデフォルトだと完全に無音（NullHandler+propagate無効）な
# ライブラリ仕様のため、明示的にloggerを渡さない限りAPIリクエストの
# 形跡は一切ログに残らない。ここで渡すことで、送信したHTTPリクエスト
# （メソッド・パス・リトライ・トークン再発行等）がkotone.logに記録される
# ようになる。yaylib側はこれをDEBUGレベルで出すが、KOTONE_LOG_LEVEL全体を
# DEBUGにするとasyncio/qasyncの内部ログまで大量に出てノイズになるため、
# このロガーだけ明示的にDEBUGへ固定し、アプリ全体のログレベルに関係なく
# API呼び出しの記録だけは常に残るようにしている。
_api_logger = logging.getLogger("kotone.api")
_api_logger.setLevel(logging.DEBUG)


def _session_file_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Kotone", "session.json")


@dataclass(frozen=True)
class LoginResult:
    user_id: int
    email: str


class ClientManager:
    def __init__(self) -> None:
        self.client: Optional[yaylib.Client] = None

    async def _ensure_client(self) -> yaylib.Client:
        if self.client is None:
            store = await new_session_store(_session_file_path())
            self.client = yaylib.Client(session_store=store, logger=_api_logger)
        return self.client

    def require_client(self) -> yaylib.Client:
        """ログイン済み前提でクライアントを取得する。ログイン画面より先の
        画面（タイムライン等）はログイン成功後にしか表示されないため、
        ここで未ログインになるのは実装バグを意味する。"""
        if self.client is None:
            raise RuntimeError("yaylib: not logged in yet")
        return self.client

    async def try_restore_session(self, email: str) -> Optional[LoginResult]:
        """保存済みセッションを復元し、軽いAPI呼び出しでトークンの有効性を
        確認する。未保存・失効していればNoneを返す（呼び出し側はログイン
        画面にフォールバックする）。"""
        if not email:
            return None
        client = await self._ensure_client()
        try:
            await client.load_session(email)
        except NoSessionError:
            logger.info("no cached session for %s", email)
            return None
        try:
            await client.get_fresh_user(id=client.user_id)
        except Exception:
            logger.exception("cached session for %s is invalid/expired", email)
            return None
        logger.info("restored session for %s", email)
        return LoginResult(user_id=client.user_id, email=email)

    async def login(self, email: str, password: str) -> LoginResult:
        client = await self._ensure_client()
        try:
            await client.login_with_email(email=email, password=password)
        except Exception:
            logger.exception("login failed for %s", email)
            raise
        logger.info("logged in as %s", email)
        return LoginResult(user_id=client.user_id, email=email)

    async def logout(self, email: str) -> None:
        """サーバー側セッションを無効化し、ローカルのキャッシュ済み
        セッションも削除してから閉じる（次回起動時に自動復元されないよう
        にするため）。"""
        if self.client is None:
            return
        try:
            await self.client.logout()
        except Exception:
            logger.exception("server-side logout failed for %s", email)
        if self.client.session_store is not None and email:
            try:
                await self.client.session_store.delete(email)
            except Exception:
                logger.exception("failed to delete cached session for %s", email)
        await self.client.close()
        self.client = None
        logger.info("logged out %s", email)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None
