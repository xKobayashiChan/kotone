"""VC(通話)機能で使うAgoraのApp ID。

Yay!の公開APIレスポンス(yaylib経由)にはagora_channel/agora_tokenしか
含まれず、接続に必須のApp IDはどこにも公開されていない。この値は
Yay!のWeb版クライアント(https://yay.space)が読み込むJSバンドルを
ブラウザDevToolsで調査して特定した固定値であり、Yay側の実装変更で
無効化される可能性がある。壊れた場合はyay.spaceのJSを再調査すること。

リポジトリには含めず、環境変数 KOTONE_AGORA_APP_ID 経由で渡す。
"""

from __future__ import annotations

import os

_ENV_KEY = "KOTONE_AGORA_APP_ID"


def get_agora_app_id() -> str:
    value = os.environ.get(_ENV_KEY)
    if not value:
        raise RuntimeError(
            f"環境変数 {_ENV_KEY} が設定されていません。"
            "VC(通話)機能を使うにはAgora App IDを設定してください。"
        )
    return value
