"""ffmpeg / ffprobe バイナリのパスを解決する。

優先順位:
  1. PyInstaller でバンドルされた .app 内 (Contents/MacOS/<name>)
  2. リポジトリ内 vendor/macos/<name>  (開発時、ビルド前検証用)
  3. システム PATH 上の `which <name>`
"""
from __future__ import annotations

import os
import shutil
import sys
from typing import Optional


def _bundled_dir() -> Optional[str]:
    """PyInstaller でフリーズ済みなら実行ファイル(同 .app 内バイナリ)のディレクトリを返す"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return None


def _project_vendor_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "vendor", "macos"))


def find_binary(name: str) -> Optional[str]:
    bundled = _bundled_dir()
    if bundled:
        candidate = os.path.join(bundled, name)
        if os.path.isfile(candidate):
            return candidate

    vendor = os.path.join(_project_vendor_dir(), name)
    if os.path.isfile(vendor):
        return vendor

    return shutil.which(name)


FFMPEG: Optional[str] = find_binary("ffmpeg")
FFPROBE: Optional[str] = find_binary("ffprobe")


def configure_pydub() -> None:
    """pydub の AudioSegment が ffmpeg/ffprobe を見つけられるよう、絶対パスを設定する。"""
    try:
        from pydub import AudioSegment  # type: ignore
    except Exception:
        return

    if FFMPEG:
        AudioSegment.converter = FFMPEG
        AudioSegment.ffmpeg = FFMPEG
    if FFPROBE:
        AudioSegment.ffprobe = FFPROBE
