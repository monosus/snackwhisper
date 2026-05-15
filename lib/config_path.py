"""config.ini のパスを OS / 実行モードに応じて解決する。

- 開発時 (python main.py): プロジェクトルートの ./config.ini を使う
- 凍結バンドル (.app / .exe): ユーザ書き込み可能な OS 標準の設定ディレクトリへ
"""
from __future__ import annotations

import os
import sys


APP_DIR_NAME = "SnackWhisper"


def _user_config_dir() -> str:
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_DIR_NAME}")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(base, APP_DIR_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_DIR_NAME.lower())


def config_path() -> str:
    if getattr(sys, "frozen", False):
        directory = _user_config_dir()
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, "config.ini")
    return "config.ini"
