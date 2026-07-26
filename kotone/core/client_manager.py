"""yaylib.Clientのライフサイクル管理。

セッション（アクセス/リフレッシュトークン）はyaylib組み込みの
FileSessionStoreにより %APPDATA%\\Kotone\\session.json へ自動永続化
される（パーミッション0o600）。パスワードはここでも保存しない —
起動時はまずキャッシュ済みセッションの復元を試み、失効していれば
ログイン画面でメール/パスワードの再入力を求める。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import yaylib
from yaylib.session import NoSessionError
from yaylib.session_file import new_session_store


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
            self.client = yaylib.Client(session_store=store)
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
            return None
        try:
            await client.get_fresh_user(id=client.user_id)
        except Exception:
            return None
        return LoginResult(user_id=client.user_id, email=email)

    async def login(self, email: str, password: str) -> LoginResult:
        client = await self._ensure_client()
        await client.login_with_email(email=email, password=password)
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
            pass
        if self.client.session_store is not None and email:
            try:
                await self.client.session_store.delete(email)
            except Exception:
                pass
        await self.client.close()
        self.client = None

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None
