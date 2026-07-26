"""同梱アセット(assets/以下)のパス解決。PyInstallerでビルドした場合、
バンドルしたデータファイルはsys._MEIPASS（onefile展開先 / onedirの
ルート）以下に配置される。ソースから直接実行している間はこのファイルの
隣を見る。"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_dir() -> Path:
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "kotone" / "assets"
    return Path(__file__).parent.parent / "assets"
